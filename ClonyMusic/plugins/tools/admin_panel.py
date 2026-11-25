import asyncio
from typing import Optional

from pyrogram import Client, filters
from pyrogram.errors import AccessTokenExpired, AccessTokenInvalid, AuthKeyUnregistered, FloodWait, MessageNotModified, UserDeactivated
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, Message

import config
from ClonyMusic import LOGGER, app
from ClonyMusic.utils.button_style import (
    ButtonStyle,
    add_bot_admin,
    get_apply_to_clones,
    get_button_style,
    get_db_admins,
    is_bot_admin,
    remove_bot_admin,
    sc_button as InlineKeyboardButton,
    set_apply_to_clones,
    set_button_style,
)
from ClonyMusic.utils.database import (
    clonebotdb,
    get_served_chats,
    get_served_users,
    is_maintenance,
    maintenance_off,
    maintenance_on,
)
from ClonyMusic.utils.database.clonedb import (
    get_all_clones,
    get_served_chats_clone,
    get_served_users_clone,
)
from ClonyMusic.utils.feature_flags import (
    FEATURE_LABELS,
    get_all_features,
    get_log_mode,
    set_log_mode,
    toggle_feature_flag,
)
from ClonyMusic.utils.fsub import (
    add_blocked_word,
    clear_blocked_words,
    get_blocked_words,
    get_fsub_state,
    remove_blocked_word,
    set_fsub_chat,
    set_fsub_enabled,
)

_ADMIN_STATE = {}
_BROADCAST_RUNNING = False


def _is_forwarded(msg: Message) -> bool:
    return bool(
        getattr(msg, "forward_date", None)
        or getattr(msg, "forward_origin", None)
        or getattr(msg, "forward_from", None)
        or getattr(msg, "forward_from_chat", None)
    )


async def _admin_home_markup() -> InlineKeyboardMarkup:
    maint = await is_maintenance()
    maint_label = "Maintenance: ON" if maint else "Maintenance: OFF"
    maint_style = ButtonStyle.DANGER if maint else ButtonStyle.SUCCESS
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Main Broadcast", callback_data="adm_bc_main", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("Clones Broadcast", callback_data="adm_bc_clone", style=ButtonStyle.PRIMARY),
            ],
            [
                InlineKeyboardButton("Button Styling", callback_data="adm_style_menu", style=ButtonStyle.SUCCESS),
                InlineKeyboardButton("Feature Controls", callback_data="adm_feat_menu", style=ButtonStyle.SUCCESS),
            ],
            [
                InlineKeyboardButton("Clone Manager", callback_data="adm_clone_menu", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("FSub Settings", callback_data="adm_fsub_menu", style=ButtonStyle.PRIMARY),
            ],
            [
                InlineKeyboardButton("Add Admin", callback_data="adm_add_admin", style=ButtonStyle.SUCCESS),
                InlineKeyboardButton("Remove Admin", callback_data="adm_rem_admin", style=ButtonStyle.DANGER),
            ],
            [
                InlineKeyboardButton("DB Transfer", callback_data="adm_db_transfer", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("Backup DB", callback_data="adm_backup_db", style=ButtonStyle.SUCCESS),
            ],
            [
                InlineKeyboardButton("Log Settings", callback_data="adm_log_menu", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("Blocked Words", callback_data="adm_block_menu", style=ButtonStyle.DANGER),
            ],
            [
                InlineKeyboardButton("Export error.txt", callback_data="adm_export_errors", style=ButtonStyle.DANGER),
                InlineKeyboardButton("Update & Restart", callback_data="adm_update_ask", style=ButtonStyle.DANGER),
            ],
            [
                InlineKeyboardButton(maint_label, callback_data="adm_toggle_maint", style=maint_style),
                InlineKeyboardButton("Admin List", callback_data="adm_list_admins"),
            ],
            [
                InlineKeyboardButton("Close", callback_data="adm_close", style=ButtonStyle.DANGER),
            ],
        ]
    )


def _broadcast_sub_markup(scope: str) -> InlineKeyboardMarkup:
    tag = "Clones" if scope == "clone" else "Main"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"Only DM ({tag})", callback_data=f"adm_bc:{scope}:dm", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton(f"Only Groups ({tag})", callback_data=f"adm_bc:{scope}:grp", style=ButtonStyle.PRIMARY),
            ],
            [
                InlineKeyboardButton(f"Groups + DM ({tag})", callback_data=f"adm_bc:{scope}:all", style=ButtonStyle.SUCCESS),
                InlineKeyboardButton(f"Groups + Pin ({tag})", callback_data=f"adm_bc:{scope}:grppin", style=ButtonStyle.SUCCESS),
            ],
            [
                InlineKeyboardButton(f"Groups + DM + Pin ({tag})", callback_data=f"adm_bc:{scope}:allpin", style=ButtonStyle.DANGER),
            ],
            [
                InlineKeyboardButton("Back", callback_data="adm_home"),
            ],
        ]
    )


def _style_menu_markup() -> InlineKeyboardMarkup:
    clones_on = get_apply_to_clones()
    clone_btn_text = "Apply to Clones: ON" if clones_on else "Apply to Clones: OFF"
    clone_btn_style = ButtonStyle.SUCCESS if clones_on else ButtonStyle.DANGER
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Primary", callback_data="adm_setstyle:primary", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("Danger", callback_data="adm_setstyle:danger", style=ButtonStyle.DANGER),
                InlineKeyboardButton("Success", callback_data="adm_setstyle:success", style=ButtonStyle.SUCCESS),
            ],
            [
                InlineKeyboardButton("None (Default)", callback_data="adm_setstyle:none", style=ButtonStyle.DEFAULT),
                InlineKeyboardButton("Mix", callback_data="adm_setstyle:mix", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("Pattern", callback_data="adm_setstyle:pattern", style=ButtonStyle.SUCCESS),
            ],
            [
                InlineKeyboardButton(clone_btn_text, callback_data="adm_toggle_clone_style", style=clone_btn_style),
            ],
            [
                InlineKeyboardButton("Back", callback_data="adm_home"),
            ],
        ]
    )


