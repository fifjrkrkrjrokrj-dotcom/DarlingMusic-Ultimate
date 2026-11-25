import os
import aiohttp
import aiofiles
import asyncio
import traceback
import random
from pathlib import Path

from PIL import (
    Image,
    ImageDraw,
    ImageFilter,
    ImageFont,
    ImageEnhance
)
from py_yt import VideosSearch

import config

# =====================================
# CACHE
# =====================================

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

# =====================================
# 4K SIZE
# =====================================

CANVAS_W = 1280
CANVAS_H = 720

# =====================================
# FONTS
# =====================================

FONT_BOLD = "ClonyMusic/assets/font3.ttf" if os.path.exists("ClonyMusic/assets/font3.ttf") else "ShrutiMusic/assets/font3.ttf"
FONT_REGULAR = "ClonyMusic/assets/font2.ttf" if os.path.exists("ClonyMusic/assets/font2.ttf") else "ShrutiMusic/assets/font2.ttf"

try:
    from unidecode import unidecode
except ImportError:
    def unidecode(s):
        return s

_SMALLCAPS_MAP = str.maketrans(
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
)


def clean_bot_name(name):
    try:
        raw = str(name or "DarlingMusic").translate(_SMALLCAPS_MAP)
        cleaned = unidecode(raw).strip()
        cleaned = "".join(c for c in cleaned if 32 <= ord(c) <= 126)
        cleaned = " ".join(cleaned.split())
        if len(cleaned) > 16:
            cleaned = cleaned[:16].rstrip()
        return cleaned or "MusicBot"
    except Exception:
        return "MusicBot"

_cthumb_session = None

async def get_cthumb_session():
    global _cthumb_session
    if _cthumb_session is None or _cthumb_session.closed:
        _cthumb_session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=50, keepalive_timeout=60))
    return _cthumb_session

# =====================================
# THUMB GENERATOR (CLONE)
# =====================================

