# -*- coding: utf-8 -*-
"""Search history management."""
import json
import xbmcvfs
from . import common


def load():
    try:
        if xbmcvfs.exists(common.HISTORY_FILE):
            f = xbmcvfs.File(common.HISTORY_FILE, "r")
            data = f.read()
            f.close()
            return json.loads(data)
    except Exception:
        pass
    return []


def save(history):
    try:
        f = xbmcvfs.File(common.HISTORY_FILE, "w")
        f.write(json.dumps(history, indent=2))
        f.close()
    except Exception:
        pass


def add(query):
    if not query:
        return
    history = load()
    if query in history:
        history.remove(query)
    history.insert(0, query)
    if len(history) > common.MAX_HISTORY:
        history = history[:common.MAX_HISTORY]
    save(history)


def get_all():
    return load()


def clear():
    save([])
