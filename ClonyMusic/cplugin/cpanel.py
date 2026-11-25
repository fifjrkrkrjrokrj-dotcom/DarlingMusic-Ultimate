import asyncio
import time
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, Message

import config
from ClonyMusic import LOGGER
from ClonyMusic.core.call import Lucky
from ClonyMusic.misc import _boot_, db
from ClonyMusic.utils.button_style import ButtonStyle, get_apply_to_clones, get_button_style, sc_button as InlineKeyboardButton
from ClonyMusic.utils.database import (
    clonebotdb,
    get_active_chats,
    get_served_chats_clone,
    get_served_users_clone,
)
from ClonyMusic.utils.database.clonedb import (
    get_cloned_support_channel,
    get_cloned_support_chat,
    get_owner_id_from_db,
)
from ClonyMusic.utils.feature_flags import FEATURE_LABELS, get_all_features
from ClonyMusic.utils.formatters import get_readable_time

_CPANEL_STATE = {}
_C_BC_RUNNING = {}


def _is_fwd(msg: Message) -> bool:
    return bool(
        getattr(msg, "forward_date", None)
        or getattr(msg, "forward_origin", None)
        or getattr(msg, "forward_from", None)
        or getattr(msg, "forward_from_chat", None)
    )


async def _is_clone_owner(bot_id: int, user_id: int) -> bool:
    if not user_id:
        return False
    if config.OWNER_ID and user_id == int(config.OWNER_ID):
        return True
    try:
        owner = await get_owner_id_from_db(bot_id)
        return owner is not None and int(owner) == int(user_id)
    except Exception:
        return False


def _cpanel_home_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Broadcast", callback_data="cp_bc_menu", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("Clone Stats", callback_data="cp_stats", style=ButtonStyle.SUCCESS),
            ],
            [
                InlineKeyboardButton("Active VCs", callback_data="cp_vcs", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("Button Style", callback_data="cp_style", style=ButtonStyle.SUCCESS),
            ],
            [
                InlineKeyboardButton("Support Links", callback_data="cp_links", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("Start Editor", callback_data="cp_start_menu", style=ButtonStyle.PRIMARY),
            ],
            [
                InlineKeyboardButton("Feature Status", callback_data="cp_feats"),
                InlineKeyboardButton("All Commands", callback_data="cp_cmds"),
            ],
            [
                InlineKeyboardButton("Delete My Clone", callback_data="cp_del_ask", style=ButtonStyle.DANGER),
                InlineKeyboardButton("Close", callback_data="cp_close", style=ButtonStyle.DANGER),
            ],
        ]
    )


def _cp_bc_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Only in DM", callback_data="cp_bc:dm", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("Only in Groups", callback_data="cp_bc:grp", style=ButtonStyle.PRIMARY),
            ],
            [
                InlineKeyboardButton("Groups + DM", callback_data="cp_bc:all", style=ButtonStyle.SUCCESS),
                InlineKeyboardButton("Groups + Pin", callback_data="cp_bc:grppin", style=ButtonStyle.SUCCESS),
            ],
            [
                InlineKeyboardButton("Groups + DM + Pin", callback_data="cp_bc:allpin", style=ButtonStyle.DANGER),
            ],
            [
                InlineKeyboardButton("Back", callback_data="cp_home"),
            ],
        ]
    )


async def _cpanel_home_text(client: Client) -> str:
    me = await client.get_me()
    uptime = get_readable_time(int(time.time() - _boot_))
    chats = len(await get_served_chats_clone(me.id))
    users = len(await get_served_users_clone(me.id))
    return (
        f"<blockquote><b><u>{me.first_name} — Clone Control Panel</u></b></blockquote>\n\n"
        f"• <b>Bot:</b> @{me.username} (<code>{me.id}</code>)\n"
        f"• <b>Groups:</b> <code>{chats}</code> | <b>Users:</b> <code>{users}</code>\n"
        f"• <b>Uptime:</b> <code>{uptime}</code>\n\n"
        "<i>Select an option below to manage your cloned bot:</i>"
    )


