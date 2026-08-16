# -*- coding: utf-8 -*-
"""Favorites management."""
import json
import time
import xbmcvfs
from . import common


def load():
    try:
        if xbmcvfs.exists(common.FAVORITES_FILE):
            f = xbmcvfs.File(common.FAVORITES_FILE, "r")
            data = f.read()
            f.close()
            return json.loads(data)
    except Exception:
        pass
    return []


def save(favs):
    try:
        fav_dir = common.PROFILE_DIR
        if not xbmcvfs.exists(fav_dir):
            xbmcvfs.mkdirs(fav_dir)
        f = xbmcvfs.File(common.FAVORITES_FILE, "w")
        f.write(json.dumps(favs))
        f.close()
        common.log(f"Saved {len(favs)} favorites")
    except Exception as e:
        common.log(f"Save favorites error: {e}")


def add(title, url, thumb):
    favs = load()
    for fav in favs:
        if fav.get("url") == url:
            common.log("Duplicate favorite")
            return False
    favs.insert(0, {"title": title, "url": url, "thumb": thumb, "added": time.time()})
    save(favs)
    common.log("Favorite added successfully")
    return True


def remove(url):
    favs = load()
    favs = [f for f in favs if f.get("url") != url]
    save(favs)


def is_favorite(url):
    favs = load()
    return any(f.get("url") == url for f in favs)


def get_all():
    return load()
