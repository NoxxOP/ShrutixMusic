from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message

import config
from ShrutixMusic import YouTube, nand
from ShrutixMusic.core.call import Shruti
from ShrutixMusic.misc import db
from ShrutixMusic.utils.database import get_loop
from ShrutixMusic.utils.decorators import AdminRightsCheck
from ShrutixMusic.utils.inline import close_markup
from ShrutixMusic.utils.rich_stream import send_now_playing_rich
from ShrutixMusic.utils.stream.autoclear import auto_clean
from ShrutixMusic.utils.stream.autoplay import try_autoplay
from ShrutixMusic.utils.stream.history import record_played
from ShrutixMusic.utils.thumbnails import get_thumb
from config import BANNED_USERS


@nand.on_message(
    filters.command(["skip", "cskip", "next", "cnext"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def skip(cli, message: Message, _, chat_id):
    if not len(message.command) < 2:
        loop = await get_loop(chat_id)
        if loop != 0:
            return await message.reply_text(_["admin_8"])
        state = message.text.split(None, 1)[1].strip()
        if state.isnumeric():
            state = int(state)
            check = db.get(chat_id)
            if check:
                count = len(check)
                if count > 2:
                    count = int(count - 1)
                    if 1 <= state <= count:
                        for x in range(state):
                            popped = None
                            try:
                                popped = check.pop(0)
                            except:
                                return await message.reply_text(_["admin_12"])
                            if popped:
                                await auto_clean(popped)
                            if not check:
                                if await try_autoplay(chat_id, popped):
                                    return
                                try:
                                    await message.reply_text(
                                        text=_["admin_6"].format(
                                            message.from_user.mention,
                                            message.chat.title,
                                        ),
                                        reply_markup=close_markup(_),
                                    )
                                    await Shruti.stop_stream(chat_id)
                                except:
                                    return
                                break
                    else:
                        return await message.reply_text(_["admin_11"].format(count))
                else:
                    return await message.reply_text(_["admin_10"])
            else:
                return await message.reply_text(_["queue_2"])
        else:
            return await message.reply_text(_["admin_9"])
    else:
        check = db.get(chat_id)
        popped = None
        try:
            popped = check.pop(0)
            if popped:
                await auto_clean(popped)
            if not check:
                if await try_autoplay(chat_id, popped):
                    return
                await message.reply_text(
                    text=_["admin_6"].format(
                        message.from_user.mention, message.chat.title
                    ),
                    reply_markup=close_markup(_),
                )
                try:
                    return await Shruti.stop_stream(chat_id)
                except:
                    return
        except:
            try:
                await message.reply_text(
                    text=_["admin_6"].format(
                        message.from_user.mention, message.chat.title
                    ),
                    reply_markup=close_markup(_),
                )
                return await Shruti.stop_stream(chat_id)
            except:
                return
    queued = check[0]["file"]
    title = (check[0]["title"]).title()
    user = check[0]["by"]
    streamtype = check[0]["streamtype"]
    videoid = check[0]["vidid"]
    if videoid and videoid not in ("telegram", "soundcloud"):
        record_played(chat_id, videoid)
    status = True if str(streamtype) == "video" else None
    db[chat_id][0]["played"] = 0
    exis = (check[0]).get("old_dur")
    if exis:
        db[chat_id][0]["dur"] = exis
        db[chat_id][0]["seconds"] = check[0]["old_second"]
        db[chat_id][0]["speed_path"] = None
        db[chat_id][0]["speed"] = 1.0
    if "live_" in queued:
        n, link = await YouTube.video(videoid, True)
        if n == 0:
            return await message.reply_text(_["admin_7"].format(title))
        try:
            image = await YouTube.thumbnail(videoid, True)
        except:
            image = None
        try:
            await Shruti.skip_stream(chat_id, link, video=status, image=image)
        except:
            return await message.reply_text(_["call_6"])
        img = await get_thumb(videoid)
        run = await send_now_playing_rich(
            nand,
            chat_id,
            message.chat.id,
            img,
            _["stream_1"].format(
                f"https://t.me/{nand.username}?start=info_{videoid}",
                title[:23],
                check[0]["dur"],
                user,
            ),
        )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "tg"
    elif "vid_" in queued:
        mystic = await message.reply_text(_["call_7"])
        try:
            file_path, direct = await YouTube.download(
                videoid,
                mystic,
                videoid=True,
                video=status,
            )
        except:
            return await mystic.edit_text(_["call_6"])
        try:
            image = await YouTube.thumbnail(videoid, True)
        except:
            image = None
        try:
            await Shruti.skip_stream(chat_id, file_path, video=status, image=image)
        except:
            return await mystic.edit_text(_["call_6"])
        img = await get_thumb(videoid)
        run = await send_now_playing_rich(
            nand,
            chat_id,
            message.chat.id,
            img,
            _["stream_1"].format(
                f"https://t.me/{nand.username}?start=info_{videoid}",
                title[:23],
                check[0]["dur"],
                user,
            ),
        )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "stream"
        await mystic.delete()
    elif "index_" in queued:
        try:
            await Shruti.skip_stream(chat_id, videoid, video=status)
        except:
            return await message.reply_text(_["call_6"])
        run = await send_now_playing_rich(
            nand,
            chat_id,
            message.chat.id,
            config.STREAM_IMG_URL,
            _["stream_2"].format(user),
        )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "tg"
    else:
        if videoid == "telegram":
            image = None
        elif videoid == "soundcloud":
            image = None
        else:
            try:
                image = await YouTube.thumbnail(videoid, True)
            except:
                image = None
        try:
            await Shruti.skip_stream(chat_id, queued, video=status, image=image)
        except:
            return await message.reply_text(_["call_6"])
        if videoid == "telegram":
            run = await send_now_playing_rich(
                nand,
                chat_id,
                message.chat.id,
                config.TELEGRAM_AUDIO_URL
                if str(streamtype) == "audio"
                else config.TELEGRAM_VIDEO_URL,
                _["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                ),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
        elif videoid == "soundcloud":
            run = await send_now_playing_rich(
                nand,
                chat_id,
                message.chat.id,
                config.SOUNCLOUD_IMG_URL
                if str(streamtype) == "audio"
                else config.TELEGRAM_VIDEO_URL,
                _["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                ),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
        else:
            img = await get_thumb(videoid)
            run = await send_now_playing_rich(
                nand,
                chat_id,
                message.chat.id,
                img,
                _["stream_1"].format(
                    f"https://t.me/{nand.username}?start=info_{videoid}",
                    title[:23],
                    check[0]["dur"],
                    user,
                ),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"