@Client.on_message(filters.command(["cpanel", "panel", "clonepanel"], prefixes=["/", "!", "%", ",", "", ".", "@", "#"]) & filters.private)
async def cpanel_command(client: Client, message: Message):
    me = await client.get_me()
    if not message.from_user or not await _is_clone_owner(me.id, message.from_user.id):
        return await message.reply_text("<b>Access Denied:</b> Only this cloned bot's owner can open `/cpanel`.")
    _CPANEL_STATE.pop((me.id, message.from_user.id), None)
    await message.reply_text(await _cpanel_home_text(client), reply_markup=_cpanel_home_markup())


@Client.on_callback_query(filters.regex(r"^cp_"))
async def cpanel_callbacks(client: Client, cq: CallbackQuery):
    try:
        return await _dispatch_cpanel_callbacks(client, cq)
    except MessageNotModified:
        pass
    except Exception as e:
        LOGGER(__name__).error(f"cpanel_callbacks error ({cq.data}): {e}")
        try:
            await cq.answer(f"Panel error: {type(e).__name__}", show_alert=True)
        except Exception:
            pass


async def _dispatch_cpanel_callbacks(client: Client, cq: CallbackQuery):
    me = await client.get_me()
    uid = cq.from_user.id if cq.from_user else 0
    if not await _is_clone_owner(me.id, uid):
        return await cq.answer("Only this Clone Bot's Owner can use /cpanel.", show_alert=True)

    data = cq.data
    if data == "cp_close":
        _CPANEL_STATE.pop((me.id, uid), None)
        return await cq.message.delete()

    if data == "cp_home":
        _CPANEL_STATE.pop((me.id, uid), None)
        return await cq.edit_message_text(await _cpanel_home_text(client), reply_markup=_cpanel_home_markup())

    if data == "cp_bc_menu":
        return await cq.edit_message_text(
            "<blockquote><b><u>Clone Broadcast Manager</u></b></blockquote>\n\n"
            "Choose your broadcast target:\n"
            "• <i>Forwarded messages preserve the forward tag.</i>\n"
            "• <i>Direct messages are delivered as clean copies.</i>",
            reply_markup=_cp_bc_markup(),
        )

    if data == "cp_stop_bc":
        _C_BC_RUNNING[me.id] = False
        return await cq.answer("Stopping broadcast...", show_alert=True)

    if data.startswith("cp_bc:"):
        mode = data.split(":", 1)[1]
        if _C_BC_RUNNING.get(me.id):
            return await cq.answer("Broadcast already running!", show_alert=True)
        _CPANEL_STATE[(me.id, uid)] = {"action": "broadcast", "mode": mode}
        return await cq.edit_message_text(
            f"<b>Send Broadcast Message (<code>{mode.upper()}</code>)</b>\n\n"
            "Send or forward the message you want to broadcast.\n"
            "<i>Send</i> `/cancel` <i>to abort.</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="cp_home", style=ButtonStyle.DANGER)]]),
        )

    if data == "cp_stats":
        chats = len(await get_served_chats_clone(me.id))
        users = len(await get_served_users_clone(me.id))
        active = len(await get_active_chats())
        uptime = get_readable_time(int(time.time() - _boot_))
        return await cq.edit_message_text(
            f"<blockquote><b><u>{me.first_name} — Live Statistics</u></b></blockquote>\n\n"
            f"• <b>Served Groups:</b> <code>{chats}</code>\n"
            f"• <b>Served DM Users:</b> <code>{users}</code>\n"
            f"• <b>Active Voice Chats:</b> <code>{active}</code>\n"
            f"• <b>Uptime:</b> <code>{uptime}</code>",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("Refresh", callback_data="cp_stats", style=ButtonStyle.SUCCESS)],
                    [InlineKeyboardButton("Back", callback_data="cp_home")],
                ]
            ),
        )

    if data == "cp_vcs":
        active = await get_active_chats()
        if not active:
            return await cq.edit_message_text(
                "<blockquote><b><u>Active Voice Chats</u></b></blockquote>\n\n<i>No active voice chats right now.</i>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="cp_home")]]),
            )
        rows = []
        lines = ["<blockquote><b><u>Active Voice Chats</u></b></blockquote>\n"]
        for cid in list(active)[:10]:
            q = db.get(cid)
            title = q[0]["title"][:28] if q else "Unknown"
            lines.append(f"• <code>{cid}</code> — {title}")
            rows.append([InlineKeyboardButton(f"Stop {cid}", callback_data=f"cp_stopvc:{cid}", style=ButtonStyle.DANGER)])
        rows.append([InlineKeyboardButton("Back", callback_data="cp_home")])
        return await cq.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))

    if data.startswith("cp_stopvc:"):
        cid = int(data.split(":", 1)[1])
        await Lucky.stop_stream(cid)
        await cq.answer(f"Stopped VC in {cid}", show_alert=True)
        return await cq.edit_message_text(await _cpanel_home_text(client), reply_markup=_cpanel_home_markup())

    if data == "cp_style":
        style = get_button_style().upper()
        c_on = "ON" if get_apply_to_clones() else "OFF"
        return await cq.edit_message_text(
            f"<blockquote><b><u>Button Styling Status</u></b></blockquote>\n\n"
            f"• <b>Global Style:</b> <code>{style}</code>\n"
            f"• <b>Apply to Cloned Bots:</b> <code>{c_on}</code>\n\n"
            "<i>Managed globally by the Main Bot Owner in /admin.</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="cp_home")]]),
        )

    if data == "cp_feats":
        flags = get_all_features()
        lines = ["<blockquote><b><u>Active Features Status</u></b></blockquote>\n"]
        for k, label in FEATURE_LABELS.items():
            lines.append(f"• <b>{label}:</b> <code>{'ON' if flags.get(k, True) else 'OFF'}</code>")
        lines.append("\n<i>Disabled features are automatically hidden from the player.</i>")
        return await cq.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="cp_home")]]),
        )

    if data == "cp_links":
        schat = await get_cloned_support_chat(me.id) or config.SUPPORT_CHAT
        schan = await get_cloned_support_channel(me.id) or config.SUPPORT_CHANNEL
        return await cq.edit_message_text(
            "<blockquote><b><u>Support Links</u></b></blockquote>\n\n"
            f"• <b>Support Group:</b> {schat}\n"
            f"• <b>Support Channel:</b> {schan}\n\n"
            "<i>Update via:</i> <code>/setchat link</code> | <code>/setchannel link</code>",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="cp_home")]]),
        )

    if data == "cp_start_menu":
        doc = await clonebotdb.find_one({"bot_id": me.id}) or {}
        has_img = "Custom Set" if doc.get("start_image") else "Default"
        has_cap = "Custom Set" if doc.get("start_caption") else "Default"
        return await cq.edit_message_text(
            "<blockquote><b><u>Start Message & Photo Editor</u></b></blockquote>\n\n"
            f"• <b>Start Photo:</b> <code>{has_img}</code>\n"
            f"• <b>Start Text:</b> <code>{has_cap}</code>\n\n"
            "<i>Select what you want to customize for your clone bot's /start message:</i>",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Set Start Photo", callback_data="cp_set_simg", style=ButtonStyle.PRIMARY),
                        InlineKeyboardButton("Set Start Text", callback_data="cp_set_scap", style=ButtonStyle.PRIMARY),
                    ],
                    [
                        InlineKeyboardButton("Reset Photo", callback_data="cp_rst_simg", style=ButtonStyle.DANGER),
                        InlineKeyboardButton("Reset Text", callback_data="cp_rst_scap", style=ButtonStyle.DANGER),
                    ],
                    [InlineKeyboardButton("Back", callback_data="cp_home")],
                ]
            ),
        )

    if data == "cp_set_simg":
        _CPANEL_STATE[(me.id, uid)] = {"action": "set_start_img"}
        return await cq.edit_message_text(
            "<b>Set Start Photo</b>\n\nSend a <b>Photo</b> or direct <b>Image URL</b> (`https://...`).\n<i>Send /cancel to abort.</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="cp_start_menu", style=ButtonStyle.DANGER)]]),
        )

    if data == "cp_set_scap":
        _CPANEL_STATE[(me.id, uid)] = {"action": "set_start_cap"}
        return await cq.edit_message_text(
            "<b>Set Start Text</b>\n\nSend the custom welcome caption text (HTML supported).\n<i>Send /cancel to abort.</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="cp_start_menu", style=ButtonStyle.DANGER)]]),
        )

    if data == "cp_rst_simg":
        await clonebotdb.update_one({"bot_id": me.id}, {"$unset": {"start_image": ""}})
        await cq.answer("Start Photo reset to default.", show_alert=True)
        return await cq.edit_message_text(
            "<b>Start Photo reset to default.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="cp_start_menu")]]),
        )

    if data == "cp_rst_scap":
        await clonebotdb.update_one({"bot_id": me.id}, {"$unset": {"start_caption": ""}})
        await cq.answer("Start Text reset to default.", show_alert=True)
        return await cq.edit_message_text(
            "<b>Start Text reset to default.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="cp_start_menu")]]),
        )

    if data == "cp_cmds":
        return await cq.edit_message_text(
            "<blockquote><b><u>Clone Bot Commands</u></b></blockquote>\n\n"
            "<b>Playback:</b>\n"
            "• `/play` `/vplay` `/playforce` `/vplayforce`\n"
            "• `/pause` `/resume` `/skip` `/stop` `/end`\n"
            "• `/seek` `/speed` `/loop` `/shuffle` `/247`\n"
            "• `/queue` (`/q`) — Queue + Admin Play Now\n"
            "• `/myplaylist` (`/saved`) — Saved songs\n\n"
            "<b>Owner Controls:</b>\n"
            "• `/cpanel` — Clone Control Panel\n"
            "• `/broadcast` `/stats` `/ping` `/activevc`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="cp_home")]]),
        )

    if data == "cp_del_ask":
        return await cq.edit_message_text(
            "<b>Confirm Deletion</b>\n\nAre you sure you want to remove this Cloned Bot from the server?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Yes, Delete", callback_data="cp_del_yes", style=ButtonStyle.DANGER),
                        InlineKeyboardButton("Cancel", callback_data="cp_home", style=ButtonStyle.SUCCESS),
                    ]
                ]
            ),
        )

    if data == "cp_del_yes":
        await clonebotdb.delete_one({"bot_id": me.id})
        await cq.edit_message_text("<b>Clone Bot removed from database.</b>")


