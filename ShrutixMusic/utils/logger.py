from pyrogram.enums import ParseMode

from ShrutixMusic import nand
from ShrutixMusic.utils.database import is_on_off
from config import LOGGER_ID


async def play_logs(message, streamtype):
    if await is_on_off(2):
        logger_text = f"""
<b>{nand.mention} ᴘʟᴀʏ ʟᴏɢ</b>

<b>ᴄʜᴀᴛ ɪᴅ :</b> <code>{message.chat.id}</code>
<b>ᴄʜᴀᴛ ɴᴀᴍᴇ :</b> {message.chat.title}
<b>ᴄʜᴀᴛ ᴜsᴇʀɴᴀᴍᴇ :</b> @{message.chat.username}

<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code>
<b>ɴᴀᴍᴇ :</b> {message.from_user.mention}
<b>ᴜsᴇʀɴᴀᴍᴇ :</b> @{message.from_user.username}

<b>ǫᴜᴇʀʏ :</b> {message.text.split(None, 1)[1]}
<b>sᴛʀᴇᴀᴍᴛʏᴘᴇ :</b> {streamtype}"""
        if message.chat.id != LOGGER_ID:
            try:
                await nand.send_message(
                    chat_id=LOGGER_ID,
                    text=logger_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            except:
                pass
        return


async def autoplay_logs(chat_id, title, video_id, previous_title, video=False):
    if not await is_on_off(2):
        return
    if chat_id == LOGGER_ID:
        return
    try:
        chat = await nand.get_chat(chat_id)
        chat_title = chat.title
        chat_username = chat.username
    except Exception:
        chat_title = "Unknown"
        chat_username = None
    streamtype = "Autoplay Video" if video else "Autoplay Audio"
    logger_text = f"""
<b>{nand.mention} ᴀᴜᴛᴏᴘʟᴀʏ ʟᴏɢ</b>

<b>ᴄʜᴀᴛ ɪᴅ :</b> <code>{chat_id}</code>
<b>ᴄʜᴀᴛ ɴᴀᴍᴇ :</b> {chat_title}
<b>ᴄʜᴀᴛ ᴜsᴇʀɴᴀᴍᴇ :</b> @{chat_username}

<b>ᴘʀᴇᴠɪᴏᴜs ᴛʀᴀᴄᴋ :</b> {previous_title}
<b>ǫᴜᴇʀʏ :</b> <a href="https://www.youtube.com/watch?v={video_id}">{title}</a>
<b>sᴛʀᴇᴀᴍᴛʏᴘᴇ :</b> {streamtype}"""
    try:
        await nand.send_message(
            chat_id=LOGGER_ID,
            text=logger_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except:
        pass
