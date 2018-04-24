#!/usr/bin/python
# Command line tool for SmugMug. Uses SmugMug API V2.

import argparse
import collections
import inspect
import json
import persistent_dict
import os
import requests
import urlparse

import smugmug as smugmug_lib
import smugmug_shell


CONFIG_FILE = os.path.expanduser('~/.smugcli')


class Helpers(object):
  @staticmethod
  def mknode(smugmug, args, node_type, parser):
    parser.add_argument('path',
                        type=lambda s: unicode(s, 'utf8'),
                        help='%s to create.' % node_type)
    parser.add_argument('-p',
                        action='store_true',
                        help='Create parents if they are missing.')
    parser.add_argument('--privacy',
                        type=lambda s: unicode(s, 'utf8'),
                        default='public',
                        choices=['public', 'private', 'unlisted'],
                        help='Access control for the created folders.')
    parser.add_argument('-u', '--user',
                        type=lambda s: unicode(s, 'utf8'),
                        default='',
                        help=('User whose SmugMug account is to be accessed. '
                              'Uses the logged-on user by default.'))
    parsed = parser.parse_args(args)

    smugmug.fs.make_node(parsed.user, parsed.path, parsed.p, {
      'Type': node_type,
      'Privacy': parsed.privacy.title(),
    })

  @staticmethod
  def ignore_or_include(smugmug, paths, ignore):
    files_by_folder = collections.defaultdict(list)
    for folder, file in [os.path.split(path) for path in paths]:
      files_by_folder[folder].append(file)

    for folder, files in files_by_folder.iteritems():
      if not os.path.isdir(folder or '.'):
        print 'Can\'t find folder %s' % folder
        return
      for file in files:
        full_path = os.path.join(folder, file)
        if not os.path.exists(full_path):
          print '%s doesn\'t exists' % full_path
          return

      configs = persistent_dict.PersistentDict(os.path.join(folder, '.smugcli'))
      original_ignore = configs.get('ignore', [])
      if ignore:
        updated_ignore = list(set(original_ignore) | set(files))
      else:
        updated_ignore = list(set(original_ignore) ^ set(files))
      configs['ignore'] = updated_ignore


