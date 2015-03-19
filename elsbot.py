import sys
import os
import time
import logging
import re
import configparser
import urllib.request
import urllib.parse
import praw
import praw.helpers
import praw.handlers
import psycopg2 as postgres
from bs4 import BeautifulSoup
from html.parser import unescape
from random import randint

CFG_FILE = 'elsbot.cfg'


class PostArchive(object):

    config = {}
    last_maintenance = 0

    def __init__(self, record_ttl_days=60, db_ttm=3600):

        logging.info('Connecting to post archive database...')

        self.config['record_TTL_days'] = record_ttl_days
        self.config['db_TTM'] = db_ttm

        urllib.parse.uses_netloc.append("postgres")
        url = urllib.parse.urlparse(os.environ["DATABASE_URL"])

        self.sql = postgres.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        self.cur = self.sql.cursor()

        self.cur.execute("CREATE TABLE IF NOT EXISTS oldposts(Id VARCHAR, Timestamp FLOAT)")
        self.sql.commit()

    def db_maintenence(self):
        if time.time() - self.config['db_TTM'] > self.last_maintenance:
            logging.info('Running database maintenance.')
            expire_date = time.time() - self.config['record_TTL_days'] * 24 * 3600
            self.cur.execute("DELETE FROM oldposts WHERE Timestamp <= %s", [expire_date])
            self.sql.commit()
            self.last_maintenance = time.time()

    def is_archived(self, post_id):
        self.cur.execute("SELECT * FROM oldposts WHERE Id=%s", [post_id])
        if self.cur.fetchone():
            return True
        return False

    def add(self, post_id):
        self.cur.execute("INSERT INTO oldposts VALUES(%s,%s)", [post_id, time.time()])
        self.sql.commit()

    def close(self):
        self.sql.close()


