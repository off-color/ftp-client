#!/usr/bin/env python3

import sys
import shlex
import argparse
import os
import getpass
import contextlib

ERROR_EXCEPTION = 1
ERROR_MODULES_MISSING = 2
ERROR_LOGIN = 3

if sys.platform.startswith('linux'):
    import readline

try:
    import exceptions
    import ftp
    import help
    import progress
    import fakeserver
except Exception as e:
    print('Program modules not found: "{}"'.format(e), file=sys.stderr)
    sys.exit(ERROR_MODULES_MISSING)


def main():
    client = ftp.Client()
    parser = setup_parser()
    args = parser.parse_args()

    try:
        ftp.IS_ACTIVE = args.active
        ftp.DEBUG = args.debug
        ftp.ENCODING = args.encoding
        print(client.connect(args.host, args.port))
        print(client.login(args.name, args.passw))
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(ERROR_LOGIN)

    while True:
        try:
            request = input('> ')
            try:
                command, *args = shlex.split(request)
            except Exception:
                print('?Invalid command')
                continue
            if command not in client.commands:
                print('?Invalid command')
                continue
            resp = execute_command(client, command, *args)
        except (EOFError, KeyboardInterrupt):
            initiate_exit(client)
        except Exception as e:
            print(str(e), file=sys.stderr)
        else:
            if ftp.DEBUG or command == 'reconnect' or command == 'help':
                print(resp)

        if client.timeToExit:
            break


def execute_command(client, command, *args):
    if (command not in client.UNDEMANDING_COMMANDS
            and not client.isConnected):
        raise exceptions.NotConnectedException('Not connected.')

    resp = client.commands[command](*args)
    if ftp.ERROR_PATTERN.match(resp):
        raise exceptions.FailedOperationException(resp)
    return resp


def setup_parser():
    '''configure arguments parser'''
    name = os.path.basename(sys.argv[0])
    parser = argparse.ArgumentParser(
        description='Ftp client')
    parser.add_argument('host', metavar='HOST',
                        help='name of server')
    parser.add_argument('name', nargs='?', metavar='[LOGIN]',
                        default='anonymous',
                        help='username, default: anonymous')
    parser.add_argument('-P', '--Password', action=Password, nargs='?',
                        dest='passw',
                        default='anonymous@',
                        help='password, default: anonymous@')
    parser.add_argument('-p', '--port', dest='port', nargs='?',
                        default=21, help='port, default: 21', type=int)
    parser.add_argument('-e', '--encoding', dest='encoding', nargs='?',
                        default='utf-8',
                        help='encoding, default: utf-8')
    parser.add_argument('-d', '--debug', action='store_true',
                        dest='debug',
                        help='print messages from server')
    parser.add_argument('-a', '--active', action='store_true',
                        dest='active',
                        help='connect with active mode')
    return parser


def initiate_exit(client):
    try:
        with contextlib.suppress(Exception):
            execute_command(client, 'exit')
    except KeyboardInterrupt:
        sys.exit(ERROR_EXCEPTION)


class Password(argparse.Action):
    def __call__(self, parser, namespace, values, option_string):
        if values is None:
            values = getpass.getpass()

        namespace.passw = values


if __name__ == '__main__':
    main()
