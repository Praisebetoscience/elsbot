__author__ = '/u/PraiseBeToScience'

import sys
import os
import time
import logging
import re
import configparser
import praw
import praw.helpers
import praw.handlers
import sqlite3 as lite
import platform
from bs4 import BeautifulSoup
from html.parser import HTMLParser
import random
from archives import ArchiveContainer

VERSION = 'v3.0.2'
DATABASE_FILE = os.environ['OPENSHIFT_DATA_DIR'] + 'sql.db'
REDDIT_PATTERN = re.compile(r'https?://(([a-z]{2})(-[a-z]{2})?|beta|i|m|pay|ssl|www)\.?reddit\.com', flags=re.I)


class PostArchive(object):

    config = {}
    last_maintenance = 0

    def __init__(self, record_ttl_days=60, db_ttm=3600):

        logging.info('Connecting to post archive database...')

        self.config['record_TTL_days'] = record_ttl_days
        self.config['db_TTM'] = db_ttm

        self.sql = lite.connect(DATABASE_FILE)
        self.cur = self.sql.cursor()

        self.cur.execute("CREATE TABLE IF NOT EXISTS oldposts(Id TXT, Timestamp FLOAT)")
        self.sql.commit()

    def db_maintenence(self):
        if time.time() - self.config['db_TTM'] > self.last_maintenance:
            logging.info('Running database maintenance.')
            expire_date = time.time() - self.config['record_TTL_days'] * 24 * 3600
            self.cur.execute("DELETE FROM oldposts WHERE Timestamp <= ?", (expire_date, ))
            self.sql.commit()
            self.last_maintenance = time.time()

    def is_archived(self, post_id):
        self.cur.execute("SELECT * FROM oldposts WHERE Id=?", (post_id, ))
        if self.cur.fetchone():
            return True
        return False

    def add(self, post_id):
        self.cur.execute("INSERT INTO oldposts VALUES(?,?)", [post_id, time.time()])
        self.sql.commit()

    def close(self):
        self.sql.close()


