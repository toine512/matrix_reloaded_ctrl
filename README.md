# Matrix Display Controller

This is the companion app to ["Matrix Reloaded" LED matrix display](https://github.com/toine512/matrix_reloaded). Written in Python with full asyncio concurrency, the "Matrix Display Controller" connects your Twitch chat to the LED matrix display.

Emotes and emojis posted in chosen channel(s) are fed to the LED matrix as an interactive element of streamers' set. The app provides a rudimentary remote control interface allowing integration in a workflow.

Necessary assets are downloaded and cached in host system's temporary directory. Any logic is done before sending an image to the matrix which is a simple queue. \
Purposely rendered [Twemoji](https://github.com/toine512/twemoji-bitmaps?tab=readme-ov-file) emojis are used.

## Installation

### Prerequisites

**Python 3.11+**

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

Two convenience tools that cover most uses are provided in the `windows/` directory.

Download or clone the repo. Python interpreter must be available in your environment (select add to PATH when you install Python). Try `python --version` in cmd.

**make.bat** performs installation steps and creates `windows/matrix_controller/` containing everything needed and which you can move elsewhere on the same machine. You need to regenerate when `matrix_display.py` or Python is updated: delete subdirectories of `windows/` and re-run the script. \
Use `matrix_controller\run.bat` in a terminal to launch the app as you would be running matrix_display.py directly.

**generate_exe.bat** uses PyInstaller to produce a standalone executable you'll find in `windows/exe/dist/`. \
You can remove subdirectories of `windows/` once you have copied `matrix_display.exe`. \
PyInstaller supports using [UPX](https://upx.github.io) in order to reduce executable size. Pass the path to the directory containing `upx.exe` as first argument of generate_exe.bat if you'd like to use UPX.

## How it works

The matrix display is a simple image queue which preserves upload order. The buffer of available memory is divided into fixed size slots, each holding one image. A slot is freed once the image it contains has been displayed. No logic besides consuming queue items happens at the receiving end. The display firmware directly decodes PNG and GIF and supports resizing. `matrix_display.py` listens to Twitch chat, collects emotes and emojis, then uploads them to the display over HTTP while ensuring maximum use of the queue.

This app connects to Twitch Messaging Interface (TMI) as the anonymous user (read only), no credentials are required. You can join multiple channels at the same time (as described in [Twitch Developers documentation](https://dev.twitch.tv/docs/irc/join-chat-room/)). Letter case doesn't matter. \
Example: `python matrix_display.py "#ioodyme,#ElisaK_,#Rancune_,#Yorzian,#SarahCoponat"`
> [!NOTE]
> Joining a channel is an asynchronous action. It only succeeded if you see the "Successfully joined #… as justinfan…!" message.

Twitch emotes and emojis from incoming messages are collected and may be ranked by popularity according to the following logic: if matrix display buffer is not full each image is sent right away, otherwise a counter of occurences is incremented for each image not yet sent. The ranking resulting from this process is used to decide upload priority order when one or more image slot becomes available in the matrix display. Higher number of occurences equals higher priority. When an image is sent to the display, its counter is reset.
> [!IMPORTANT]
> By default multiple occurences of the same emote/emoji in a message are counted. This behaviour can be disabled using `--no-summation` in order to prevent emote priority war by flooding with very long messages. On the other hand, default function better reflects viewer excitement if they don't abuse it. When this argument is used, any amount of the same image in a message counts for 1.

Twitch emote files are obtained from [Twitch static CDN](https://dev.twitch.tv/docs/irc/emotes/#cdn-template), emojis are [Twemoji purposely rendered at 128x128](https://github.com/toine512/twemoji-bitmaps?tab=readme-ov-file) served by jsDelivr. Image files are downloaded once and cached forever in `python_matrix_reloaded_cache` directory located at user's temporary files path as returned by [tempfile](https://docs.python.org/3/library/tempfile.html#tempfile.gettempdir) Python module. \
Under Windows it yields `<User Directory>/AppData/Local/Temp/python_matrix_reloaded_cache/`.
> [!NOTE]
> This cache can be removed for cleanup purposes or when an emoji is updated using `--purge`.

By default the target display is `matrix-reloaded.local`, this can be changed by specifying `--matrix-hostname`. While the display is unreachable, emote/emoji collection, ranking and download remain running. The backlog is uploaded to the matrix display as soon as it is available.

## Command interface

### Overview

The command interface is intended to help handing over control of the matrix display to another software in an automation system. It doesn't provide remote dynamic full functionality.

Text over a TCP connection is used to issue commands. The command interface can be enabled by providing the port you'd like to use: `--command-port <port>`. Concurrent connections are not supported, which greatly simplified implementation. When a new connection is established, the existing one (if any) is closed. **You will receive a banner when the connection is established.** All commands have a response message.

### Commands

Available commands are explained in the following table. I've reused the IRC Protocol syntax. Charset is UTF-8, **end of line character is LF**.

<table align="center">
  <thead>
    <tr>
      <th align="center">Command</th>
      <th align="center">Description</th>
      <th align="center">Explanation</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td align="center">ON</td>
      <td>Connects to TMI and starts operation.</td>
      <td rowspan=2>

Enables or disables this software. When "OFF", TMI is disconnected and no contact with the matrix display is attempted. Only the command interface remains active. \
Necessary with `--interactive` to do anything.

> [!IMPORTANT]
> If one or more channel is provided in the command line, it is joined during the startup sequence.
      </td>
    </tr>
    <tr>
      <td align="center">OFF</td>
      <td>Disconnects from TMI and stops operation.</td>
    </tr>
    <tr>
      <td align="center">CLEAR</td>
      <td>Clears all queues and the matrix display.</td>
      <td>Empties local and remote queue and blacks out the display.</td>
    </tr>
    <tr>
      <td align="center">PAUSE</td>
      <td>Stops sending images to the matrix display, *emotes and emoji collection remaining active*.</td>
      <td rowspan=2>
These commands are intended for handing over control of the display to a third party client. HTTP requests can then be issued to the display without interference when paused.

Example workflow: \
An established connection with the command interface is assumed.
1. A special chat command is posted by a Twitch user. \
   `!souverain` \
   In reaction, the automation bot whatching chat intends to display specific graphics on the matrix.
2. The automation bot queries `PAUSE` to the command interface. Now the automation bot can freely take control of the matrix display.
3. The automation bot makes HTTP requests to the matrix display… \
   `POST /image-prio souverain.png` \
   or \
   `GET /clear` \
   `POST /image souverain.png`
4. After some time, the normal emote/emoji show will be restored: the automation bot queries `RESUME` to the command interface. Images accumulated during pause are now sent to the matrix display.
      </td>
    </tr>
    <tr>
      <td align="center">RESUME</td>
      <td>Resumes sending images to the matrix display.</td>
    </tr>
    <tr>
      <td align="center">JOIN :&lt;#chan&gt;{,&lt;#chan&gt;{,…}}</td>
      <td>Joins &lt;#chan&gt;.</td>
      <td>
Example: `JOIN :#ioodyme,#CanardPC`
    </tr>
  </tbody>
</table>

> [!NOTE]
> The clear command implemented in the matrix display firmware (`GET /clear` endpoint) empties its queue and sets the display to black. If you only want to black out currently displayed image, pause this app using the command and send a black image in priority mode to the display (`POST /image-prio` endpoint). Then operation can be resumed.

### Human commands

Although the command interface is meant for machine control, terminal-friendly features are provided for debug and exploration purposes.

First connect the TCP socket to the port you specified via command line input with your favourite client. telnet or PuTTY can be used. There is no protocol. \
**Immediately send the command `TELNET` after receiving the first message. This will replace line endings you receive by CR LF and interpret BS (backspace) so you can type normally in your terminal.** You will receive the welcome banner again, with CR LF line endings. The "telnet mode" lasts until you close the connection.

Send the command `?` or `h` or `help` to get help.

Example with the software running on the same machine at port 6666:
```
Microsoft Telnet> o ::1 6666 ⏎

> Matrix Display Controller v1.0
>                               Type '?' to obtain available commands.
>                                                                     Hello ::1!

< telnet

> CR LF line breaks
> BS is interpreted
> Matrix Display Controller v1.0
> Type '?' to obtain available commands.
> Hello ::1!

< ?

>   ** Command list **
> |      ? - Shows this message.
> |     ON - Starts operation.
> |    OFF - Stops operation.
> |  CLEAR - Clears all queues and the matrix display.
> |  PAUSE - Stops sending images to the matrix display, emotes and emoji collection remaining active.
> | RESUME - Resumes sending images to the matrix display. The backlog is sent.
> | TELNET - All line breaks (LF) are converted to CR LF for the lifetime of the connection.
> | JOIN :<#chan>{,<#chan>{,...}} - Joins <#chan>.
```

### Modes of operation

The default behaviour of this program is to connect to TMI and join specified channels autonomously upon startup. The user providing a channel string (the one positional argument) is required.

When `--interactive` argument is used, no action is automatically performed. This mode is intended to be used with the command interface, as an always-running service. Thus `--command-port` becomes required, you must enable the command interface in order to do anything. \
The channel string provided by command line input becomes optional. If one is given, joining will be attempted automatically after a successful connection to TMI.

## More integration oriented features

- Logging: by default there are good and bad warnings output to stderr (level SUCCESS and WARNING). If you only want warnings when something's wrong, for automated log processing: set `--log-level warning` explicitely.

- `--forbidden-users` allows you to ignore your bots so that emojis in notifications and responses to stats queries are not shown. Multiple usernames can be passed separated by a comma, letter case doesn't matter. \
  Example: `--forbidden-users WizeBot,StreamElements`

- `--forbidden-emotes` allows you to ignore specific Twitch emotes. Multiple emote ids can be passed separated by a comma. \
  This argument takes an **emote id**. You can get the identifier of an emote using [Twitch API](https://dev.twitch.tv/docs/irc/emotes/) or by browsing [twitchemotes.com](https://twitchemotes.com). \
  Example: `--forbidden-emotes emotesv2_bf2ee530e5a04b5bb305847719998dc7,emotesv2_c9108ca6f1c344e287e1a565ce4dbd57`

## Use cases

> [!TIP]
> It is advised that you use `--log-level debug` while setting up in order to see all messages.

### Basic - run ondemand

The basic scenario is running the program when you need it, and terminate it when you don't. The operation with a simple command line is easy: \
`matrix_display.py "#ioodyme"` \
Maybe you have a chat services bot you want to ignore because it uses emojis in its responses to commands: \
`matrix_display.py --forbidden-users WizeBot "#ioodyme"` \
While you are experimenting, it is good to set logging level to DEBUG in order to see everything happening: \
`matrix_display.py --log-level debug --forbidden-users WizeBot "#ioodyme"`

### Remote controlled

## Usage
```
Matrix Display Controller v1.0 [-h] [-q] [-s] [-u] [-i]
                               [--matrix-hostname MATRIX_HOSTNAME]
                               [--log-level {TRACE,DEBUG,INFO,SUCCESS,WARNING,ERROR,CRITICAL}]
                               [--forbidden-emotes FORBIDDEN_EMOTES]
                               [--forbidden-users FORBIDDEN_USERS]
                               [--command-port COMMAND_PORT]
                               [--purge]
                               [--version]
                               [--license]
                               [chan]

positional arguments:
  chan                  Required if standalone. Twitch Messaging Interface channel(s) to join.
                        Format: <#chan>{,<#chan>{,...}}

options:
  -h, --help            show this help message and exit
  --matrix-hostname MATRIX_HOSTNAME
                        Defaults to 'matrix-reloaded.local'.
                        Matrix display hostname or IP address to connect to.
  --log-level {TRACE,DEBUG,INFO,SUCCESS,WARNING,ERROR,CRITICAL}
                        Defaults to INFO. Messages level SUCCESS and higher are output to stderr.
                        Level SUCCESS corresponds to successful events that are important
                        to the user (good warnings), select WARNING if you want to only be notified
                        of failure warnings.
                        Setting log level to DEBUG is suggested while experimenting.
                        TRACE level prints IRC communications, which will expose credentials!
  -q, --quiet           No ouput to stdout. All messages are ouput to stderr.
                        Log level can still be set using --log-level. Defaults to SUCCESS then.
  -s, --silent          No output.
  --forbidden-emotes FORBIDDEN_EMOTES
                        Comma-separated list of forbidden Twitch emote ids.
  --forbidden-users FORBIDDEN_USERS
                        Comma-separated list of Twitch users to be ignored.
                        Use this to ignore your bots.
  -u, --no-summation    Don't count repetitions of the same emote/emoji in A message.
  -i, --interactive     Don't do anything. Wait for commands on the command interface.
                        --command-port is mandatory.
  --command-port COMMAND_PORT
                        TCP port for the command interface.
                        The command interface is disabled if this argument is not specified.
  --purge               Cleans the local cache and exits. Sometimes emojis get corrections.
  --version             Shows version and exits.
  --license             Shows license prompt and exits.

Built-in forbidden Twitch emotes: MercyWing1, MercyWing2, PowerUpL, PowerUpR, Squid1, Squid2,
                                  Squid4, DinoDance
```

## Known issues

- At least on Windows, when command interface is enabled, sometimes an uncaught exception of unknown origin prevents the app from shutting down upon a SIGTERM. The workaround is issuing SIGTERM twice in order to ensure shutdown if it aborted the first time. \
  This issue is under investigation.

- Extremely rarely, error "Display: Cache miss. This isn't supposed to happen!" appears. Please report it, accompanied by a description of what you were doing.

## Licensing

The one-file Python app and associated scripted tools are licensed under **GNU Affero General Public License version 3.0** and comes with absolutely no warranty. Full license text is available as the [LICENSE](LICENSE.md) file, which is a mandatory part of this distribution. \
This program is free software: you can redistribute it and/or modify it under specified terms. [More information here](https://www.gnu.org/licenses/agpl-3.0.html).

The Windows icon `ioodymDeni.ico` is provided by Alain Gervasi following terms of [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/).
