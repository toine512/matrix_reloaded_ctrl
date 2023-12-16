# -*- coding: utf-8 -*-
# Dependencies: emoji aiohttp brotli aiofile loguru
from __future__ import annotations

### Internal Configuration ###

FORBIDDEN_TWITCH_EMOTES = {
	"MercyWing1": "1003187",
	"MercyWing2": "1003189",
	"PowerUpL": "425688",
	"PowerUpR": "425671",
	"Squid1": "191762",
	"Squid2": "191763",
	"Squid4": "191767"
}
FULL_LOG_INFO_TO_CONSOLE = False
PRGM_VERSION = "0.0"

### ***************************** ###



### License notice ###
#
#	Matrix Display Controller: connects the Matrix Reloaded LED panel display to Twitch chat
#	<https://github.com/toine512/matrix_reloaded_ctrl>
#	Copyright © 2023  toine512 <os@toine512.fr>
#
#	This program is free software: you can redistribute it and/or modify
#	it under the terms of the GNU Affero General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU Affero General Public License for more details.
#
#	You should have received a copy of the GNU Affero General Public License
#	along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
### ***************************** ###



### Imports ###

# Built-ins
import abc
import argparse
import asyncio
from asyncio import CancelledError
from collections import defaultdict, Counter
from collections.abc import Iterable, Iterator, AsyncIterator, Collection, Callable, Coroutine
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, NoReturn
import re
import sys
from tempfile import gettempdir
import textwrap
import traceback
from uuid import uuid1

# External modules
from aiofile import async_open
import aiohttp
import emoji
from loguru import logger as LOGGER
from loguru._defaults import LOGURU_FORMAT as LOGURU_DEFAULT_FORMAT
from yarl import URL

### ***************************** ###



### General usage functions ###

def exception_str(exception: BaseException) -> str:
	return "".join( traceback.format_exception_only(exception) ).strip()



class EmoteQueue (asyncio.Queue):

	@dataclass
	class EmoteItem:

		class Type (StrEnum):
			TWITCH_EMOTE = "twitch"
			EMOJI = "emoji"

		type: Type
		value: str
		count: int


	def __init__(self, maxsize: int = 0) -> None:
		super().__init__(maxsize)


	def clear(self) -> None:
		try:
			while True:
				self.get_nowait()
		except asyncio.QueueEmpty:
			return

### ***************************** ###



### Messaging interface ###
### (data source)       ###

