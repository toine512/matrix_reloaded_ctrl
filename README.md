# matrix_reloaded_ctrl

## Installation

### Prerequisites

**Python 3.12+** \
May or may not work with Python 3.11.

Libraries used: [aiohttp](https://docs.aiohttp.org), [aiofile](https://github.com/mosquito/aiofile), [emoji](https://carpedm20.github.io/emoji/docs/), [loguru](https://github.com/Delgan/loguru)

### General case

Download or clone the repo. Alternatively, files you really need for running the app are `matrix_display.py` and `requirements.txt`.

All dependencies are available from PyPI. You probably should create a Python virtual environment to install them: \
`python -m venv matrix_env`

Then switch to the virtual environment and install packages using pip: \
`. matrix_env/bin/activate` for POSIX shell \
`matrix_env\Scripts\activate.bat` for cmd \
`matrix_env\Scripts\Activate.ps1` for PowerShell \
`pip install -r requirements.txt`

matrix_display.py has a command line interface. To run, first activate the venv as above then use Python from the local environment. \
Try `python matrix_display.py --help` to get the usage prompt below.

### Windows

Two convenience tools that cover most usages are provided in the `windows/` directory.

Download or clone the repo. Python interpreter must be available in your environment (select add to PATH when you install Python). Try `python --version` in cmd.

**make.bat** performs installation steps and creates `windows/matrix_controller/` containing everything needed and which you can move elsewhere on the same machine. Delete subdirectories of `windows/` and re-run the script when `matrix_display.py` or Python is updated. \
Use `matrix_controller\run.bat` in a terminal to launch the app as you would run matrix_display.py directly.

**generate_exe.bat** uses PyInstaller to produce a standalone executable you'll find in `windows/exe/dist/`. \
You can remove subdirectories of `windows/` once you have copied `matrix_display.exe`. \
PyInstaller supports using [UPX](https://upx.github.io) in order to reduce executable size. Pass the path to the directory containing `upx.exe` as first argument of generate_exe.bat if you'd like to use UPX.

## How it works


## Usage
```
Matrix Display Controller v0.0 [-h] [-q] [-s] [-i]
                               [--matrix-hostname MATRIX_HOSTNAME]
                               [--log-level {TRACE,DEBUG,INFO,SUCCESS,WARNING,ERROR,CRITICAL}]
                               [--forbidden-emotes FORBIDDEN_EMOTES]
                               [--forbidden-users FORBIDDEN_USERS] [-u]
                               [--command-port COMMAND_PORT]
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
