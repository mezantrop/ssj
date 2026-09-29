#!/usr/bin/env python3

# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Mikhail Zakharov
# License: BSD-2-Clause
# The full text is available in the LICENSE file
# ------------------------------------------------------------------------------------------------ #

import getopt
import getpass
import json
import os
import shutil
import sys
import threading
if os.name == 'posix':
    import signal
    import termios
    import tty
if os.name == 'nt':
    import msvcrt

import paramiko


# -- Defaults ------------------------------------------------------------------------------------ #
TIMEOUT = 10
BANNER_TIMEOUT = 10
AUTH_TIMEOUT = 10
KNOWN_HOSTS = '~/.ssh/known_hosts'
ACCEPT_HOST_KEY = True
PTY = False

# ------------------------------------------------------------------------------------------------ #
SCRIPT_INFO = {'file': os.path.basename(sys.argv[0]), 'name': 'SSJ', 'version': '1.0.1'}

# ------------------------------------------------------------------------------------------------ #
def usage(ret_code=0, ret_msg=''):
    if ret_msg:
        print(f'{ret_msg}\n\n', file=sys.stderr)

    print(f'Usage:\n'
          f'\t{SCRIPT_INFO["file"]} [-t] --profile profile.json [command]\n'
          '\n'
          f'\t{SCRIPT_INFO["file"]} [-t]\n'
          f'\t\t--dest [user:[password]]@target.example.org[:port]\n'
          f'\t\t[--jump [user:[password]]@jump_1.example.org[:port]\n'
          f'\t\t--jump [user:[password]]@jump_n.example.org[:port]]\n'
          f'\t\t[command]\n\n'
          f'\t{SCRIPT_INFO["file"]} -h|--help\n\n'
          f'\t{SCRIPT_INFO["file"]} -V|--version\n\n'
          f'\t{SCRIPT_INFO["file"]} -v|--verbose\n\n'
          f'Notes:\n'
          f'\t* If user credentials are not specified {SCRIPT_INFO["file"]} will ask them interactively\n'
          f'\t* In batch processing always use -p | --profile for security!\n'
          f'\t* -t force pseudo-terminal\n'
          f'\t* With no [command] specified {SCRIPT_INFO["file"]} falls into shell\n\n')

    sys.exit(ret_code)

# ------------------------------------------------------------------------------------------------ #
def parse_authority(astr):
    authority = {}
    u, _, h = astr.rpartition('@')
    authority['user'], _, authority['password'] = u.partition(':')
    authority['host'], _, authority['port'] = h.partition(':')
    return authority

# ------------------------------------------------------------------------------------------------ #
def read_cli_args(argv):
    opts = ''
    args = ''
    verbose = False
    profile = {'hops': []}

    try:
        opts, args = getopt.getopt(argv, 'p:td:j:hvV',
                                   ['profile=', 'dest=', 'jump=',
                                        'help', 'version', 'verbose'])
    except getopt.GetoptError as err:
        usage(1, str(err))

    if not opts:
        usage(0)

    for opt, arg in opts:
        if opt == '-h' or opt == '--help':
            usage(0)
        elif opt == '-V' or opt == '--version':
            print(f'{SCRIPT_INFO["file"]}: {SCRIPT_INFO["name"]}-{SCRIPT_INFO["version"]}')
            sys.exit(0)
        elif opt == '-v' or opt == '--verbose':
            verbose = True
        elif opt == '-t':
            profile['pty'] = True
        elif opt == '-p' or opt == '--profile':
            profile = profile | read_profile(arg)
            if not profile:
                usage(1, f'Error reading profile: {arg}')
        elif opt == '-d' or opt == '--dest':
            profile = profile | parse_authority(arg)
        elif opt == '-j' or opt == '--jump':
            profile['hops'].append(parse_authority(arg))
        else:
            raise Exception(f'Unknown option: {opt}')

    return profile, ' '.join(args), verbose

# ------------------------------------------------------------------------------------------------ #
def read_profile(arg):
    try:
        with open(arg, 'r') as f:
            profile = json.load(f)
    except FileNotFoundError as err:
        print(f'read_profile(): {err}')
        sys.exit(1)

    return profile

