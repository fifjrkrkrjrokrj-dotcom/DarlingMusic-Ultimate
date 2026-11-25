from pyrogram import Client, errors
from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.types import BotCommand

import config

from ..logging import LOGGER


class Lucky(Client):
    def __init__(self):
        LOGGER(__name__).info(f"Starting Bot...")
        super().__init__(
            name="ClonyMusic",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            in_memory=True,
            workers=16,
            max_concurrent_transmissions=10,
        )

    async def start(self):
        await super().start()
        self.id = self.me.id
        self.name = self.me.first_name + " " + (self.me.last_name or "")
        self.username = self.me.username
        self.mention = self.me.mention

        try:
            await self.send_message(
                chat_id=config.LOGGER_ID,
                text=(
                    f"✨ <b><u>{self.mention} ɪs ɴᴏᴡ ᴏɴʟɪɴᴇ</u></b> ✨\n\n"
                    f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
                    f"┣★ <b>ʙᴏᴛ ɴᴀᴍᴇ :</b> {self.name}\n"
                    f"┣★ <b>ʙᴏᴛ ɪᴅ :</b> <code>{self.id}</code>\n"
                    f"┣★ <b>ᴜsᴇʀɴᴀᴍᴇ :</b> @{self.username}\n"
                    f"┣★ <b>sᴛᴀᴛᴜs :</b> <code>ᴀᴄᴛɪᴠᴇ & sᴘᴇᴇᴅʏ 🚀</code>\n"
                    f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
                    f"💖 <i>ᴛʜᴀɴᴋ ʏᴏᴜ ғᴏʀ ᴅᴇᴘʟᴏʏɪɴɢ {self.name}!</i>"
                ),
            )
        except (errors.ChannelInvalid, errors.PeerIdInvalid):
            LOGGER(__name__).error(
                "Bot has failed to access the log group/channel. Make sure that you have added your bot to your log group/channel."
            )
            exit()
        except Exception as ex:
            LOGGER(__name__).error(
                f"Bot has failed to access the log group/channel.\n  Reason : {type(ex).__name__}."
            )
            exit()

        a = await self.get_chat_member(config.LOGGER_ID, self.id)
        if a.status != ChatMemberStatus.ADMINISTRATOR:
            LOGGER(__name__).error(
                "Please Promote your bot as an admin in your log group/channel."
            )
            exit()

        try:
            await self.set_bot_commands([
                BotCommand("start", "Start the music bot"),
                BotCommand("help", "Get help and commands menu"),
                BotCommand("play", "Play audio stream on voice chat"),
                BotCommand("vplay", "Play video stream on voice chat"),
                BotCommand("myplaylist", "Open and play your saved playlist"),
                BotCommand("pause", "Pause the currently playing stream"),
                BotCommand("resume", "Resume paused stream"),
                BotCommand("skip", "Skip currently playing track"),
                BotCommand("end", "Stop streaming and leave voice chat"),
                BotCommand("ping", "Check bot ping and system stats"),
                BotCommand("settings", "Bot and group settings"),
                BotCommand("reload", "Reload bot and admin cache"),
            ])
        except Exception as e:
            LOGGER(__name__).warning(f"Failed to set bot commands: {e}")

        LOGGER(__name__).info(f"Music Bot Started as {self.name}")

    async def stop(self):
        await super().stop()