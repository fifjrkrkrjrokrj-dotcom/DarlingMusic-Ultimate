from pyrogram import Client, filters
from pyrogram.types import Message

from ClonyMusic.core.call import Lucky
from ClonyMusic.misc import db
from ClonyMusic.utils.vc_watcher import clear_vc_join_msgs, handle_video_chat_invited

welcome = 20
vc_invite = 25
close = 30


@Client.on_message(filters.video_chat_started, group=welcome)
@Client.on_message(filters.video_chat_ended, group=close)
async def video_chat_events(_, message: Message):
    await Lucky.stop_stream_force(message.chat.id)
    try:
        db[message.chat.id] = []
    except Exception:
        pass
    if message.video_chat_ended:
        await clear_vc_join_msgs(message.chat.id)


@Client.on_message(filters.video_chat_members_invited, group=vc_invite)
async def clone_on_vc_invited(client, message: Message):
    await handle_video_chat_invited(client, message)
