import asyncio
import os
import wave
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls import filters as pt_filters
from pytgcalls.exceptions import (
    NoActiveGroupCall,
)
from pytgcalls.types import AudioQuality, ChatUpdate, GroupCallConfig, MediaStream, StreamEnded, VideoQuality

import config
from ShrutixMusic import LOGGER, YouTube, nand
from ShrutixMusic.misc import db
from ShrutixMusic.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_active_chat,
    is_autoend,
    music_on,
    music_off,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from ShrutixMusic.utils.exceptions import AssistantErr
from ShrutixMusic.utils.formatters import check_duration, seconds_to_min, speed_converter
from ShrutixMusic.utils.rich_stream import release_mystic, send_now_playing_rich
from ShrutixMusic.utils.stream.autoclear import auto_clean
from ShrutixMusic.utils.stream.autoplay import discard_prefetch, try_autoplay
from ShrutixMusic.utils.stream.history import record_played
from ShrutixMusic.utils.thumbnails import get_thumb
from strings import get_string

autoend = {}
counter = {}


async def _clear_(chat_id):
    current = db.get(chat_id) or []
    if current:
        await release_mystic(current[0].get("mystic"))
    db[chat_id] = []
    discard_prefetch(chat_id)
    await music_off(chat_id)
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)


PLACEHOLDER_SECONDS = 120

_video_placeholder_lock = asyncio.Lock()


