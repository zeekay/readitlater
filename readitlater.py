#!/usr/bin/env python
# encoding: utf-8

import argparse, errno, json, os
from datetime import datetime
import requests

CONFIG_DIR = os.path.expanduser('~/.config/readitlater')
SETTINGS_FILE = os.path.join(CONFIG_DIR, 'settings.json')
REQUIRED_SETTINGS = ['username', 'password', 'apikey']

# global settings
settings = {}


class AttrDict(dict):
    def __getattr__(self, name):
        if name.startswith('_') or name == 'trait_names':
            raise AttributeError
        return self[name]


class API(object):
    def __init__(self, url='https://readitlaterlist.com/v2/'):
        self.url = url

    def request(self, method, **params):
        if not settings:
            # Attempt to load settings in case this module is used externally or interactively.
            load_settings()
        # remove any invalid params
        params = {k:v for k,v in params.items() if v}
        # inject settings
        params.update(settings)
        # make request
        self._res = requests.get(self.url+method, params=params)
        if not self._res.ok:
            raise Exception(self._res.headers['status'])
        # return response
        return json.loads(self._res.content, object_hook=AttrDict)

    def __getattr__(self, name):
        if name.startswith('_') or name == 'trait_names':
            raise AttributeError
        return lambda **params: self.request(name, **params)


def make_dir():
    try:
        os.makedirs(CONFIG_DIR)
    except OSError as e:
        if e.errno == errno.EEXIST:
            pass
        else: raise

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        make_dir()
        raise Exception('{0} does not exist'.format(SETTINGS_FILE))
    try:
        with open(SETTINGS_FILE) as f:
            settings.update(json.load(f))
    except ValueError:
        raise Exception('{0} is invalid'.format(SETTINGS_FILE))

def settings_valid():
    try:
        load_settings()
    except Exception:
        print 'Create {0} with proper values for {1} either manually or using settings command'.format(SETTINGS_FILE, ', '.join(REQUIRED_SETTINGS))
        return False
    for opt in REQUIRED_SETTINGS:
        if opt not in settings:
            print 'Required setting {0} missing'.format(opt)
    else:
        return True

def show_settings(args):
    try:
        load_settings()
        for k,v in settings.items():
            print k + ':', v
    except Exception as e:
        print e

def save_settings(args):
    try: load_settings()
    except: pass
    for opt in ['apikey', 'username', 'password']:
        val = getattr(args, opt)
        if val:
            settings[opt] = val
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)

# commands
def list_command(args):
    api = API()

    # defaults
    count = args.count or 10
    since = args.since or None
    reverse = args.reverse or False

    res = api.get(count=count, since=since)
    for item in sorted(res.list.values(), key=lambda x: x.time_added, reverse=reverse):
        time_added = datetime.fromtimestamp(float(item.time_added))
        print time_added, item.title, item.url

def read_command(args):
    pass

def search_command(args):
    pass

def settings_command(args):
    if args.show:
        show_settings(args)
    else:
        save_settings(args)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='commands')

    # list command
    list_parser = subparsers.add_parser('list', help='List articles')
    list_parser.add_argument('--count', action='store_true', help='Number of articles to retrieve')
    list_parser.add_argument('--since', action='store_true', help='Only retrieve articles added since this time')
    list_parser.add_argument('--reverse', '-r', action='store_true', help='Reverse order of results')
    list_parser.set_defaults(command=list_command)

    # read command
    read_parser = subparsers.add_parser('read', help='Read article')
    read_parser.add_argument('article', action='store', help='Article to read')
    read_parser.set_defaults(command=read_command)

    # search command
    search_parser = subparsers.add_parser('search', help='Search articles')
    search_parser.add_argument('query', action='store', help='Search query')
    search_parser.set_defaults(command=search_command)

    # settings command
    settings_parser = subparsers.add_parser('settings', help='Configure settings')
    settings_parser.add_argument('--api-key', dest='apikey', action='store', help='API Key to use')
    settings_parser.add_argument('--username', action='store', help='Username to use')
    settings_parser.add_argument('--password', action='store', help='Password to use')
    settings_parser.add_argument('--show', action='store_true', help='Show settings')
    settings_parser.set_defaults(command=settings_command)

    # parse args
    args = parser.parse_args()
    command = args.command

    if command == settings_command:
        command(args)
    else:
        # validate settings first
        if settings_valid():
            command(args)
