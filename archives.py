__author__ = '/u/Praisebetoscience'

import time
import requests
from urllib.parse import urlencode
import re

LEN_MAX = 35
ARCHIVE_ORG_FORMAT = "%Y%m%d%H%M%S"


def ratelimit(max_per_second):
    min_interval = 1.0 / float(max_per_second)

    def decorate(func):
        last_time_called = [0.0]

        def rate_limited_func(*args, **kargs):
            elapsed = time.clock() - last_time_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            ret = func(*args, **kargs)
            last_time_called[0] = time.clock()
            return ret
        return rate_limited_func
    return decorate


class ArchiveIsArchive(object):

    def __init__(self, url):
        self.archived = self.archive(url)
        self.error_link = "https://archive.is/?" + urlencode({'url': url, 'run': 1})

    @staticmethod
    @ratelimit(0.5)
    def archive(url):
        params = {'url': url}
        res = requests.post('https://archive.is/submit/', params)
        if res.status_code != 200:
            return False
        url_re = re.search(r'^.*(?:archiveurl.{0,10}|replace\(")(?P<url>https?://archive\.is/[0-z]{1,6}).*$',
                           res.text, flags=re.I | re.M)
        if url_re:
            return url_re.group('url')
        return False


class ArchiveOrgArchive(object):

    def __init__(self, url):
        self.archived = self.archive(url)
        self.error_link = "https://web.archive.org/save/" + url

    @staticmethod
    @ratelimit(0.5)
    def archive(url):
        res = requests.get('https://web.archive.org/save/' + url)
        if res.status_code == 200:
            date = time.strftime(ARCHIVE_ORG_FORMAT)
            return 'https://web.archive.org/' + date + '/' + url
        if res.status_code == 403:
            return None
        return False


class MegalodonJPArchive(object):

    def __init__(self, url):
        self.archived = self.archive(url)
        self.error_link = "http://megalodon.jp"

    @staticmethod
    @ratelimit(0.5)
    def archive(url):
        params = {'url': url}
        res = requests.post("http://megalodon.jp/pc/get_simple/decide", params)
        if res.url == 'http://megalodon.jp/pc/get_simple/decide':
            return False
        return res.url


class ArchiveContainer(object):

    def __init__(self, url, text):
        self.url = url
        self.text = text[:LEN_MAX] + "..." if len(text) > LEN_MAX else text
        self.archives = [ArchiveIsArchive(url), ArchiveOrgArchive(url), MegalodonJPArchive(url)]

    def __iter__(self):
        for elem in self.archives:
            yield elem


def main():
    pass

if __name__ == "__main__":
    main()