class IRCBase (abc.ABC):

	class IRCMessage:
		v3tags: str | None = None
		prefix: str | None = None
		command: str | None = None
		params: str | None = None


	class IRCMessagePrefix:
		name: str | None = None
		user: str | None = None
		host: str | None = None


	@abc.abstractmethod
	async def run(self) -> NoReturn:
		pass


	def __init__(self, answer: bool, character_encoding: str = "utf-8") -> None:
		self.b_transmit = bool(answer)
		self.encoding = str(character_encoding)

		self.socket_reader: asyncio.StreamReader | None = None
		self.socket_writer: asyncio.StreamWriter | None = None


	## I/O
	# Readline reused in other classes
	@staticmethod
	async def read_line_agenerator(socket_reader: asyncio.StreamReader, encoding: str, log_tag: str) -> AsyncIterator[str]:
		end_of_msg = "\r\n".encode(encoding)

		while True:
			try:
				msg = str( await socket_reader.readuntil(end_of_msg) , encoding, "ignore")

			except asyncio.IncompleteReadError as e: # EOF
				# Is there something expected before EOF?
				if e.expected != 0:
					# Try to decode what's left
					try:
						msg = e.partial.decode(encoding, "ignore")
					except Exception:
						LOGGER.trace("{tag}: IncompleteReadError, failure to decode", tag=log_tag)
					else:
						# Was the last byte lost? (socket closed too fast?) => Is there a partial separator: \r from \r\n?
						if len(msg) > 1 and msg[-1] == "\r":
							msg = msg[0:-1]
							LOGGER.trace("{tag}: {line}", tag=log_tag, line=repr(msg)[1:-1])
							yield msg
							continue
						else:
							LOGGER.trace("{tag}: IncompleteReadError{line}", tag=log_tag, line=f"\n{repr(msg)[1:-1]}" if msg else "")
				# Else the message is incomplete, drop it and EOFError
				raise

			except asyncio.LimitOverrunError as e: # Data accumulated without a separator
				LOGGER.trace("{tag}: LimitOverrunError")
				# Purge buffer
				await socket_reader.read(e.consumed)
				# Continue waiting for more

			else:
				msg = msg[0:-2]
				LOGGER.trace("{tag}: {line}", tag=log_tag, line=repr(msg)[1:-1])
				yield msg


	# Readline parametrized for this class
	def _read_msg(self) -> AsyncIterator[str]:
		return self.read_line_agenerator(self.socket_reader, self.encoding, "IRC Read")


	async def _send(self, msg: Iterable) -> None:
		if isinstance(msg, str):
			LOGGER.trace("IRC Send: {esc}", esc=repr(msg)[1:-1])
			self.socket_writer.write(f"{msg}\r\n".encode(self.encoding))
		elif isinstance(msg, Iterable):
			if LOGGER._core.min_level <= LOGGER.level("TRACE").no: # type: ignore
				msg = list(msg)
				for line in msg:
					LOGGER.trace("IRC Send: {esc}", esc=repr(line)[1:-1])
			self.socket_writer.writelines( (f"{line}\r\n".encode(self.encoding) for line in msg) )
		else:
			raise TypeError()
		await self.socket_writer.drain()

	## ##

	## IRC parsing functions
	@staticmethod
	def _extract_header(key: str, pos: int, msg: str) -> tuple[int, str | None]:
		if msg[pos] == key: # Found
			i = msg.find(" ", pos)
			if i == -1: # Nothing after this block
				return len(msg), msg[pos+1:]
			# Else extract a section
			return i + 1, msg[pos+1:i]

		# Not found
		return pos, None


	@staticmethod
	def _extract_section(key: str, end: int, msg: str) -> tuple[int, str | None]:
		i = msg.rfind(key, 0, end)
		if i > -1:
			return i, msg[i+1:end]

		# Not found
		return end, None


	@classmethod
	def parse_message(cls, msg: str) -> IRCMessage:
		parsed = cls.IRCMessage()
		i_content_len = len(msg)
		i_pos = 0

		if i_content_len > 1:

			# Optional parts
			## IRCv3 Message Tag
			i_pos, parsed.v3tags = cls._extract_header("@", i_pos, msg)
			if i_pos >= i_content_len: # nothing left to parse, stop
				return parsed
			## Prefix
			i_pos, parsed.prefix = cls._extract_header(":", i_pos, msg)
			if i_pos >= i_content_len: # nothing left to parse, stop
				return parsed

			# Command
			i = msg.find(' ', i_pos)
			if i > -1:
				parsed.command = msg[i_pos:i]
				parsed.params = msg[i+1:]

		return parsed


	@staticmethod
	def parse_ircv3_tags(tags: str) -> dict[str, str]:
		return {key: val for key, _, val in (tag.partition("=") for tag in tags.split(";") if tag) if key}


	@classmethod
	def parse_prefix(cls, prefix: str) -> IRCMessagePrefix:
		parsed = cls.IRCMessagePrefix()
		i_pos = len(prefix)

		if i_pos > 0:
			i_pos, parsed.host = cls._extract_section("@", i_pos, prefix)
			i_pos, parsed.user = cls._extract_section("!", i_pos, prefix)
			parsed.name = prefix[0:i_pos]

		return parsed


	@staticmethod
	def parse_params(params: str) -> tuple[list, str]:
		li_middle: list[str] = list()
		i_content_len = len(params)
		i_pos = 0

		while i_pos < i_content_len:

			# Reached trailing?
			if params[i_pos] == ":":
				return (li_middle, params[i_pos+1:])

			# Skip preceding spaces
			elif params[i_pos] == " ":
				i_pos += 1

			# Extract one middle
			else:
				i_found = params.find(" ", i_pos)

				if i_found > 0:
					li_middle.append(params[i_pos:i_found])
					i_pos = i_found + 1
				else:
					li_middle.append(params[i_pos:])
					i_pos = i_content_len

		# Reaching here if there is no trailing
		return (li_middle, "")

	## ##

	## IRC commands
	async def _send_quit(self, message: str = "Goodbye.") -> None:
		if self.b_transmit:
			await self._send(f"QUIT {message}")
		LOGGER.info("IRC Quit: {}", message)


	async def _send_join(self, chan: str) -> None:
		if self.b_transmit:
			await self._send(f"JOIN {chan}")


	async def _send_pong(self, param: str) -> None:
		if self.b_transmit:
			await self._send(f"PONG {param}")

	## ##

	## IRC incoming handler
	# Command dispatcher to overload
	async def _process_command(self, msg: IRCMessage) -> None:
		match msg.command:
			case "PING":
				await self._send_pong(msg.params)

			case _:
				pass

	## ##



