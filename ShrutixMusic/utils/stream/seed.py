_seed = {}


def set_seed(chat_id, video_id):
    if video_id:
        _seed[chat_id] = video_id


def get_seed(chat_id):
    return _seed.get(chat_id)