async def gen_thumb(videoid: str, user_id=None, client=None, title: str = None, duration: str = None, thumburl: str = None, bot_name: str = None):
    try:
        bot_id = 0
        current_bot_name = clean_bot_name(bot_name) if bot_name else clean_bot_name(getattr(config, "BOT_NAME", None) or "DarlingMusic")
        if client:
            try:
                me = await client.get_me()
                bot_id = me.id
                if not bot_name and getattr(me, "first_name", None):
                    current_bot_name = clean_bot_name(me.first_name)
            except Exception:
                pass

        output = CACHE_DIR / f"{videoid}_{bot_id}_final.png"
        if os.path.exists(output):
            return str(output)

        if not thumburl:
            thumburl = f"https://img.youtube.com/vi/{videoid}/hqdefault.jpg"
        if not duration:
            duration = "3:20"
        if not title:
            title = current_bot_name

        thumb_path = CACHE_DIR / f"{videoid}_{bot_id}.jpg"
        if not os.path.exists(thumb_path):
            session = await get_cthumb_session()
            try:
                async with session.get(thumburl) as resp:
                    if resp.status == 200:
                        async with aiofiles.open(thumb_path, "wb") as f:
                            await f.write(await resp.read())
                    else:
                        fallback_url = f"https://img.youtube.com/vi/{videoid}/hqdefault.jpg"
                        async with session.get(fallback_url) as resp2:
                            if resp2.status == 200:
                                async with aiofiles.open(thumb_path, "wb") as f:
                                    await f.write(await resp2.read())
            except Exception:
                fallback_url = f"https://img.youtube.com/vi/{videoid}/hqdefault.jpg"
                try:
                    async with session.get(fallback_url) as resp2:
                        if resp2.status == 200:
                            async with aiofiles.open(thumb_path, "wb") as f:
                                await f.write(await resp2.read())
                except Exception:
                    pass

        if not os.path.exists(thumb_path):
            if isinstance(config.YOUTUBE_IMG_URL, list):
                return random.choice(config.YOUTUBE_IMG_URL)
            return config.YOUTUBE_IMG_URL

        def _draw_thumb():
            # Open the base downloaded youtube thumbnail
            base = Image.open(thumb_path).convert("RGB")
            
            # Open our template background image if available, else blurred background
            bg_path = None
            for p in ["ClonyMusic/assets/elina_thumb_bg.jpg", "ShrutiMusic/assets/elina_thumb_bg.jpg", "assets/elina_thumb_bg.jpg"]:
                if os.path.exists(p):
                    bg_path = p
                    break

            hue_shift = random.randint(0, 255)
            if bg_path:
                bg_base = Image.open(bg_path).convert("RGBA")
                hsv = bg_base.convert("HSV")
                h_band, s_band, v_band = hsv.split()
                h_band = h_band.point(lambda p: (p + hue_shift) % 256)
                bg = Image.merge("HSV", (h_band, s_band, v_band)).convert("RGBA")
            else:
                bg_base = base.resize((CANVAS_W, CANVAS_H))
                bg_base = bg_base.filter(ImageFilter.GaussianBlur(25))
                bg_base = ImageEnhance.Brightness(bg_base).enhance(0.25).convert("RGBA")
                hsv = bg_base.convert("HSV")
                h_band, s_band, v_band = hsv.split()
                h_band = h_band.point(lambda p: (p + hue_shift) % 256)
                bg = Image.merge("HSV", (h_band, s_band, v_band)).convert("RGBA")
            
            canvas = bg.copy()
            draw = ImageDraw.Draw(canvas)
            
            # Calculate theme color matching the shifted hue
            import colorsys
            orig_r, orig_g, orig_b = 236 / 255.0, 40 / 255.0, 112 / 255.0
            orig_h, orig_s, orig_v = colorsys.rgb_to_hsv(orig_r, orig_g, orig_b)
            new_h = (orig_h + (hue_shift / 256.0)) % 1.0
            new_r, new_g, new_b = colorsys.hsv_to_rgb(new_h, orig_s, orig_v)
            theme_color = (int(new_r * 255), int(new_g * 255), int(new_b * 255), 255)
            
            # Load fonts
            try:
                title_font = ImageFont.truetype(FONT_BOLD, 38)
                subtitle_font = ImageFont.truetype(FONT_REGULAR, 20)
                player_title_font = ImageFont.truetype(FONT_BOLD, 18)
                player_sub_font = ImageFont.truetype(FONT_REGULAR, 13)
                small_font = ImageFont.truetype(FONT_REGULAR, 16)
                logo_title_font = ImageFont.truetype(FONT_BOLD, 24)
                logo_sub_font = ImageFont.truetype(FONT_REGULAR, 12)
            except Exception:
                title_font = ImageFont.load_default()
                subtitle_font = ImageFont.load_default()
                player_title_font = ImageFont.load_default()
                player_sub_font = ImageFont.load_default()
                small_font = ImageFont.load_default()
                logo_title_font = ImageFont.load_default()
                logo_sub_font = ImageFont.load_default()
                
            # Helper to get text width
            def get_text_width(text, font):
                try:
                    return draw.textlength(text, font=font)
                except AttributeError:
                    try:
                        return draw.textsize(text, font=font)[0]
                    except Exception:
                        return len(text) * 12

            # Draw the branding dynamically on the top right
            icon_x, icon_y = 1000, 30
            # Circle
            draw.ellipse((icon_x, icon_y, icon_x + 50, icon_y + 50), fill=theme_color)
            # Music note lines inside circle
            draw.ellipse((icon_x + 12, icon_y + 25, icon_x + 24, icon_y + 37), fill=(0, 0, 0, 255))
            draw.ellipse((icon_x + 26, icon_y + 22, icon_x + 38, icon_y + 34), fill=(0, 0, 0, 255))
            draw.line([(icon_x + 24, icon_y + 12), (icon_x + 24, icon_y + 30)], fill=(0, 0, 0, 255), width=3)
            draw.line([(icon_x + 38, icon_y + 9), (icon_x + 38, icon_y + 27)], fill=(0, 0, 0, 255), width=3)
            draw.line([(icon_x + 24, icon_y + 12), (icon_x + 38, icon_y + 9)], fill=(0, 0, 0, 255), width=4)
            # Text
            draw.text((1065, 30), current_bot_name, font=logo_title_font, fill="white")
            draw.text((1065, 58), "FEEL THE MUSIC", font=logo_sub_font, fill=theme_color)

            # 1. Overlay resized and rounded YouTube thumbnail in the center
            # Center thumbnail size: 688 x 387 (16:9 ratio)
            thumb_w, thumb_h = 688, 387
            thumb = base.resize((thumb_w, thumb_h))
            
            # Create rounded corners mask
            radius = 24
            mask = Image.new('L', (thumb_w, thumb_h), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle((0, 0, thumb_w, thumb_h), radius=radius, fill=255)
            
            # Paste the thumbnail onto canvas using mask
            thumb_x = (CANVAS_W - thumb_w) // 2 # 296
            thumb_y = 60
            canvas.paste(thumb, (thumb_x, thumb_y), mask)
            
            # Draw themed glowing rounded border around the thumbnail
            draw.rounded_rectangle(
                (thumb_x - 3, thumb_y - 3, thumb_x + thumb_w + 3, thumb_y + thumb_h + 3),
                radius=radius + 3,
                outline=theme_color,
                width=4
            )
            
            # 2. Draw Title & Subtitle (below the card, centered)
            clean_title = title.title()
            if len(clean_title) > 36:
                clean_title = clean_title[:33] + "..."
                
            title_w = get_text_width(clean_title, font=title_font)
            title_x = (CANVAS_W - title_w) // 2
            title_y = 465
            draw.text((title_x, title_y), clean_title, font=title_font, fill="white")
            
            # Subtitle
            channel = "YOUTUBE"
            subtitle_text = f"{channel} • HD AUDIO"
            if len(subtitle_text) > 40:
                subtitle_text = subtitle_text[:37] + "..."
                
            sub_w = get_text_width(subtitle_text, font=subtitle_font)
            sub_x = (CANVAS_W - sub_w) // 2
            sub_y = 515
            draw.text((sub_x, sub_y), subtitle_text, font=subtitle_font, fill=theme_color)
            
            # 3. Draw player bar contents (bottom overlay)
            player_title = clean_title
            if len(player_title) > 16:
                player_title = player_title[:13] + "..."
            draw.text((315, 575), player_title, font=player_title_font, fill="white")
            draw.text((315, 603), current_bot_name, font=player_sub_font, fill=(180, 180, 180))
            
            # Progress bar lines
            bar_start_x = 490
            bar_end_x = 990
            bar_y = 598
            # Gray background line
            draw.line([(bar_start_x, bar_y), (bar_end_x, bar_y)], fill=(80, 80, 80), width=4)
            # Active themed progress line (random progress, e.g. 35%)
            progress_pct = random.uniform(0.25, 0.55)
            active_end_x = int(bar_start_x + (bar_end_x - bar_start_x) * progress_pct)
            draw.line([(bar_start_x, bar_y), (active_end_x, bar_y)], fill=theme_color, width=5)
            # Handle dot
            draw.ellipse((active_end_x - 6, bar_y - 6, active_end_x + 6, bar_y + 6), fill="white")
            
            # Duration texts
            draw.text((bar_start_x, 615), "00:00", font=small_font, fill=(180, 180, 180))
            draw.text((bar_end_x - 45, 615), duration, font=small_font, fill=(180, 180, 180))
            
            # Dynamic Equalizer lines
            eq_start_x = 1025
            for i in range(5):
                h = random.randint(10, 30)
                line_x = eq_start_x + i * 8
                draw.line([(line_x, bar_y - h // 2), (line_x, bar_y + h // 2)], fill=theme_color, width=3)
                
            # Save the final image
            canvas.save(output, format="PNG", quality=95)
            try:
                os.remove(thumb_path)
            except Exception:
                pass

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _draw_thumb)

        return str(output)

    except Exception as e:
        print(f"[THUMB ERROR] {e}")
        traceback.print_exc()
        if isinstance(config.YOUTUBE_IMG_URL, list):
            return random.choice(config.YOUTUBE_IMG_URL)
        return config.YOUTUBE_IMG_URL

async def get_thumb(videoid: str, user_id=None, client=None, title: str = None, duration: str = None, thumburl: str = None, bot_name: str = None):
    return await gen_thumb(videoid, user_id=user_id, client=client, title=title, duration=duration, thumburl=thumburl, bot_name=bot_name)
