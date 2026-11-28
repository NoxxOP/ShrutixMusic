import html
import os
import re
import time
import traceback

from pyrogram.enums import ParseMode

import config

_FAILURES = {}
_SECRET_RE = re.compile(r"(api_key=)[^&\s'\"]+")


def mask(text) -> str:
    return _SECRET_RE.sub(r"\1***", str(text))


def key_state(api_key: str) -> str:
    if not api_key or api_key == "YOUR_API_KEY":
        return "NOT SET (placeholder in use)"
    return f"set ({len(api_key)} chars)"


def remember_failure(key: str, report: dict):
    report["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _FAILURES[key] = report
    if len(_FAILURES) > 200:
        _FAILURES.pop(next(iter(_FAILURES)))


def pop_failure(key: str):
    return _FAILURES.pop(key, None)


def format_report(title: str, fields: dict, exc: BaseException = None) -> str:
    lines = [f"<b>⚠️ {html.escape(title)}</b>", ""]
    for name, value in fields.items():
        if value is None or value == "":
            continue
        text = html.escape(mask(value))
        if len(text) > 700:
            text = text[:700] + "…"
        lines.append(f"<b>{html.escape(str(name))} :</b> <code>{text}</code>")
    if exc is not None:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        tb = html.escape(mask(tb))
        if len(tb) > 2200:
            tb = "…" + tb[-2200:]
        lines += ["", f"<b>Traceback :</b>\n<pre>{tb}</pre>"]
    return "\n".join(lines)[:4000]


async def send_log(text: str):
    if not config.LOGGER_ID:
        return
    from ShrutixMusic import nand

    try:
        await nand.send_message(
            chat_id=config.LOGGER_ID,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception as e:
        from ShrutixMusic import LOGGER

        LOGGER(__name__).error("Could not send error report to logger group: %s", e)


async def report_play_error(title: str, message, exc: BaseException, extra: dict = None):
    fields = {}
    chat = getattr(message, "chat", None)
    user = getattr(message, "from_user", None)
    if chat is not None:
        fields["Chat"] = f"{chat.title} ({chat.id})"
    if user is not None:
        fields["User"] = f"{user.first_name} ({user.id})"
    text = getattr(message, "text", None)
    if text:
        fields["Command"] = text
    fields["Exception"] = f"{type(exc).__name__}: {exc}"
    if isinstance(exc, FileNotFoundError):
        fields["Missing file"] = getattr(exc, "filename", None)
        fields["CWD"] = os.getcwd()
    if extra:
        fields.update(extra)
    await send_log(format_report(title, fields, exc))
