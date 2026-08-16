# -*- coding: utf-8 -*-
"""Offline cache system (JSON-based, 24h TTL)."""
import os
import json
import time
import xbmcvfs
from . import common


def _load():
    try:
        if xbmcvfs.exists(common.CACHE_FILE):
            f = xbmcvfs.File(common.CACHE_FILE, "r")
            data = f.read()
            f.close()
            return json.loads(data)
    except Exception:
        pass
    return {}


def _save(data):
    try:
        f = xbmcvfs.File(common.CACHE_FILE, "w")
        f.write(json.dumps(data, indent=2))
        f.close()
    except Exception:
        pass


def get(kind, slug, page):
    cache = _load()
    key = f"{kind}:{slug}:{page}"
    if key in cache:
        entry = cache[key]
        if time.time() - entry.get("ts", 0) < common.CACHE_MAX_AGE:
            return entry.get("data")
    return None


def set_cache(kind, slug, page, data):
    cache = _load()
    key = f"{kind}:{slug}:{page}"
    cache[key] = {"data": data, "ts": time.time()}
    _save(cache)


def clear():
    try:
        if xbmcvfs.exists(common.CACHE_FILE):
            xbmcvfs.delete(common.CACHE_FILE)
    except Exception:
        pass
