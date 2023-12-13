# matrix_reloaded_ctrl
## Usage
```
usage: Matrix Display Controller v0.0 [-h] [--matrix-hostname MATRIX_HOSTNAME]
                                      [--log-level {TRACE,DEBUG,INFO,SUCCESS,WARNING,ERROR,CRITICAL}]
                                      [-q] [-s]
                                      [--forbidden-emotes FORBIDDEN_EMOTES]
                                      [--forbidden-users FORBIDDEN_USERS] [-u]
                                      [-i] [--command-port COMMAND_PORT]
                                      [chan]

positional arguments:
  chan                  Required if standalone. Twitch Messaging Interface
                        channel(s) to join. Format: <#chan>{,<#chan>{,...}}

options:
  -h, --help            show this help message and exit
  --matrix-hostname MATRIX_HOSTNAME
                        Defaults to 'matrix-reloaded.local'. Matrix display
                        hostname or IP address to connect to.
  --log-level {TRACE,DEBUG,INFO,SUCCESS,WARNING,ERROR,CRITICAL}
                        Defaults to INFO. Messages level SUCCESS and higher
                        are output to stderr. Level SUCCESS corresponds to
                        successful events that are important to the user (good
                        warnings), select WARNING if you want to only be
                        notified of failure warnings. Setting log level to
                        DEBUG is suggested while experimenting. TRACE level
                        prints IRC communications, which will expose
                        credentials!
  -q, --quiet           No ouput to stdout. All messages are ouput to stderr.
                        Log level can still be set using --log-level. Defaults
                        to SUCCESS then.
  -s, --silent          No output.
  --forbidden-emotes FORBIDDEN_EMOTES
                        Comma-separated list of forbidden Twitch emote ids.
  --forbidden-users FORBIDDEN_USERS
                        Comma-separated list of Twitch users to be ignored.
                        Use this to ignore your bots.
  -u, --no-summation    Don't count repetitions of the same emote/emoji in A
                        message.
  -i, --interactive     Don't do anything. Wait for commands on the command
                        interface. --command-port is mandatory.
  --command-port COMMAND_PORT
                        TCP port for the command interface. The command
                        interface is disabled if this argument is not
                        specified.

Built-in forbidden Twitch emotes: MercyWing1, MercyWing2, PowerUpL, PowerUpR,
Squid1, Squid2, Squid4
```

## Licensing

The one-file Python app and associated scripted tools are licensed under **GNU Affero General Public License version 3.0** and comes with absolutely no warranty. Full license text is available as the [LICENSE](LICENSE.md) file, which is a mandatory part of this distribution. \
This program is free software: you can redistribute it and/or modify it under specified terms. [More information here](https://www.gnu.org/licenses/agpl-3.0.html).

The Windows icon `ioodymDeni.ico` is provided by Alain Gervasi following terms of [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/).
