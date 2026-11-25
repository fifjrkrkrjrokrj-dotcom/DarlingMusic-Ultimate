from pyrogram import filters
from pyrogram.types import Message

from ClonyMusic import app
from ClonyMusic.core.call import Lucky
from ClonyMusic.utils.vc_watcher import clear_vc_join_msgs, handle_video_chat_invited

welcome = 20
vc_invite = 25
close = 30


@app.on_message(filters.video_chat_started, group=welcome)
@app.on_message(filters.video_chat_ended, group=close)
async def welcome_vc(_, message: Message):
    await Lucky.stop_stream_force(message.chat.id)
    if message.video_chat_ended:
        await clear_vc_join_msgs(message.chat.id)


@app.on_message(filters.video_chat_members_invited, group=vc_invite)
async def on_vc_invited(client, message: Message):
    await handle_video_chat_invited(client, message)
