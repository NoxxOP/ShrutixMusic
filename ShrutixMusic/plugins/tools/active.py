import asyncio
import time

from pyrogram import filters, types
from pyrogram.enums import ButtonStyle
from pyrogram.types import Message
from unidecode import unidecode

from ShrutixMusic import nand
from ShrutixMusic.misc import SUDOERS
from ShrutixMusic.utils.database import (
    get_active_chats,
    get_active_video_chats,
    get_lang,
    remove_active_chat,
    remove_active_video_chat,
)
from ShrutixMusic.utils.rich_stream import caption_blocks, edit_rich
from strings import get_string

FETCH_CONCURRENCY = 15
DISPLAY_LIMIT = 60
REFRESH_COOLDOWN = 5

_gate = asyncio.Semaphore(FETCH_CONCURRENCY)
_last_refresh = {}


async def _lang(chat_id):
    return get_string(await get_lang(chat_id))


async def _resolve(chat_id, drop):
    async with _gate:
        try:
            chat = await nand.get_chat(chat_id)
        except Exception:
            await drop(chat_id)
            return None
    title = unidecode((chat.title or str(chat_id)).strip()).upper() or str(chat_id)
    return {"id": chat_id, "title": title, "username": chat.username}


async def _resolve_all(chat_ids, drop):
    tasks = [asyncio.ensure_future(_resolve(cid, drop)) for cid in chat_ids]
    resolved = await asyncio.gather(*tasks) if tasks else []
    return [r for r in resolved if r]


def _entry_line(index, chat):
    label = f"{index}. {chat['title']}"
    if chat["username"]:
        line = f'<a href="https://t.me/{chat["username"]}">{label}</a>'
    else:
        line = label
    return f"{line}  <code>{chat['id']}</code>"


def _build_caption(_, kind_label, chats, elapsed):
    if not chats:
        return _["ACTIVE_EMPTY"].format(kind_label, nand.mention)
    shown = chats[:DISPLAY_LIMIT]
    body = "\n".join(_entry_line(i, chat) for i, chat in enumerate(shown, start=1))
    remaining = len(chats) - len(shown)
    if remaining > 0:
        body += "\n\n" + _["ACTIVE_MORE"].format(remaining)
    return _["ACTIVE_LIST"].format(kind_label, len(chats), nand.mention, body, elapsed)


def _button(_, key, data, style):
    return types.RichMessageButton(text=_[key], style=style, callback_data=data)


def _controls(_, kind):
    return [
        types.InputRichBlockButtons(
            buttons=[
                _button(_, "ACTIVE_BTN_REFRESH", f"ACTIVE r|{kind}", ButtonStyle.SUCCESS),
                _button(_, "ACTIVE_BTN_CLOSE", "ACTIVE x", ButtonStyle.DANGER),
            ]
        )
    ]


async def _fetch(kind):
    if kind == "vc":
        chat_ids = await get_active_chats()
        chats = await _resolve_all(chat_ids, remove_active_chat)
    else:
        chat_ids = await get_active_video_chats()
        chats = await _resolve_all(chat_ids, remove_active_video_chat)
    return chats


async def _render(_, kind, message):
    label = _["ACTIVE_KIND_VOICE"] if kind == "vc" else _["ACTIVE_KIND_VIDEO"]
    started = time.monotonic()
    chats = await _fetch(kind)
    elapsed = round(time.monotonic() - started, 2)
    caption = _build_caption(_, label, chats, elapsed)
    blocks = caption_blocks(caption) + _controls(_, kind)
    return await edit_rich(message, blocks)


async def _launch(message: Message, kind):
    _ = await _lang(message.chat.id)
    loading = await message.reply_text(_["ACTIVE_LOADING"])
    try:
        await _render(_, kind, loading)
    except Exception:
        try:
            await loading.edit_text(_["ACTIVE_FAILED"])
        except Exception:
            pass


@nand.on_message(filters.command(["activevc", "activevoice", "activechats", "avc", "ac"]) & SUDOERS)
async def activevc(client, message: Message):
    await _launch(message, "vc")


@nand.on_message(filters.command(["activev", "activevideo", "activevideos", "avideo", "av"]) & SUDOERS)
async def activevi_(client, message: Message):
    await _launch(message, "video")


@nand.on_callback_query(filters.regex(r"^ACTIVE ") & SUDOERS)
async def active_callback(client, cq):
    _ = await _lang(cq.message.chat.id)
    action, _sep, kind = cq.data.split(" ", 1)[1].partition("|")
    if action == "x":
        await cq.answer()
        return await cq.message.delete()
    if action != "r":
        return await cq.answer()
    key = (cq.message.chat.id, cq.message.id)
    now = time.monotonic()
    if now - _last_refresh.get(key, 0) < REFRESH_COOLDOWN:
        return await cq.answer(_["ACTIVE_WAIT"], show_alert=False)
    _last_refresh[key] = now
    await cq.answer(_["ACTIVE_REFRESHING"])
    try:
        await _render(_, kind, cq.message)
    except Exception:
        await cq.answer(_["ACTIVE_FAILED"], show_alert=True)
