import asyncio
import inspect
import os
import random
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls, filters as fl
from pytgcalls.exceptions import CallBusy, NoActiveGroupCall, NotInCallError
from pytgcalls.types import (
    AudioQuality,
    ChatUpdate,
    GroupCallParticipant,
    MediaStream,
    StreamEnded,
    Update,
    VideoQuality,
)

import config
from ClonyMusic import LOGGER, YouTube, app
from ClonyMusic.misc import db
from ClonyMusic.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from ClonyMusic.utils.exceptions import AssistantErr
from ClonyMusic.utils.formatters import check_duration, seconds_to_min, speed_converter
from ClonyMusic.utils.inline.play import stream_markup, telegram_markup
from ClonyMusic.utils.stream.autoclear import auto_clean
from ClonyMusic.utils.thumbnails import get_thumb
from ClonyMusic.utils.vc_watcher import get_chat_bot
from strings import get_string

autoend = {}
counter = {}


def get_random_img(img_list):
    """Return a single image URL from a list or string with a safe fallback."""
    if img_list:
        if isinstance(img_list, list):
            return random.choice(img_list)
        return img_list
    return "https://i.ibb.co/0VKCS20y/stream.jpg"


def _build_stream(
    link: str,
    video: bool = False,
    ffmpeg_parameters: str = None,
) -> MediaStream:
    """Build a high-quality MediaStream for py-tgcalls v2 (ntgcalls)."""
    if video:
        return MediaStream(
            link,
            audio_parameters=AudioQuality.HIGH,
            video_parameters=VideoQuality.HD_720p,
            ffmpeg_parameters=ffmpeg_parameters,
        )
    return MediaStream(
        link,
        audio_parameters=AudioQuality.HIGH,
        video_flags=MediaStream.Flags.IGNORE,
        ffmpeg_parameters=ffmpeg_parameters,
    )


async def _clear_(chat_id):
    queue = db.get(chat_id)
    if queue and isinstance(queue, list):
        for item in queue:
            try:
                m = item.get("mystic")
                if m:
                    await m.delete()
                    item["mystic"] = None
            except Exception:
                pass
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)


async def _pre_download_next(chat_id: int):
    """Pre-download the next queued YouTube track in background for gapless playback."""
    try:
        queue = db.get(chat_id)
        if not queue or len(queue) < 2:
            return
        nxt = queue[1]
        vidid = nxt.get("vidid", "")
        queued = nxt.get("file", "")
        if not vidid or vidid in ("telegram", "soundcloud") or any(
            tag in str(queued) for tag in ("live_", "index_")
        ):
            return
        is_video = str(nxt.get("streamtype")) == "video"
        await YouTube.download(vidid, None, videoid=True, video=is_video)
    except Exception:
        pass


