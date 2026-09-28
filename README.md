# SSJ

**SSJ** is a small SSH client with support for multi-hop connections through SSH `direct-tcpip` channels.

It is roughly inspired by:

```text
ssh -J jump1,jump2 target
```

but is intentionally much smaller and more straightforward.

SSJ can:

* connect to a target directly or through multiple SSH jump hosts;
* authenticate with password or SSH key;
* execute a command on the target;
* open an interactive shell with a remote PTY;
* resize the remote PTY when the local terminal is resized on POSIX systems;
* use `known_hosts` files;
* optionally accept previously unknown host keys automatically;
* configure connection, SSH banner and authentication timeouts;
* configure SSH keepalive;
* run on both Unix-like systems and Windows.

## Requirements

* Python 3
* [Paramiko](https://www.paramiko.org/)

Install Paramiko with:

```sh
python3 -m pip install paramiko
```

## Usage

### Interactive shell

Direct connection:

```sh
ssj.py --dest user:password@host.example.org
```

Through one jump host:

```sh
ssj.py \
    --dest user:password@target.example.org \
    --jump user:password@jump.example.org
```

Multiple jump hosts are supported:

```sh
ssj.py \
    --dest user:password@target.example.org \
    --jump user:password@jump1.example.org \
    --jump user:password@jump2.example.org
```

The connections are established as:

```text
local
  |
  +-- SSH --> jump1
                |
                +-- direct-tcpip --> jump2
                                      |
                                      +-- direct-tcpip --> target
```

No SSH client is executed on the jump hosts. Each hop is an SSH connection, and the connection to the next host is forwarded through a `direct-tcpip` channel.

### Execute a command

```sh
ssj.py --dest user:password@host.example.org uname -a
```

Everything after the options is treated as the command:

```sh
ssj.py --dest user:password@host.example.org ls -la /tmp
```

By default, commands are executed without a pseudo-terminal.

Use `-t` when a command requires a PTY:

```sh
ssj.py -t --dest user:password@host.example.org top
```

This is useful for programs such as `top`, `vim`, `mc`, and other terminal-oriented applications.

### Verbose mode

```sh
ssj.py -v --dest user:password@host.example.org
```

Verbose mode shows the progress of each SSH connection and forwarding channel.

For example:

```text
jump1.example.org:22 > target.example.org:22 | target.example.org:22 > "SHELL"
```

The markers are intentionally printed before the corresponding operation completes, so the output can also indicate where a connection is stuck.

## Profiles

For repeated connections, a JSON profile can be used:

```sh
ssj.py --profile server.json
```

Example:

```json
{
    "host": "server.example.org",
    "port": 22,
    "user": "user",
    "password": "secret",

    "hops": [
        {
            "host": "jump1.example.org",
            "port": 22,
            "user": "user1",
            "password": "jump-secret"
        },
        {
            "host": "jump2.example.org",
            "port": 22,
            "user": "user2",
            "password": "jump-secret-2"
        }
    ]
}
```

The profile can also contain SSH keys:

```json
{
    "host": "server.example.org",
    "user": "user",
    "password": null,
    "key": "~/.ssh/id_ed25519"
}
```

Keys are read by SSJ on the local machine. They are not copied to or executed on jump hosts.

### Profile options

| Option            |                            Default | Description                                       |
| ----------------- | ---------------------------------: | ------------------------------------------------- |
| `host`            |                           required | SSH target hostname or address                    |
| `port`            |                               `22` | SSH port                                          |
| `user`            |                           required | SSH username                                      |
| `password`        | required by current implementation | SSH password                                      |
| `key`             |                             `null` | Private key filename                              |
| `hops`            |                               `[]` | List of jump hosts                                |
| `known_hosts`     |               `~/.ssh/known_hosts` | User known-hosts file                             |
| `accept_host_key` |                             `true` | Automatically accept previously unknown host keys |
| `timeout`         |                               `10` | Connection timeout in seconds                     |
| `banner_timeout`  |                               `10` | SSH banner timeout in seconds                     |
| `auth_timeout`    |                               `10` | Authentication timeout in seconds                 |
| `keepalive`       |                           disabled | Keepalive interval in seconds                     |
| `pty`             |                            `false` | Request a PTY for command execution               |

The same connection options can be specified for individual jump hosts.

For example:

```json
{
    "host": "server.example.org",
    "user": "user",
    "password": "secret",
    "known_hosts": "~/.ssh/known_hosts",
    "accept_host_key": true,
    "timeout": 10,
    "banner_timeout": 10,
    "auth_timeout": 10,
    "keepalive": 30,
    "pty": false,

    "hops": [
        {
            "host": "jump.example.org",
            "user": "user1",
            "password": "jump-secret",
            "keepalive": 30
        }
    ]
}
```

`~` in `known_hosts` and key filenames is expanded by Python with `os.path.expanduser()`, so the same profile format can be used on Unix-like systems and Windows.

## Host keys

SSJ loads:

1. system SSH host keys;
2. the configured user `known_hosts` file.

By default, SSJ also accepts previously unknown host keys:

```json
{
    "accept_host_key": true
}
```

This behavior is convenient for jump hosts and ephemeral infrastructure.

For stricter host-key checking:

```json
{
    "accept_host_key": false
}
```

When automatic acceptance is disabled, unknown host keys are rejected by Paramiko's default policy.

Host keys which are already known are still checked. Automatically accepting a new host key does not mean that an existing known host key can silently change.

## Security

Command-line connection strings may contain passwords:

```text
ssj.py --dest user:password@host.example.org
```

This may expose credentials through shell history or the operating system's process listing.

For regular use, prefer a profile:

```sh
ssj.py --profile server.json
```

and protect the profile appropriately.

The default `accept_host_key` behavior is intended to make SSJ convenient for multi-hop and temporary environments. For environments where host identity must be explicitly verified, set:

```json
"accept_host_key": false
```

and maintain the appropriate `known_hosts` entries.

## PTY and terminals

Interactive shells always request a remote PTY.

The terminal type is taken from the local `TERM` environment variable:

```python
TERM
```

with `xterm` used as a fallback.

On POSIX systems SSJ switches the local terminal into raw mode while the interactive shell is running and restores the original terminal settings when the connection closes.

Terminal resize events are propagated to the remote PTY on systems supporting `SIGWINCH`.

Windows does not provide `SIGWINCH`, so terminal resizing is currently handled differently.

## Exit status

When executing a command, SSJ returns the remote command's exit status.

For example:

```sh
ssj.py --dest user:password@host.example.org false
echo $?
```

returns the exit status reported by the remote SSH channel.

## Command-line options

```text
ssj.py [-t] --profile profile.json [command]

ssj.py [-t]
       --dest user:password@target.example.org[:port]
       [--jump user:password@jump.example.org[:port]
        --jump user:password@jump.example.org[:port]]
       [command]

ssj.py -h|--help
ssj.py -V|--version
ssj.py -v|--verbose
```

### Options

```text
-p, --profile FILE
    Read connection settings from a JSON profile.

-d, --dest USER:PASSWORD@HOST[:PORT]
    Specify the target directly.

-j, --jump USER:PASSWORD@HOST[:PORT]
    Add an SSH jump host. Can be specified multiple times.

-t
    Request a pseudo-terminal for command execution.

-v, --verbose
    Print connection progress information.

-h, --help
    Show help.

-V, --version
    Show version information.
```

## Why another SSH client?

Because apparently there were not enough.

SSJ is primarily an experiment in implementing a small SSH jump client directly with Python and Paramiko.

The goal is not to replace OpenSSH. It deliberately avoids trying to reproduce its enormous collection of forwarding, authentication, configuration and terminal features.

The core model is simple:

```text
SSH connection
      |
      +-- direct-tcpip channel --> next SSH connection
                                      |
                                      +-- direct-tcpip channel --> target
```

This makes the implementation relatively easy to understand while still being useful for ordinary multi-hop SSH access.

## License

Copyright (c) 2026 Mikhail Zakharov

Licensed under the BSD 2-Clause License.

See [`LICENSE`](LICENSE) for the full license text.
