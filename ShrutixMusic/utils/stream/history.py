MAX_HISTORY = 30

_history = {}


def record_played(chat_id, video_id):
    if not video_id:
        return
    played = _history.setdefault(chat_id, [])
    if video_id in played:
        played.remove(video_id)
    played.append(video_id)
    if len(played) > MAX_HISTORY:
        del played[: len(played) - MAX_HISTORY]


def was_recently_played(chat_id, video_id) -> bool:
    return video_id in _history.get(chat_id, [])