def _feature_menu_markup() -> InlineKeyboardMarkup:
    flags = get_all_features()
    rows = []
    for key, label in FEATURE_LABELS.items():
        on = flags.get(key, True)
        rows.append(
            [
                InlineKeyboardButton(
                    f"{label}: {'ON' if on else 'OFF'}",
                    callback_data=f"adm_toggle_feat:{key}",
                    style=ButtonStyle.SUCCESS if on else ButtonStyle.DANGER,
                )
            ]
        )
    rows.append([InlineKeyboardButton("Back", callback_data="adm_home")])
    return InlineKeyboardMarkup(rows)


def _clone_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("View Clone Info / Token", callback_data="adm_view_tokens", style=ButtonStyle.PRIMARY),
            ],
            [
                InlineKeyboardButton("List / Delete Specific Clone", callback_data="adm_list_clones", style=ButtonStyle.PRIMARY),
            ],
            [
                InlineKeyboardButton("Delete Dead Cloned Bots", callback_data="adm_del_dead_clones", style=ButtonStyle.DANGER),
            ],
            [
                InlineKeyboardButton("Back", callback_data="adm_home"),
            ],
        ]
    )


def _block_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Add Word", callback_data="adm_blk_add", style=ButtonStyle.SUCCESS),
                InlineKeyboardButton("Remove Word", callback_data="adm_blk_rem", style=ButtonStyle.DANGER),
            ],
            [
                InlineKeyboardButton("Clear All Words", callback_data="adm_blk_clear", style=ButtonStyle.DANGER),
                InlineKeyboardButton("Back", callback_data="adm_home"),
            ],
        ]
    )


def _fsub_menu_markup() -> InlineKeyboardMarkup:
    enabled, _ = get_fsub_state()
    tog_text = "FSub: ON" if enabled else "FSub: OFF"
    tog_style = ButtonStyle.SUCCESS if enabled else ButtonStyle.DANGER
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(tog_text, callback_data="adm_fsub_toggle", style=tog_style),
                InlineKeyboardButton("Set Channel / Group", callback_data="adm_fsub_set", style=ButtonStyle.PRIMARY),
            ],
            [
                InlineKeyboardButton("Back", callback_data="adm_home"),
            ],
        ]
    )


async def _admin_home_text() -> str:
    admins = await get_db_admins()
    env_admins = len(getattr(config, "BOT_ADMINS", []))
    style = get_button_style().upper()
    clone_style = "ON" if get_apply_to_clones() else "OFF"
    total_clones = await clonebotdb.count_documents({})
    return (
        "<b><u>Bot Admin Control Panel</u></b>\n\n"
        f"• <b>Active Button Style:</b> <code>{style}</code> (Clones: <code>{clone_style}</code>)\n"
        f"• <b>Owner ID:</b> <code>{config.OWNER_ID}</code>\n"
        f"• <b>DB Admins:</b> <code>{len(admins)}</code> | <b>ENV Admins:</b> <code>{env_admins}</code>\n"
        f"• <b>Total Cloned Bots:</b> <code>{total_clones}</code>\n\n"
        "<i>Select an option below to manage broadcasts, features, styling, clones, or admins:</i>"
    )


@app.on_message(filters.command(["admin"], prefixes=["/", "!", "%", ",", "", ".", "@", "#"]) & filters.private)
async def admin_panel_cmd(client, message: Message):
    if not message.from_user or not is_bot_admin(message.from_user.id):
        return await message.reply_text("<b>Access Denied:</b> Only Bot Owner & Admins can open the Admin Panel.")
    _ADMIN_STATE.pop(message.from_user.id, None)
    await message.reply_text(
        await _admin_home_text(),
        reply_markup=await _admin_home_markup(),
    )


@app.on_callback_query(filters.regex(r"^adm_"))
async def admin_panel_callbacks(client, cq: CallbackQuery):
    try:
        return await _dispatch_admin_callbacks(client, cq)
    except MessageNotModified:
        pass
    except Exception as e:
        LOGGER(__name__).error(f"admin_panel_callbacks error ({cq.data}): {e}")
        try:
            await cq.answer(f"Panel error: {type(e).__name__}", show_alert=True)
        except Exception:
            pass


