import asyncio
import html
import json
import os
import random
import time
from types import SimpleNamespace
from uuid import uuid4

from PIL import Image
from py_yt import VideosSearch
from pyrogram import filters, types
from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import BANNED_USERS, DURATION_LIMIT, DURATION_LIMIT_MIN
from ShrutixMusic import YouTube, nand
from ShrutixMusic.misc import SUDOERS, db
from ShrutixMusic.platforms.Youtube import is_external_path
from ShrutixMusic.utils.decorators.language import language, languageCB
from ShrutixMusic.utils.formatters import time_to_seconds
from ShrutixMusic.utils.rich_stream import caption_blocks, deliver_rich, edit_rich
from ShrutixMusic.utils.thumbnails import get_thumb

COOLDOWN = 4
SESSION_TTL = 3600
SESSION_MAX = 400
RESULT_LIMIT = 5
MAX_BYTES = 2000 * 1024 * 1024
NAV_STYLES = (ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER)

_sessions = {}
_cooldown = {}
_busy = set()
_in_use = {}
_convert_gate = asyncio.Semaphore(2)


class SongError(Exception):
    def __init__(self, key):
        super().__init__(key)
        self.key = key


def _prune_sessions():
    now = time.time()
    for token in [t for t, s in _sessions.items() if now - s["at"] > SESSION_TTL]:
        _sessions.pop(token, None)
    while len(_sessions) > SESSION_MAX:
        _sessions.pop(next(iter(_sessions)))


def _new_session(user_id, results):
    _prune_sessions()
    token = uuid4().hex[:8]
    _sessions[token] = {"user": user_id, "results": results, "at": time.time()}
    return token


def _seconds(text):
    try:
        return time_to_seconds(text) if text else 0
    except Exception:
        return 0


def _normalize(result):
    video_id = result.get("id")
    if not video_id:
        return None
    duration = result.get("duration")
    return {
        "id": video_id,
        "title": (result.get("title") or "Unknown")[:90],
        "duration": duration,
        "seconds": _seconds(duration),
        "channel": (result.get("channel") or {}).get("name") or "Unknown",
        "views": (result.get("viewCount") or {}).get("short") or "Unknown",
        "published": result.get("publishedTime") or "Unknown",
        "link": result.get("link") or f"https://www.youtube.com/watch?v={video_id}",
    }


async def _search(query):
    is_link = await YouTube.exists(query)
    search = VideosSearch(query, limit=1 if is_link else RESULT_LIMIT * 2)
    data = (await search.next()).get("result") or []
    items = []
    for result in data:
        item = _normalize(result)
        if not item:
            continue
        if not is_link and not item["seconds"]:
            continue
        items.append(item)
        if len(items) >= RESULT_LIMIT:
            break
    return items


async def _query_from(message):
    url = await YouTube.url(message)
    if url:
        return url
    parts = message.text.split(None, 1) if message.text else []
    if len(parts) > 1:
        return parts[1].strip()[:200]
    reply = message.reply_to_message
    if reply:
        text = reply.text or reply.caption
        if text:
            return text.strip()[:200]
    return ""


def _photo_block(photo):
    return types.InputRichBlockPhoto(photo=types.InputMediaPhoto(photo))


def _row(*buttons):
    return types.InputRichBlockButtons(buttons=list(buttons))


def _button(text, data=None, style=ButtonStyle.DEFAULT, url=None):
    if url:
        return types.RichMessageButton(text=text, style=style, url=url)
    return types.RichMessageButton(text=text, style=style, callback_data=data)


