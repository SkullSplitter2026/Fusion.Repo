# -*- coding: utf-8 -*-
"""Genre management for organizing downloaded wallpapers."""
import os
import json
import time
import xbmcvfs
from . import common

GENRES_FILE = xbmcvfs.translatePath(os.path.join(common.PROFILE_DIR, "genres.json"))


def _load():
    try:
        if xbmcvfs.exists(GENRES_FILE):
            f = xbmcvfs.File(GENRES_FILE, "r")
            data = f.read()
            f.close()
            return json.loads(data)
    except Exception:
        pass
    return {}


def _save(data):
    try:
        if not xbmcvfs.exists(common.PROFILE_DIR):
            xbmcvfs.mkdirs(common.PROFILE_DIR)
        f = xbmcvfs.File(GENRES_FILE, "w")
        f.write(json.dumps(data, indent=2))
        f.close()
    except Exception as e:
        common.log(f"Save genres error: {e}")


def get_all():
    return _load()


def get_names():
    data = _load()
    return sorted(data.keys())


def get_path(genre_name):
    data = _load()
    genre = data.get(genre_name, {})
    if "path" in genre:
        return genre["path"]
    base_dir = common.get_download_dir()
    genre_dir = os.path.join(base_dir, _sanitize_genre(genre_name))
    return genre_dir


def exists(genre_name):
    return genre_name in _load()


def create(genre_name, base_dir=None):
    data = _load()
    if genre_name in data:
        return False, "Genre already exists"
    if base_dir is None:
        base_dir = common.get_download_dir()
    genre_path = os.path.join(base_dir, _sanitize_genre(genre_name))
    try:
        if not xbmcvfs.exists(genre_path):
            xbmcvfs.mkdirs(genre_path)
    except Exception as e:
        common.log(f"Failed to create genre folder: {e}")
        return False, str(e)
    data[genre_name] = {"path": genre_path, "created": time.time()}
    _save(data)
    return True, genre_path


def rename(old_name, new_name):
    data = _load()
    if old_name not in data:
        return False, "Genre not found"
    if new_name in data and new_name != old_name:
        return False, "New name already exists"
    old_path = data[old_name]["path"]
    new_path = os.path.join(os.path.dirname(old_path), _sanitize_genre(new_name))
    if old_path != new_path and xbmcvfs.exists(old_path):
        try:
            import shutil
            xbmcvfs.rename(old_path, new_path)
        except Exception:
            pass
    entry = data.pop(old_name)
    entry["path"] = new_path
    data[new_name] = entry
    _save(data)
    return True, new_path


def delete(genre_name, delete_files=False):
    data = _load()
    if genre_name not in data:
        return False, "Genre not found"
    genre_path = data[genre_name].get("path", "")
    if delete_files and genre_path and xbmcvfs.exists(genre_path):
        try:
            dirs, files = xbmcvfs.listdir(genre_path)
            for f in files:
                xbmcvfs.delete(os.path.join(genre_path, f))
            for d in dirs:
                sub = os.path.join(genre_path, d)
                sub_dirs, sub_files = xbmcvfs.listdir(sub)
                for sf in sub_files:
                    xbmcvfs.delete(os.path.join(sub, sf))
                xbmcvfs.rmdir(sub)
            xbmcvfs.rmdir(genre_path)
        except Exception as e:
            common.log(f"Delete genre files error: {e}")
    del data[genre_name]
    _save(data)
    return True, ""


def list_contents(genre_name):
    genre_path = get_path(genre_name)
    results = []
    if not genre_path or not xbmcvfs.exists(genre_path):
        return results
    try:
        dirs, files = xbmcvfs.listdir(genre_path)
        for d in dirs:
            results.append({"name": d, "is_dir": True, "path": os.path.join(genre_path, d)})
        for f in files:
            if f.lower().endswith(common.IMG_EXTS):
                full = os.path.join(genre_path, f)
                results.append({"name": f, "is_dir": False, "path": full})
    except Exception as e:
        common.log(f"List genre contents error: {e}")
    return results


def move_file(src_path, genre_name):
    dest_dir = get_path(genre_name)
    if not dest_dir:
        return False, "Genre path not found"
    try:
        if not xbmcvfs.exists(dest_dir):
            xbmcvfs.mkdirs(dest_dir)
        fname = os.path.basename(src_path)
        dest_path = os.path.join(dest_dir, fname)
        i = 0
        while xbmcvfs.exists(dest_path):
            name, ext = os.path.splitext(fname)
            dest_path = os.path.join(dest_dir, f"{name}_{i}{ext}")
            i += 1
        if xbmcvfs.copy(src_path, dest_path):
            return True, dest_path
        return False, "Copy failed"
    except Exception as e:
        return False, str(e)


def _sanitize_genre(name):
    bad = '<>:"/\\|?*'
    out = "".join(("_" if c in bad else c) for c in name).strip()
    return out[:80] or "misc"
