import os

from config import autoclean
from ShrutixMusic.platforms.Youtube import is_external_path


async def auto_clean(popped):
    try:
        rem = popped["file"]
        autoclean.remove(rem)
        if is_external_path(rem):
            return
        count = autoclean.count(rem)
        if count == 0:
            if "vid_" not in rem or "live_" not in rem or "index_" not in rem:
                try:
                    os.remove(rem)
                except:
                    pass
    except:
        pass