async def _dispatch_admin_callbacks(client, cq: CallbackQuery):
    global _BROADCAST_RUNNING
    uid = cq.from_user.id if cq.from_user else 0
    if not is_bot_admin(uid):
        return await cq.answer("Only Bot Owner & Admins can use this panel.", show_alert=True)

    data = cq.data
    if data == "adm_close":
        _ADMIN_STATE.pop(uid, None)
        return await cq.message.delete()

    if data == "adm_home":
        _ADMIN_STATE.pop(uid, None)
        return await cq.edit_message_text(await _admin_home_text(), reply_markup=await _admin_home_markup())

    if data == "adm_stop_bc":
        if not _BROADCAST_RUNNING:
            return await cq.answer("No broadcast is currently running.", show_alert=True)
        _BROADCAST_RUNNING = False
        return await cq.answer("Stopping broadcast...", show_alert=True)

    if data == "adm_toggle_maint":
        if await is_maintenance():
            await maintenance_off()
            await cq.answer("Maintenance Mode turned OFF.", show_alert=True)
        else:
            await maintenance_on()
            await cq.answer("Maintenance Mode turned ON.", show_alert=True)
        return await cq.edit_message_text(await _admin_home_text(), reply_markup=await _admin_home_markup())

    if data == "adm_feat_menu":
        return await cq.edit_message_text(
            "<b><u>Global Feature Controls (Main & Cloned Bots)</u></b>\n\n"
            "Yahan se aap kisi bhi feature ko ON/OFF kar sakte hain. "
            "Jo feature OFF hoga woh Main Bot aur sabhi Cloned Bots ke player & commands se hide ho jayega:",
            reply_markup=_feature_menu_markup(),
        )

    if data.startswith("adm_toggle_feat:"):
        key = data.split(":", 1)[1]
        new_val = await toggle_feature_flag(key)
        label = FEATURE_LABELS.get(key, key)
        await cq.answer(f"{label}: {'ON' if new_val else 'OFF'}", show_alert=True)
        return await cq.edit_message_text(
            "<b><u>Global Feature Controls (Main & Cloned Bots)</u></b>\n\n"
            "Yahan se aap kisi bhi feature ko ON/OFF kar sakte hain. "
            "Jo feature OFF hoga woh Main Bot aur sabhi Cloned Bots ke player & commands se hide ho jayega:",
            reply_markup=_feature_menu_markup(),
        )

    if data == "adm_clone_menu":
        total = await clonebotdb.count_documents({})
        return await cq.edit_message_text(
            f"<b><u>Clone Bots Manager</u></b>\n\n"
            f"• <b>Total Cloned Bots in DB:</b> <code>{total}</code>\n\n"
            "Yahan se aap specific cloned bot ya expired/revoked (dead) cloned bots ko manually delete kar sakte hain.\n"
            "<i>Note: Cloned bots kabhi auto-delete nahi honge jab tak aap khud button na dabayein.</i>",
            reply_markup=_clone_menu_markup(),
        )

    if data == "adm_list_clones":
        clones = []
        async for c in get_all_clones():
            clones.append(c)
        if not clones:
            return await cq.answer("No cloned bots found.", show_alert=True)
        rows = []
        for c in clones[:12]:
            bid = c.get("bot_id")
            uname = c.get("username") or str(bid)
            rows.append([InlineKeyboardButton(f"Delete @{uname}", callback_data=f"adm_del_clone:{bid}", style=ButtonStyle.DANGER)])
        rows.append([InlineKeyboardButton("Back", callback_data="adm_clone_menu")])
        return await cq.edit_message_text(
            f"<b><u>Cloned Bots ({len(clones)})</u></b>\n\nClick any clone below to delete it from DB:",
            reply_markup=InlineKeyboardMarkup(rows),
        )

    if data.startswith("adm_del_clone:"):
        bid = int(data.split(":", 1)[1])
        await clonebotdb.delete_one({"bot_id": bid})
        await cq.answer(f"Deleted clone {bid}.", show_alert=True)
        return await cq.edit_message_text(
            f"<b>Clone Bot <code>{bid}</code> deleted from database.</b>",
            reply_markup=_clone_menu_markup(),
        )

    if data == "adm_fsub_menu":
        enabled, chat = get_fsub_state()
        return await cq.edit_message_text(
            "<b><u>Force-Subscribe (FSub) Manager</u></b>\n\n"
            f"• <b>Status:</b> <code>{'ON' if enabled else 'OFF'}</code>\n"
            f"• <b>Target Channel/Group:</b> <code>{chat or 'Not Set'}</code>\n\n"
            "<i>Bot must be Admin in the FSub channel/group.</i>",
            reply_markup=_fsub_menu_markup(),
        )

    if data == "adm_fsub_toggle":
        enabled, chat = get_fsub_state()
        if not enabled and not chat:
            return await cq.answer("Please set FSub Channel/Group first!", show_alert=True)
        await set_fsub_enabled(not enabled)
        new_state = "ON" if not enabled else "OFF"
        await cq.answer(f"FSub turned {new_state}", show_alert=True)
        return await cq.edit_message_text(
            "<b><u>Force-Subscribe (FSub) Manager</u></b>\n\n"
            f"• <b>Status:</b> <code>{new_state}</code>\n"
            f"• <b>Target Channel/Group:</b> <code>{chat or 'Not Set'}</code>",
            reply_markup=_fsub_menu_markup(),
        )

    if data == "adm_fsub_set":
        _ADMIN_STATE[uid] = {"action": "set_fsub"}
        return await cq.edit_message_text(
            "<b><u>Set FSub Channel / Group</u></b>\n\n"
            "Apne Channel/Group ka <code>@username</code> ya numeric ID (e.g. <code>-1001234567890</code>) bhejein.\n"
            "<i>Cancel karne ke liye</i> `/cancel` <i>bhejein.</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="adm_fsub_menu", style=ButtonStyle.DANGER)]]),
        )

    if data == "adm_del_dead_clones":
        await cq.answer("Scanning cloned bots...", show_alert=False)
        await cq.edit_message_text("<b>Scanning all cloned bots for dead/expired tokens...</b>\n<i>Please wait...</i>")
        clones = []
        async for c in get_all_clones():
            clones.append(c)

        dead_count = 0
        alive_count = 0
        for clone in clones:
            token = clone.get("token")
            bot_id = clone.get("bot_id")
            if not token:
                if bot_id:
                    await clonebotdb.delete_one({"bot_id": bot_id})
                dead_count += 1
                continue
            try:
                async with Client(
                    f"chk_{bot_id}",
                    api_id=config.API_ID,
                    api_hash=config.API_HASH,
                    bot_token=token,
                    in_memory=True,
                    no_updates=True,
                ) as chk_app:
                    await chk_app.get_me()
                alive_count += 1
            except (AuthKeyUnregistered, UserDeactivated, AccessTokenExpired, AccessTokenInvalid):
                await clonebotdb.delete_one({"bot_id": bot_id})
                dead_count += 1
            except Exception:
                alive_count += 1

        return await cq.edit_message_text(
            "<b><u>Dead Cloned Bots Cleanup Complete</u></b>\n\n"
            f"• <b>Alive Clones:</b> <code>{alive_count}</code>\n"
            f"• <b>Dead Clones Deleted:</b> <code>{dead_count}</code>",
            reply_markup=_clone_menu_markup(),
        )

    if data == "adm_bc_main":
        return await cq.edit_message_text(
            "<b><u>Main Bot Broadcast</u></b>\n\n"
            "Choose where to broadcast:\n"
            "• <i>Forwarded messages will be sent as Forwarded.</i>\n"
            "• <i>Direct messages will be copied cleanly without forward tag.</i>",
            reply_markup=_broadcast_sub_markup("main"),
        )

    if data == "adm_bc_clone":
        return await cq.edit_message_text(
            "<b><u>All Cloned Bots Broadcast</u></b>\n\n"
            "Choose where to broadcast across all active cloned bots:\n"
            "• <i>Forwarded messages will be sent as Forwarded.</i>\n"
            "• <i>Direct messages will be copied cleanly.</i>",
            reply_markup=_broadcast_sub_markup("clone"),
        )

    if data.startswith("adm_bc:"):
        _, scope, mode = data.split(":", 2)
        if _BROADCAST_RUNNING:
            return await cq.answer("A broadcast is already running. Please wait.", show_alert=True)
        _ADMIN_STATE[uid] = {"action": "broadcast", "scope": scope, "mode": mode}
        return await cq.edit_message_text(
            f"<b>Send Broadcast Message</b>\n\n"
            f"• <b>Target:</b> <code>{scope.upper()} ({mode.upper()})</code>\n\n"
            "Ab aap apna message bhejein ya forward karein.\n"
            "• Agar <b>forward</b> karoge toh forward tag ke saath jayega.\n"
            "• Agar <b>direct</b> bhejoge toh bina forward tag ke jayega.\n\n"
            "<i>Cancel karne ke liye</i> `/cancel` <i>bhejein.</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="adm_home", style=ButtonStyle.DANGER)]]),
        )

    if data == "adm_style_menu":
        cur = get_button_style().upper()
        c_status = "ON" if get_apply_to_clones() else "OFF"
        return await cq.edit_message_text(
            f"<b><u>Global Button Styling</u></b>\n\n"
            f"• <b>Current Style:</b> <code>{cur}</code>\n"
            f"• <b>Apply to Cloned Bots:</b> <code>{c_status}</code>\n\n"
            "Yahan se aap Main Bot aur sabhi Cloned Bots ke inline buttons ka color style change kar sakte hain:",
            reply_markup=_style_menu_markup(),
        )

    if data == "adm_toggle_clone_style":
        new_val = not get_apply_to_clones()
        await set_apply_to_clones(new_val)
        await cq.answer(f"Clone Button Styling: {'ON' if new_val else 'OFF'}", show_alert=True)
        cur = get_button_style().upper()
        return await cq.edit_message_text(
            f"<b><u>Global Button Styling</u></b>\n\n"
            f"• <b>Current Style:</b> <code>{cur}</code>\n"
            f"• <b>Apply to Cloned Bots:</b> <code>{'ON' if new_val else 'OFF'}</code>\n\n"
            "Sabhi naye inline buttons par yeh setting apply hogi.",
            reply_markup=_style_menu_markup(),
        )

    if data.startswith("adm_setstyle:"):
        mode = data.split(":", 1)[1]
        await set_button_style(mode)
        await cq.answer(f"Button style set to: {mode.upper()}", show_alert=True)
        c_status = "ON" if get_apply_to_clones() else "OFF"
        return await cq.edit_message_text(
            f"<b><u>Global Button Styling</u></b>\n\n"
            f"• <b>Current Style:</b> <code>{mode.upper()}</code>\n"
            f"• <b>Apply to Cloned Bots:</b> <code>{c_status}</code>\n\n"
            "Sabhi naye inline buttons par yeh style automatically apply hoga.",
            reply_markup=_style_menu_markup(),
        )

    if data == "adm_add_admin":
        _ADMIN_STATE[uid] = {"action": "add_admin"}
        return await cq.edit_message_text(
            "<b><u>Add Bot Admin</u></b>\n\n"
            "Jis user ko admin banana hai uska <b>Numeric User ID</b> bhejein (ya uska koi message forward karein).\n\n"
            "<i>Cancel karne ke liye</i> `/cancel` <i>bhejein.</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="adm_home")]]),
        )

    if data == "adm_rem_admin":
        admins = await get_db_admins()
        if not admins:
            return await cq.answer("No DB admins added yet.", show_alert=True)
        rows = [
            [InlineKeyboardButton(f"Remove {aid}", callback_data=f"adm_deladmin:{aid}", style=ButtonStyle.DANGER)]
            for aid in admins
        ]
        rows.append([InlineKeyboardButton("Back", callback_data="adm_home")])
        return await cq.edit_message_text(
            "<b><u>Remove Bot Admin</u></b>\n\nClick any Admin ID below to remove:",
            reply_markup=InlineKeyboardMarkup(rows),
        )

    if data.startswith("adm_deladmin:"):
        target_id = int(data.split(":", 1)[1])
        ok = await remove_bot_admin(target_id)
        if not ok:
            return await cq.answer("Cannot remove Owner ID!", show_alert=True)
        await cq.answer(f"Removed {target_id} from Admins.", show_alert=True)
        admins = await get_db_admins()
        if not admins:
            return await cq.edit_message_text(await _admin_home_text(), reply_markup=await _admin_home_markup())
        rows = [
            [InlineKeyboardButton(f"Remove {aid}", callback_data=f"adm_deladmin:{aid}", style=ButtonStyle.DANGER)]
            for aid in admins
        ]
        rows.append([InlineKeyboardButton("Back", callback_data="adm_home")])
        return await cq.edit_message_text(
            "<b><u>Remove Bot Admin</u></b>\n\nClick any Admin ID below to remove:",
            reply_markup=InlineKeyboardMarkup(rows),
        )

    if data == "adm_list_admins":
        db_admins = await get_db_admins()
        env_admins = getattr(config, "BOT_ADMINS", [])
        lines = [
            "<b><u>Bot Admins List</u></b>\n",
            f"<b>Owner:</b> <code>{config.OWNER_ID}</code>",
        ]
        if env_admins:
            lines.append("\n<b>ENV Admins (.env):</b>")
            for a in env_admins:
                lines.append(f"  • <code>{a}</code>")
        if db_admins:
            lines.append("\n<b>Panel Admins (DB):</b>")
            for a in db_admins:
                lines.append(f"  • <code>{a}</code>")
        if not env_admins and not db_admins:
            lines.append("\n<i>No extra admins configured.</i>")
        return await cq.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="adm_home")]]),
        )

    if data == "adm_update_ask":
        return await cq.edit_message_text(
            "<b><u>Git Update & Restart</u></b>\n\n"
            "Kya aap GitHub se latest code pull karke bot ko restart karna chahte hain?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Yes, Update & Restart", callback_data="adm_update_yes", style=ButtonStyle.DANGER),
                        InlineKeyboardButton("Cancel", callback_data="adm_home", style=ButtonStyle.SUCCESS),
                    ]
                ]
            ),
        )

    if data == "adm_db_transfer":
        if config.OWNER_ID and uid != int(config.OWNER_ID):
            return await cq.answer("Only Main Bot Owner can transfer MongoDB!", show_alert=True)
        _ADMIN_STATE[uid] = {"action": "db_transfer"}
        return await cq.edit_message_text(
            "<b><u>Transfer Database to Another MongoDB</u></b>\n\n"
            "Naya <b>Target MONGO_DB_URI</b> bhejein (e.g. <code>mongodb+srv://user:pass@cluster.mongodb.net/NewDB?...</code>).\n\n"
            "• Current database ke saare collections (Clones, Chats, Users, Playlists, Settings, Admins) safely copy ho jayenge.\n"
            "• Source database delete nahi hoga.\n\n"
            "<i>Cancel karne ke liye</i> `/cancel` <i>bhejein.</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="adm_home", style=ButtonStyle.DANGER)]]),
        )

    if data == "adm_update_yes":
        import os
        import sys
        await cq.edit_message_text("<b>Pulling latest updates and restarting bot...</b>")
        os.system("git pull origin master")
        os.execl(sys.executable, sys.executable, "-m", "ClonyMusic")

    if data == "adm_log_menu":
        cur_log = get_log_mode().upper()
        return await cq.edit_message_text(
            "<b><u>Log Group Settings</u></b>\n\n"
            f"• <b>Current Log Mode:</b> <code>{cur_log}</code>\n\n"
            "Select which logs bots should send to your Log Group:",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("All Logs", callback_data="adm_setlog:all", style=ButtonStyle.SUCCESS),
                        InlineKeyboardButton("Play + Error", callback_data="adm_setlog:play_error", style=ButtonStyle.PRIMARY),
                    ],
                    [
                        InlineKeyboardButton("Error Only", callback_data="adm_setlog:error_only", style=ButtonStyle.PRIMARY),
                        InlineKeyboardButton("Logs Off", callback_data="adm_setlog:off", style=ButtonStyle.DANGER),
                    ],
                    [InlineKeyboardButton("Back", callback_data="adm_home")],
                ]
            ),
        )

    if data.startswith("adm_setlog:"):
        mode = data.split(":", 1)[1]
        await set_log_mode(mode)
        await cq.answer(f"Log mode set to: {mode.upper()}", show_alert=True)
        return await cq.edit_message_text(
            "<b><u>Log Group Settings</u></b>\n\n"
            f"• <b>Current Log Mode:</b> <code>{mode.upper()}</code>\n\n"
            "Select which logs bots should send to your Log Group:",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("All Logs", callback_data="adm_setlog:all", style=ButtonStyle.SUCCESS),
                        InlineKeyboardButton("Play + Error", callback_data="adm_setlog:play_error", style=ButtonStyle.PRIMARY),
                    ],
                    [
                        InlineKeyboardButton("Error Only", callback_data="adm_setlog:error_only", style=ButtonStyle.PRIMARY),
                        InlineKeyboardButton("Logs Off", callback_data="adm_setlog:off", style=ButtonStyle.DANGER),
                    ],
                    [InlineKeyboardButton("Back", callback_data="adm_home")],
                ]
            ),
        )

    if data == "adm_export_errors":
        import os
        err_lines = []
        if os.path.exists("error.txt"):
            with open("error.txt", "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().strip()
                if content:
                    err_lines.append(content)
        if not err_lines and os.path.exists("log.txt"):
            with open("log.txt", "r", encoding="utf-8", errors="ignore") as f:
                filtered = [ln for ln in f if "[ERROR]" in ln or "Traceback" in ln or "Error:" in ln]
                if filtered:
                    err_lines.append("".join(filtered[-200:]))
        if not err_lines:
            return await cq.answer("No errors recorded yet!", show_alert=True)
        with open("error.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(err_lines))
        await cq.answer("Sending error.txt...", show_alert=False)
        return await cq.message.reply_document(
            document="error.txt",
            caption="<b>Collected Bot Errors (error.txt)</b>",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Clear error.txt", callback_data="adm_clear_errors", style=ButtonStyle.DANGER),
                        InlineKeyboardButton("Close", callback_data="close"),
                    ]
                ]
            ),
        )

    if data == "adm_clear_errors":
        with open("error.txt", "w", encoding="utf-8") as f:
            f.write("")
        await cq.answer("error.txt cleared!", show_alert=True)
        return await cq.message.edit_caption("<b>error.txt has been cleared.</b>")

    if data == "adm_view_tokens":
        if config.OWNER_ID and uid != int(config.OWNER_ID):
            return await cq.answer("Only Main Bot Owner can view Clone Bot tokens!", show_alert=True)
        clones = []
        async for c in get_all_clones():
            clones.append(c)
        if not clones:
            return await cq.answer("No cloned bots found.", show_alert=True)
        rows = []
        for c in clones[:15]:
            bid = c.get("bot_id")
            uname = c.get("username") or str(bid)
            rows.append([InlineKeyboardButton(f"@{uname} ({bid})", callback_data=f"adm_tok_one:{bid}", style=ButtonStyle.PRIMARY)])
        rows.append([InlineKeyboardButton("Back", callback_data="adm_clone_menu")])
        return await cq.edit_message_text(
            f"<b><u>View Clone Bot Info & Token ({len(clones)})</u></b>\n\nSelect a cloned bot below:",
            reply_markup=InlineKeyboardMarkup(rows),
        )

    if data.startswith("adm_tok_one:"):
        if config.OWNER_ID and uid != int(config.OWNER_ID):
            return await cq.answer("Only Main Bot Owner can view Clone Bot tokens!", show_alert=True)
        bid = int(data.split(":", 1)[1])
        doc = await clonebotdb.find_one({"bot_id": bid})
        if not doc:
            return await cq.answer("Clone not found.", show_alert=True)
        tok = doc.get("token", "Not found")
        owner_id = doc.get("user_id", "Unknown")
        uname = doc.get("username", "Unknown")
        name = doc.get("name", "Clone")
        return await cq.edit_message_text(
            f"<b><u>Clone Bot Details</u></b>\n\n"
            f"• <b>Name:</b> {name}\n"
            f"• <b>Username:</b> @{uname}\n"
            f"• <b>Bot ID:</b> <code>{bid}</code>\n"
            f"• <b>Owner ID:</b> <code>{owner_id}</code>\n"
            f"• <b>Bot Token:</b> <tg-spoiler><code>{tok}</code></tg-spoiler>",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("Delete This Clone", callback_data=f"adm_del_clone:{bid}", style=ButtonStyle.DANGER)],
                    [InlineKeyboardButton("Back", callback_data="adm_view_tokens")],
                ]
            ),
        )

    if data == "adm_backup_db":
        if config.OWNER_ID and uid != int(config.OWNER_ID):
            return await cq.answer("Only Main Bot Owner can backup database!", show_alert=True)
        import json
        import os
        from ClonyMusic.core.mongo import mongodb

        await cq.answer("Generating JSON database backup...", show_alert=False)
        backup_path = "db_backup.json"
        dump = {}
        try:
            for cname in await mongodb.list_collection_names():
                if cname.startswith("system."):
                    continue
                docs = [doc async for doc in mongodb[cname].find({})]
                dump[cname] = docs
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(dump, f, default=str, indent=2, ensure_ascii=False)
            await cq.message.reply_document(
                document=backup_path,
                caption=f"<b>MongoDB Backup Complete</b>\n• <b>Collections:</b> <code>{len(dump)}</code>",
            )
        except Exception as e:
            await cq.message.reply_text(f"<b>Backup Failed:</b> <code>{e}</code>")
        finally:
            if os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except Exception:
                    pass
        return

    if data == "adm_block_menu":
        words = get_blocked_words()
        w_text = ", ".join(f"<code>{w}</code>" for w in words[:30]) if words else "<i>None</i>"
        return await cq.edit_message_text(
            f"<b><u>Blocked Keywords Filter ({len(words)})</u></b>\n\n"
            f"• <b>Active Blocked Words:</b> {w_text}\n\n"
            "Users cannot `/play` any query containing these keywords.",
            reply_markup=_block_menu_markup(),
        )

    if data == "adm_blk_add":
        _ADMIN_STATE[uid] = {"action": "blk_add"}
        return await cq.edit_message_text(
            "<b>Add Blocked Word</b>\n\nSend the word/phrase to block (or comma-separated words).\n<i>Send /cancel to abort.</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="adm_block_menu", style=ButtonStyle.DANGER)]]),
        )

    if data == "adm_blk_rem":
        words = get_blocked_words()
        if not words:
            return await cq.answer("No blocked words to remove.", show_alert=True)
        rows = [[InlineKeyboardButton(f"Remove: {w}", callback_data=f"adm_blk_del:{w[:40]}", style=ButtonStyle.DANGER)] for w in words[:15]]
        rows.append([InlineKeyboardButton("Back", callback_data="adm_block_menu")])
        return await cq.edit_message_text(
            "<b>Remove Blocked Word</b>\n\nClick any word below to unblock:",
            reply_markup=InlineKeyboardMarkup(rows),
        )

    if data.startswith("adm_blk_del:"):
        w = data.split(":", 1)[1]
        await remove_blocked_word(w)
        await cq.answer(f"Removed '{w}'", show_alert=True)
        words = get_blocked_words()
        w_text = ", ".join(f"<code>{x}</code>" for x in words[:30]) if words else "<i>None</i>"
        return await cq.edit_message_text(
            f"<b><u>Blocked Keywords Filter ({len(words)})</u></b>\n\n• <b>Active Blocked Words:</b> {w_text}",
            reply_markup=_block_menu_markup(),
        )

    if data == "adm_blk_clear":
        await clear_blocked_words()
        await cq.answer("All blocked words cleared.", show_alert=True)
        return await cq.edit_message_text(
            "<b><u>Blocked Keywords Filter (0)</u></b>\n\n• <b>Active Blocked Words:</b> <i>None</i>",
            reply_markup=_block_menu_markup(),
        )


