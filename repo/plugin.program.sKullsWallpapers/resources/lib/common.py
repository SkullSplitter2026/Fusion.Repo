# -*- coding: utf-8 -*-
"""Shared constants, helpers, and Kodi API wrappers."""
import os
import sys
import time
import json
import urllib.parse as up
import urllib.request as urlreq

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id") or "plugin.program.sKullsWallpapers"
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else -1
BASE_URL = sys.argv[0] if len(sys.argv) > 0 else "plugin.program.sKullsWallpapers"
BASE_SITE = "https://wallpaperscraft.com/"

PROFILE_DIR = xbmcvfs.translatePath(ADDON.getAddonInfo("profile")) or xbmcvfs.translatePath(
    f"special://profile/addon_data/{ADDON_ID}"
)
CAT_THUMB_DIR = os.path.join(PROFILE_DIR, "cat_thumbs")
CACHE_DIR = os.path.join(PROFILE_DIR, "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "wallpaper_cache.json")
CACHE_MAX_AGE = 24 * 3600
FAVORITES_FILE = xbmcvfs.translatePath(os.path.join(PROFILE_DIR, "favorites.json"))
SET_SELECT_FILE = xbmcvfs.translatePath(os.path.join(PROFILE_DIR, "set_selection.json"))
HISTORY_FILE = xbmcvfs.translatePath(os.path.join(PROFILE_DIR, "search_history.json"))
MAX_HISTORY = 10
IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp")
RESOLUTION_FILTERS = {"0": "", "1": "3840", "2": "2560", "3": "1920", "4": "1280"}

for d in (PROFILE_DIR, CAT_THUMB_DIR, CACHE_DIR):
    try:
        if not xbmcvfs.exists(d):
            xbmcvfs.mkdirs(d)
    except Exception:
        pass

try:
    ADDON_LANG = ADDON.getLocalizedString
except Exception:
    def ADDON_LANG(id):
        return str(id)


def log(msg):
    try:
        xbmc.log(f"[{ADDON_ID}] {msg}", xbmc.LOGINFO)
    except Exception:
        print(f"[{ADDON_ID}] {msg}")


def url(**kwargs):
    return BASE_URL + "?" + up.urlencode(kwargs)


def get(setting, default=""):
    try:
        v = ADDON.getSetting(setting)
        return v if v not in ("", None) else default
    except Exception:
        return default


def get_bool(setting, default=False):
    return (get(setting, "true" if default else "false").lower() in ("true", "1", "yes", "on"))


def sanitize_name(name):
    bad = '<>:"/\\|?*'
    out = "".join(("_" if c in bad else c) for c in name).strip()
    return out[:120] or "wallpaper"


def addon_path(*parts):
    base = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
    return os.path.join(base, *parts)


def media_icon(name):
    name_map = {"mywallpaper": "my-wallpaper", "set": "wallpaper-set", "history": "search-history"}
    icon_name = name_map.get(name, name)
    icon_path = os.path.join(addon_path("resources", "media", f"{icon_name}.png"))
    if xbmcvfs.exists(icon_path):
        return icon_path
    fallback = {
        "search": "DefaultAddonsSearch.png", "random": "DefaultMovie.png",
        "favorites": "DefaultAddonsInfo.png", "set": "DefaultFolder.png",
        "download": "DefaultDownload.png", "preview": "DefaultPicture.png",
        "slideshow": "Default slideshow.png", "archive": "DefaultFolder.png",
        "mywallpaper": "DefaultFolder.png", "categories": "DefaultFolder.png",
        "wallpaper": "DefaultPicture.png", "history": "DefaultAddonsSearch.png",
    }
    return fallback.get(name, "DefaultAddonsInfo.png")


def http_get_small(u, timeout=5, max_bytes=400 * 1024):
    try:
        req = urlreq.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urlreq.urlopen(req, timeout=timeout) as r:
            chunks, total = [], 0
            while True:
                buf = r.read(min(64 * 1024, max_bytes - total))
                if not buf:
                    break
                chunks.append(buf)
                total += len(buf)
                if total >= max_bytes:
                    break
            return b"".join(chunks)
    except Exception as e:
        log(f"thumb fetch failed: {e}")
        return b""


def cat_cache_path(slug):
    return os.path.join(CAT_THUMB_DIR, f"{slug}.jpg")


def cat_local_art(slug):
    cat_dir = addon_path("resources", "media", "categories")
    for ext in (".png", ".jpg", ".jpeg"):
        p = os.path.join(cat_dir, slug + ext)
        if xbmcvfs.exists(p):
            return p
    aliases = {
        "black_and_white": ["black-and-white", "bw"],
        "tv-series": ["tv_series", "tvseries", "serials", "tv"],
        "hi-tech": ["technologies", "technology", "tech"],
        "sport": ["sports"],
    }
    for alt in aliases.get(slug, []):
        for ext in (".png", ".jpg", ".jpeg"):
            p = os.path.join(cat_dir, alt + ext)
            if xbmcvfs.exists(p):
                return p
    fallback = addon_path("resources", "media", "catalog_default.png")
    return fallback if xbmcvfs.exists(fallback) else ""


def cat_thumb(slug):
    cached = cat_cache_path(slug)
    if xbmcvfs.exists(cached):
        return cached
    return cat_local_art(slug)


def get_download_dir():
    raw = get("download_path", "").strip()
    if not raw or "resource.images.skinbackgrounds" in raw:
        raw = "special://profile/Wallpaper"
        ADDON.setSetting("download_path", raw)
    try:
        if not xbmcvfs.exists(raw):
            xbmcvfs.mkdirs(raw)
    except Exception:
        pass
    dest_dir = xbmcvfs.translatePath(raw)
    try:
        if not xbmcvfs.exists(dest_dir):
            xbmcvfs.mkdirs(dest_dir)
    except Exception:
        pass
    return dest_dir


def should_abort():
    try:
        return xbmc.Monitor().abortRequested()
    except Exception:
        return False


def set_video_title(li, title):
    try:
        vit = li.getVideoInfoTag()
        vit.setTitle(title)
    except Exception:
        li.setInfo("video", {"title": title})


def get_resolution_filter():
    return get("resolution_filter", "0")


def apply_resolution_filter(items):
    res_filter = get_resolution_filter()
    min_width = RESOLUTION_FILTERS.get(res_filter, "")
    if not min_width:
        return items
    return [it for it in items if min_width in it.get("thumb", "")]


CATEGORY_ENTRIES = [
    ("3D", "3d", "catalog"), ("Abstract", "abstract", "catalog"),
    ("Anime", "anime", "catalog"), ("City", "city", "catalog"),
    ("Dark", "dark", "catalog"), ("Flowers", "flowers", "catalog"),
    ("Minimalism", "minimalism", "catalog"), ("Motorcycles", "motorcycles", "catalog"),
    ("Other", "other", "catalog"), ("Space", "space", "catalog"),
    ("Textures", "textures", "catalog"), ("Vector", "vector", "catalog"),
    ("Animals", "animals", "catalog"), ("Art", "art", "catalog"),
    ("Black", "black", "catalog"), ("Black and White", "black_and_white", "catalog"),
    ("Cars", "cars", "catalog"), ("Fantasy", "fantasy", "catalog"),
    ("Food", "food", "catalog"), ("Holidays", "holidays", "catalog"),
    ("Macro", "macro", "catalog"), ("Music", "music", "catalog"),
    ("Nature", "nature", "catalog"), ("Sport", "sport", "catalog"),
    ("Technologies", "hi-tech", "catalog"), ("TV Series", "tv-series", "tag"),
    ("Words", "words", "catalog"),
]
