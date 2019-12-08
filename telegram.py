import telebot
from telebot.apihelper import ApiException
import settings
import os
import converter
import twitter_
import re
from util import get_version


class TGBot:
	"""This is the Telegram Bot class
	
	Attributes:
		:ivar key: Telegram API key
		:ivar user: Telegram user ID that the bot is linked to
		:ivar bot: The pyTelegramBotAPI bot instance
		:type key: str
		:type user: int
		:type bot: TeleBot
	"""
	
	def __init__(self, cfg: settings.Settings):
		"""Inits the bot and tests that the API key is valid.
		
		:param cfg: configurations class
		:type cfg: Settings
		"""
		self.cfg = cfg
		self.tw = twitter_.Twitter(cfg)
		self.key = cfg.telegram_key
		self.user = cfg.telegram_user_id
		self.bot = telebot.TeleBot(self.key)
		self.link_key = None
		try:
			cuentabot = self.bot.get_me()
		except ApiException:
			raise ValueError("Invalid Telegram API key.")
		print("Connected to Telegram: " + cuentabot.username)
		
		@self.bot.message_handler(content_types=['voice', 'audio'])
		def launch_voice(msg):
			self.tg_audio_handler(msg)
		
		@self.bot.message_handler(func=lambda msg: True)
		def launch_text(msg):
			self.tg_message_handler(msg)
	
	def tg_audio_handler(self, message: telebot.types.Message):
		"""Audio handler

		:param message: message generated by PyTelegramBotAPI
		:return:
		"""
		if message.from_user.id == self.user:
			self.send_msg(
				"We received the voice note. Please wait a few seconds while we send it to Twitter. Please don't send me anything else until you receive a reply from me.")
			if message.voice is not None:
				archivo = message.voice
			else:
				archivo = message.audio
			voice_info = self.bot.get_file(archivo.file_id)
			downloaded_voice = self.bot.download_file(voice_info.file_path)
			if not os.path.exists("media"):
				os.makedirs("media")
			filename = "media/" + str(archivo.file_id)
			duration = archivo.duration
			with open(filename + ".ogg", "wb") as file:
				file.write(downloaded_voice)
			try:
				os.remove(filename + ".mp4")
			except:
				pass
			converter.convert(filename, duration)
			try:
				self.tw.tweet(filename + ".mp4")
				self.send_msg(
					"Audio sent. If you were replying to a Tweet, send \"/cancel\" to exit reply mode. Tweet text is now empty.")
			except KeyError as e:
				self.send_msg("Audio could not be sent. Please check that you can send DM to that user.")
			os.remove(filename + ".ogg")
			os.remove(filename + ".mp4")
	
	def tg_message_handler(self, message: telebot.types.Message):
		"""Text message handler

		:param message: message generated by PyTelegramBotAPI
		:return:
		"""
		if self.user is None:
			if message.text == self.link_key:
				self.cfg.telegram_user_id = message.from_user.id
				self.user = message.from_user.id
				print("Bot linked to " + str(message.from_user.id) + " (" + message.from_user.first_name + ")")
				self.send_msg(
					"Bot successfully linked. You can send me voice notes and I will Tweet them as a video or send me a link to a Tweet and then the voice note and I will tweet them as a reply to the specified Tweet.\nYou can also add text to the tweet using \"/text <your text here>\". To remove the text, just send that command with no text.\nSend Direct messages with /dm <user>. @ is not needed.")
				self.cfg.save_settings("config.cfg")
		else:
			if message.from_user.id == self.user:
				match = re.search("https://twitter.com/[a-z|A-Z|0-9|_]+/status/[0-9]+", message.text)
				if match is not None:
					url = message.text[match.start():match.end()]
					foo, tweet_id = url.rsplit("/", 1)
					tweet_text, user = self.tw.set_reply(tweet_id)
					if tweet_text is not None:
						self.send_msg(
							"Now replying to: @" + user + ": " + tweet_text + "\nTo post the audio as a tweet instead of a reply, send \"/cancel\"")
					else:
						self.send_msg("The tweet you sent seems to not exist.")
				else:
					if message.text == "/cancel":
						self.tw.set_reply(None)
						self.send_msg("Now posting as a Tweet.")
					elif message.text.startswith("/text"):
						if message.text == "/text" or message.text == "/text ":
							text = ""
						else:
							text = message.text[6:]
						
						while len(text) > 240:
							spacestext = " ".join(text.split(" ")[:-1])
							if spacestext == "":
								# if it has returned an empty string it means the word has no more spaces (safety check)
								# slice at max and go
								text = text[:239]
							else:
								text = spacestext
						# check again
						
						self.tw.set_text(text)
						if text == "":
							self.send_msg("Text cleared.")
						else:
							self.send_msg("Text set to: " + text)
					elif message.text.startswith("/dm"):
						if message.text == "/dm" or message.text == "/dm ":
							user = None
						else:
							user = message.text[4:]
							user = user.replace("@", "")
						user = self.tw.set_dm_user(user)
						if user is None:
							self.send_msg("DM cancelled.")
						else:
							self.send_msg("Sending DM to @" + user + ". Send /dm with no user to exit DM mode.")
					elif message.text == "/help":
						self.send_msg("""Available commands:
· /text <text> - Sets the text for your next Tweet or DM.
· /dm <user> - Sends audios to a user through DM instead of posting Tweets. Sending no user or a nonexisting one will exit DM mode.
· Send a link to a Tweet and I'll reply to that one.
· /cancel - Exits reply mode and posts next audios as a normal Tweet.
· Send an audio or a music file and I will post that audio with the previous configurations. If the file is longer than 2:20 mins, it will be cut at that time.
· /help - Shows this help.
· /about - Shows the about page.""")
					elif message.text == "/about":
						self.send_msg("""*About:*
*AudiosToTwitter v""" + get_version() + """*

Created by: [rogama25](https://twitter.com/rogama25)

[Check the project's official site.](https://github.com/rogama25/AudiosToTwitter)
With help from [IceWildcat](https://github.com/IceWildcat)

Report any bugs at [my GitHub repo](https://github.com/rogama25/audiosToTwitter/issues/new)

*With ❤️ from Spain*""", parse_mode="Markdown", disableweb=True)
	
	def send_msg(self, text: str, parse_mode=None, disableweb=False):
		"""Sends a Telegram message to the linked user
		
		:param text: Text message
		:type text: str
		:return: None
		"""
		self.bot.send_message(self.user, text, parse_mode=parse_mode, disable_web_page_preview=disableweb)

	def set_auth_code(self, code):
		self.link_key = code