class TMIClient (IRCBase):

	s_server_hostname: str = "irc.chat.twitch.tv"
	i_server_port: int = 6697 # "SSL"


	def __init__(self, channel: str, user: str = "", oauth2_token: str = "") -> None:
		super().__init__(True)

		self.s_chan = str(channel).strip().lower()
		#if len(self.s_chan) < 2:
		#	raise ValueError("Twitch IRC channel must be supplied!")

		# Perform an anonymous authentication if user and token are not provided
		user = str(user).strip().lower()
		if user:
			self.s_user = user
		else:
			self.s_user = f"justinfan{uuid1().int>>79}"

		oauth2_token = str(oauth2_token)
		if oauth2_token:
			self.s_pass = f"oauth:{oauth2_token}"
		else:
			self.s_pass = "ILikeTrains!"

		self.b_available = False


	## App-available methods
	async def join(self, chan: str) -> bool:
		if chan and self.b_available: # do nothing if empty string
			async with asyncio.timeout(30):
				await self._send_join(chan)
				return True

		return False

	## ##

	## IRC incoming handlers
	# Overloaded command dispatcher
	async def _process_command(self, msg: IRCBase.IRCMessage) -> None:
		match msg.command:
			case "JOIN":
				self._in_join(msg)

			case "PART":
				self._in_part(msg)

			case _:
				await super()._process_command(msg)


	def _in_join(self, msg: IRCBase.IRCMessage) -> None:
		chan = msg.params
		if ( msg.prefix != None
		     and self.parse_prefix(msg.prefix).name == self.s_user
		     and chan
		     and chan[0] == "#" ):
			LOGGER.success("TMI: Successfully joined {ch} as {usr}!", ch=chan, usr=self.s_user)


	def _in_part(self, msg: IRCBase.IRCMessage) -> None:
		chan = msg.params
		if ( msg.prefix != None
		     and self.parse_prefix(msg.prefix).name == self.s_user
		     and chan
		     and chan[0] == "#" ):
			LOGGER.error("TMI: Got kicked out of {ch}! ({usr})", ch=chan, usr=self.s_user)

	## ##

	## Task
	async def _caps(self, li_additional_messages: list, caps: Collection[str]) -> None:
		if caps:
			async with asyncio.timeout(5):
				# Capabilities request
				await self._send("CAP REQ :" + " ".join(caps))

				# Intepret response
				# CAP * ACK :<caps> if success
				# CAP * NAK :<caps> if failure
				# Else pass message to the future
				async for msg in self._read_msg():
					msg = self.parse_message(msg)
					match msg.command:
						case None:
							pass

						case "CAP":
							li_result, s_caps = self.parse_params(msg.params)
							try:
								s_result = li_result[1]
							except IndexError:
								pass
							else:
								match s_result:
									case "ACK":
										LOGGER.debug("TMI: Granted capabilities: {}", s_caps)
										break
									case "NAK":
										LOGGER.critical("TMI: Refused capabilities: {}", s_caps)
										raise ValueError("Requested TMI capabilities can't be obtained!")
							raise RuntimeError("TMI CAP REQ unrecognised response!")

						case _:
							li_additional_messages.append(msg)
					# Else will eventually timeout


	async def _auth(self, li_additional_messages: list) -> None:
		async with asyncio.timeout(30):
			# Auth request
			await self._send( (f"PASS {self.s_pass}", f"NICK {self.s_user}") )

			# Interpret response
			# For success 376 (end of MOTD) is expected
			# Errors come as NOTICE
			# Else pass message to the future
			async for msg in self._read_msg():
				msg = self.parse_message(msg)
				match msg.command:
					case None:
						pass

					case "376": # Athentication success
						LOGGER.info("TMI: Authentication successful.")
						break

					case "NOTICE":
						match msg.params:
							case "* :Login authentication failed": # Wrong credentials
								await self._send_quit("Can't authenticate, aborting.")
								raise ValueError("Authentication failed.")

							case "* :Improperly formatted auth": # Implementation failure
								await self._send_quit("Can't authenticate, aborting.")
								raise RuntimeError('TMI "Improperly formatted auth"!')

							case _: # Other NOTICE message
								li_additional_messages.append(msg)

					case _:
						li_additional_messages.append(msg)
				# Else will eventually timeout


	async def run(self) -> NoReturn:
		while True: # reconnection loop

			# Open connection
			try:
				self.socket_reader, self.socket_writer = await asyncio.open_connection(self.s_server_hostname, self.i_server_port, ssl=True)
			except OSError as e:
				LOGGER.error("TMI: Can't connect to Twitch Messaging Interface! {exc!s}\nRetry in 5 minutes.", exc=e)
				# Try to reconnect
			else: # Socket is open

				li_deferred_messages: list[IRCBase.IRCMessage] = list()

				try:
					# Setup IRC
					## Request capabilities
					await self._caps(li_deferred_messages, ("twitch.tv/tags", ))
					## Try to authenticate
					await self._auth(li_deferred_messages)
					self.b_available = True
					## Join channel(s), fails silently
					await self.join(self.s_chan)
					## Consume other messages from previous steps
					for msg in li_deferred_messages:
						await self._process_command(msg)
					del li_deferred_messages

					# Run main client loop
					async for msg in self._read_msg():
						await self._process_command( self.parse_message(msg) )

				except CancelledError:
					self.b_available = False
					await self._send_quit()
					raise

				except (EOFError, TimeoutError, ConnectionError) as e:
					LOGGER.error("TMI: Twitch Messaging Interface connection error! {exc!s}\nRetry in 5 minutes.", exc=e)
					# Try to reconnect

				finally:
					self.b_available = False
					self.socket_writer.close()
					try:
						await self.socket_writer.wait_closed()
					except Exception:
						pass

			await asyncio.sleep(300)

	## ##