class ELSBot(object):

    config = {}
    post_comment = """
[Snapshot of link]({link})

---

I am a bot.  For questions or issues, please post [here](/r/{subreddit}/submit?selftext=true).
    """
    post_comment_multi = """
Snapshots:

{links}---

I am a bot.  For questions or issues, please post [here](/r/{subreddit}/submit?selftext=true).
    """

    def __init__(self, cfg, handler=praw.handlers.DefaultHandler()):

        # open config file

        logging.info('Reading in configuration file...')
        cfg_file = configparser.ConfigParser()
        path_to_cfg = os.path.abspath(os.path.dirname(sys.argv[0]))
        path_to_cfg = os.path.join(path_to_cfg, cfg)
        cfg_file.read(path_to_cfg)

        # read in config
        self.config['user_agent'] = cfg_file['reddit']['user_agent']
        self.config['operator'] = cfg_file['reddit']['operator']
        self.config['username'] = os.environ['USER_NAME']
        self.config['password'] = os.environ['PASSWORD']
        self.config['subreddit'] = cfg_file['reddit']['subreddit']
        self.config['bot_subreddit'] = cfg_file['reddit']['bot_subreddit']
        self.config['domains'] = [x.strip() for x in str(cfg_file['reddit']['snapshot_domains']).split(',')]

        # read in database config
        self.config['record_TTL_days'] = int(cfg_file['database']['record_TTL_days'])
        self.config['db_TTM'] = int(cfg_file['database']['time_to_maintenance'])

        # Initialize Reddit Connection
        self.r = praw.Reddit(self.config['user_agent'], handler=handler)
        self.r.login(self.config['username'], self.config['password'])
        self.sr = self.r.get_subreddit(self.config['subreddit'])

        # Initialize post database which prevents double posts
        self.post_archive = PostArchive(self.config['record_TTL_days'],
                                        self.config['db_TTM'])

        # Do an initial maintenance on db when starting
        self.post_archive.db_maintenence()

    def _check_for_comment(self, post):
        comments_flat = praw.helpers.flatten_tree(post.comments)
        for comment in comments_flat:
            if not hasattr(comment, 'author') or not hasattr(comment.author, 'name'):
                continue
            if comment.author.name == self.config['username']:
                return True
        return False

    @staticmethod
    def _fix_reddit_url(url):
        if 'reddit.com' in url or 'redd.it' in url:
            return re.sub('://[\w]+[.]red', '://red', url)

    @staticmethod
    def _get_archive_url(url):

        data = urllib.parse.urlencode({'url': url})
        data = data.encode('utf-8')

        # Get url from archive.today
        res = urllib.request.urlopen("https://archive.today/submit/", data)
        archive_url = re.findall("http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
                                 str(res.read(), 'utf-8'))[0]
        return archive_url

    def _post_archive_comment(self, post):
        try:
            logging.debug("Fetching archive link for submission {0}: {1}"
                          .format(post.id, "http://redd.it/" + post.id))
            archive_link = self._get_archive_url(self._fix_reddit_url(post.url))
        except Exception as e:
            logging.error("Error fetching archive link on submission {0}: {1}"
                          .format(post.id, "http://redd.it/" + post.id))
            logging.error(str(e))
            return

        logging.info("Adding link to archive.today on submission {0}: {1}"
                     .format(post.id, "http://redd.it/" + post.id))
        try:
            post.add_comment(self.post_comment.format(link=archive_link,
                                                      subreddit=self.config['bot_subreddit']))
            self.post_archive.add(post.id)
        except Exception as e:
            logging.error("Error adding comment on submission {0}: {1}"
                          .format(post.id, "http://redd.it/" + post.id))
            logging.error(str(e))

    def _post_archive_multicomment(self, post):
        link_list = ""

        soup = BeautifulSoup(unescape(post.selftext_html))
        for anchor in soup.find_all('a'):
            netloc = urllib.parse.urlparse(anchor['href'])[1]
            if netloc in self.config['domains']:
                try:
                    logging.debug("Fetching archive link for submission {0}: {1}"
                                  .format(post.id, "http://redd.it/" + post.id))
                    archive_link = self._get_archive_url(self._fix_reddit_url(anchor['href']))
                except Exception as e:
                    logging.error("Error fetching archive link on submission {0}: {1}"
                                  .format(post.id, "http://redd.it/" + post.id))
                    logging.error(str(e))
                    return

                link_list += "* [{0}...]({1})\n\n".format(anchor.contents[0][0:randint(35, 40)], archive_link)

        if link_list == "":
            return False

        try:
            post.add_comment(self.post_comment_multi.format(links=link_list,
                                                            subreddit=self.config['bot_subreddit']))
            self.post_archive.add(post.id)
        except Exception as e:
            logging.error("Error adding comment on submission {0}: {1}"
                          .format(post.id, "http://redd.it/" + post.id))
            logging.error(str(e))

    def scan_posts(self):
        logging.info("Scanning new posts in /r/{}...".format(self.config['subreddit']))
        posts = self.sr.get_new()
        for post in posts:
            if post.domain in self.config['domains']:
                try:
                    if self.post_archive.is_archived(post.id):
                        logging.debug("Skipping previously processed post {0}: {1}"
                                      .format(post.id, "http://redd.it/" + post.id))
                        continue
                except Exception as e:
                    logging.error("Error connecting to post archive database.")
                    logging.error(str(e))
                    continue

                try:
                    if self._check_for_comment(post):
                        logging.debug("Already commented in submission, skipping {0}: {1}"
                                      .format(post.id, "http://redd.it/" + post.id))
                        self.post_archive.add(post.id)
                        continue
                except Exception as e:
                    logging.error("Error loading comments on submission {0}: {1}"
                                  .format(post.id, "http://redd.it/" + post.id))
                    logging.error(str(e))
                    continue

                if post.is_self:
                    self._post_archive_multicomment(post)
                else:
                    self._post_archive_comment(post)

            else:
                logging.debug("Domain not in snapshot domain list: {}".format(post.domain))

    def run_db_maintenance(self):
        self.post_archive.db_maintenence()

    def close(self):
        self.post_archive.close()
        logging.warning("ELSbot exiting...")


def main():
    logging.basicConfig(format='%(asctime)s (%(levelname)s): %(message)s',
                        datefmt='%m-%d-%Y %I:%M:%S %p', level=logging.INFO)
    logging.info("ELSbot starting...")

    elsbot = ELSBot(CFG_FILE)

    while True:
        try:
            elsbot.scan_posts()
            elsbot.run_db_maintenance()
            time.sleep(10)
        except KeyboardInterrupt:
            elsbot.close()
            exit()
        except Exception as e:
            logging.error("Error running bot.")
            logging.error(str(e))
            time.sleep(10)


if __name__ == "__main__":
    main()