async def _run_cp_broadcast(client: Client, bot_id: int, status_msg: Message, src_msg: Message, mode: str):
    _C_BC_RUNNING[bot_id] = True
    try:
        fwd = _is_fwd(src_msg)
        want_grp = mode in ("grp", "all", "grppin", "allpin")
        want_dm = mode in ("dm", "all", "allpin")
        want_pin = mode in ("grppin", "allpin")

        targets = []
        seen = set()
        if want_grp:
            for c in await get_served_chats_clone(bot_id):
                cid = c.get("chat_id") if isinstance(c, dict) else c
                if cid:
                    try:
                        cid = int(cid)
                        if cid not in seen:
                            seen.add(cid)
                            targets.append(cid)
                    except Exception:
                        pass
        if want_dm:
            for u in await get_served_users_clone(bot_id):
                uid = u.get("user_id") if isinstance(u, dict) else u
                if uid:
                    try:
                        uid = int(uid)
                        if uid not in seen:
                            seen.add(uid)
                            targets.append(uid)
                    except Exception:
                        pass

        sent_grp, sent_dm, pinned, failed = 0, 0, 0, 0
        for tid in targets:
            if not _C_BC_RUNNING.get(bot_id):
                break
            try:
                if fwd:
                    m = await client.forward_messages(tid, src_msg.chat.id, src_msg.id)
                else:
                    m = await src_msg.copy(tid)
                if tid < 0:
                    sent_grp += 1
                    if want_pin and m:
                        obj = m[0] if isinstance(m, list) else m
                        try:
                            await obj.pin(disable_notification=True)
                            pinned += 1
                        except Exception:
                            pass
                else:
                    sent_dm += 1
                await asyncio.sleep(0.08)
            except FloodWait as fw:
                await asyncio.sleep(min(int(fw.value), 60))
            except Exception:
                failed += 1

        label = "Complete" if _C_BC_RUNNING.get(bot_id) else "Stopped"
        await status_msg.edit_text(
            f"<b>Clone Broadcast {label}</b>\n\n"
            f"• <b>Type:</b> <code>{'Forwarded' if fwd else 'Direct Copy'}</code>\n"
            f"• <b>Groups Sent:</b> <code>{sent_grp}</code>\n"
            f"• <b>DM Users Sent:</b> <code>{sent_dm}</code>\n"
            f"• <b>Pinned:</b> <code>{pinned}</code> | <b>Failed:</b> <code>{failed}</code>"
        )
    finally:
        _C_BC_RUNNING[bot_id] = False