# ------------------------------------------------------------------------------------------------ #
def ssh_connect(profile_dest, sock=None):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    known_hosts = os.path.expanduser(profile_dest.get('known_hosts', KNOWN_HOSTS) or KNOWN_HOSTS)
    client.load_host_keys(known_hosts)
    if profile_dest.get('accept_host_key', ACCEPT_HOST_KEY):
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    host = profile_dest['host']
    user = profile_dest.get('user') or input(f'Username@{host}: ')
    key = profile_dest.get('key', None) or None
    password = profile_dest.get('password')
    if not key and not password:
        password = getpass.getpass(prompt=f'{user}@{host} Password: ')

    try:
        client.connect(
            host,
            port=profile_dest.get('port'),
            username=user,
            key_filename=key,
            password=password,
            sock=sock,
            timeout=profile_dest.get('timeout', TIMEOUT) or TIMEOUT,
            banner_timeout=profile_dest.get('banner_timeout', BANNER_TIMEOUT) or BANNER_TIMEOUT,
            auth_timeout=profile_dest.get('auth_timeout', AUTH_TIMEOUT) or AUTH_TIMEOUT,
        )
    except paramiko.SSHException as err:
        print(f'ssh_connect(): {err}', file=sys.stderr)
        sys.exit(1)

    if profile_dest.get('keepalive'):
        client.get_transport().set_keepalive(profile_dest['keepalive'])

    return client

# ------------------------------------------------------------------------------------------------ #
def from_stdin(ch):
    while True:
        if os.name == 'posix':
            stdin_fd = sys.stdin.fileno()
            data = os.read(stdin_fd, 1)
        elif os.name == 'nt':
            data = msvcrt.getch()
        else:
            print(f'Unsupported operating system: "{os.name}"', file=sys.stderr)
            sys.exit(1)

        if not data:
            return
        try:
            ch.send(data)
        except (OSError, EOFError):
            return

# ------------------------------------------------------------------------------------------------ #
def from_ssh(ch):
    while True:
        if ch.closed:
            return
        data = ch.recv(4096)
        if not data:
            return
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()

# ------------------------------------------------------------------------------------------------ #
def make_resize_handler(ch):
    def resize(signum, frame):
        size = shutil.get_terminal_size()
        ch.resize_pty(width=size.columns, height=size.lines)
    return resize


# -- MAIN ---------------------------------------------------------------------------------------- #
if __name__ == '__main__':
    profile, command, verbose = read_cli_args(sys.argv[1:])

    if not profile.get('host'):
        usage(1, f'No destination host specified')

    profile['port'] = profile.get('port', 22) or 22
    profile['key'] = profile.get('key', None) or None
    for h in profile['hops']:
        h['port'] = h.get('port', 22) or 22
        h['key'] = h.get('key', None) or None

    hops = []
    ch = None
    for i, hop in enumerate(profile['hops']):
        if verbose:
            print(f'{hop["host"]}:{hop["port"]} > ', end='', file=sys.stderr, flush=True)
        h = ssh_connect(hop, ch)
        hops.append(h)

        if i + 1 < len(profile['hops']):
            next_dest = profile['hops'][i + 1]
        else:
            next_dest = profile

        if verbose:
            print(f'{next_dest["host"]}:{next_dest["port"]} | ', end='', file=sys.stderr, flush=True)
        ch = h.get_transport().open_channel(kind='direct-tcpip',
                                            dest_addr=(next_dest['host'], next_dest['port']),
                                            src_addr=('127.0.0.1', 0))

    if verbose:
        print(f'{profile["host"]}:{profile["port"]} > ', end='', file=sys.stderr, flush=True)
    dest = ssh_connect(profile, sock=ch)

    if command:
        if verbose:
            print(f'"{command[:20]}"', file=sys.stderr)

        _,  stdout, stderr = dest.exec_command(command, get_pty=profile.get('pty', PTY))
        out = stdout.read().decode()
        err = stderr.read().decode()
        status = stdout.channel.recv_exit_status()

        print(out)
        print(err)

        dest.close()
        while hops:
            hop = hops.pop()
            hop.close()

        exit(status)
    else:
        if verbose:
            print(f'"SHELL"', file=sys.stderr)

        term_size = shutil.get_terminal_size()
        term = os.environ.get('TERM') or 'xterm'
        ch = dest.invoke_shell(term=term, width=term_size.columns, height=term_size.lines)
        if os.name == 'posix':
            stdin_fd = sys.stdin.fileno()
            old_tty = termios.tcgetattr(stdin_fd)
            tty.setraw(stdin_fd)

            if os.name == 'posix':
                signal.signal(signal.SIGWINCH, make_resize_handler(ch))

        try:
            th_stdin = threading.Thread(target=from_stdin, args=(ch, ), daemon=True)
            th_ssh = threading.Thread(target=from_ssh, args=(ch, ))

            th_stdin.start()
            th_ssh.start()
            th_ssh.join()
            ch.close()
        finally:
            if os.name == 'posix':
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_tty)

        dest.close()
        while hops:
            hop = hops.pop()
            hop.close()
