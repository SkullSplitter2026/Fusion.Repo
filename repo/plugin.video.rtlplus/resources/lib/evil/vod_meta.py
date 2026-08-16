import os
import json

_MAX_ENTRIES = 500

def _meta_file():
    from .constants import ADDON_PROFILE
    return os.path.join(ADDON_PROFILE, 'vod_meta.json')

def _load_all():
    path = _meta_file()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_all(data):
    path = _meta_file()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass

def save(video_id, meta):
    if not video_id:
        return
    data = _load_all()
    data[video_id] = meta
    if len(data) > _MAX_ENTRIES:
        keys = list(data.keys())
        for k in keys[:len(data) - _MAX_ENTRIES]:
            del data[k]
    _save_all(data)

def load(video_id):
    if not video_id:
        return {}
    data = _load_all()
    return data.get(video_id, {})