class ELSBot(object):

    config = {}

    def __init__(self, cfg, handler=praw.handlers.DefaultHandler()):

        # open config file

        logging.info('Reading in configuration file...')
        cfg_file = configparser.ConfigParser()
        path_to_cfg = os.path.abspath(os.path.dirname(sys.argv[0]))
        path_to_cfg = os.path.join(path_to_cfg, cfg)
        cfg_file.read(path_to_cfg)

        # read in config
        self.config['client_id'] = cfg_file['reddit']['client_id']
        self.config['client_secret'] = cfg_file['reddit']['client_secret']
        self.config['redirect_uri'] = cfg_file['reddit']['redirect_uri']
        self.config['refresh_token'] = cfg_file['reddit']['refresh_token']
        self.config['subreddit'] = cfg_file['reddit']['subreddit']
        self.config['bot_subreddit'] = cfg_file['reddit']['bot_subreddit']
        self.config['quote_wiki_page'] = cfg_file['reddit']['quote_wiki_page']

        # read in database config
        self.config['record_TTL_days'] = int(cfg_file['database']['record_TTL_days'])
        self.config['db_TTM'] = int(cfg_file['database']['time_to_maintenance'])

        # Set useragent
        self.config['user_agent'] = "{platform}:{botname}:{version} by {author}"\
            .format(platform=platform.system(),
                    botname=os.path.basename(__file__).strip('.py'),
                    version=VERSION,
                    author=__author__)

        # Initialize Reddit Connection
        self.r = praw.Reddit(self.config['user_agent'], handler=handler)
        self.r.config.api_request_delay = 1.0  # OAuth rate limit
        self.r.set_oauth_app_info(client_id=self.config['client_id'],
                                  client_secret=self.config['client_secret'],
                                  redirect_uri=self.config['redirect_uri'])

        self.r.refresh_access_information(self.config['refresh_token'], update_session=True)
        self.sr = self.r.get_subreddit(self.config['subreddit'])
        self.config['username'] = self.r.get_me().name

        # Load quotes from wiki
        self.quote_list = []
        self.quote_last_revised = 0
        self.load_quote_list()

        # Initialize post database which prevents double posts
        self.post_archive = PostArchive(self.config['record_TTL_days'],
                                        self.config['db_TTM'])

        # Do an initial maintenance on db when starting
        self.post_archive.db_maintenence()

    @staticmethod
    def _get_quotes(wiki_page):
        # Remove remaining escape characters from wiki content
        quotes = HTMLParser().unescape(wiki_page.content_md)

        # Remove comment lines starting with # or ; including any leading whitespace
        quotes = re.sub('^[ \t]*[#;].*$', '', quotes, flags=re.MULTILINE)

        # Split and strip the quotes into an array using --- as a delimiter
        quotes = [quote.strip() for quote in quotes.split('---')]

        # Remove any blank quotes
        quotes = [quote for quote in quotes if quote]

        return quotes

    def _check_for_comment(self, post):
        comments_flat = praw.helpers.flatten_tree(post.comments)
        for comment in comments_flat:
            if not hasattr(comment, 'author') or not hasattr(comment.author, 'name'):
                continue
            if comment.author.name in [self.config['username'], 'SnapshillBot']:
                return True
        return False

    def _get_quote(self):
        if self.quote_list:
            return random.choice(self.quote_list)
        return ''

    @staticmethod
    def _fix_url(url):
        if url.startswith(('/r/', '/u/')):
            url = "http://www.reddit.com" + url
        if url.startswith(('r/', 'u/')):
            url = "http://www.reddit.com/" + url
        return re.sub(REDDIT_PATTERN, 'http://www.reddit.com', url)

    @staticmethod
    def _build(archives, quote, subreddit):

        # Header
        comment = quote + "\n\nSnapshots:\n\n"

        # List of snapshots
        for ac in archives:
            comment += "* {} - ".format(ac.text)
            i = 1
            for a in ac:
                if a.archived:
                    comment += "[{}]({}), ".format(i, a.archived)
                elif a.archived is None:
                    continue
                else:
                    comment += "[{}]({}), ".format('Error', a.error_link)
                i += 1
            comment = comment.strip(', ') + '\n'

        # Footer
        comment += "\n\n*I am a bot. ([Info](/r/{0}) | [Contact](/r/{0}/submit?selftext=true))*".format(subreddit)

        return comment

    def _post_snapshots(self, post):
        logging.debug("Fetching Archives for: {}".format(post.permalink))

        archives = [ArchiveContainer(self._fix_url(post.url), "*This Post*")]

        if post.is_self and post.selftext_html is not None:
            links = BeautifulSoup(HTMLParser().unescape(post.selftext_html), "html.parser").find_all('a')
            for link in links:
                url = self._fix_url(link['href'])
                archives.append(ArchiveContainer(url, link.contents[0]))

        quote = self._get_quote()

        try:
            if not post.archived:
                logging.info("Posting snapshot: {}".format(post.permalink))
                post.add_comment(self._build(archives, quote, self.config['bot_subreddit']))
                self.post_archive.add(post.id)
        except Exception as e:
            logging.error("Error posting snapshot: {}".format(post.permalink))
            logging.error(str(e))

    def load_quote_list(self):
        logging.debug("Checking quote wiki pate for updates...")

        try:
            wiki = self.r.get_wiki_page(self.config['subreddit'], self.config['quote_wiki_page'])
        except Exception as e:
            logging.error("Error loading quote wikipage.")
            logging.error(str(e))
            return False

        if self.quote_last_revised >= wiki.revision_date:
            return False

        logging.info('Quote wiki page updated, loading quotes...')
        self.quote_list = self._get_quotes(wiki)
        self.quote_last_revised = wiki.revision_date

    def scan_posts(self):

        logging.info("Scanning new posts in /r/{}...".format(self.config['subreddit']))

        posts = self.sr.get_new()
        for post in posts:
            if self.post_archive.is_archived(post.id):
                logging.debug("Skipping, archived: {}".format(post.permalink))
                continue

            try:
                if self._check_for_comment(post):
                    logging.debug("Skipping, previously commented: {}".format(post.permalink))
                    self.post_archive.add(post.id)
                    continue
            except Exception as e:
                logging.error("Error loading comments: {}".format(post.permalink))
                logging.error(str(e))
                continue

            self._post_snapshots(post)

    def db_maintenance(self):
        self.post_archive.db_maintenence()

    def close(self):
        self.post_archive.close()
        logging.warning("ELSbot exiting...")


def main():
    import argparse
    import warnings

    warnings.simplefilter('ignore', ResourceWarning)
    warnings.simplefilter('ignore', UserWarning)

    logging.basicConfig(format='%(asctime)s (%(levelname)s): %(message)s',
                        datefmt='%m-%d-%Y %I:%M:%S %p', level=logging.INFO)
    logging.info("ELSbot starting...")

    parser = argparse.ArgumentParser(description="Snap Shot Bot with Quotes.")
    parser.add_argument('--run-once', '-r', action='store_true', help='run scan once then quit')
    parser.add_argument('--config-file', '-f', default='elsbot.cfg', help="specify a configuration file.")
    args = parser.parse_args()

    if not os.path.isfile(args.config_file):
        logging.error("Config file {} does not exist.".format(args.config_file))
        exit()

    elsbot = ELSBot(args.config_file)

    while True:
        try:
            elsbot.scan_posts()
            if args.run_once:
                break

            elsbot.db_maintenance()
            elsbot.load_quote_list()
            time.sleep(10)
        except KeyboardInterrupt:
            elsbot.close()
            exit()
        except Exception as e:
            logging.error("Error running bot.")
            logging.error(str(e))
            if args.run_once:
                exit()
            time.sleep(10)


if __name__ == "__main__":
    main()
