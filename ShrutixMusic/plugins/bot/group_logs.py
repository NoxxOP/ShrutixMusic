import html
import time

from pyrogram.enums import ChatMemberStatus, ChatType

import config
from ShrutixMusic import nand
from ShrutixMusic.utils.database import (
    delete_chat_link,
    get_chat_link,
    remove_served_chat,
    save_chat_link,
)

NOT_APPLICABLE = "Not Applicable"
OUT_OF_CHAT = (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED)
GROUP_TYPES = (ChatType.GROUP, ChatType.SUPERGROUP)
DEDUPE_SECONDS = 30

_recent = {}


def _already_logged(chat_id, kind):
    now = time.time()
    for key in [k for k, t in _recent.items() if now - t > DEDUPE_SECONDS]:
        _recent.pop(key, None)
    key = (chat_id, kind)
    if key in _recent:
        return True
    _recent[key] = now
    return False


def _who(user):
    if not user:
        return NOT_APPLICABLE, NOT_APPLICABLE
    try:
        mention = user.mention
    except Exception:
        mention = html.escape(str(getattr(user, "first_name", "") or user.id))
    return mention, f"<code>{user.id}</code>"


def _link_text(link):
    return html.escape(link) if link else NOT_APPLICABLE


def _can_invite(member):
    rights = getattr(member, "privileges", None)
    return (
        member is not None
        and member.status == ChatMemberStatus.ADMINISTRATOR
        and rights is not None
        and bool(getattr(rights, "can_invite_users", False))
    )


async def _current_link(chat, member):
    if getattr(chat, "username", None):
        return f"https://t.me/{chat.username}"
    if _can_invite(member):
        try:
            full = await nand.get_chat(chat.id)
            return full.invite_link or None
        except Exception:
            return None
    return None


async def _send_log(text):
    try:
        await nand.send_message(
            config.LOGGER_ID, text
        )
    except Exception as ex:
        print(ex)


async def _on_added(update, member):
    chat = update.chat
    link = await _current_link(chat, member)
    if link:
        try:
            await save_chat_link(chat.id, link)
        except Exception as ex:
            print(ex)
    adder, adder_id = _who(update.from_user)
    await _send_log(
        f"<b>➕ {nand.mention} ᴀᴅᴅᴇᴅ ɪɴ ᴀ ɴᴇᴡ ɢʀᴏᴜᴘ</b>\n\n"
        f"<b>ɢʀᴏᴜᴘ :</b> {html.escape(chat.title or NOT_APPLICABLE)}\n"
        f"<b>ɢʀᴏᴜᴘ ɪᴅ :</b> <code>{chat.id}</code>\n"
        f"<b>ɢʀᴏᴜᴘ ʟɪɴᴋ :</b> {_link_text(link)}\n\n"
        f"<b>ᴀᴅᴅᴇᴅ ʙʏ :</b> {adder}\n"
        f"<b>ᴜsᴇʀ ɪᴅ :</b> {adder_id}"
    )


async def _on_removed(update):
    chat = update.chat
    link = None
    if getattr(chat, "username", None):
        link = f"https://t.me/{chat.username}"
    if not link:
        try:
            link = await get_chat_link(chat.id)
        except Exception:
            link = None
    actor = update.from_user
    if actor and actor.id == nand.id:
        remover, remover_id = "ʙᴏᴛ ɪᴛsᴇʟғ (ʟᴇғᴛ ᴛʜᴇ ɢʀᴏᴜᴘ)", NOT_APPLICABLE
    else:
        remover, remover_id = _who(actor)
    await _send_log(
        f"<b>➖ {nand.mention} ʀᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ ᴀ ɢʀᴏᴜᴘ</b>\n\n"
        f"<b>ɢʀᴏᴜᴘ :</b> {html.escape(chat.title or NOT_APPLICABLE)}\n"
        f"<b>ɢʀᴏᴜᴘ ɪᴅ :</b> <code>{chat.id}</code>\n"
        f"<b>ɢʀᴏᴜᴘ ʟɪɴᴋ :</b> {_link_text(link)}\n\n"
        f"<b>ʀᴇᴍᴏᴠᴇᴅ ʙʏ :</b> {remover}\n"
        f"<b>ᴜsᴇʀ ɪᴅ :</b> {remover_id}"
    )
    for cleanup in (delete_chat_link, remove_served_chat):
        try:
            await cleanup(chat.id)
        except Exception as ex:
            print(ex)


async def _refresh_link(update, member):
    if not _can_invite(member):
        return
    link = await _current_link(update.chat, member)
    if link:
        await save_chat_link(update.chat.id, link)


@nand.on_chat_member_updated()
async def bot_membership_changed(client, update):
    try:
        new = update.new_chat_member
        old = update.old_chat_member
        member = new or old
        if not member or not member.user or member.user.id != nand.id:
            return
        if update.chat.type not in GROUP_TYPES:
            return
        was_in = old is not None and old.status not in OUT_OF_CHAT
        now_in = new is not None and new.status not in OUT_OF_CHAT
        if now_in and not was_in:
            if not _already_logged(update.chat.id, "added"):
                await _on_added(update, new)
        elif was_in and not now_in:
            if not _already_logged(update.chat.id, "removed"):
                await _on_removed(update)
        elif now_in:
            await _refresh_link(update, new)
    except Exception as ex:
        print(ex)