async def _send_with_client(
    bot_client: Client,
    target_id: int,
    src_msg: Message,
    forwarded: bool,
    relay_chat_id: Optional[int],
    relay_msg_id: Optional[int],
    pin: bool,
):
    if forwarded and relay_chat_id and relay_msg_id:
        m = await bot_client.forward_messages(target_id, relay_chat_id, relay_msg_id)
    elif not forwarded and relay_chat_id and relay_msg_id:
        m = await bot_client.copy_message(target_id, relay_chat_id, relay_msg_id)
    elif src_msg.text:
        m = await bot_client.send_message(target_id, src_msg.text, entities=src_msg.entities)
    else:
        return None

    if pin and target_id < 0 and m:
        msg_obj = m[0] if isinstance(m, list) else m
        try:
            await msg_obj.pin(disable_notification=True)
            return True, True
        except Exception:
            return True, False
    return True, False


async def _run_main_broadcast(status_msg: Message, src_msg: Message, mode: str):
    global _BROADCAST_RUNNING
    _BROADCAST_RUNNING = True
    try:
        forwarded = _is_forwarded(src_msg)
        want_grp = mode in ("grp", "all", "grppin", "allpin")
        want_dm = mode in ("dm", "all", "allpin")
        want_pin = mode in ("grppin", "allpin")

        targets = []
        seen = set()
        if want_grp:
            for c in await get_served_chats():
                cid = int(c["chat_id"])
                if cid not in seen:
                    seen.add(cid)
                    targets.append(cid)
        if want_dm:
            for u in await get_served_users():
                uid = int(u["user_id"])
                if uid not in seen:
                    seen.add(uid)
                    targets.append(uid)

        sent_grp, sent_dm, pinned, failed = 0, 0, 0, 0
        for tid in targets:
            if not _BROADCAST_RUNNING:
                break
            try:
                if forwarded:
                    m = await app.forward_messages(tid, src_msg.chat.id, src_msg.id)
                else:
                    m = await src_msg.copy(tid)
                if tid < 0:
                    sent_grp += 1
                    if want_pin and m:
                        msg_obj = m[0] if isinstance(m, list) else m
                        try:
                            await msg_obj.pin(disable_notification=True)
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

        state_label = "Complete" if _BROADCAST_RUNNING else "Stopped by Admin"
        await status_msg.edit_text(
            f"<b>Main Bot Broadcast {state_label}</b>\n\n"
            f"• <b>Type:</b> <code>{'Forwarded' if forwarded else 'Direct Copy'}</code>\n"
            f"• <b>Groups Sent:</b> <code>{sent_grp}</code>\n"
            f"• <b>DM Users Sent:</b> <code>{sent_dm}</code>\n"
            f"• <b>Pinned:</b> <code>{pinned}</code>\n"
            f"• <b>Failed:</b> <code>{failed}</code>"
        )
    finally:
        _BROADCAST_RUNNING = False