class ProcessTwitchEmotes:

	def __init__(self, q: EmoteQueue, no_summation: bool, forbidden_nicks: set, forbidden_emotes: set) -> None:
		if isinstance(q, EmoteQueue):
			self.emotes_q = q
		else:
			raise TypeError("asyncio queue expected!")
		if isinstance(forbidden_nicks, set):
			self.st_forbidden_nik = forbidden_nicks
		else:
			raise TypeError("Expected a set of forbidden nicknames!")
		if isinstance(forbidden_emotes, set):
			self.st_forbidden_ids = forbidden_emotes
		else:
			raise TypeError("Expected a set of forbidden emotes!")
		self.b_no_sum = bool(no_summation)


	## String processing helpers
	@staticmethod
	def extract_emojis(s: str, only_list: bool) -> Iterator[tuple[str, int]]:
		# Get each emoji occurrence, remove the presentation specifier if there is no zero-width joiner
		emojis = (chars if match.is_zwj() else chars.replace("\ufe0e", "").replace("\ufe0f", "") for chars, match in emoji.analyze(s, False, True))

		if only_list:
			# Remove duplicates
			emojis = set(emojis)
			# Set count to 1
			return ((emoji, 1) for emoji in emojis)

		# Else accumulate
		return Counter(emojis).items()


	@staticmethod
	def str_to_formatted_codepoints(s: str) -> str:
		codes = (f"{code:x}" for code in (ord(char) for char in s))
		return "-".join(codes)

	## ##

	## IRC incoming handlers
	# Overloaded command dispatcher (mixin with IRCBase child)
	async def _process_command(self, msg: IRCBase.IRCMessage) -> None:
		if msg.command == "PRIVMSG":
			self._in_privmsg(msg)
		else:
			await super()._process_command(msg) # type: ignore


	def _in_privmsg(self, msg: IRCBase.IRCMessage) -> None:
		b_skip_content = False
		EM = self.emotes_q.EmoteItem
		EM_T = self.emotes_q.EmoteItem.Type

		# Filter out ignored nicks (also rejects no nick)
		s_nick = IRCBase.parse_prefix(msg.prefix).name
		if s_nick and s_nick not in self.st_forbidden_nik:
			# Count emotes
			if msg.v3tags != None:
				di_tags = IRCBase.parse_ircv3_tags(msg.v3tags)

				if "emotes" in di_tags and di_tags["emotes"]:
					twi_emotes = di_tags["emotes"].split("/")
					twi_emotes = (emote_specifier.partition(":") for emote_specifier in twi_emotes)
					twi_emotes = ((emote_id, emote_pos) for emote_id, _, emote_pos in twi_emotes if emote_id and emote_id not in self.st_forbidden_ids and emote_pos)
					if self.b_no_sum:
						twi_emotes = ((emote_id, 1) for emote_id, emote_pos in twi_emotes)
					else:
						twi_emotes = ((emote_id, emote_pos.count(",")+1) for emote_id, emote_pos in twi_emotes)

					for s_id, i_count in twi_emotes:
						self.emotes_q.put_nowait( EM(EM_T.TWITCH_EMOTE, s_id, i_count) )

					b_skip_content = "emote-only" in di_tags and di_tags["emote-only"] == "1"

			# Count emojis
			if not b_skip_content:
				# Get message content (trailing of PRIVMSG)
				_, s_text = IRCBase.parse_params(msg.params)

				# Extract emojis
				for s_emoji, i_count in self.extract_emojis(s_text, self.b_no_sum):
					s_emoji_cp = self.str_to_formatted_codepoints(s_emoji)
					if s_emoji_cp not in self.st_forbidden_ids:
						self.emotes_q.put_nowait( EM(EM_T.EMOJI, s_emoji_cp, i_count) )

		#((not "first-msg" in di_tags) or di_tags["first-msg"] == "0")

	## ##



# Assembles the TMI client with the emote processing mixin
class TMIEmotesSource (ProcessTwitchEmotes, TMIClient):

	def __init__(self,  emotes_id_q: EmoteQueue, no_summation: bool, forbidden_users: set, forbidden_emotes: set, channel: str, user: str = "", oauth2_token: str = "") -> None:
		ProcessTwitchEmotes.__init__(self, emotes_id_q, no_summation, forbidden_users, forbidden_emotes)
		TMIClient.__init__(self, channel, user, oauth2_token)

#class TCPEmotesSource (ProcessTwitchEmotes):
#	def __init__(self, emotes_id_q: EmoteQueue) -> None:
#		ProcessTwitchEmotes.__init__(self, emotes_id_q)

### ***************************** ###



### Image downloader ###