async def _panel_blocks(_, token, idx, notice=None):
    session = _sessions[token]
    results = session["results"]
    item = results[idx]
    photo = await get_thumb(item["id"])
    caption = _["SONG_PANEL"].format(
        item["link"],
        item["title"],
        item["channel"],
        item["duration"] or "Live",
        item["views"],
        item["published"],
    )
    blocks = [_photo_block(photo)] + caption_blocks(caption)
    if notice:
        blocks += caption_blocks(f"\n<b>{notice}</b>")
    blocks.append(
        _row(
            _button(_["SONG_BTN_AUDIO"], f"SONG a|{token}|{idx}", ButtonStyle.SUCCESS),
            _button(_["SONG_BTN_VIDEO"], f"SONG v|{token}|{idx}", ButtonStyle.PRIMARY),
        )
    )
    total = len(results)
    if total > 1:
        style = random.choice(NAV_STYLES)
        blocks.append(
            _row(
                _button("◁", f"SONG p|{token}|{(idx - 1) % total}", style),
                _button(f"{idx + 1} / {total}", "SONG n"),
                _button("▷", f"SONG p|{token}|{(idx + 1) % total}", style),
            )
        )
    blocks.append(
        _row(
            _button(_["SONG_BTN_WATCH"], style=ButtonStyle.DEFAULT, url=item["link"]),
            _button(_["CLOSE_BUTTON"], f"SONG x|{token}", ButtonStyle.DANGER),
        )
    )
    return blocks


async def _status_blocks(item, text):
    photo = await get_thumb(item["id"])
    blocks = [_photo_block(photo)]
    blocks += caption_blocks(f"<a href={item['link']}>{item['title']}</a>")
    blocks.append(_row(_button(text, "SONG n", ButtonStyle.PRIMARY)))
    return blocks


class Status:
    def __init__(self, message, item):
        self.message = message
        self.item = item
        self.last = 0
        self.percent = -1

    async def show(self, text, force=False):
        now = time.monotonic()
        if not force and now - self.last < 3:
            return
        self.last = now
        try:
            await edit_rich(self.message, await _status_blocks(self.item, text))
        except Exception:
            pass


async def _run(*cmd, timeout):
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
    )
    try:
        out, _err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise
    return proc.returncode, out


async def _probe(path):
    try:
        code, out = await _run(
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", path,
            timeout=30,
        )
        return json.loads(out) if code == 0 and out else {}
    except Exception:
        return {}


def _format_name(info):
    return (info.get("format") or {}).get("format_name", "")


def _duration(info, fallback=0):
    try:
        return int(float((info.get("format") or {}).get("duration")))
    except Exception:
        return fallback


def _video_size(info):
    for stream in info.get("streams") or []:
        if stream.get("codec_type") == "video":
            return int(stream.get("width") or 0), int(stream.get("height") or 0)
    return 0, 0


def _remove(path):
    try:
        if path and os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass


def _temp(ext):
    os.makedirs("cache", exist_ok=True)
    return os.path.join("cache", f"song_{uuid4().hex[:10]}.{ext}")


async def _prepare_audio(path, status, _):
    info = await _probe(path)
    name = _format_name(info)
    duration = _duration(info)
    if name.split(",")[0] == "mp3" or (not name and path.lower().endswith(".mp3")):
        return SimpleNamespace(path=path, temp=None, duration=duration)
    await status.show(_["SONG_STATUS_CONVERT"], force=True)
    out = _temp("mp3")
    async with _convert_gate:
        try:
            code, _out = await _run(
                "ffmpeg", "-y", "-i", path, "-vn", "-map_metadata", "-1",
                "-c:a", "libmp3lame", "-b:a", "192k", out,
                timeout=600,
            )
        except Exception:
            code = 1
    if code != 0 or not os.path.isfile(out):
        _remove(out)
        raise SongError("SONG_FAILED")
    return SimpleNamespace(path=out, temp=out, duration=duration)


async def _prepare_video(path, status, _):
    info = await _probe(path)
    name = _format_name(info)
    duration = _duration(info)
    width, height = _video_size(info)
    if "mp4" in name or (not name and path.lower().endswith(".mp4")):
        return SimpleNamespace(
            path=path, temp=None, duration=duration, width=width, height=height, video=True
        )
    await status.show(_["SONG_STATUS_CONVERT"], force=True)
    out = _temp("mp4")
    async with _convert_gate:
        try:
            code, _out = await _run(
                "ffmpeg", "-y", "-i", path, "-c", "copy", "-movflags", "+faststart", out,
                timeout=600,
            )
        except Exception:
            code = 1
    if code == 0 and os.path.isfile(out):
        return SimpleNamespace(
            path=out, temp=out, duration=duration, width=width, height=height, video=True
        )
    _remove(out)
    return SimpleNamespace(
        path=path, temp=None, duration=duration, width=width, height=height, video=False
    )