async def _run_clone_broadcast(status_msg: Message, src_msg: Message, mode: str):
    global _BROADCAST_RUNNING
    _BROADCAST_RUNNING = True
    relay_msg = None
    try:
        forwarded = _is_forwarded(src_msg)
        want_grp = mode in ("grp", "all", "grppin", "allpin")
        want_dm = mode in ("dm", "all", "allpin")
        want_pin = mode in ("grppin", "allpin")

        if config.LOGGER_ID:
            try:
                if forwarded:
                    relay_msg = await app.forward_messages(config.LOGGER_ID, src_msg.chat.id, src_msg.id)
                else:
                    relay_msg = await src_msg.copy(config.LOGGER_ID)
                if isinstance(relay_msg, list):
                    relay_msg = relay_msg[0]
            except Exception:
                relay_msg = None

        clones = []
        async for c in get_all_clones():
            clones.append(c)

        if not clones:
            return await status_msg.edit_text("<b>No cloned bots found in database.</b>")

        sent_grp, sent_dm, pinned, active_bots, dead_bots = 0, 0, 0, 0, 0
        for clone in clones:
            if not _BROADCAST_RUNNING:
                break
            token = clone.get("token")
            bot_id = clone.get("bot_id")
            if not token or not bot_id:
                continue

            targets = []
            seen = set()
            if want_grp:
                for ch in await get_served_chats_clone(bot_id):
                    cid = int(ch["chat_id"])
                    if cid not in seen:
                        seen.add(cid)
                        targets.append(cid)
            if want_dm:
                for us in await get_served_users_clone(bot_id):
                    uid = int(us["user_id"])
                    if uid not in seen:
                        seen.add(uid)
                        targets.append(uid)

            if not targets:
                continue

            try:
                async with Client(
                    f"bc_{bot_id}",
                    api_id=config.API_ID,
                    api_hash=config.API_HASH,
                    bot_token=token,
                    in_memory=True,
                    no_updates=True,
                ) as c_app:
                    try:
                        await c_app.get_me()
                    except (AuthKeyUnregistered, UserDeactivated):
                        dead_bots += 1
                        continue
                    active_bots += 1
                    relay_cid = config.LOGGER_ID if relay_msg else None
                    relay_mid = relay_msg.id if relay_msg else None

                    for tid in targets:
                        if not _BROADCAST_RUNNING:
                            break
                        try:
                            res = await _send_with_client(
                                c_app, tid, src_msg, forwarded, relay_cid, relay_mid, want_pin
                            )
                            if res:
                                _, did_pin = res
                                if tid < 0:
                                    sent_grp += 1
                                    if did_pin:
                                        pinned += 1
                                else:
                                    sent_dm += 1
                            await asyncio.sleep(0.08)
                        except FloodWait as fw:
                            await asyncio.sleep(min(int(fw.value), 60))
                        except Exception:
                            pass
            except Exception:
                dead_bots += 1

        state_label = "Complete" if _BROADCAST_RUNNING else "Stopped by Admin"
        await status_msg.edit_text(
            f"<b>All Cloned Bots Broadcast {state_label}</b>\n\n"
            f"• <b>Type:</b> <code>{'Forwarded' if forwarded else 'Direct Copy'}</code>\n"
            f"• <b>Active Clones:</b> <code>{active_bots}</code> | <b>Dead/Skipped:</b> <code>{dead_bots}</code>\n"
            f"• <b>Groups Sent:</b> <code>{sent_grp}</code>\n"
            f"• <b>DM Users Sent:</b> <code>{sent_dm}</code>\n"
            f"• <b>Pinned:</b> <code>{pinned}</code>"
        )
    finally:
        if relay_msg:
            try:
                await relay_msg.delete()
            except Exception:
                pass
        _BROADCAST_RUNNING = False


