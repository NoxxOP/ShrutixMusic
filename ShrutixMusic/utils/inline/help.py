import random
from typing import Union

from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ShrutixMusic import nand

PAGE_ONE = ["hb1", "hb2", "hb3", "hb4", "hb5", "hb6", "hb7", "hb8", "hb9"]
PAGE_TWO = ["hb10", "hb11", "hb12", "hb13", "hb14", "hb15", "hb16"]
NAV_STYLES = (ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER)


def _chunk(items, size):
    return [items[i : i + size] for i in range(0, len(items), size)]


def _mark_button(_, START, style):
    if START:
        return InlineKeyboardButton(
            text=_["BACK_BUTTON"], callback_data="settingsback_helper", style=style
        )
    return InlineKeyboardButton(
        text=_["CLOSE_BUTTON"], callback_data="close", style=style
    )


def help_pannel(_, START: Union[bool, int] = None, page: int = 1):
    sf = "1" if START else "0"
    items = PAGE_ONE if page == 1 else PAGE_TWO
    rows = _chunk(
        [
            InlineKeyboardButton(
                text=_[f"H_B_{key[2:]}"],
                callback_data=f"help_callback {key} {sf}",
            )
            for key in items
        ],
        3,
    )
    style = random.choice(NAV_STYLES)
    mark = _mark_button(_, START, style)
    if page == 1:
        nav = [
            mark,
            InlineKeyboardButton(
                text=_["NEXT_BUTTON"],
                callback_data=f"help_page 2 {sf}",
                style=style,
            ),
        ]
    else:
        nav = [
            InlineKeyboardButton(
                text=_["PREV_BUTTON"],
                callback_data=f"help_page 1 {sf}",
                style=style,
            ),
            mark,
        ]
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def help_back_markup(_, page: int = 1, START: Union[bool, int] = None):
    sf = "1" if START else "0"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=_["BACK_BUTTON"], callback_data=f"help_page {page} {sf}"
                )
            ]
        ]
    )


def private_help_panel(_):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["S_B_4"],
                url=f"https://t.me/{nand.username}?start=help",
            ),
        ],
    ]
    return buttons
