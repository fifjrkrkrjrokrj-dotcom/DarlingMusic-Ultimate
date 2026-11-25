import asyncio
import os
import re
from typing import Union
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from py_yt import VideosSearch, Playlist
import aiohttp
import aiofiles

API_URL = os.environ.get("SHRUTI_API_URL", "https://api.shrutibots.in")

API_KEY = os.environ.get("SHRUTI_API_KEY", "ShrutiBotszkdLh2Fkn1TVwS1T3bnN")  ## Get This API KEY FROM https://dash.shrutibots.in                                                    

DOWNLOAD_DIR = "downloads"

_session = None

async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(limit=100, keepalive_timeout=60, enable_cleanup_closed=True)
        _session = aiohttp.ClientSession(connector=connector)
    return _session


def _env_dir(name: str) -> str:
    value = os.environ.get(name, "").strip()
    return os.path.abspath(os.path.expanduser(value)) if value else ""


AUDIO_DOWNLOAD_PATH = _env_dir("AUDIO_DOWNLOAD_PATH")
VIDEO_DOWNLOAD_PATH = _env_dir("VIDEO_DOWNLOAD_PATH")
AUDIO_EXTENSIONS = ("webm", "m4a", "mp3", "ogg")
VIDEO_EXTENSIONS = ("mp4", "mkv", "webm")


def is_external_path(path) -> bool:
    if not path:
        return False
    full = os.path.abspath(str(path))
    for base in (AUDIO_DOWNLOAD_PATH, VIDEO_DOWNLOAD_PATH):
        if base and full.startswith(base + os.sep):
            return True
    return False


def _find_external(directory: str, video_id: str, extensions, resp=None):
    names = []
    if resp is not None:
        disposition = resp.content_disposition
        if disposition and disposition.filename:
            name = os.path.basename(disposition.filename)
            if name.startswith(video_id + "."):
                names.append(name)
    names.extend(f"{video_id}.{ext}" for ext in extensions)
    for name in names:
        path = os.path.join(directory, name)
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            return path
    return None


def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60 ** i for i, x in enumerate(reversed(stringt.split(":"))))


async def _download_media(link: str, kind: str, timeout: int) -> str:
    video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    if not video_id or len(video_id) < 3:
        return None

    is_audio = kind == "audio"
    external = AUDIO_DOWNLOAD_PATH if is_audio else VIDEO_DOWNLOAD_PATH
    extensions = AUDIO_EXTENSIONS if is_audio else VIDEO_EXTENSIONS

    if external:
        found = _find_external(external, video_id, extensions)
        if found:
            return found

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{'mp3' if is_audio else 'mp4'}")
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return file_path

    try:
        session = await get_session()
        async with session.get(
            f"{API_URL}/download",
            params={"url": video_id, "type": kind, "api_key": API_KEY},
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            if resp.status == 200:
                if external:
                    found = _find_external(external, video_id, extensions, resp)
                    if found:
                        return found
                async with aiofiles.open(file_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(262144):
                        await f.write(chunk)
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    return file_path
    except Exception:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    # Fallback to yt-dlp if primary API failed or timed out
    def _ytdlp_fallback():
        out_tmpl = os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s")
        opts = {
            "format": "bestaudio/best" if is_audio else "bestvideo[height<=720]+bestaudio/best",
            "outtmpl": out_tmpl,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "geo_bypass": True,
        }
        if is_audio:
            opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ]
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _ytdlp_fallback)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return file_path
        for ext in extensions:
            alt = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")
            if os.path.exists(alt) and os.path.getsize(alt) > 0:
                return alt
    except Exception:
        pass
    return None


async def download_song(link: str) -> str:
    return await _download_media(link, "audio", 300)


async def download_video(link: str) -> str:
    return await _download_media(link, "video", 600)


AUTOPLAY_REQUEST_TIMEOUT = 20
AUTOPLAY_MAX_RETRIES = 3
AUTOPLAY_RETRY_DELAY = 1
AUTOPLAY_RETRYABLE_STATUS = (408, 425, 429, 500, 502, 503, 504)


async def get_autoplay(
    video_id: str,
    timeout: int = AUTOPLAY_REQUEST_TIMEOUT,
    retries: int = AUTOPLAY_MAX_RETRIES,
    seed_id: str = None,
) -> list:
    video_id = video_id.split("v=")[-1].split("&")[0] if "v=" in video_id else video_id
    if not video_id or len(video_id) < 3:
        return []

    params = {"video_id": video_id, "api_key": API_KEY}
    if seed_id and seed_id != video_id:
        params["seed_id"] = seed_id

    attempt = 0
    while attempt < retries:
        attempt += 1
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{API_URL}/autoplay",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        tracks = data.get("tracks", [])
                        if tracks:
                            return tracks
                    if resp.status in AUTOPLAY_RETRYABLE_STATUS and attempt < retries:
                        await asyncio.sleep(AUTOPLAY_RETRY_DELAY)
                        continue
        except (asyncio.TimeoutError, aiohttp.ClientError):
            if attempt < retries:
                await asyncio.sleep(AUTOPLAY_RETRY_DELAY)
                continue
        except Exception:
            pass

    # Fallback to search query for related songs if API returned empty
    try:
        from py_yt import VideosSearch
        vs = await VideosSearch(f"{video_id} related music", limit=8).next()
        fallback_tracks = []
        for item in vs.get("result", []):
            v_id = item.get("id")
            if v_id and v_id != video_id:
                fallback_tracks.append({
                    "video_id": v_id,
                    "title": item.get("title", "Related Track"),
                    "duration": item.get("duration", "3:30"),
                })
        if fallback_tracks:
            return fallback_tracks
    except Exception:
        pass

    return []


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def get_autoplay(self, video_id: str, seed_id: str = None) -> list:
        return await get_autoplay(video_id=video_id, seed_id=seed_id)

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
            return 0, "Video download failed"
        except Exception as e:
            return 0, f"Video download error: {e}"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            plist = await Playlist.get(link)
        except Exception:
            return []
        videos = plist.get("videos") or []
        ids = []
        for data in videos[:limit]:
            if not data:
                continue
            vid = data.get("id")
            if not vid:
                continue
            ids.append(vid)
        return ids

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        cache_key = f"{videoid}_{link}"
        if hasattr(self, "_track_cache") and cache_key in self._track_cache:
            return self._track_cache[cache_key]
        if not hasattr(self, "_track_cache"):
            self._track_cache = {}

        results = VideosSearch(link, limit=1)
        res = await results.next()
        result = res["result"][0]
        title = result["title"]
        duration_min = result["duration"]
        vidid = result["id"]
        yturl = result["link"]
        thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        self._track_cache[cache_key] = (track_details, vidid)
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    if "dash" not in str(format["format"]).lower():
                        formats_available.append(
                            {
                                "format": format["format"],
                                "filesize": format.get("filesize"),
                                "format_id": format["format_id"],
                                "ext": format["ext"],
                                "format_note": format["format_note"],
                                "yturl": link,
                            }
                        )
                except Exception:
                    continue
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link
        try:
            if video:
                downloaded_file = await download_video(link)
            else:
                downloaded_file = await download_song(link)
            if downloaded_file:
                return downloaded_file, True
            return None, False
        except Exception:
            return None, False


YouTube = YouTubeAPI()