@app.on_message(filters.private & ~filters.command(["admin", "start", "help", "stats", "gstats", "botstats", "cleandb", "cleanstats", "resetstats", "ping", "clone", "cloned", "mybots"], prefixes=["/", "!", "%", ",", "", ".", "@", "#"]), group=-5)
async def admin_state_listener(client, message: Message):
    uid = message.from_user.id if message.from_user else 0
    if uid not in _ADMIN_STATE or not is_bot_admin(uid):
        return

    if message.text and message.text.strip().lower() == "/cancel":
        _ADMIN_STATE.pop(uid, None)
        await message.reply_text("<b>Action Cancelled.</b>", reply_markup=await _admin_home_markup())
        return

    state = _ADMIN_STATE.pop(uid)
    action = state.get("action")

    if action == "add_admin":
        target_uid = None
        if message.forward_from:
            target_uid = message.forward_from.id
        elif message.text and message.text.strip().lstrip("-").isdigit():
            target_uid = int(message.text.strip())

        if not target_uid or target_uid <= 0:
            return await message.reply_text("<b>Invalid User ID.</b> Please use `/admin` and try again.")
        await add_bot_admin(target_uid)
        return await message.reply_text(
            f"<b>Admin Added Successfully</b>\n\nUser ID: <code>{target_uid}</code>",
            reply_markup=await _admin_home_markup(),
        )

    if action == "set_fsub":
        val = (message.text or "").strip()
        if not val:
            return await message.reply_text("<b>Invalid Channel/Group.</b>")
        await set_fsub_chat(val)
        await set_fsub_enabled(True)
        return await message.reply_text(
            f"<b>FSub Channel/Group Set & Enabled</b>\n\nTarget: <code>{val}</code>",
            reply_markup=_fsub_menu_markup(),
        )

    if action == "blk_add":
        raw = (message.text or "").strip()
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        added = 0
        for p in parts:
            if await add_blocked_word(p):
                added += 1
        return await message.reply_text(
            f"<b>Added {added} blocked keyword(s).</b>",
            reply_markup=_block_menu_markup(),
        )

    if action == "db_transfer":
        target_uri = (message.text or "").strip()
        if not target_uri.startswith(("mongodb://", "mongodb+srv://")):
            return await message.reply_text("<b>Invalid MongoDB URI.</b> Must start with `mongodb://` or `mongodb+srv://`.")
        status_msg = await message.reply_text("<b>Connecting to target MongoDB and transferring collections...</b>")
        asyncio.create_task(_run_db_transfer(status_msg, target_uri))
        return

    if action == "broadcast":
        scope = state["scope"]
        mode = state["mode"]
        if _BROADCAST_RUNNING:
            return await message.reply_text("<b>A broadcast is already running.</b>")
        status_msg = await message.reply_text(
            f"<b>Starting {scope.upper()} broadcast ({mode.upper()})...</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Stop Broadcast", callback_data="adm_stop_bc", style=ButtonStyle.DANGER)]]),
        )
        if scope == "main":
            asyncio.create_task(_run_main_broadcast(status_msg, message, mode))
        else:
            asyncio.create_task(_run_clone_broadcast(status_msg, message, mode))