class Call(PyTgCalls):
    def __init__(self):
        self.userbot1 = Client(
            name="LuckyAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.one = PyTgCalls(self.userbot1)
        self.custom_assistants = {}
        self.active_clients = {}

    async def get_active_clients(self, chat_id):
        clients = []
        if chat_id in self.active_clients:
            val = self.active_clients[chat_id]
            if isinstance(val, list):
                clients.extend(val)
            else:
                clients.append(val)

        if not clients:
            try:
                main_ass = await group_assistant(self, chat_id)
                clients.append(main_ass)
            except Exception:
                clients.append(self.one)

        return list(set(clients))

    async def pause_stream(self, chat_id: int, assistant_type=None):
        assistants = await self.get_active_clients(chat_id)
        for assistant in assistants:
            try:
                await assistant.pause(chat_id)
            except Exception:
                pass

    async def resume_stream(self, chat_id: int, assistant_type=None):
        assistants = await self.get_active_clients(chat_id)
        for assistant in assistants:
            try:
                await assistant.resume(chat_id)
            except Exception:
                pass

    async def mute_stream(self, chat_id: int):
        assistants = await self.get_active_clients(chat_id)
        for assistant in assistants:
            try:
                await assistant.mute(chat_id)
            except Exception:
                pass

    async def unmute_stream(self, chat_id: int):
        assistants = await self.get_active_clients(chat_id)
        for assistant in assistants:
            try:
                await assistant.unmute(chat_id)
            except Exception:
                pass

    async def stop_stream(self, chat_id: int, assistant_type=None):
        assistants = await self.get_active_clients(chat_id)
        try:
            await _clear_(chat_id)
        except Exception:
            pass

        for assistant in assistants:
            try:
                await assistant.leave_call(chat_id)
            except Exception:
                pass

        if chat_id in self.active_clients:
            del self.active_clients[chat_id]

    async def stop_stream_force(self, chat_id: int):
        assistants = await self.get_active_clients(chat_id)
        for assistant in assistants:
            try:
                await assistant.leave_call(chat_id)
            except Exception:
                pass

        if chat_id in self.active_clients:
            del self.active_clients[chat_id]

        try:
            await _clear_(chat_id)
        except Exception:
            pass

    async def force_stop_stream(self, chat_id: int):
        return await self.stop_stream_force(chat_id)

    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistants = await self.get_active_clients(chat_id)

        if str(speed) != "1.0":
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            if not os.path.isdir(chatdir):
                os.makedirs(chatdir)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                speed_map = {"0.5": 2.0, "0.75": 1.35, "1.5": 0.68, "2.0": 0.5}
                vs = speed_map.get(str(speed), 1.0)
                proc = await asyncio.create_subprocess_shell(
                    cmd=(
                        f"ffmpeg -i {file_path} "
                        f"-filter:v setpts={vs}*PTS "
                        f"-filter:a atempo={speed} "
                        f"{out}"
                    ),
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
        else:
            out = file_path

        dur = await asyncio.get_event_loop().run_in_executor(None, check_duration, out)
        dur = int(dur)
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)
        stream = _build_stream(
            out,
            video=(playing[0]["streamtype"] == "video"),
            ffmpeg_parameters=f"-ss {played} -to {duration}",
        )
        if str(db[chat_id][0]["file"]) == str(file_path):
            for assistant in assistants:
                try:
                    await assistant.play(chat_id, stream)
                except Exception:
                    pass
        else:
            raise AssistantErr("Umm")
        if str(db[chat_id][0]["file"]) == str(file_path):
            exis = (playing[0]).get("old_dur")
            if not exis:
                db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
                db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]
            db[chat_id][0]["played"] = con_seconds
            db[chat_id][0]["dur"] = duration
            db[chat_id][0]["seconds"] = dur
            db[chat_id][0]["speed_path"] = out
            db[chat_id][0]["speed"] = speed

    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
        assistant_type=None,
    ):
        assistants = await self.get_active_clients(chat_id)
        stream = _build_stream(link, video=bool(video))
        for assistant in assistants:
            try:
                await assistant.play(chat_id, stream)
            except Exception:
                pass

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistants = await self.get_active_clients(chat_id)
        stream = _build_stream(
            file_path,
            video=(mode == "video"),
            ffmpeg_parameters=f"-ss {to_seek} -to {duration}",
        )
        for assistant in assistants:
            try:
                await assistant.play(chat_id, stream)
            except Exception:
                pass

    async def effect_stream(self, chat_id: int, file_path: str, effect: str, mode: str = "audio"):
        """Apply live FFmpeg audio effect (bass, nightcore, 8d, vocal, normal) to active stream."""
        fx_map = {
            "bass": "-af bass=g=10:f=100:w=0.6",
            "nightcore": "-af asetrate=48000*1.25,aresample=48000",
            "8d": "-af apulsator=hz=0.125",
            "vocal": "-af highpass=f=200,lowpass=f=3500,volume=1.35",
            "normal": None,
        }
        filter_arg = fx_map.get(effect.lower())
        played = 0
        if chat_id in db and db[chat_id]:
            played = int(db[chat_id][0].get("played", 0) or 0)

        parts = []
        if played > 0:
            parts.append(f"-ss {played}")
        if filter_arg:
            parts.append(filter_arg)
        ffmpeg_params = " ".join(parts) if parts else None

        assistants = await self.get_active_clients(chat_id)
        stream = _build_stream(
            file_path,
            video=(mode == "video"),
            ffmpeg_parameters=ffmpeg_params,
        )
        for assistant in assistants:
            try:
                await assistant.play(chat_id, stream)
            except Exception:
                try:
                    fallback_stream = _build_stream(
                        file_path,
                        video=(mode == "video"),
                        ffmpeg_parameters=f"-ss {played}" if played > 0 else None,
                    )
                    await assistant.play(chat_id, fallback_stream)
                except Exception:
                    pass

    async def switch_av_stream(self, chat_id: int, playing_item: dict) -> str:
        """Toggle currently playing track between Audio and Video without losing queue."""
        cur_mode = str(playing_item.get("streamtype", "audio"))
        new_mode = "audio" if cur_mode == "video" else "video"
        want_video = new_mode == "video"
        file_path = playing_item.get("file", "")
        vidid = playing_item.get("vidid", "")

        target_path = file_path
        if want_video and vidid and vidid not in ("telegram", "soundcloud"):
            if not str(file_path).endswith(".mp4"):
                dl_path, _ = await YouTube.download(vidid, None, videoid=True, video=True)
                if dl_path:
                    target_path = dl_path
                    playing_item["file"] = dl_path
                else:
                    return ""

        assistants = await self.get_active_clients(chat_id)
        stream = _build_stream(target_path, video=want_video)
        for assistant in assistants:
            try:
                await assistant.play(chat_id, stream)
            except Exception:
                pass
        playing_item["streamtype"] = new_mode
        if want_video:
            await add_active_video_chat(chat_id)
        else:
            await remove_active_video_chat(chat_id)
        return new_mode

    async def stream_call(self, link):
        assistant = await group_assistant(self, config.LOGGER_ID)
        await assistant.play(config.LOGGER_ID, _build_stream(link, video=True))
        await asyncio.sleep(0.2)
        await assistant.leave_call(config.LOGGER_ID)

    def _register_assistant_handlers(self, assistant_client: PyTgCalls):
        @assistant_client.on_update(fl.stream_end())
        async def _on_stream_end(client, update: Update):
            if not isinstance(update, StreamEnded):
                return
            await self.change_stream(client, update.chat_id)

        @assistant_client.on_update(
            fl.chat_update(
                ChatUpdate.Status.KICKED
                | ChatUpdate.Status.LEFT_GROUP
                | ChatUpdate.Status.CLOSED_VOICE_CHAT
            )
        )
        async def _on_chat_update(_, update: Update):
            from ClonyMusic.utils.vc_watcher import clear_vc_join_msgs

            await self.stop_stream(update.chat_id)
            await clear_vc_join_msgs(update.chat_id)

        @assistant_client.on_update(
            fl.call_participant(
                GroupCallParticipant.Action.JOINED
                | GroupCallParticipant.Action.LEFT
                | GroupCallParticipant.Action.KICKED
            )
        )
        async def _on_call_participant(client, update: Update):
            from ClonyMusic.utils.vc_watcher import handle_vc_participant_update

            await handle_vc_participant_update(client, update)

    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
        userbot=None,
    ):
        from ClonyMusic.core.userbot import assistantids
        ub_id = getattr(getattr(userbot, "me", None), "id", None) or getattr(userbot, "id", None)
        if userbot and ub_id not in assistantids:
            if ub_id in self.custom_assistants:
                assistant_to_join = self.custom_assistants[ub_id]
            else:
                assistant_to_join = PyTgCalls(userbot)
                await assistant_to_join.start()
                self._register_assistant_handlers(assistant_to_join)
                self.custom_assistants[ub_id] = assistant_to_join
        else:
            assistant_to_join = await group_assistant(self, chat_id)

        if chat_id not in self.active_clients:
            self.active_clients[chat_id] = []
        if assistant_to_join not in self.active_clients[chat_id]:
            self.active_clients[chat_id].append(assistant_to_join)

        language = await get_lang(chat_id)
        _ = get_string(language)
        stream = _build_stream(link, video=bool(video))

        try:
            await assistant_to_join.play(chat_id, stream)
        except NoActiveGroupCall:
            raise AssistantErr(_["call_8"])
        except CallBusy:
            raise AssistantErr(_["call_9"])
        except Exception as e:
            err_name = type(e).__name__
            if "Already" in err_name:
                raise AssistantErr(_["call_9"])
            raise AssistantErr(_["call_10"])

        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)
        if await is_autoend():
            counter[chat_id] = {}
            try:
                users = len(await assistant_to_join.get_participants(chat_id))
                if users == 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
            except Exception:
                pass
        asyncio.create_task(_pre_download_next(chat_id))

    async def change_stream(self, client, chat_id):
        from ClonyMusic.utils.player_extras import is_247, is_autoplay
        from ClonyMusic.utils.stream.queue import put_queue

        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
                try:
                    old_m = check[0].get("mystic")
                    if old_m:
                        await old_m.delete()
                        check[0]["mystic"] = None
                except Exception:
                    pass
            if popped:
                try:
                    m = popped.get("mystic")
                    if m:
                        await m.delete()
                        popped["mystic"] = None
                except Exception:
                    pass
            await auto_clean(popped)
            if not check and popped and is_autoplay(chat_id):
                last_vid = popped.get("vidid", "")
                last_title = popped.get("title", "")
                if last_vid and last_vid not in ("telegram", "soundcloud"):
                    recs = []
                    try:
                        recs = await YouTube.get_autoplay(last_vid)
                    except Exception:
                        pass
                    if not recs and last_title:
                        try:
                            from py_yt import VideosSearch
                            vs = await VideosSearch(f"{last_title} song", limit=6).next()
                            for item in vs.get("result", []):
                                v_id = item.get("id")
                                if v_id and v_id != last_vid:
                                    recs.append({
                                        "video_id": v_id,
                                        "title": item.get("title", "Related Track"),
                                        "duration": item.get("duration", "3:30"),
                                    })
                        except Exception:
                            pass
                    if recs and isinstance(recs, list):
                        nxt = recs[0]
                        nxt_vid = nxt.get("id") or nxt.get("video_id")
                        nxt_title = nxt.get("title", "Related Track")
                        nxt_dur = nxt.get("duration", "3:30")
                        if isinstance(nxt_dur, (int, float)):
                            from ClonyMusic.utils.formatters import seconds_to_min
                            nxt_dur = seconds_to_min(int(nxt_dur))
                        if nxt_vid:
                            await put_queue(
                                chat_id,
                                popped.get("chat_id", chat_id),
                                f"vid_{nxt_vid}",
                                nxt_title,
                                nxt_dur,
                                "AutoPlay 📻",
                                nxt_vid,
                                popped.get("user_id", 0),
                                "audio",
                            )
                            if chat_id in db and db[chat_id]:
                                db[chat_id][-1]["client"] = popped.get("client") or get_chat_bot(chat_id)
                            check = db.get(chat_id)
            if not check:
                await _clear_(chat_id)
                if is_247(chat_id):
                    return
                if chat_id in self.active_clients:
                    del self.active_clients[chat_id]
                return await client.leave_call(chat_id)
        except Exception:
            try:
                await _clear_(chat_id)
                if is_247(chat_id):
                    return
                if chat_id in self.active_clients:
                    del self.active_clients[chat_id]
                return await client.leave_call(chat_id)
            except Exception:
                return

        queued = check[0]["file"]
        language = await get_lang(chat_id)
        _ = get_string(language)
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        original_chat_id = check[0]["chat_id"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]

        chat_client = check[0].get("client") or get_chat_bot(chat_id) or get_chat_bot(original_chat_id) or app

        try:
            from ClonyMusic.plugins.play.queue import clear_active_queue_msg as clr1
            clr1(chat_id)
        except Exception:
            pass
        try:
            from ClonyMusic.cplugin.queue import clear_active_queue_msg as clr2
            clr2(chat_id)
        except Exception:
            pass

        db[chat_id][0]["played"] = 0
        exis = (check[0]).get("old_dur")
        if exis:
            db[chat_id][0]["dur"] = exis
            db[chat_id][0]["seconds"] = check[0]["old_second"]
            db[chat_id][0]["speed_path"] = None
            db[chat_id][0]["speed"] = 1.0
        video = str(streamtype) == "video"

        if "live_" in queued:
            n, link = await YouTube.video(videoid, True)
            if n == 0:
                try:
                    return await chat_client.send_message(original_chat_id, text=_["call_6"])
                except Exception:
                    return
            try:
                await client.play(chat_id, _build_stream(link, video=video))
            except Exception:
                try:
                    return await chat_client.send_message(original_chat_id, text=_["call_6"])
                except Exception:
                    return
            button = telegram_markup(_, chat_id)
            try:
                run = await chat_client.send_photo(
                    chat_id=original_chat_id,
                    photo=get_random_img(config.STREAM_IMG_URL),
                    caption=_["stream_1"].format(
                        f"https://t.me/{getattr(chat_client, 'username', app.username)}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                    has_spoiler=True,
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            except Exception:
                pass
        elif "vid_" in queued:
            mystic = None
            try:
                mystic = await chat_client.send_message(original_chat_id, _["call_7"])
            except Exception:
                pass
            try:
                file_path, direct = await YouTube.download(
                    videoid, mystic, videoid=True, video=video
                )
            except Exception:
                try:
                    file_path, direct = await YouTube.download(
                        videoid, mystic, videoid=True, video=video
                    )
                except Exception:
                    if mystic:
                        try:
                            await mystic.edit_text(_["call_6"], disable_web_page_preview=True)
                        except Exception:
                            pass
                    return
            try:
                await client.play(chat_id, _build_stream(file_path, video=video))
            except Exception:
                try:
                    return await chat_client.send_message(original_chat_id, text=_["call_6"])
                except Exception:
                    return
            if chat_client != app:
                from ClonyMusic.cplugin.utils.cthumbnail import get_thumb as c_get_thumb
                try:
                    img = await c_get_thumb(videoid, client=chat_client, title=title, duration=check[0].get("dur")) or get_random_img(config.PLAYLIST_IMG_URL)
                except Exception:
                    img = get_random_img(config.PLAYLIST_IMG_URL)
            else:
                try:
                    img = await get_thumb(videoid, title=title, duration=check[0].get("dur")) or get_random_img(config.PLAYLIST_IMG_URL)
                except Exception:
                    img = get_random_img(config.PLAYLIST_IMG_URL)
            button = stream_markup(_, chat_id)
            if mystic:
                try:
                    await mystic.delete()
                except Exception:
                    pass
            try:
                run = await chat_client.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{getattr(chat_client, 'username', app.username)}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                    has_spoiler=True,
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
            except Exception:
                pass
        elif "index_" in queued:
            try:
                await client.play(chat_id, _build_stream(videoid, video=video))
            except Exception:
                return await chat_client.send_message(original_chat_id, text=_["call_6"])
            button = telegram_markup(_, chat_id)
            run = await chat_client.send_photo(
                chat_id=original_chat_id,
                photo=get_random_img(config.STREAM_IMG_URL),
                caption=_["stream_2"].format(user),
                reply_markup=InlineKeyboardMarkup(button),
                has_spoiler=True,
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
        else:
            try:
                await client.play(chat_id, _build_stream(queued, video=video))
            except Exception:
                return await chat_client.send_message(original_chat_id, text=_["call_6"])
            if videoid == "telegram":
                button = telegram_markup(_, chat_id)
                tg_img = (
                    get_random_img(config.TELEGRAM_AUDIO_URL)
                    if str(streamtype) == "audio"
                    else get_random_img(config.TELEGRAM_VIDEO_URL)
                )
                run = await chat_client.send_photo(
                    chat_id=original_chat_id,
                    photo=tg_img,
                    caption=_["stream_1"].format(
                        config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                    has_spoiler=True,
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            elif videoid == "soundcloud":
                button = telegram_markup(_, chat_id)
                run = await chat_client.send_photo(
                    chat_id=original_chat_id,
                    photo=get_random_img(config.SOUNCLOUD_IMG_URL),
                    caption=_["stream_1"].format(
                        config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                    has_spoiler=True,
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            else:
                if chat_client != app:
                    from ClonyMusic.cplugin.utils.cthumbnail import get_thumb as c_get_thumb
                    img = await c_get_thumb(videoid, client=chat_client) or get_random_img(config.PLAYLIST_IMG_URL)
                else:
                    img = await get_thumb(videoid) or get_random_img(config.PLAYLIST_IMG_URL)
                button = stream_markup(_, chat_id)
                run = await chat_client.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                    has_spoiler=True,
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
        asyncio.create_task(_pre_download_next(chat_id))

    async def ping(self):
        pings = []
        if config.STRING1:
            p = self.one.ping
            if inspect.isawaitable(p):
                p = await p
            pings.append(p)
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    async def start(self):
        LOGGER(__name__).info("Starting PyTgCalls v2 (ntgcalls) Client...")
        if config.STRING1:
            await self.one.start()

    async def decorators(self):
        self._register_assistant_handlers(self.one)
        asyncio.create_task(self._periodic_maintenance())

    async def _periodic_maintenance(self):
        """Auto-leave empty VCs and clean old temp files in downloads/playback."""
        import time

        last_disk_clean = 0.0
        empty_since = {}
        while True:
            await asyncio.sleep(45)
            now = time.time()

            # 1. Auto-leave empty VCs (only assistant present > 90s, unless 24/7 mode is ON)
            from ClonyMusic.utils.player_extras import is_247

            for chat_id in list(self.active_clients.keys()):
                if is_247(chat_id):
                    empty_since.pop(chat_id, None)
                    continue
                try:
                    clients = await self.get_active_clients(chat_id)
                    if not clients:
                        continue
                    parts = await clients[0].get_participants(chat_id)
                    if len(parts) <= 1:
                        first_seen = empty_since.setdefault(chat_id, now)
                        if now - first_seen >= 90:
                            empty_since.pop(chat_id, None)
                            await self.stop_stream(chat_id)
                    else:
                        empty_since.pop(chat_id, None)
                except Exception:
                    empty_since.pop(chat_id, None)

            # 2. Clean temp files older than 2 hours once every 30 minutes
            if now - last_disk_clean >= 1800:
                last_disk_clean = now
                for folder in ("downloads", "playback"):
                    if not os.path.isdir(folder):
                        continue
                    for root, _, files in os.walk(folder):
                        for fn in files:
                            fp = os.path.join(root, fn)
                            try:
                                if now - os.path.getmtime(fp) > 7200:
                                    os.remove(fp)
                            except Exception:
                                pass


Lucky = Call()