class GetImages:

	url_twitch_base = URL("https://static-cdn.jtvnw.net/emoticons/v2/")
	url_emoji_base = URL("https://cdn.jsdelivr.net/gh/toine512/twemoji-bitmaps@main/128x128_png32/")
	path_cache = Path( gettempdir() ) / "python_matrix_reloaded_cache"


	def __init__(self, emotes_id_q: EmoteQueue, forbidden_emotes: set) -> None:
		if isinstance(emotes_id_q, EmoteQueue):
			self.emotes_q = emotes_id_q
		else:
			raise TypeError("asyncio queue expected!")
		if isinstance(forbidden_emotes, set):
			self.st_forbidden = forbidden_emotes
		else:
			raise TypeError("Expected a set of forbidden emotes!")

		# Create cache dir
		self.path_cache.mkdir(exist_ok=True)

		self.di_ladder: defaultdict[str, int] = defaultdict(lambda: 0)
		self.b_do_twitch = False
		self.b_do_emoji = False
		self._event_ladder = asyncio.Event()


	## Caching (FS) helpers
	@staticmethod
	def to_filename(name: str) -> str:
		"""Letters and _ . - characters. Others removed. Doesn't check for reserved names."""
		# Cleanup
		name = name.strip().replace(" ", "_")
		# Keep only Unicode letters and _ . -
		name = re.sub(r"(?u)[^-\w.]", "", name)
		# Is result invalid?
		if name in (".", ".."):
			name = ""
		# May return "", which is invalid
		return name


	@classmethod
	def _get_cachepath(cls, item: str) -> Path | None:
		s_file_name = cls.to_filename(item)
		if s_file_name:
			return (cls.path_cache/"placeholder.bin").with_stem(s_file_name)
		return None

	## ##

	## App-available methods
	async def get_ladder(self) -> dict[str, int]:
		await self._event_ladder.wait()
		self._event_ladder.clear()
		return self.di_ladder


	def clear_ladder(self) -> None:
		self._event_ladder.clear()
		self.di_ladder.clear()

	## ##

	## Task
	async def _check_availability(self, http_cli: aiohttp.ClientSession) -> None:
		# Test Twitch static CDN
		# Get a small Kappa
		self.b_do_twitch = False
		try:
			async with http_cli.get(self.url_twitch_base/"25/static/light/1.0") as http_res:
				if http_res.status == 200:
					self.b_do_twitch = True
				else:
					LOGGER.error("Downloader: Twitch emotes CDN URL issue. Response: {code} {res} Message: {msg}", code=http_res.status, res=http_res.reason, msg=await http_res.text() )

		except aiohttp.ClientError as e:
			LOGGER.error("Downloader: HTTPS GET failed: {exc!s}", exc=e)

		if not self.b_do_twitch:
			LOGGER.error("Downloader: Disabling Twitch emotes download!")

		# Test emoji
		# Get the first code point 😀
		self.b_do_emoji = False
		try:
			async with http_cli.get(self.url_emoji_base/"1f600.png") as http_res:
				match http_res.status:
					case 200:
						self.b_do_emoji = True
					case 404:
						LOGGER.error("Downloader: Emoji repository not found, app update is required. Error: {err}", err=await http_res.text() )
					case 403:
						LOGGER.error("Downloader: Access to emoji repository denied. Error: {err}", err=await http_res.text() )
					case _:
						LOGGER.error("Downloader: Emoji repository server error {code}. Message: {err}", code=http_res.status, err=await http_res.text() )

		except aiohttp.ClientError as e:
			LOGGER.error("Downloader: HTTPS GET failed: {exc!s}", exc=e)

		if not self.b_do_emoji:
			LOGGER.error("Downloader: Disabling emojis download!")

		if not (self.b_do_twitch or self.b_do_emoji):
			raise RuntimeError("No image source available!")


	async def _download_emote(self, emote: EmoteQueue.EmoteItem, file: Path, http_cli: aiohttp.ClientSession) -> bool:
		EM_T = EmoteQueue.EmoteItem.Type

		if not file.is_file():
			match emote.type:
				case EM_T.TWITCH_EMOTE:
					if self.b_do_twitch:
						http_req = http_cli.get(self.url_twitch_base / emote.value / "default/dark/3.0")
					else:
						return False

				case EM_T.EMOJI:
					if self.b_do_emoji:
						http_req = http_cli.get(self.url_emoji_base / f"{emote.value}.png")
					else:
						return False

				case _:
					raise NotImplementedError

			async with http_req as http_res:
				match http_res.status:
					case 200:
						try:
							async with async_open(file, "wb") as fd:
								await fd.write( await http_res.read() )
						except:
							# Don't leave empty or incomplete files behind, especially in case of task cancellation
							file.unlink(True)
							raise

					case 403 | 404:
						self.st_forbidden.add(emote.value)
						LOGGER.debug("Downloader: Server error: {} {} {}", http_res.url.human_repr(), http_res.status, http_res.reason)
						LOGGER.info("Downloader: Adding {name} to forbidden list.", name=emote.value)
						return False

					case _:
						LOGGER.debug("Downloader: Server error: {} {} {}", http_res.url.human_repr(), http_res.status, http_res.reason)
						return False

		return True


	async def run(self) -> NoReturn:
		async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as http_cli:

			while True: # retry loop

				await self._check_availability(http_cli)

				while True:
					# Wait forever for items
					emote = await self.emotes_q.get()

					# Get a cache path for the image
					path_file = self._get_cachepath(f"{emote.type}_{emote.value}")

					# Download if missing
					try:
						# Returns true if file is available
						if not await self._download_emote(emote, path_file, http_cli):
							continue # if not, abort, go to next item
					except (aiohttp.ClientError, OSError): # aiohttp client errors, file errors
						break # maybe recoverable error, restart

					# Add to ranking memory
					# Insertion order is preserved, so it's FIFO for an equal rank.
					self.di_ladder[path_file.name] += emote.count
					self._event_ladder.set() # inform paused reader there's new data


				await asyncio.sleep(300)

	## ##

### ***************************** ###



### Image uploader to matrix display ###

class MatrixPush:

	def __init__(self, host: str, emote_ladder_function: Callable[[], Coroutine[Any, Any, dict[str, int]]]) -> None:
		self._s_host = str(host).strip()
		self._fn_source = emote_ladder_function
		self._st_banlist: set[str] = set()
		self.pause = False


	## App-available method
	async def clear(self) -> bool:
		async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as http_cli:
			try:
				async with http_cli.get(URL.build(scheme="http", host=self._s_host, path="/clear"), compress=False) as http_res:
					match http_res.status:
						case 200:
							LOGGER.info("Display: Matrix cleared.")
							return True

						case 500:
							LOGGER.error("Display: Clearing matrix failed. {}", await http_res.text())

						case _:
							raise RuntimeError("Unexpected matrix HTTP response!")

			except aiohttp.ClientError as e:
				LOGGER.error("Display: Unable to clear matrix! {exc!s}", exc=e)

			return False

	## ##

	## Task
	async def run(self) -> NoReturn:

		async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as http_cli:

			while True:

				di_ladder = await self._fn_source()

				while True:
					# Trap to pause operation
					while self.pause:
						await asyncio.sleep(1.5)

					# Get highest ranked emote
					try:
						s_name = max(di_ladder, key=di_ladder.get)
					except ValueError:
						# ladder is now empty
						break

					# Upload to the matrix
					## Expected response codes
					## 200 OK: Loaded
					## 503 Service Unavailable: no slot available, retry later!
					## 408 Request Timeout: something went wrong during the transfer, can retry
					## 413 Content Too Large: file too large
					## 422 Unprocessable Content: bad file
					## 500 Internal Server Error: something is very wrong

					## Check if file is banned from upload (previous error)
					if s_name in self._st_banlist:
						del di_ladder[s_name]

					## Open file
					else:
						try:
							async with async_open(GetImages.path_cache/s_name, "rb") as fd:
								## POST
								try:
									async with http_cli.post(URL.build(scheme="http", host=self._s_host, path="/image"), data=await fd.read(), headers={"Content-Type": "application/octet-stream"}, compress=False, chunked=None, expect100=False) as http_res:
										match http_res.status:
										# Normal operation
											case 200:
												# Good
												del di_ladder[s_name]
												LOGGER.debug("Display: Uploaded {name} to matrix", name=s_name)

											case 503:
												http_res.release()
												LOGGER.debug("Display: Matrix memory full")
												# Wait for a bit and retry
												await asyncio.sleep(2.5)

										# Errors
											case 408:
												LOGGER.error("Display: Matrix request timeout, something went wrong with the transfer. Retrying.")
												# Retry
												await asyncio.sleep(0.1)

											case 413 | 422:
												del di_ladder[s_name]
												self._st_banlist.add(s_name)
												LOGGER.debug("Display: Matrix error: {} {}", http_res.reason, await http_res.text() )
												LOGGER.info("Display: Adding {name} to forbidden list.", name=s_name)

											case 500:
												del di_ladder[s_name]
												LOGGER.error("Display: Matrix internal server error! {}", http_res.text())

											case _:
												raise RuntimeError("Unexpected matrix HTTP response!")

								except aiohttp.ClientError as e:
									# Maybe recoverable error, wait 30 s and retry
									LOGGER.warning("Display: Matrix unavailable. {exc!s}\nRetry in 30 seconds.", exc=e)
									await asyncio.sleep(30)

						except OSError:
							LOGGER.error("Display: Cache miss. This isn't supposed to happen!")
							del di_ladder[s_name]

	## ##

