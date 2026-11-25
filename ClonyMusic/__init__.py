from ClonyMusic.core.bot import Lucky
from ClonyMusic.core.dir import dirr
from ClonyMusic.core.git import git
from ClonyMusic.core.userbot import Userbot
from ClonyMusic.misc import dbb, heroku
from pyrogram import Client
from .logging import LOGGER

dirr()
git()
dbb()
heroku()

app = Lucky()
userbot = Userbot()

from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()