async def _run_db_transfer(status_msg: Message, target_uri: str):
    from motor.motor_asyncio import AsyncIOMotorClient
    from pymongo import ReplaceOne
    from ClonyMusic.core.mongo import mongodb

    client_dest = None
    try:
        client_dest = AsyncIOMotorClient(target_uri, serverSelectionTimeoutMS=8000, connectTimeoutMS=8000)
        await client_dest.admin.command("ping")
        try:
            dest_db = client_dest.get_default_database()
            if dest_db is None or dest_db.name in ("admin", "test"):
                dest_db = client_dest[mongodb.name]
        except Exception:
            dest_db = client_dest[mongodb.name]

        colls = await mongodb.list_collection_names()
        total_colls = 0
        total_docs = 0
        for cname in colls:
            if cname.startswith("system."):
                continue
            src_col = mongodb[cname]
            dst_col = dest_db[cname]
            ops = []
            async for doc in src_col.find({}):
                ops.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert=True))
                if len(ops) >= 500:
                    await dst_col.bulk_write(ops, ordered=False)
                    total_docs += len(ops)
                    ops.clear()
            if ops:
                await dst_col.bulk_write(ops, ordered=False)
                total_docs += len(ops)
            total_colls += 1

        await status_msg.edit_text(
            "<b>Database Transfer Complete</b>\n\n"
            f"• <b>Target DB Name:</b> <code>{dest_db.name}</code>\n"
            f"• <b>Collections Copied:</b> <code>{total_colls}</code>\n"
            f"• <b>Documents Transferred:</b> <code>{total_docs}</code>\n\n"
            "<i>Ab aap Railway/.env mein MONGO_DB_URI update karke bot restart kar sakte hain.</i>"
        )
    except Exception as e:
        await status_msg.edit_text(f"<b>DB Transfer Failed:</b> <code>{e}</code>")
    finally:
        if client_dest is not None:
            client_dest.close()