@Client.on_message(filters.private & ~filters.command(["cpanel", "panel", "clonepanel", "start", "help", "stats", "gstats", "ping"], prefixes=["/", "!", "%", ",", "", ".", "@", "#"]), group=-5)
async def cpanel_state_listener(client: Client, message: Message):
    me = await client.get_me()
    uid = message.from_user.id if message.from_user else 0
    key = (me.id, uid)
    if key not in _CPANEL_STATE:
        return
    if message.text and message.text.strip().lower() == "/cancel":
        _CPANEL_STATE.pop(key, None)
        return await message.reply_text("<b>Cancelled.</b>", reply_markup=_cpanel_home_markup())

    state = _CPANEL_STATE.pop(key)
    action = state.get("action")
    if action == "set_start_img":
        img_val = None
        if message.photo:
            img_val = message.photo.file_id
        elif message.text and message.text.strip().startswith(("http://", "https://")):
            img_val = message.text.strip()
        if not img_val:
            return await message.reply_text("<b>Invalid Photo or URL.</b> Please try again from `/cpanel`.")
        await clonebotdb.update_one({"bot_id": me.id}, {"$set": {"start_image": img_val}}, upsert=True)
        return await message.reply_text("<b>Custom Start Photo saved!</b>", reply_markup=_cpanel_home_markup())

    if action == "set_start_cap":
        cap_val = message.text or message.caption
        if not cap_val:
            return await message.reply_text("<b>Invalid text.</b> Please send text from `/cpanel`.")
        await clonebotdb.update_one({"bot_id": me.id}, {"$set": {"start_caption": cap_val}}, upsert=True)
        return await message.reply_text("<b>Custom Start Text saved!</b>", reply_markup=_cpanel_home_markup())

    if action == "broadcast":
        if _C_BC_RUNNING.get(me.id):
            return await message.reply_text("<b>Broadcast already running.</b>")
        status_msg = await message.reply_text(
            f"<b>Starting Clone Broadcast ({state['mode'].upper()})...</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Stop Broadcast", callback_data="cp_stop_bc", style=ButtonStyle.DANGER)]]),
        )
        asyncio.create_task(_run_cp_broadcast(client, me.id, status_msg, message, state["mode"]))