def _small_thumb(photo):
    if not photo or not os.path.isfile(str(photo)):
        return None
    out = _temp("jpg")
    try:
        with Image.open(photo) as image:
            image = image.convert("RGB")
            image.thumbnail((320, 320))
            image.save(out, "JPEG", quality=85)
        return out
    except Exception:
        _remove(out)
        return None


def _in_queue(path):
    for queue in db.values():
        for item in queue or []:
            if item.get("file") == path:
                return True
    return False


def _release_download(path):
    count = _in_use.get(path, 1) - 1
    if count > 0:
        _in_use[path] = count
        return
    _in_use.pop(path, None)
    if is_external_path(path) or _in_queue(path):
        return
    _remove(path)


async def _fetch(item, kind):
    result = await YouTube.download(
        item["id"], None, video=True if kind == "v" else None, videoid=True
    )
    path = result[0] if isinstance(result, tuple) else result
    if not path or not os.path.isfile(path):
        raise SongError("SONG_FAILED")
    return path


def _final_markup(_, item, user_id):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=_["SONG_BTN_WATCH"], url=item["link"], style=ButtonStyle.PRIMARY
                ),
                InlineKeyboardButton(
                    text=_["CLOSE_BUTTON"],
                    callback_data=f"SONG d|{user_id}",
                    style=ButtonStyle.DANGER,
                ),
            ]
        ]
    )


async def _send_file(client, cq, _, item, kind, path, status):
    thumb = None
    media = None
    try:
        if kind == "a":
            media = await _prepare_audio(path, status, _)
        else:
            media = await _prepare_video(path, status, _)
        if os.path.getsize(media.path) > MAX_BYTES:
            raise SongError("SONG_TOO_BIG")
        thumb = _small_thumb(await get_thumb(item["id"]))
        seconds = media.duration or item["seconds"]
        caption = _["SONG_CAPTION"].format(
            html.escape(item["title"]),
            html.escape(item["channel"]),
            item["duration"] or "Live",
            cq.from_user.mention,
            nand.mention,
        )
        chat_id = cq.message.chat.id
        options = {"reply_markup": _final_markup(_, item, cq.from_user.id)}
        thread = getattr(cq.message, "message_thread_id", None)
        if thread:
            options["message_thread_id"] = thread

        async def progress(current, total):
            if not total:
                return
            percent = int(current * 100 / total)
            if percent == status.percent:
                return
            status.percent = percent
            await status.show(_["SONG_STATUS_UPLOAD"].format(percent))

        await status.show(_["SONG_STATUS_UPLOAD"].format(0), force=True)
        file_name = "".join(c for c in item["title"] if c not in '\\/:*?"<>|').strip() or item["id"]
        if kind == "a":
            await client.send_audio(
                chat_id,
                media.path,
                caption=caption,
                duration=seconds,
                performer=item["channel"],
                title=item["title"],
                thumb=thumb,
                file_name=f"{file_name}.mp3",
                progress=progress,
                **options,
            )
        elif media.video:
            await client.send_video(
                chat_id,
                media.path,
                caption=caption,
                duration=seconds,
                width=media.width,
                height=media.height,
                thumb=thumb,
                file_name=f"{file_name}.mp4",
                supports_streaming=True,
                progress=progress,
                **options,
            )
        else:
            await client.send_document(
                chat_id,
                media.path,
                caption=caption,
                thumb=thumb,
                file_name=f"{file_name}.mp4",
                progress=progress,
                **options,
            )
    finally:
        if media and media.temp:
            _remove(media.temp)
        _remove(thumb)


async def _download_flow(client, cq, _, token, idx, kind):
    session = _sessions[token]
    item = session["results"][idx]
    panel = cq.message
    status = Status(panel, item)
    path = None
    try:
        word = _["SONG_WORD_AUDIO"] if kind == "a" else _["SONG_WORD_VIDEO"]
        await status.show(_["SONG_STATUS_DOWNLOAD"].format(word), force=True)
        path = await _fetch(item, kind)
        _in_use[path] = _in_use.get(path, 0) + 1
        await _send_file(client, cq, _, item, kind, path, status)
    except SongError as e:
        await _restore_panel(_, panel, token, idx, _[e.key])
        return
    except Exception:
        await _restore_panel(_, panel, token, idx, _["SONG_FAILED"])
        return
    finally:
        if path:
            _release_download(path)
    try:
        await panel.delete()
    except Exception:
        pass


