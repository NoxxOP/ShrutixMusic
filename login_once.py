import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())

import config
from pyrogram import Client


async def main():
    app = Client(
        name="ShrutixMusic",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        workdir=os.getcwd(),
    )
    await app.start()
    me = await app.get_me()
    print("LOGIN OK:", me.username)
    await app.stop()
    print("Session file:", os.path.join(os.getcwd(), "ShrutixMusic.session"))


asyncio.run(main())
