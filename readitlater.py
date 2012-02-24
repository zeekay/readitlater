#!/usr/bin/env python
# encoding: utf-8

import argparse
import codecs
from datetime import datetime
import errno
import json
import os
import sys
import requests

CONFIG_DIR = os.path.expanduser('~/.config/readitlater')
SETTINGS_FILE = os.path.join(CONFIG_DIR, 'settings.json')
REQUIRED_SETTINGS = ['username', 'password', 'apikey']
DATE_FORMAT = "%a %b %d %I:%M %p"


class AttrDict(dict):
    def __getattr__(self, name):
        if name.startswith('_') or name == 'trait_names':
            raise AttributeError
        return self[name]


class API(object):
    def __init__(self, settings, url='https://readitlaterlist.com/v2/'):
        self.settings = settings
        self.url = url

    def request(self, method, **params):
        # remove any invalid params
        params = {k: v for k, v in params.items() if v}
        # inject settings
        params.update(self.settings)
        # make request
        res = requests.get(self.url + method, params=params)
        # try to convert response content to json
        try:
            res.json = json.loads(res.content, object_hook=AttrDict)
        except ValueError:
            res.json = None
        return res

    def __getattr__(self, name):
        if name.startswith('_') or name == 'trait_names':
            raise AttributeError
        return lambda **params: self.request(name, **params)


# utility functions
def make_dir():
    try:
        os.makedirs(CONFIG_DIR)
    except OSError as e:
        if e.errno == errno.EEXIST:
            pass
        else:
            raise


def format_date(timestamp):
    dt = datetime.fromtimestamp(float(timestamp))
    return dt.strftime(DATE_FORMAT)


def load_settings(validate=True):
    if not os.path.exists(SETTINGS_FILE):
        make_dir()
        raise Exception('{0} does not exist'.format(SETTINGS_FILE))
    try:
        with open(SETTINGS_FILE) as f:
            settings = json.load(f)
    except ValueError:
        raise Exception('{0} is invalid'.format(SETTINGS_FILE))

    if validate:
        missing = [opt for opt in REQUIRED_SETTINGS if not opt in settings]
        if missing:
            print 'Missing required settings: {0}'.format(', '.join(missing))
            return False
    return settings


# commands
def add_command(api, args):
    res = api.add(url=args.url)
    if not res.ok:
        print 'Unable to add url'


def list_command(api, args):
    # defaults
    count = args.count or 10
    since = args.since or None
    reverse = args.reverse or False

    res = api.get(count=count, since=since)
    if res.ok:
        for item in sorted(res.json.list.values(), key=lambda x: x.time_added, reverse=reverse):
            print format_date(item.time_added), item.title, item.url
    else:
        print res.headers['status']


def read_command(api, args):
    from readability.readability import Document
    import html2text
    h = html2text.HTML2Text()
    h.inline_links = False
    h.ignore_images = True
    h.ignore_emphasis = True
    res = requests.get(args.url)
    if res.ok:
        article = Document(res.content)
        print article.short_title()
        print h.handle(article.summary())
    else:
        print res.headers['status']


def search_command(api, args):
    res = api.get()
    for item in sorted(res.json.list.values(), key=lambda x: x.time_added):
        if args.query in ' '.join([item.url, item.title]):
            time_added = datetime.fromtimestamp(float(item.time_added))
            print time_added, item.title, item.url


def limit_command(api, args):
    res = api.api()
    for k, v in sorted(res.headers.items()):
        if k.startswith('x-limit'):
            print ' '.join(k[8:].split('-')) + ':', v


def settings_command(args):
    try:
        settings = load_settings()
    except:
        settings = {k:'' for k in REQUIRED_SETTINGS}

    if args.show:
        for k, v in settings.items():
            print k + ':', v
    else:
        new_settings = {}
        for opt in REQUIRED_SETTINGS:
            val = getattr(args, opt)
            if val:
                new_settings[opt] = val

        if not new_settings:
            return settings_parser.print_help()

        settings.update(new_settings)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f)


if __name__ == '__main__':
    sys.stdout = codecs.getwriter('UTF-8')(sys.stdout)
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    # add command
    add_parser = subparsers.add_parser('add', help='Add url to readitlater')
    add_parser.add_argument('url', action='store', help='Url to add')
    add_parser.set_defaults(command=add_command)

    # list command
    list_parser = subparsers.add_parser('list', help='List articles')
    list_parser.add_argument('--count', action='store_true', help='Number of articles to retrieve')
    list_parser.add_argument('--since', action='store_true', help='Only retrieve articles added since this time')
    list_parser.add_argument('--reverse', '-r', action='store_true', help='Reverse order of results')
    list_parser.set_defaults(command=list_command)

    # read command
    read_parser = subparsers.add_parser('read', help='Read text version of url')
    read_parser.add_argument('url', action='store', help='Url to read')
    read_parser.set_defaults(command=read_command)

    # search command
    search_parser = subparsers.add_parser('search', help='Search articles')
    search_parser.add_argument('query', action='store', help='Search query')
    search_parser.set_defaults(command=search_command)

    # limit command
    limit_parser = subparsers.add_parser('limit', help='Print current API limits')
    limit_parser.set_defaults(command=limit_command)

    # settings command
    settings_parser = subparsers.add_parser('settings', help='Show or configure settings')
    settings_parser.add_argument('--apikey', action='store', help='API Key to use')
    settings_parser.add_argument('--username', action='store', help='Username to use')
    settings_parser.add_argument('--password', action='store', help='Password to use')
    settings_parser.add_argument('--show', action='store_true', help='Show current settings')
    settings_parser.set_defaults(command=settings_command)

    # parse args
    args = parser.parse_args()
    command = args.command

    if command == settings_command:
        command(args)
    else:
        settings = load_settings(validate=True)
        if settings:
            api = API(settings)
            command(api, args)