async def _restore_panel(_, panel, token, idx, notice):
    try:
        await edit_rich(panel, await _panel_blocks(_, token, idx, notice))
    except Exception:
        pass


async def _delete_later(message, seconds):
    await asyncio.sleep(seconds)
    try:
        await message.delete()
    except Exception:
        pass


def _close_markup(_, user_id):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=_["CLOSE_BUTTON"],
                    callback_data=f"SONG d|{user_id}",
                    style=ButtonStyle.DANGER,
                )
            ]
        ]
    )


@nand.on_message(filters.command(["song"]) & ~BANNED_USERS)
@language
async def song_command(client, message, _):
    user = message.from_user
    if not user:
        return
    now = time.time()
    if now - _cooldown.get(user.id, 0) < COOLDOWN:
        notice = await message.reply_text(_["SONG_COOLDOWN"])
        asyncio.ensure_future(_delete_later(notice, 4))
        return
    if len(_cooldown) > 2000:
        _cooldown.clear()
    _cooldown[user.id] = now
    query = await _query_from(message)
    if not query:
        return await message.reply_text(
            _["SONG_USAGE"], reply_markup=_close_markup(_, user.id)
        )
    mystic = await message.reply_text(_["SONG_SEARCHING"])
    try:
        results = await _search(query)
    except Exception:
        return await mystic.edit_text(
            _["SONG_FAILED"], reply_markup=_close_markup(_, user.id)
        )
    if not results:
        return await mystic.edit_text(
            _["SONG_NOT_FOUND"], reply_markup=_close_markup(_, user.id)
        )
    token = _new_session(user.id, results)
    blocks = await _panel_blocks(_, token, 0)
    await deliver_rich(client, message.chat.id, blocks, replace=mystic)
    for other in results[1:]:
        asyncio.ensure_future(get_thumb(other["id"]))


@nand.on_callback_query(filters.regex(r"^SONG ") & ~BANNED_USERS)
@languageCB
async def song_callback(client, cq, _):
    try:
        await _handle(client, cq, _)
    except Exception:
        try:
            await cq.answer(_["SONG_FAILED"], show_alert=True)
        except Exception:
            pass


async def _handle(client, cq, _):
    payload = cq.data.split(" ", 1)[1]
    action, _sep, rest = payload.partition("|")
    user = cq.from_user
    if action == "n":
        return await cq.answer()
    if action == "d":
        if str(user.id) != rest and user.id not in SUDOERS:
            return await cq.answer(_["SONG_NOT_YOURS"], show_alert=True)
        await cq.answer()
        return await cq.message.delete()
    token, _sep, idx_text = rest.partition("|")
    session = _sessions.get(token)
    if not session:
        if action == "x":
            await cq.answer()
            return await cq.message.delete()
        return await cq.answer(_["SONG_EXPIRED"], show_alert=True)
    if user.id != session["user"] and user.id not in SUDOERS:
        return await cq.answer(_["SONG_NOT_YOURS"], show_alert=True)
    if action == "x":
        _sessions.pop(token, None)
        await cq.answer()
        return await cq.message.delete()
    total = len(session["results"])
    idx = min(int(idx_text), total - 1) if idx_text.isdigit() else 0
    if action == "p":
        await cq.answer()
        await edit_rich(cq.message, await _panel_blocks(_, token, idx))
        for step in (1, -1):
            asyncio.ensure_future(get_thumb(session["results"][(idx + step) % total]["id"]))
        return
    if action not in ("a", "v"):
        return await cq.answer()
    item = session["results"][idx]
    key = (cq.message.chat.id, cq.message.id)
    if key in _busy:
        return await cq.answer(_["SONG_BUSY"], show_alert=True)
    if not item["seconds"]:
        return await cq.answer(_["SONG_LIVE"], show_alert=True)
    if item["seconds"] > DURATION_LIMIT:
        return await cq.answer(
            _["SONG_TOO_LONG"].format(DURATION_LIMIT_MIN), show_alert=True
        )
    _busy.add(key)
    try:
        await cq.answer()
        await _download_flow(client, cq, _, token, idx, action)
    finally:
        _busy.discard(key)
