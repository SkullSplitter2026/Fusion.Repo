# -*- coding: utf-8 -*-
"""Wallpaper Set (batch collection) management."""
import json
import xbmcvfs
from . import common


def load():
    try:
        if xbmcvfs.exists(common.SET_SELECT_FILE):
            f = xbmcvfs.File(common.SET_SELECT_FILE, "r")
            data = f.read()
            f.close()
            return json.loads(data)
    except Exception:
        pass
    return []


def save(items):
    try:
        set_dir = common.PROFILE_DIR
        if not xbmcvfs.exists(set_dir):
            xbmcvfs.mkdirs(set_dir)
        f = xbmcvfs.File(common.SET_SELECT_FILE, "w")
        f.write(json.dumps(items))
        f.close()
    except Exception as e:
        common.log(f"Save set error: {e}")


def add(title, url, thumb):
    items = load()
    for it in items:
        if it.get("url") == url:
            return False
    items.append({"title": title, "url": url, "thumb": thumb})
    save(items)
    return True


def remove(url):
    items = load()
    items = [i for i in items if i.get("url") != url]
    save(items)


def clear():
    save([])


def count():
    return len(load())