class Commands(object):
  @staticmethod
  def login(smugmug, args):
    parser = argparse.ArgumentParser(
      prog='login', description='Login onto the SmugMug service')
    parser.add_argument('--key',
                        type=lambda s: unicode(s, 'utf8'),
                        required=True,
                        help='SmugMug API key')
    parser.add_argument('--secret',
                        type=lambda s: unicode(s, 'utf8'),
                        required=True,
                        help='SmugMug API secret')
    parsed = parser.parse_args(args)

    smugmug.login((parsed.key, parsed.secret))

  @staticmethod
  def logout(smugmug, args):
    smugmug.logout()

  @staticmethod
  def get(smugmug, args):
    url = args[0]
    scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
    params = urlparse.parse_qs(query)
    result = smugmug.get_json(path, params=params)
    print json.dumps(result, sort_keys=True, indent=2, separators=(',', ': '))

  @staticmethod
  def ls(smugmug, args):
    parser = argparse.ArgumentParser(
      prog='ls', description='List the content of a folder or album.')
    parser.add_argument('path',
                        type=lambda s: unicode(s, 'utf8'),
                        nargs='?',
                        default=os.sep,
                        help='Path to list.')
    parser.add_argument('-l',
                        help='Show details.',
                        action='store_true')
    parser.add_argument('-u', '--user',
                        type=lambda s: unicode(s, 'utf8'),
                        default='',
                        help=('User whose SmugMug account is to be accessed. '
                              'Uses the logged-on user by default.'))
    parsed = parser.parse_args(args)

    smugmug.fs.ls(parsed.user, parsed.path, parsed.l)

  @staticmethod
  def mkdir(smugmug, args):
    parser = argparse.ArgumentParser(
      prog='mkdir', description='Create a folder.')
    Helpers.mknode(smugmug, args, 'Folder', parser)

  @staticmethod
  def mkalbum(smugmug, args):
    parser = argparse.ArgumentParser(
      prog='mkalbum', description='Create a album.')
    Helpers.mknode(smugmug, args, 'Album', parser)

  @staticmethod
  def upload(smugmug, args):
    parser = argparse.ArgumentParser(
      prog='upload', description='Upload files to SmugMug.')
    parser.add_argument('src',
                        type=lambda s: unicode(s, 'utf8'),
                        nargs='+', help='Files to upload.')
    parser.add_argument('album',
                        type=lambda s: unicode(s, 'utf8'),
                        help='Path to the album.')
    parser.add_argument('-u', '--user',
                        type=lambda s: unicode(s, 'utf8'),
                        default='',
                        help=('User whose SmugMug account is to be accessed. '
                              'Uses the logged-on user by default.'))
    parsed = parser.parse_args(args)

    smugmug.fs.upload(parsed.user, parsed.src, parsed.album)

  @staticmethod
  def sync(smugmug, args):
    parser = argparse.ArgumentParser(
      prog='sync',
      description='Synchronize all local albums with SmugMug.')
    parser.add_argument('source',
                        type=lambda s: unicode(s, 'utf8'),
                        nargs='*',
                        default=u'*',
                        help=('Folder to sync. Defaults to the local folder. '
                              'Uploads the current folder by default.'))
    parser.add_argument('-t', '--target',
                        type=lambda s: unicode(s, 'utf8'),
                        default=os.sep,
                        help=('The destination folder in which to upload data. '
                              'Uploads to the root folder by default.'))
    parser.add_argument('-u', '--user',
                        type=lambda s: unicode(s, 'utf8'),
                        default='',
                        help=('User whose SmugMug account is to be accessed. '
                              'Uses the logged-on user by default.'))
    parsed = parser.parse_args(args)

    smugmug.fs.sync(parsed.user, parsed.source, parsed.target)

  @staticmethod
  def ignore(smugmug, args):
    parser = argparse.ArgumentParser(
      prog='ignore',
      description='Mark paths to be ignored during sync.')
    parser.add_argument('paths',
                        type=lambda s: unicode(s, 'utf8'),
                        nargs='+',
                        help=('List of paths to ignore during sync.'))
    parsed = parser.parse_args(args)
    Helpers.ignore_or_include(smugmug, parsed.paths, True)

  @staticmethod
  def include(smugmug, args):
    parser = argparse.ArgumentParser(
      prog='include',
      description=('Mark paths to be included during sync. '
                   'Everything is included by default, this commands is used to '
                   'negate the effect of the "ignore" command.'))
    parser.add_argument('paths',
                        type=lambda s: unicode(s, 'utf8'),
                        nargs='+',
                        help=('List of paths to include during sync.'))
    parsed = parser.parse_args(args)
    Helpers.ignore_or_include(smugmug, parsed.paths, False)

  @staticmethod
  def shell(smugmug, args):
    shell = smugmug_shell.SmugMugShell(smugmug)
    shell.cmdloop()


def main():
  commands = {name: func for name, func in
              inspect.getmembers(Commands, predicate=inspect.isfunction)}

  smugmug_shell.SmugMugShell.set_commands(commands)

  parser = argparse.ArgumentParser(description='SmugMug commandline interface.')
  parser.add_argument('command',
                      type=lambda s: unicode(s, 'utf8'),
                      choices=commands.keys(),
                      help='The command to run.')
  parser.add_argument('args', nargs=argparse.REMAINDER)
  args = parser.parse_args()

  try:
    config = persistent_dict.PersistentDict(CONFIG_FILE)
  except persistent_dict.InvalidFileError:
    print ('Config file (%s) is invalid. '
           'Please fix or delete the file.' % CONFIG_FILE)
    return

  smugmug = smugmug_lib.SmugMug(config)

  try:
    commands[args.command](smugmug, args.args)
  except smugmug_lib.NotLoggedInError:
    return


if __name__ == '__main__':
  main()