### ***************************** ###



### TCP command interface ###

class CommandInterface:

	encoding = "utf-8"


	def __init__(self, app: MatrixReloadedApp) -> None:
		self._app = app

		self._client_socket_writer: asyncio.StreamWriter | None = None


	## Command processing helper
	@staticmethod
	def interpret_bs(line: str) -> str:
		while True:
			pos = line.find("\b")
			if pos < 0:
				break
			elif pos == 0:
				line = line[1:]
			else:
				line = line[0:pos-1] + line[pos+1:]
		return line

	## ##

	## I/O
	@classmethod
	async def _send(cls, socket_writer: asyncio.StreamWriter, crlf_breaks: bool, msg: str) -> None:
		LOGGER.trace("Remote Send: {esc}", esc=repr(msg)[1:-1])
		if crlf_breaks:
			msg = msg.replace("\n", "\r\n")
		socket_writer.write(f"{msg}\r\n".encode(cls.encoding))
		await socket_writer.drain()

	## ##

	## Client handler
	async def _handle_client(self, socket_reader: asyncio.StreamReader, socket_writer: asyncio.StreamWriter) -> None:
		# Single client, close previous if it exists
		if self._client_socket_writer != None:
			self._client_socket_writer.close()

		self._client_socket_writer = socket_writer
		s_peername = socket_writer.get_extra_info("peername", ("[unknown]", ))[0]
		s_hello_message = f"Matrix Display Controller v{PRGM_VERSION}\nType '?' to obtain available commands.\nHello {s_peername}!"
		b_telnet = False

		# Say hi!
		LOGGER.info("Remote: {peer} opened a command connection.", peer=s_peername)
		await self._send(socket_writer, b_telnet, s_hello_message)

		# Process commands
		try:
			async for msg in IRCBase.read_line_agenerator(socket_reader, self.encoding, "Remote Read"):
				if b_telnet:
					msg = self.interpret_bs(msg)
				cmds, trailing = IRCBase.parse_params(msg)

				if cmds:
					match cmds[0].lower():
						case "telnet":
							b_telnet = True
							await self._send(socket_writer, b_telnet, f"CR LF line breaks\nBS is interpreted\n{s_hello_message}")

						case "on":
							if self._app.start():
								LOGGER.info("Remote: Commanded start.")
								await self._send(socket_writer, b_telnet, "Started the show.")
							else:
								LOGGER.debug("Remote: Start command failed.")
								await self._send(socket_writer, b_telnet, "Can't start the show.")

						case "off":
							if await self._app.stop():
								LOGGER.info("Remote: Commanded stop.")
								await self._send(socket_writer, b_telnet, "Stopped the show.")
							else:
								LOGGER.debug("Remote: Stop command failed.")
								await self._send(socket_writer, b_telnet, "Can't stop the show.")

						case "join":
							LOGGER.debug("Remote: Requested JOIN {}.", textwrap.shorten(repr(trailing), 300))
							try:
								b_res = await self._app.join_channel(trailing)
							except Exception:
								await self._send(socket_writer, b_telnet, "JOIN command failed.")
							else:
								if b_res:
									await self._send(socket_writer, b_telnet, "JOIN command sent.")
								else:
									await self._send(socket_writer, b_telnet, "TMI is not ready.")

						case "clear":
							if await self._app.clear_all():
								LOGGER.info("Remote: Cleared.")
								await self._send(socket_writer, b_telnet, "Cleared matrix display.")
							else:
								LOGGER.debug("Remote: Clear all command failed.")
								await self._send(socket_writer, b_telnet, "Error clearing matrix display.")

						case "pause":
							if self._app.pause():
								LOGGER.info("Remote: Paused display.")
								await self._send(socket_writer, b_telnet, "Paused display.")
							else:
								LOGGER.debug("Remote: Requested PAUSE while not running.")
								await self._send(socket_writer, b_telnet, "Show is not running!.")

						case "resume":
							if self._app.resume():
								LOGGER.info("Remote: Resumed displaying images.")
								await self._send(socket_writer, b_telnet, "Resumed display.")
							else:
								LOGGER.debug("Remote: Requested RESUME while not running.")
								await self._send(socket_writer, b_telnet, "Show is not running!.")

						case "?" | "help" | "h":
							prompt = (
								"  ** Command list **",
								"     ? - Shows this message.",
								"    ON - Starts operation.",
								"   OFF - Stops operation.",
								" CLEAR - Clears all queues and the matrix display.",
								" PAUSE - Stops sending images to the matrix display, emotes and emoji collection remaining active.",
								"RESUME - Resumes sending images to the matrix display. The backlog is sent.",
								"TELNET - All line breaks (LF) are converted to CR LF for the lifetime of the connection.",
								"JOIN :<#chan>{,<#chan>{,...}} - Joins <#chan>."
							)
							await self._send(socket_writer, b_telnet, "\n| ".join(prompt))

						case _:
							LOGGER.debug("Remote: Unknown command.")
							await self._send(socket_writer, b_telnet, "Unknown command!")

		except (EOFError, ConnectionError) as e:
			LOGGER.trace("Remote: Connection ended reason = {exc}", exc=exception_str(e))
			LOGGER.info("Remote: Command connection with {peer} ended.", peer=s_peername)

	## ##

	## Task
	async def run(self, tcp_port: int) -> NoReturn: # type: ignore
		# Start serving
		try:
			server = await asyncio.start_server(self._handle_client, port=tcp_port)
		except Exception:
			LOGGER.critical("Remote: Unable to start command interface!")
			raise
		LOGGER.info("Remote: Command interface listening on port {port}.", port=tcp_port)

		# Wait forever
		try:
			await asyncio.sleep(float("inf"))

		# Close everything when cancelled
		except CancelledError:
			LOGGER.debug("Remote: Shutting down command interface.")
			# Stop serving
			try:
				server.close()
			except Exception:
				pass
			# Close (single) client connection
			if self._client_socket_writer != None:
				self._client_socket_writer.close()
			# Wait until all sockets are closed
			try:
				await server.wait_closed()
			except Exception:
				pass
			# Pass the cancelation
			raise

	## ##

