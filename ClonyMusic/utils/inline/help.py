from typing import Union
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from ClonyMusic import app

def help_pannel(_, START: Union[bool, int] = None):
    first = [
        [
            InlineKeyboardButton(text=_["H_B_1"], callback_data="help_callback hb1"),
            InlineKeyboardButton(text=_["H_B_2"], callback_data="help_callback hb2"),
            InlineKeyboardButton(text=_["H_B_6"], callback_data="help_callback hb6"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_8"], callback_data="help_callback hb8"),
            InlineKeyboardButton(text=_["H_B_10"], callback_data="help_callback hb10"),
            InlineKeyboardButton(text=_["H_B_11"], callback_data="help_callback hb11"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_12"], callback_data="help_callback hb12"),
            InlineKeyboardButton(text=_["H_B_13"], callback_data="help_callback hb13"),
            InlineKeyboardButton(text=_["H_B_14"], callback_data="help_callback hb14"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_15"], callback_data="help_callback hb15"),
            InlineKeyboardButton(text="ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs", callback_data="help_callback all_features"),
        ],
        [
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="settingsback_helper"),
        ],
    ]
    return InlineKeyboardMarkup(first)


def first_page(_, is_owner: bool = False):
    first = [
        [
            InlineKeyboardButton(text=_["H_B_1"], callback_data="help_callback hb1"),
            InlineKeyboardButton(text=_["H_B_2"], callback_data="help_callback hb2"),
            InlineKeyboardButton(text=_["H_B_6"], callback_data="help_callback hb6"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_8"], callback_data="help_callback hb8"),
            InlineKeyboardButton(text=_["H_B_10"], callback_data="help_callback hb10"),
            InlineKeyboardButton(text=_["H_B_11"], callback_data="help_callback hb11"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_12"], callback_data="help_callback hb12"),
            InlineKeyboardButton(text=_["H_B_13"], callback_data="help_callback hb13"),
            InlineKeyboardButton(text=_["H_B_14"], callback_data="help_callback hb14"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_15"], callback_data="help_callback hb15"),
            InlineKeyboardButton(text="ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs", callback_data="help_callback all_features"),
        ],
    ]

    if is_owner:
        first.append([
            InlineKeyboardButton(text="ᴄʟᴏɴᴇ ғᴇᴀᴛᴜʀᴇs", callback_data="help_callback chelp"),
        ])

    first.append([
        InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="settingsback_home"),
    ])

    return InlineKeyboardMarkup(first)


def clone_help_panel(_):
    buttons = [
        [
            InlineKeyboardButton(text="ᴍᴀɴᴀɢᴇ", callback_data="help_callback clone_manage"),
        ],
        [
            # Start aur Ping ab upar hain
            InlineKeyboardButton(text="sᴛᴀʀᴛ", callback_data="help_callback clone_start"),
            InlineKeyboardButton(text="ᴘɪɴɢ", callback_data="help_callback clone_ping"),
        ],
        [
            InlineKeyboardButton(text="ᴘʟᴀʏ ᴍᴏᴅᴇ", callback_data="help_callback clone_play"),
            InlineKeyboardButton(text="ʟᴏɢɢᴇʀ", callback_data="help_callback clone_logger"),
        ],
        [
            # Merged Button
            InlineKeyboardButton(text="ʙᴜᴛᴛᴏɴs & ʀᴇɴᴀᴍᴇ", callback_data="help_callback clone_buttons"),
        ],
        [
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="settings_back_helper"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def clone_back_markup(_):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=_["BACK_BUTTON"],
                    callback_data="help_callback chelp",
                )
            ]
        ]
    )


def help_back_markup(_):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=_["BACK_BUTTON"],
                    callback_data="settings_back_helper",
                )
            ]
        ]
    )


def private_help_panel(_):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=_["S_B_4"],
                    url=f"https://t.me/{app.username}?start=help",
                )
            ]
        ]
    )