def _silence_path():
    path = os.path.abspath(os.path.join("cache", "silence.wav"))
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with wave.open(path, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(1)
            f.setframerate(8000)
            f.writeframes(b"\x80" * 8000 * PLACEHOLDER_SECONDS)
    return path


async def _silence_video_path():
    path = os.path.abspath(os.path.join("cache", "silence.mp4"))
    if os.path.isfile(path) and os.path.getsize(path) > 0:
        return path
    async with _video_placeholder_lock:
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            return path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=320x180:r=15",
            "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono",
            "-t", str(PLACEHOLDER_SECONDS),
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", "-f", "mp4", tmp,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
        if proc.returncode != 0 or not os.path.isfile(tmp) or os.path.getsize(tmp) == 0:
            if os.path.isfile(tmp):
                os.remove(tmp)
            raise RuntimeError("silent video placeholder generation failed")
        os.replace(tmp, path)
    return path


class Call(PyTgCalls):
    def __init__(self):
        self.userbot1 = Client(
            name="ShrutiXAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.one = PyTgCalls(
            self.userbot1,
            cache_duration=100,
        )
        self.userbot2 = Client(
            name="ShrutiXAss2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
        )
        self.two = PyTgCalls(
            self.userbot2,
            cache_duration=100,
        )
        self.userbot3 = Client(
            name="ShrutiXAss3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
        )
        self.three = PyTgCalls(
            self.userbot3,
            cache_duration=100,
        )
        self.userbot4 = Client(
            name="ShrutiXAss4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
        )
        self.four = PyTgCalls(
            self.userbot4,
            cache_duration=100,
        )
        self.userbot5 = Client(
            name="ShrutiXAss5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
        )
        self.five = PyTgCalls(
            self.userbot5,
            cache_duration=100,
        )
        self._prejoin_tasks = {}
        self._prejoin_video = {}
        self._chat_locks = {}

    def chat_lock(self, chat_id: int):
        lock = self._chat_locks.get(chat_id)
        if lock is None:
            lock = asyncio.Lock()
            self._chat_locks[chat_id] = lock
        return lock

    async def _assistant_join(self, assistant, chat_id: int, stream, _):
        try:
            await assistant.play(
                chat_id,
                stream,
                config=GroupCallConfig(auto_start=False),
            )
        except NoActiveGroupCall:
            raise AssistantErr(_["call_8"])

    async def _run_prejoin(self, chat_id: int, video: bool = False):
        assistant = await group_assistant(self, chat_id)
        _ = get_string(await get_lang(chat_id))
        used_video = False
        if video:
            try:
                video_path = await _silence_video_path()
                stream = MediaStream(video_path, audio_parameters=AudioQuality.HIGH, video_parameters=VideoQuality.SD_480p)
                used_video = True
            except Exception:
                stream = MediaStream(_silence_path(), audio_parameters=AudioQuality.HIGH, video_flags=MediaStream.Flags.IGNORE)
        else:
            stream = MediaStream(_silence_path(), audio_parameters=AudioQuality.HIGH, video_flags=MediaStream.Flags.IGNORE)
        self._prejoin_video[chat_id] = used_video
        await self._assistant_join(assistant, chat_id, stream, _)

    async def prejoin_start(self, chat_id: int, video: bool = False) -> bool:
        if chat_id in self._prejoin_tasks or await is_active_chat(chat_id):
            return False
        self._prejoin_tasks[chat_id] = asyncio.ensure_future(
            self._run_prejoin(chat_id, video)
        )
        return True

    async def await_prejoin(self, chat_id: int):
        task = self._prejoin_tasks.get(chat_id)
        if task is not None:
            await asyncio.shield(task)

    async def prejoin_settle(self, chat_id: int):
        async with self.chat_lock(chat_id):
            task = self._prejoin_tasks.pop(chat_id, None)
            self._prejoin_video.pop(chat_id, None)
            if task is None:
                return
            try:
                await task
            except Exception:
                return
            try:
                assistant = await group_assistant(self, chat_id)
                await assistant.leave_call(chat_id)
            except Exception:
                pass

    async def pause_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await _clear_(chat_id)
        try:
            await assistant.leave_call(chat_id)
        except NoActiveGroupCall:
            pass

    async def stop_stream_force(self, chat_id: int):
        try:
            if config.STRING1:
                await self.one.leave_call(chat_id)
        except:
            pass
        try:
            if config.STRING2:
                await self.two.leave_call(chat_id)
        except:
            pass
        try:
            if config.STRING3:
                await self.three.leave_call(chat_id)
        except:
            pass
        try:
            if config.STRING4:
                await self.four.leave_call(chat_id)
        except:
            pass
        try:
            if config.STRING5:
                await self.five.leave_call(chat_id)
        except:
            pass
        try:
            await _clear_(chat_id)
        except:
            pass

    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistant = await group_assistant(self, chat_id)
        if str(speed) != str("1.0"):
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            if not os.path.isdir(chatdir):
                os.makedirs(chatdir)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                if str(speed) == str("0.5"):
                    vs = 2.0
                if str(speed) == str("0.75"):
                    vs = 1.35
                if str(speed) == str("1.5"):
                    vs = 0.68
                if str(speed) == str("2.0"):
                    vs = 0.5
                proc = await asyncio.create_subprocess_shell(
                    cmd=(
                        "ffmpeg "
                        "-i "
                        f"{file_path} "
                        "-filter:v "
                        f"setpts={vs}*PTS "
                        "-filter:a "
                        f"atempo={speed} "
                        f"{out}"
                    ),
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
            else:
                pass
        else:
            out = file_path
        dur = await asyncio.get_event_loop().run_in_executor(None, check_duration, out)
        dur = int(dur)
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)
        stream = (
            MediaStream(out, audio_parameters=AudioQuality.HIGH, video_parameters=VideoQuality.SD_480p, ffmpeg_parameters=f"-ss {played} -to {duration}")
            if playing[0]["streamtype"] == "video"
            else MediaStream(
                out,
                audio_parameters=AudioQuality.HIGH,
                video_flags=MediaStream.Flags.IGNORE,
                ffmpeg_parameters=f"-ss {played} -to {duration}",
            )
        )
        if str(db[chat_id][0]["file"]) == str(file_path):
            await assistant.play(chat_id, stream, config=GroupCallConfig(auto_start=False))
        else:
            raise AssistantErr("Umm")
        if str(db[chat_id][0]["file"]) == str(file_path):
            exis = (playing[0]).get("old_dur")
            if not exis:
                db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
                db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]
            db[chat_id][0]["played"] = con_seconds
            db[chat_id][0]["dur"] = duration
            db[chat_id][0]["seconds"] = dur
            db[chat_id][0]["speed_path"] = out
            db[chat_id][0]["speed"] = speed

    async def force_stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            check = db.get(chat_id)
            check.pop(0)
        except:
            pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        try:
            await assistant.leave_call(chat_id)
        except:
            pass

    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        if video:
            stream = MediaStream(link, audio_parameters=AudioQuality.HIGH, video_parameters=VideoQuality.SD_480p)
        else:
            stream = MediaStream(link, audio_parameters=AudioQuality.HIGH, video_flags=MediaStream.Flags.IGNORE)
        await assistant.play(
            chat_id,
            stream,
            config=GroupCallConfig(auto_start=False),
        )

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        stream = (
            MediaStream(file_path, audio_parameters=AudioQuality.HIGH, video_parameters=VideoQuality.SD_480p, ffmpeg_parameters=f"-ss {to_seek} -to {duration}")
            if mode == "video"
            else MediaStream(
                file_path,
                audio_parameters=AudioQuality.HIGH,
                video_flags=MediaStream.Flags.IGNORE,
                ffmpeg_parameters=f"-ss {to_seek} -to {duration}",
            )
        )
        await assistant.play(chat_id, stream, config=GroupCallConfig(auto_start=False))

    async def stream_call(self, link):
        assistant = await group_assistant(self, config.LOGGER_ID)
        await assistant.play(
            config.LOGGER_ID,
            MediaStream(link, video_parameters=VideoQuality.SD_480p),
            config=GroupCallConfig(auto_start=False),
        )
        await asyncio.sleep(0.2)
        await assistant.leave_call(config.LOGGER_ID)

    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        language = await get_lang(chat_id)
        _ = get_string(language)
        if video:
            stream = MediaStream(link, audio_parameters=AudioQuality.HIGH, video_parameters=VideoQuality.SD_480p)
        else:
            stream = MediaStream(link, audio_parameters=AudioQuality.HIGH, video_flags=MediaStream.Flags.IGNORE)
        joined = False
        task = self._prejoin_tasks.pop(chat_id, None)
        if task is not None:
            await task
            prejoin_was_video = self._prejoin_video.pop(chat_id, False)
            if bool(video) == prejoin_was_video:
                try:
                    await assistant.play(chat_id, stream, config=GroupCallConfig(auto_start=False))
                    joined = True
                except Exception:
                    try:
                        await assistant.leave_call(chat_id)
                    except Exception:
                        pass
            else:
                try:
                    await assistant.leave_call(chat_id)
                except Exception:
                    pass
        if not joined:
            await self._assistant_join(assistant, chat_id, stream, _)
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)
        if await is_autoend():
            counter[chat_id] = {}
            users = len(await assistant.get_participants(chat_id))
            if users == 1:
                autoend[chat_id] = datetime.now() + timedelta(minutes=1)

    async def change_stream(self, client, chat_id):
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            await auto_clean(popped)
            if not check:
                if await try_autoplay(chat_id, popped):
                    return
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
        except:
            try:
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
            except:
                return
        else:
            queued = check[0]["file"]
            language = await get_lang(chat_id)
            _ = get_string(language)
            title = (check[0]["title"]).title()
            user = check[0]["by"]
            original_chat_id = check[0]["chat_id"]
            streamtype = check[0]["streamtype"]
            videoid = check[0]["vidid"]
            if videoid and videoid not in ("telegram", "soundcloud"):
                record_played(chat_id, videoid)
            db[chat_id][0]["played"] = 0
            exis = (check[0]).get("old_dur")
            if exis:
                db[chat_id][0]["dur"] = exis
                db[chat_id][0]["seconds"] = check[0]["old_second"]
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["speed"] = 1.0
            video = True if str(streamtype) == "video" else False
            if "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0:
                    return await nand.send_message(
                        original_chat_id,
                        text=_["call_6"],
                    )
                if video:
                    stream = MediaStream(link, audio_parameters=AudioQuality.HIGH, video_parameters=VideoQuality.SD_480p)
                else:
                    stream = MediaStream(link, audio_parameters=AudioQuality.HIGH, video_flags=MediaStream.Flags.IGNORE)
                try:
                    await client.play(chat_id, stream, config=GroupCallConfig(auto_start=False))
                except Exception:
                    return await nand.send_message(
                        original_chat_id,
                        text=_["call_6"],
                    )
                img = await get_thumb(videoid)
                run = await send_now_playing_rich(
                    nand,
                    chat_id,
                    original_chat_id,
                    img,
                    _["stream_1"].format(
                        f"https://t.me/{nand.username}?start=info_{videoid}",
                        title,
                        check[0]["dur"],
                        user,
                    ),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            elif "vid_" in queued:
                mystic = await nand.send_message(original_chat_id, _["call_7"])
                try:
                    file_path, direct = await YouTube.download(
                        videoid,
                        mystic,
                        videoid=True,
                        video=True if str(streamtype) == "video" else False,
                    )
                except:
                    return await mystic.edit_text(_["call_6"])
                if video:
                    stream = MediaStream(file_path, audio_parameters=AudioQuality.HIGH, video_parameters=VideoQuality.SD_480p)
                else:
                    stream = MediaStream(file_path, audio_parameters=AudioQuality.HIGH, video_flags=MediaStream.Flags.IGNORE)
                try:
                    await client.play(chat_id, stream, config=GroupCallConfig(auto_start=False))
                except:
                    return await nand.send_message(
                        original_chat_id,
                        text=_["call_6"],
                    )
                img = await get_thumb(videoid)
                await mystic.delete()
                run = await send_now_playing_rich(
                    nand,
                    chat_id,
                    original_chat_id,
                    img,
                    _["stream_1"].format(
                        f"https://t.me/{nand.username}?start=info_{videoid}",
                        title,
                        check[0]["dur"],
                        user,
                    ),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
            elif "index_" in queued:
                stream = (
                    MediaStream(videoid, audio_parameters=AudioQuality.HIGH, video_parameters=VideoQuality.SD_480p)
                    if str(streamtype) == "video"
                    else MediaStream(videoid, audio_parameters=AudioQuality.HIGH, video_flags=MediaStream.Flags.IGNORE)
                )
                try:
                    await client.play(chat_id, stream, config=GroupCallConfig(auto_start=False))
                except:
                    return await nand.send_message(
                        original_chat_id,
                        text=_["call_6"],
                    )
                run = await send_now_playing_rich(
                    nand,
                    chat_id,
                    original_chat_id,
                    config.STREAM_IMG_URL,
                    _["stream_2"].format(user),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            else:
                if video:
                    stream = MediaStream(queued, audio_parameters=AudioQuality.HIGH, video_parameters=VideoQuality.SD_480p)
                else:
                    stream = MediaStream(queued, audio_parameters=AudioQuality.HIGH, video_flags=MediaStream.Flags.IGNORE)
                try:
                    await client.play(chat_id, stream, config=GroupCallConfig(auto_start=False))
                except:
                    return await nand.send_message(
                        original_chat_id,
                        text=_["call_6"],
                    )
                if videoid == "telegram":
                    run = await send_now_playing_rich(
                        nand,
                        chat_id,
                        original_chat_id,
                        config.TELEGRAM_AUDIO_URL
                        if str(streamtype) == "audio"
                        else config.TELEGRAM_VIDEO_URL,
                        _["stream_1"].format(
                            config.SUPPORT_CHAT, title, check[0]["dur"], user
                        ),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
                elif videoid == "soundcloud":
                    run = await send_now_playing_rich(
                        nand,
                        chat_id,
                        original_chat_id,
                        config.SOUNCLOUD_IMG_URL,
                        _["stream_1"].format(
                            config.SUPPORT_CHAT, title, check[0]["dur"], user
                        ),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
                else:
                    img = await get_thumb(videoid)
                    run = await send_now_playing_rich(
                        nand,
                        chat_id,
                        original_chat_id,
                        img,
                        _["stream_1"].format(
                            f"https://t.me/{nand.username}?start=info_{videoid}",
                            title,
                            check[0]["dur"],
                            user,
                        ),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"

    async def ping(self):
        pings = []
        if config.STRING1:
            pings.append(self.one.ping)
        if config.STRING2:
            pings.append(self.two.ping)
        if config.STRING3:
            pings.append(self.three.ping)
        if config.STRING4:
            pings.append(self.four.ping)
        if config.STRING5:
            pings.append(self.five.ping)
        return str(round(sum(pings) / len(pings), 3))

    async def start(self):
        LOGGER(__name__).info("Starting PyTgCalls Client...\n")
        if config.STRING1:
            await self.one.start()
        if config.STRING2:
            await self.two.start()
        if config.STRING3:
            await self.three.start()
        if config.STRING4:
            await self.four.start()
        if config.STRING5:
            await self.five.start()

    async def decorators(self):
        clients = [self.one, self.two, self.three, self.four, self.five]

        async def stream_services_handler(client, update):
            if not db.get(update.chat_id) and not await is_active_chat(update.chat_id):
                return
            LOGGER(__name__).warning(
                "Assistant left the voice chat %s (status: %s); clearing stale playback state",
                update.chat_id,
                update.status,
            )
            async with self.chat_lock(update.chat_id):
                await _clear_(update.chat_id)

        async def stream_end_handler(client, update: StreamEnded):
            if update.chat_id in self._prejoin_tasks:
                return
            await self.change_stream(client, update.chat_id)

        for client in clients:
            client.on_update(pt_filters.chat_update(
                ChatUpdate.Status.LEFT_CALL
            ))(stream_services_handler)
            client.on_update(pt_filters.stream_end(StreamEnded.Type.AUDIO))(stream_end_handler)


Shruti = Call()