### ***************************** ###



### Text-mode application ###

class MatrixReloadedApp:

	def __init__(self) -> None:
		cli = argparse.ArgumentParser(prog=f"Matrix Display Controller v{PRGM_VERSION}", epilog="Built-in forbidden Twitch emotes: " + ", ".join(FORBIDDEN_TWITCH_EMOTES.keys()))
		cli.add_argument("chan", action="store", nargs="?", default="", help="Required if standalone. Twitch Messaging Interface channel(s) to join. Format: <#chan>{,<#chan>{,...}}")
		cli.add_argument("--matrix-hostname", action="store", default="matrix-reloaded.local", help="Defaults to 'matrix-reloaded.local'. Matrix display hostname or IP address to connect to.")
		cli.add_argument("--log-level", action="store", choices=LOGGER._core.levels.keys(), type=str.upper, help="Defaults to INFO. Messages level SUCCESS and higher are output to stderr. Level SUCCESS corresponds to successful events that are important to the user (good warnings), select WARNING if you want to only be notified of failure warnings. Setting log level to DEBUG is suggested while experimenting. TRACE level prints IRC communications, which will expose credentials!") # type: ignore
		cli.add_argument("-q", "--quiet", action="store_true", help="No ouput to stdout. All messages are ouput to stderr. Log level can still be set using --log-level. Defaults to SUCCESS then.")
		cli.add_argument("-s", "--silent", action="store_true", help="No output.")
		cli.add_argument("--forbidden-emotes", action="store", default="", help="Comma-separated list of forbidden Twitch emote ids.")
		cli.add_argument("--forbidden-users", action="store", default="", help="Comma-separated list of Twitch users to be ignored. Use this to ignore your bots.")
		cli.add_argument("-u", "--no-summation", action="store_true", help="Don't count repetitions of the same emote/emoji in A message.")
		cli.add_argument("-i", "--interactive", action="store_true", help="Don't do anything. Wait for commands on the command interface. --command-port is mandatory.")
		cli.add_argument("--command-port", action="store", type=int, help="TCP port for the command interface. The command interface is disabled if this argument is not specified.")
		cli.add_argument("--version", action="version", version=PRGM_VERSION, help="Shows version and exits.")
		cli.add_argument("--license", action="store_true", help="Shows license prompt and exits.")
		self._cli_parser = cli

		self._taskgroup_main: asyncio.TaskGroup | None = None
		self._task_run_show: asyncio.Task | None = None
		self._task_tmi: asyncio.Task | None = None

		self.emotes_q = EmoteQueue()
		self.command = CommandInterface(self)
		self.st_forbidden_ids = set(FORBIDDEN_TWITCH_EMOTES.values())


	## CLI parsing helper
	@staticmethod
	def comma_separated_list(s: str) -> Iterator[str]:
		return (x.strip() for x in s.split(","))

	## ##

	## Actions
	def purge_waiting(self) -> None:
		self.emotes_q.clear()
		try:
			self.downloader.clear_ladder()
		except AttributeError:
			return


	async def clear_display(self) -> bool:
		try:
			return await self.uploader.clear()
		except AttributeError:
			return False


	async def clear_all(self) -> bool:
		self.purge_waiting()
		return await self.clear_display()


	def start(self) -> bool:
		if self._taskgroup_main == None:
			raise RuntimeError("App is not running!")

		if self._task_run_show == None or self._task_run_show.done():
			self._task_run_show = self._taskgroup_main.create_task( self._run_show() )
			return True

		return False


	async def stop(self, wait: bool = False) -> bool:
		if not (self._task_run_show == None or self._task_run_show.done()):
			# Stop input
			if not (self._task_tmi == None or self._task_tmi.done()):
				self._task_tmi.cancel("Stopping the show.")
				try:
					await self._task_tmi
				except CancelledError:
					pass

			# Do a clear
			await self.clear_all()

			# Stop everything else
			self._task_run_show.cancel("Stopping the show.")
			if wait:
				try:
					await self._task_run_show
				except CancelledError:
					pass
			return True

		return False


	def pause(self) -> bool:
		if not (self._task_run_show == None or self._task_run_show.done()):
			# Defined if "the show" runs
			self.uploader.pause = True
			return True

		return False


	def resume(self) -> bool:
		if not (self._task_run_show == None or self._task_run_show.done()):
			# Defined if "the show" runs
			self.uploader.pause = False
			return True

		return False

	## ##

	## Task
	async def _run_show(self) -> None:
		async with asyncio.TaskGroup() as tg:
			self._task_tmi = tg.create_task( self.tmi.run() )
			tg.create_task( self.downloader.run() )
			tg.create_task( self.uploader.run() )


	async def main(self) -> None:
		# Parse command line
		args = self._cli_parser.parse_args()

		# Prints AGPL prompt to stdout and exits if requested
		if args.license:
			print(textwrap.dedent("""\
				Matrix Display Controller: connects the Matrix Reloaded LED panel display to Twitch chat
				<https://github.com/toine512/matrix_reloaded_ctrl>
				Copyright © 2023  toine512 <os@toine512.fr>

				This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

				This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details. <https://www.gnu.org/licenses/>""" \
			))
			exit(0)

		# Else validate args
		if args.interactive and not args.command_port:
			self._cli_parser.error("--command-port must be specified with --interactive!")
		if args.command_port and args.command_port < 1:
			self._cli_parser.error("Port value forbidden!")
		if not (args.chan or args.command_port): # This is also what's displayed when no argument is given at all
			self._cli_parser.error("A channel to join must be supplied when remote command interface is not enabled. Try --help to see the list of arguments and their explanation.")
		# Forbidden emotes
		self.st_forbidden_ids.update( self.comma_separated_list(args.forbidden_emotes) )
		# Fobidden nicks
		self.st_forbidden_usr = set( (nick.lower() for nick in self.comma_separated_list(args.forbidden_users)) )

		# Configure logging
		LOGGER.remove()
		if not args.silent:
			if FULL_LOG_INFO_TO_CONSOLE:
				s_con_format = LOGURU_DEFAULT_FORMAT
			else:
				s_con_format = "<level>{message}</level>"

			if args.quiet:
				LOGGER.add(sys.stderr, level="SUCCESS" if args.log_level == None else args.log_level, format=s_con_format, diagnose=FULL_LOG_INFO_TO_CONSOLE, backtrace=FULL_LOG_INFO_TO_CONSOLE)

			else:
				s_lvl = "INFO" if args.log_level == None else args.log_level
				i_stderr_pivot = LOGGER.level("SUCCESS").no

				if LOGGER.level(s_lvl).no < i_stderr_pivot:
					LOGGER.add(sys.stdout, filter=lambda record: record["level"].no < i_stderr_pivot, level=s_lvl, format=s_con_format, diagnose=FULL_LOG_INFO_TO_CONSOLE, backtrace=FULL_LOG_INFO_TO_CONSOLE)
					LOGGER.add(sys.stderr, level=i_stderr_pivot, format=s_con_format, diagnose=FULL_LOG_INFO_TO_CONSOLE, backtrace=FULL_LOG_INFO_TO_CONSOLE)

				else:
					LOGGER.add(sys.stderr, level=s_lvl, format=s_con_format, diagnose=FULL_LOG_INFO_TO_CONSOLE, backtrace=FULL_LOG_INFO_TO_CONSOLE)

		# Create instances
		self.tmi = TMIEmotesSource(self.emotes_q, args.no_summation, self.st_forbidden_usr, self.st_forbidden_ids, args.chan)
		self.join_channel = self.tmi.join # needs to be exposed to command
		self.downloader = GetImages(self.emotes_q, self.st_forbidden_ids)
		self.uploader = MatrixPush(args.matrix_hostname, self.downloader.get_ladder)

		# Banner
		LOGGER.info("Matrix Display Controller\nversion {ver}\thttps://github.com/toine512/matrix_reloaded_ctrl", ver=PRGM_VERSION)

		# Run
		async with asyncio.TaskGroup() as tg:
			# Make the group universally usable (dangerous)
			self._taskgroup_main = tg

			# Start command interface
			if args.command_port:
				tg.create_task( self.command.run(args.command_port) )

			# Start if not in interactive mode
			if not (args.interactive and args.command_port):
				self.start()
		# Remove the reference after the context manager exits
		self._taskgroup_main = None

	## ##

### ***************************** ###



### Run ###

if __name__ == '__main__':
	try:
		app = MatrixReloadedApp()
		asyncio.run( app.main() )
	except KeyboardInterrupt:
		LOGGER.debug("User exit.")
	except Exception:
		LOGGER.opt(exception=True).critical("Program terminated!")
		sys.exit(1)

### ***************************** ###