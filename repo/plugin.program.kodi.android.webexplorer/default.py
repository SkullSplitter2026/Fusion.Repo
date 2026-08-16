# -*- coding: utf-8 -*-
"""
Kodi Android Web File Explorer © André Albus E-Dat-300320260500 Ver-1.2.0
"""

from __future__ import annotations

import os
import sys
import mmap
import json
import shutil
import socket
import tempfile
import urllib.parse
import zipfile
import traceback
import threading
import socketserver
import secrets
import time
import http.client
import unicodedata
from pathlib import Path, PurePosixPath
from typing import List, Optional, Tuple, Callable, Dict, Any
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import quote

# Globale Socket-Timeouts moderat setzen
try:
    socket.setdefaulttimeout(15.0)
except Exception:
    pass

# Kodi APIs
try:
    import xbmc
    import xbmcgui
    import xbmcplugin
    import xbmcaddon
except Exception:
    class _Mock:
        LOGDEBUG = 0
        LOGINFO = 1
        LOGWARNING = 2
        LOGERROR = 3
        NOTIFICATION_INFO = 0

        def __getattr__(self, name):
            def _noop(*a, **k):
                pass
            return _noop

        @staticmethod
        def log(msg: str, level: int = 1) -> None:
            print("MOCK-XBMC:", msg)

        @staticmethod
        def getIPAddress() -> str:
            return ""

        @staticmethod
        def getCondVisibility(_expr: str) -> bool:
            return True

        class Dialog:
            def ok(self, *a, **k):
                print("DIALOG OK:", a, k)

            def notification(self, *a, **k):
                print("NOTIFY:", a, k)

        class ListItem:
            def __init__(self, label=""):
                self.label = label

            def setArt(self, *a, **k):
                pass

        class Addon:
            def __init__(self, id=None):
                self._id = id

            def getSetting(self, k):
                return ""

            def openSettings(self):
                print("OPEN SETTINGS (mock)")

    xbmc = _Mock()
    xbmcgui = _Mock()
    xbmcplugin = _Mock()
    xbmcaddon = _Mock()

# ----------------------------
# Konfiguration
# ----------------------------
ADDON_ID = "plugin.program.kodi.android.webexplorer"
CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB für bessere Performance

# Hinweis: ROOT_DIRS['Android'] dient nur noch als "Kategorie", NICHT als konkreter Pfad.
ROOT_DIRS = {
    "Android": "/",  # wird zur Laufzeit korrekt auf den bevorzugten, lesbaren Pfad gemappt
    "Kodi": os.path.expanduser("~/.kodi")
}

ADDON_ROOT = Path(__file__).resolve().parent
ADDON_ROOT_ABS = str(ADDON_ROOT.resolve())
RESOURCES_HTML = ADDON_ROOT / "resources" / "html"
RESOURCES_ART = ADDON_ROOT / "resources" / "art"

# Kodi Home + Schutzpfade
KODI_HOME = os.path.expanduser("~/.kodi")

# Safelists
__addon_id__ = ADDON_ID
CLEANER_SAFELIST: set[str] = set()
EXTRACT_SAFELIST: set[str] = set()
INSERT_SAFELIST: set[str] = set()

# Schutz / Settings
PROTECT_DELETE_ENABLED: bool = True
PROTECT_UNZIP_ENABLED: bool = True
INSERT_PROTECT_ENABLED: bool = True
FOLLOW_SYMLINKS: bool = False

# UI Mode
UI_MODE: str = "AUTO"  # AUTO | DESKTOP | MOBILE

MAX_PARALLEL_TASKS: int = 4
LOG_LEVEL_STR: str = "INFO"
LOG_LEVEL = getattr(xbmc, "LOGINFO", 1)


# ----------------------------
# Einstellungen sicher lesen
# ----------------------------
def get_addon() -> object:
    try:
        return xbmcaddon.Addon(id=ADDON_ID)
    except Exception:
        return xbmcaddon


def get_setting_str(key: str, default: str = "") -> str:
    try:
        addon = get_addon()
        val = addon.getSetting(key)
        if val is None:
            return default
        return str(val)
    except Exception:
        return default


def get_setting_bool(key: str, default: bool = False) -> bool:
    v = get_setting_str(key, "true" if default else "false").strip().lower()
    return v in ("true", "1", "yes", "on")


def get_setting_int(key: str, default: int) -> int:
    raw = get_setting_str(key, str(default)).strip()
    try:
        return int(raw)
    except Exception:
        return default


def parse_csv_set(raw: str) -> set[str]:
    out: set[str] = set()
    for item in (raw or "").split(","):
        s = item.strip()
        if s:
            out.add(s)
    return out


def get_port_from_settings() -> int:
    raw = get_setting_str("port", "8080").strip()
    try:
        port = int(raw)
        if not (1 <= port <= 65535):
            raise ValueError()
        return port
    except Exception:
        return 8080


def get_credentials_from_settings() -> Tuple[str, str, bool]:
    username = get_setting_str("username", "").strip()
    password = get_setting_str("password", "").strip()
    auth_required = (username != "") and (password != "")
    return username, password, auth_required


def refresh_settings():
    global PROTECT_DELETE_ENABLED, PROTECT_UNZIP_ENABLED, FOLLOW_SYMLINKS
    global CLEANER_SAFELIST, EXTRACT_SAFELIST, INSERT_SAFELIST
    global MAX_PARALLEL_TASKS, LOG_LEVEL_STR, LOG_LEVEL
    global INSERT_PROTECT_ENABLED, UI_MODE

    PROTECT_DELETE_ENABLED = get_setting_bool("protect_delete", True)
    PROTECT_UNZIP_ENABLED = get_setting_bool("protect_unzip", True)
    INSERT_PROTECT_ENABLED = get_setting_bool("insert_protect", True)
    FOLLOW_SYMLINKS = get_setting_bool("follow_symlinks", False)

    cleaner_default = f"{__addon_id__},Addons33.db,Textures13.db,kodi.log"
    extract_default = f"{__addon_id__}"
    insert_default = f"{__addon_id__}"

    CLEANER_SAFELIST = parse_csv_set(get_setting_str("cleaner_safelist", cleaner_default))
    EXTRACT_SAFELIST = parse_csv_set(get_setting_str("extract_safelist", extract_default))
    INSERT_SAFELIST = parse_csv_set(get_setting_str("insert_safelist", insert_default))

    MAX_PARALLEL_TASKS = max(1, min(32, get_setting_int("max_tasks", 4)))
    LOG_LEVEL_STR = get_setting_str("log_level", "INFO").upper()
    lv_map = {
        "DEBUG": getattr(xbmc, "LOGDEBUG", 0),
        "INFO": getattr(xbmc, "LOGINFO", 1),
        "WARN": getattr(xbmc, "LOGWARNING", 2),
        "ERROR": getattr(xbmc, "LOGERROR", 3)
    }
    LOG_LEVEL = lv_map.get(LOG_LEVEL_STR, getattr(xbmc, "LOGINFO", 1))

    UI_MODE = get_setting_str("ui_mode", "AUTO").strip().upper()
    if UI_MODE not in ("AUTO", "DESKTOP", "MOBILE"):
        UI_MODE = "AUTO"


# initial laden
refresh_settings()

# ----------------------------
# Logging
# ----------------------------
def log(msg: str, level: int = None):
    if level is None:
        level = LOG_LEVEL
    try:
        xbmc.log(f"[webexplorer] {msg}", level)
    except Exception:
        print("[webexplorer]", msg)


def log_err(msg: str):
    log(msg, getattr(xbmc, "LOGERROR", 3))


def log_dbg(msg: str):
    if LOG_LEVEL_STR == "DEBUG":
        log(msg, getattr(xbmc, "LOGDEBUG", 0))


# ----------------------------
# Pfad-Helfer
# ----------------------------
def canonical_path(p: str) -> str:
    try:
        return str(Path(p).resolve())
    except Exception:
        return os.path.abspath(p)


def is_within(path: str, base: str) -> bool:
    try:
        p = canonical_path(path)
        b = canonical_path(base)
        if p == b:
            return True
        if b.endswith(os.sep):
            return p.startswith(b)
        return p.startswith(b + os.sep)
    except Exception:
        p = os.path.abspath(path)
        b = os.path.abspath(base)
        return p == b or p.startswith(b.rstrip(os.sep) + os.sep)


def safe_join(base: str, rel: Optional[str]) -> str:
    if rel is None:
        rel = ""
    rel = urllib.parse.unquote(rel)
    try:
        rel = unicodedata.normalize("NFKC", rel)
    except Exception:
        pass
    rel = rel.lstrip(os.sep)
    base_c = canonical_path(base)
    candidate = Path(base_c) / PurePosixPath(rel)
    try:
        cand_c = str(candidate.resolve())
    except Exception:
        cand_c = str((Path(base_c) / rel).absolute())
    if not is_within(cand_c, base_c):
        raise ValueError("Ungültiger Pfad: außerhalb des aktuellen Root.")
    return cand_c


# ----------------------------
# Schutz-Helfer
# ----------------------------
def is_kodi_home(path: str) -> bool:
    return is_within(path, KODI_HOME)


def _kodi_rel_parts(path: str) -> List[str]:
    try:
        p = os.path.abspath(path)
        if not is_kodi_home(p):
            return []
        rel = os.path.relpath(p, KODI_HOME)
        return list(Path(rel).parts)
    except Exception:
        return []


def _has_anchor(path: str, names: set[str]) -> bool:
    if not names:
        return False
    parts = _kodi_rel_parts(path)
    if not parts:
        return False
    for part in parts:
        if part in names:
            return True
    return False


def cleaner_saved_basename(path: str) -> bool:
    try:
        return os.path.basename(path) in CLEANER_SAFELIST
    except Exception:
        return False


def extract_saved_top(member_name: str) -> bool:
    try:
        parts = PurePosixPath(member_name).parts
        top = parts[0] if parts else ""
        return top in EXTRACT_SAFELIST
    except Exception:
        return False


def insert_saved_basename(path: str) -> bool:
    try:
        return os.path.basename(path) in INSERT_SAFELIST
    except Exception:
        return False


def is_protected_path(path: str) -> bool:
    if not is_kodi_home(path):
        return False
    anchor_names = CLEANER_SAFELIST | EXTRACT_SAFELIST | INSERT_SAFELIST
    return _has_anchor(path, anchor_names)


def is_insert_protected(path: str) -> bool:
    if not INSERT_PROTECT_ENABLED:
        return False
    if not is_kodi_home(path):
        return False
    if not os.path.exists(path):
        return False
    return _has_anchor(path, INSERT_SAFELIST)


# ----------------------------
# Safe-Deletion
# ----------------------------
def _should_skip_delete(target: str) -> bool:
    try:
        if not PROTECT_DELETE_ENABLED:
            return False
        if not is_kodi_home(target):
            return False
        anchor_names = CLEANER_SAFELIST | EXTRACT_SAFELIST | INSERT_SAFELIST
        if _has_anchor(target, anchor_names):
            return True
        try:
            if os.path.basename(target) in anchor_names:
                return True
        except Exception:
            pass
    except Exception:
        pass
    return False


def _contains_protected_under(path: str) -> bool:
    try:
        if _should_skip_delete(path):
            return True
        if not os.path.isdir(path):
            return False
        stack = [path]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as it:
                    for entry in it:
                        full = entry.path
                        if _should_skip_delete(full):
                            return True
                        try:
                            if entry.is_dir(follow_symlinks=FOLLOW_SYMLINKS):
                                stack.append(full)
                        except Exception:
                            continue
            except Exception:
                continue
        return False
    except Exception:
        return False


def safe_delete_tree(path: str,
                     delete_self: bool = True,
                     progress_cb=None,
                     bytes_cb=None,
                     cancel_cb=None):
    deleted = 0
    skipped: List[str] = []
    errors: List[str] = []

    try:
        st = os.lstat(path)
        size_hint = getattr(st, "st_size", 0)
    except Exception:
        size_hint = 0

    if cancel_cb and cancel_cb():
        return deleted, skipped, errors

    if not os.path.isdir(path):
        try:
            if _should_skip_delete(path):
                skipped.append(path)
                return deleted, skipped, errors
            os.remove(path)
            deleted += 1
            if progress_cb:
                progress_cb(1, 0)
            if bytes_cb:
                bytes_cb(size_hint)
        except PermissionError:
            skipped.append(path)
        except Exception as e:
            errors.append(f"{path}: {e}")
        return deleted, skipped, errors

    stack: List[Tuple[str, bool]] = [(path, False)]
    while stack:
        current, children_done = stack.pop()

        if cancel_cb and cancel_cb():
            return deleted, skipped, errors

        if not children_done:
            if _should_skip_delete(current):
                skipped.append(current)
                continue

            try:
                with os.scandir(current) as it:
                    stack.append((current, True))
                    for entry in it:
                        child = entry.path
                        if cancel_cb and cancel_cb():
                            return deleted, skipped, errors
                        try:
                            if entry.is_dir(follow_symlinks=FOLLOW_SYMLINKS):
                                if _should_skip_delete(child):
                                    skipped.append(child)
                                    continue
                                stack.append((child, False))
                            else:
                                if _should_skip_delete(child):
                                    skipped.append(child)
                                    continue
                                try:
                                    size_local = 0
                                    try:
                                        st = entry.stat(follow_symlinks=False)
                                        size_local = getattr(st, "st_size", 0)
                                    except Exception:
                                        size_local = 0
                                    os.remove(child)
                                    deleted += 1
                                    if progress_cb:
                                        progress_cb(1, 0)
                                    if bytes_cb and size_local:
                                        bytes_cb(size_local)
                                except PermissionError:
                                    skipped.append(child)
                                except Exception as e:
                                    errors.append(f"{child}: {e}")
                        except Exception as e:
                            errors.append(f"{child}: {e}")
            except Exception as e:
                errors.append(f"{current}: {e}")
            continue

        if not delete_self and os.path.abspath(current) == os.path.abspath(path):
            continue

        try:
            if _contains_protected_under(current):
                skipped.append(current)
            else:
                os.rmdir(current)
                deleted += 1
                if progress_cb:
                    progress_cb(1, 0)
        except PermissionError:
            skipped.append(current)
        except OSError as e:
            errors.append(f"{current}: {e}")
        except Exception as e:
            errors.append(f"{current}: {e}")

    return deleted, skipped, errors


def count_deletables_and_bytes(root_path: str,
                               delete_self: bool = True,
                               follow_links: bool = False,
                               update_cb: Optional[Callable[[int, int], None]] = None) -> Tuple[int, int]:
    total = 0
    btotal = 0

    if not os.path.exists(root_path):
        return 0, 0

    def upd():
        if update_cb:
            try:
                update_cb(total, btotal)
            except Exception:
                pass

    if os.path.isfile(root_path) or os.path.islink(root_path):
        if _should_skip_delete(root_path):
            upd()
            return 0, 0
        try:
            btotal_local = os.path.getsize(root_path)
        except Exception:
            btotal_local = 0
        btotal += btotal_local
        total += 1
        upd()
        return total, btotal

    stack: List[str] = [root_path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    path = entry.path
                    try:
                        if entry.is_dir(follow_symlinks=follow_links):
                            if _should_skip_delete(path) or _contains_protected_under(path):
                                continue
                            total += 1
                            stack.append(path)
                        else:
                            if _should_skip_delete(path):
                                continue
                            total += 1
                            try:
                                st = entry.stat(follow_symlinks=False)
                                btotal += getattr(st, "st_size", 0)
                            except Exception:
                                pass
                    except Exception:
                        continue
        except Exception:
            continue

        if (total & 1023) == 0:
            upd()

    if delete_self and not _should_skip_delete(root_path) and not _contains_protected_under(root_path):
        total += 1

    upd()
    return total, btotal


# ----------------------------
# IP-Helfer
# ----------------------------
def resolve_primary_ip() -> Optional[str]:
    try:
        ip = xbmc.getIPAddress()
        if ip and ip not in ("0.0.0.0", "127.0.0.1"):
            return ip
    except Exception:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2.0)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except Exception:
        pass
    return None


def get_local_ips() -> List[str]:
    ip = resolve_primary_ip()
    if ip:
        return [ip]
    ips: List[str] = []
    try:
        hostname = socket.gethostname()
        for res in socket.getaddrinfo(hostname, None):
            af, _, _, _, sa = res
            if af == socket.AF_INET and not sa[0].startswith("127."):
                ips.append(sa[0])
    except Exception:
        pass
    return sorted(set(ips)) or ["127.0.0.1"]


# ----------------------------
# Root-Ermittlung
# ----------------------------
def dir_is_readable(path: str) -> bool:
    try:
        if not os.path.isdir(path):
            return False
        _ = os.listdir(path)
        return True
    except Exception:
        return False


def detect_android_root() -> str:
    candidates = [
        "/storage/emulated/0",
        "/sdcard",
        "/storage/self/primary",
        "/storage",
        "/",
    ]
    seen = []
    for p in candidates:
        if p and p not in seen:
            seen.append(p)
    for c in seen:
        if dir_is_readable(c):
            return c
    return "/"


def choose_initial_root() -> Tuple[str, str, str]:
    android_root = detect_android_root()
    if dir_is_readable(android_root):
        return android_root, "Android", android_root
    kodi_candidate = ROOT_DIRS.get("Kodi", os.path.expanduser("~/.kodi"))
    if dir_is_readable(kodi_candidate):
        return kodi_candidate, "Kodi", android_root
    return android_root, "Android", android_root


# ----------------------------
# MIME & ZIP helpers
# ----------------------------
def guess_content_type(filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    mapping = {
        "html": "text/html; charset=utf-8",
        "htm": "text/html; charset=utf-8",
        "css": "text/css; charset=utf-8",
        "js": "application/javascript; charset=utf-8",
        "json": "application/json; charset=utf-8",
        "txt": "text/plain; charset=utf-8",
        "xml": "application/xml; charset=utf-8",
        "csv": "text/csv; charset=utf-8",
        "ico": "image/x-icon",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "svg": "image/svg+xml",
        "webp": "image/webp",
        "heic": "image/heic",
        "heif": "image/heif",
        "pdf": "application/pdf",
        "zip": "application/zip",
        "7z": "application/x-7z-compressed",
        "rar": "application/vnd.rar",
        "tar": "application/x-tar",
        "gz": "application/gzip",
        "bz2": "application/x-bzip2",
        "xz": "application/x-xz",
        "apk": "application/vnd.android.package-archive",
        "mp3": "audio/mpeg",
        "flac": "audio/flac",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
        "aac": "audio/aac",
        "ogg": "audio/ogg",
        "oga": "audio/ogg",
        "mp4": "video/mp4",
        "m4v": "video/x-m4v",
        "webm": "video/webm",
        "mov": "video/quicktime",
        "avi": "video/x-msvideo",
        "mkv": "video/x-matroska",
        "ts": "video/mp2t",
        "srt": "application/x-subrip",
        "ass": "text/plain; charset=utf-8",
        "md": "text/markdown; charset=utf-8",
        "log": "text/plain; charset=utf-8",
        "ini": "text/plain; charset=utf-8",
        "cfg": "text/plain; charset=utf-8",
        "py": "text/x-python; charset=utf-8",
        "avif": "image/avif",
        "jxl": "image/jxl",
        "opus": "audio/ogg",
        "m3u8": "application/vnd.apple.mpegurl",
        "tsv": "text/tab-separated-values; charset=utf-8",
        "yaml": "application/x-yaml; charset=utf-8",
        "yml": "application/x-yaml; charset=utf-8",
        "toml": "application/toml; charset=utf-8",
        "bat": "text/plain; charset=utf-8",
        "sh": "text/x-shellscript; charset=utf-8",

    }
    return mapping.get(ext, "application/octet-stream")


def build_content_disposition(filename: str) -> str:
    safe_fn = filename.replace('"', "'")
    fn_star = quote(filename, safe="")
    return f'attachment; filename="{safe_fn}"; filename*=UTF-8\'\'{fn_star}'


# ----------------------------
# Temporäre Verzeichnisse
# ----------------------------
_tempdir = None


def _ensure_tempdir() -> None:
    global _tempdir
    if _tempdir is not None:
        return
    try:
        tempfile.gettempdir()
        _tempdir = tempfile.gettempdir()
        return
    except FileNotFoundError:
        candidates = [
            os.path.join(os.path.dirname(__file__), "tmp"),
            os.path.join(os.path.expanduser("~"), ".cache", "webexplorer"),
            os.getcwd(),
        ]
        for cand in candidates:
            try:
                os.makedirs(cand, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=cand, delete=True):
                    pass
                _tempdir = cand
                return
            except Exception as e:
                log_err(f"Tempdir-Kandidat verworfen: {cand}: {e}")
        raise FileNotFoundError("Kein benutzbares temporäres Verzeichnis gefunden")


def get_work_tempdir() -> str:
    _ensure_tempdir()
    return _tempdir


# ----------------------------
# Multipart parsing (no cgi)
# ----------------------------
def _parse_ct_params(ct: str) -> Tuple[str, Dict[str, str]]:
    main = (ct or "").split(";", 1)[0].strip().lower()
    params: Dict[str, str] = {}
    for part in (ct or "").split(";")[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip().lower()
            v = v.strip().strip('"')
            params[k] = v
    return main, params


def _read_request_to_tempfile(rfile, content_length: int) -> str:
    _ensure_tempdir()
    tmpdir = tempfile.mkdtemp(prefix="kodi_upload_raw_", dir=get_work_tempdir())
    raw_path = os.path.join(tmpdir, "body.bin")
    remaining = content_length
    chunk_size = max(CHUNK_SIZE, 2 * 1024 * 1024)
    with open(raw_path, "wb") as out:
        while remaining > 0:
            chunk = rfile.read(min(chunk_size, remaining))
            if not chunk:
                break
            out.write(chunk)
            remaining -= len(chunk)
    return raw_path


def _parse_multipart_from_file(raw_path: str, content_type: str):
    main, params = _parse_ct_params(content_type)
    if not main or "multipart/form-data" not in main:
        return {}, []

    boundary = params.get("boundary")
    if not boundary:
        return {}, []

    boundary_bytes = b"--" + boundary.encode("utf-8", errors="ignore")
    end_boundary_bytes = boundary_bytes + b"--"

    try:
        with open(raw_path, "rb") as f:
            try:
                mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            except Exception as e:
                log_err(f"mmap fehlgeschlagen, fallback auf read(): {e}")
                data = f.read()
                mm = memoryview(data)
    except Exception as e:
        log_err(f"Fehler beim Öffnen von raw_path in _parse_multipart_from_file: {e}")
        return {}, []

    fields: Dict[str, List[bytes]] = {}
    files: List[Dict[str, str]] = []

    def _parse_content_disposition(value: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        parts_cd = value.split(";")
        if parts_cd:
            out["__type"] = parts_cd[0].strip().lower()
        for part_cd in parts_cd[1:]:
            if "=" in part_cd:
                k, v = part_cd.split("=", 1)
                k = k.strip().lower()
                v = v.strip().strip('"')
                out[k] = v
        return out

    try:
        pos = mm.find(boundary_bytes)
        if pos == -1:
            return {}, []
        pos += len(boundary_bytes)

        while True:
            if mm[pos:pos + 2] == b"--":
                break
            if mm[pos:pos + 2] == b"\r\n":
                pos += 2
            elif mm[pos:pos + 1] == b"\n":
                pos += 1

            header_end = mm.find(b"\r\n\r\n", pos)
            if header_end == -1:
                break

            header_bytes = mm[pos:header_end]
            body_start = header_end + 4

            next_boundary = mm.find(boundary_bytes, body_start)
            if next_boundary == -1:
                next_boundary = mm.find(end_boundary_bytes, body_start)
                if next_boundary == -1:
                    break

            body_end = next_boundary
            if body_end >= 2 and mm[body_end - 2:body_end] == b"\r\n":
                body_end -= 2
            elif body_end >= 1 and mm[body_end - 1:body_end] == b"\n":
                body_end -= 1

            body = bytes(mm[body_start:body_end])

            headers: Dict[str, str] = {}
            for line in header_bytes.split(b"\r\n"):
                if not line:
                    continue
                try:
                    h = line.decode("utf-8", errors="ignore")
                except Exception:
                    h = ""
                if not h:
                    continue
                if ":" in h:
                    k, v = h.split(":", 1)
                    headers[k.strip().lower()] = v.strip()

            cd_raw = headers.get("content-disposition", "")
            if not cd_raw:
                pos = next_boundary + len(boundary_bytes)
                continue

            cd = _parse_content_disposition(cd_raw)
            name = cd.get("name", "")
            filename = cd.get("filename")

            if filename:
                try:
                    _ensure_tempdir()
                    upload_tmpdir = tempfile.mkdtemp(prefix="kodi_upload_", dir=get_work_tempdir())
                    safe_name = os.path.basename(filename) or "upload.bin"
                    try:
                        safe_name = unicodedata.normalize("NFKC", safe_name)
                    except Exception:
                        pass
                    safe_name = "".join(ch for ch in safe_name if ch not in ("\r", "\n", "\t", "\x00"))
                    if not safe_name:
                        safe_name = "upload.bin"

                    temp_path = os.path.join(upload_tmpdir, safe_name)

                    with open(temp_path, "wb") as out:
                        out.write(body)

                    files.append({
                        "name": name or "",
                        "filename": os.path.basename(filename),
                        "temp_path": temp_path,
                    })
                except Exception as e:
                    log_err(f"Fehler beim Schreiben eines Upload-Teils: {e}")
            else:
                fields.setdefault(name or "", []).append(body)

            pos = next_boundary + len(boundary_bytes)
            if mm[pos:pos + 2] == b"--":
                break

    finally:
        try:
            mm.close()
        except Exception:
            pass

    return fields, files


# ----------------------------
# Aufgaben / Tasks
# ----------------------------
class BaseTask:
    def __init__(self):
        self.total = 0
        self.done = 0
        self.bytes_total = 0
        self.bytes_done = 0
        self.state = "pending"
        self.message = ""
        self.started_at = time.time()
        self.finished_at: Optional[float] = None
        self._cancel = False
        self._lock = threading.Lock()

    def set_total(self, total: int):
        with self._lock:
            self.total = total

    def set_bytes_total(self, btotal: int):
        with self._lock:
            self.bytes_total = btotal

    def inc_bytes(self, inc: int):
        with self._lock:
            self.bytes_done += inc

    def set_progress(self, done: Optional[int] = None, total: Optional[int] = None):
        with self._lock:
            if done is not None:
                self.done = done
            if total is not None:
                self.total = total

    def set_state(self, state: str, message: str = ""):
        with self._lock:
            self.state = state
            if message:
                self.message = message
            if state in ("done", "error", "canceled"):
                self.finished_at = time.time()

    def request_cancel(self):
        with self._lock:
            self._cancel = True

    def is_canceled(self) -> bool:
        with self._lock:
            return self._cancel


class UnzipTask(BaseTask):
    def __init__(self, zip_path: str, dest_dir: str):
        super().__init__()
        self.zip_path = zip_path
        self.dest_dir = dest_dir
        self.skipped: List[str] = []


class ZipTask(BaseTask):
    def __init__(self, src_dir: str, include_root: bool, out_name: str):
        super().__init__()
        self.src_dir = src_dir
        self.include_root = include_root
        self.tmpdir: Optional[str] = None
        self.archive_path: Optional[str] = None
        self.filename: str = out_name


class CopyTask(BaseTask):
    def __init__(self, src: str, dest_dir: str, dest_root: str):
        super().__init__()
        self.src = src
        self.dest_dir = dest_dir
        self.dest_root = dest_root
        self.created_paths: List[str] = []
        self.entries: List[Tuple[str, str, int]] = []


class DeleteTask(BaseTask):
    def __init__(self, base_dir: str):
        super().__init__()
        self.base_dir = base_dir
        self.skipped: List[str] = []
        self.errors: List[str] = []


class ThreadingSimpleServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
    current_root = ROOT_DIRS["Android"]
    current_root_name = "Android"
    android_root_path: str = "/"
    auth_required: bool = False
    username: str = ""
    password: str = ""
    sessions: set = set()
    sessions_lock: threading.Lock = threading.Lock()
    clip_source: Optional[str] = None

    unzip_tasks: Dict[str, UnzipTask] = {}
    unzip_lock: threading.Lock = threading.Lock()
    zip_tasks: Dict[str, ZipTask] = {}
    zip_lock: threading.Lock = threading.Lock()
    copy_tasks: Dict[str, CopyTask] = {}
    copy_lock: threading.Lock = threading.Lock()
    delete_tasks: Dict[str, DeleteTask] = {}
    delete_lock: threading.Lock = threading.Lock()

    task_semaphore = threading.Semaphore(MAX_PARALLEL_TASKS)
    task_limit_lock = threading.Lock()
    cleanup_stop = False


# ----------------------------
# HTTP Handler
# ----------------------------
class ExplorerHandler(BaseHTTPRequestHandler):
    server_version = "KodiWebExplorer/1.2.0"
    rbufsize = CHUNK_SIZE
    wbufsize = CHUNK_SIZE

    def setup(self):
        super().setup()
        try:
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass

    def _safe_wfile_write(self, data: bytes):
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            log_dbg("Client aborted connection while writing.")
        except Exception as e:
            log_err(f"Write error: {e}")

    def write_text(self, text: str, status: HTTPStatus = HTTPStatus.OK):
        raw = text.encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Connection", "close")
            self.end_headers()
            self._safe_wfile_write(raw)
        except Exception as e:
            log_err(f"write_text failed: {e}\n{traceback.format_exc()}")

    def send_json(self, obj: object, status: HTTPStatus = HTTPStatus.OK):
        try:
            raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        except Exception:
            raw = b'{"status":"error","message":"JSON serialization failed"}'
            status = HTTPStatus.INTERNAL_SERVER_ERROR
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Connection", "close")
            self.end_headers()
            self._safe_wfile_write(raw)
        except Exception as e:
            log_err(f"send_json failed: {e}\n{traceback.format_exc()}")

    def send_json_error(self, message: str, code: HTTPStatus):
        self.send_json({"status": "error", "message": message, "code": code.value}, status=code)

    def send_bytes(self, data: bytes, content_type: str = "application/octet-stream"):
        try:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.end_headers()
            self._safe_wfile_write(data)
            try:
                self.wfile.flush()
            except Exception:
                pass
        except Exception as e:
            log_err(f"send_bytes failed: {e}\n{traceback.format_exc()}")

    # ---- Auth
    def auth_enabled(self) -> bool:
        return getattr(self.server, "auth_required", False)

    def _sessions(self):
        return getattr(self.server, "sessions", set()), getattr(self.server, "sessions_lock", None)

    def get_session_id(self) -> Optional[str]:
        cookie = self.headers.get("Cookie") or ""
        for part in cookie.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "webexplorer_session":
                sid = v.strip()
                return sid if sid else None
        return None

    def is_authenticated(self) -> bool:
        if not self.auth_enabled():
            return True
        sid = self.get_session_id()
        if not sid:
            return False
        sessions, lock = self._sessions()
        if lock:
            with lock:
                return sid in sessions
        return sid in sessions

    # ---- Clipboard
    def _clip_set(self, path: Optional[str]):
        self.server.clip_source = path

    def _clip_get(self) -> Optional[str]:
        return getattr(self.server, "clip_source", None)

    # ---- Helfer
    def _exists_safe(self, path: str) -> bool:
        try:
            return os.path.exists(path)
        except Exception:
            return False

    def _same_or_descendant(self, src: str, dst_dir: str) -> bool:
        try:
            src_c = canonical_path(src)
            dst_c = canonical_path(dst_dir)
            return is_within(dst_c, src_c)
        except Exception:
            return False

    def _unique_dest_name(self, dest_dir: str, base_name: str) -> str:
        stem, ext = os.path.splitext(base_name)
        candidate = os.path.join(dest_dir, base_name)
        if not self._exists_safe(candidate):
            return candidate
        i = 1
        while True:
            name = f"{stem} (Copy {i}){ext}"
            candidate = os.path.join(dest_dir, name)
            if not self._exists_safe(candidate):
                return candidate
            i += 1

    def _resolve_android_root(self) -> str:
        srv_val = getattr(self.server, "android_root_path", None)
        if srv_val and dir_is_readable(srv_val):
            return srv_val
        new_root = detect_android_root()
        self.server.android_root_path = new_root
        return new_root

    # ---- Multipart parsing (replaces cgi.FieldStorage)
    def _parse_multipart(self) -> Tuple[Optional[str], Dict[str, str], Optional[str]]:
        ctype = self.headers.get("Content-Type") or ""
        clen = int(self.headers.get("Content-Length") or "0")
        main, _ = _parse_ct_params(ctype)
        if "multipart/form-data" not in main or clen <= 0:
            raise ValueError("Ungültiger Upload (Content-Type/Length)")

        raw_path = _read_request_to_tempfile(self.rfile, clen)

        try:
            fields_b, files = _parse_multipart_from_file(raw_path, ctype)
        except Exception as e:
            try:
                base = os.path.dirname(raw_path)
                shutil.rmtree(base, ignore_errors=True)
            except Exception:
                pass
            raise ValueError(f"Multipart parse failed: {e}")

        tmpfile_path = None
        filename = None

        file_part = None
        for p in files:
            if p.get("name") == "file":
                file_part = p
                break
        if file_part is None and files:
            file_part = files[0]

        if file_part:
            filename = os.path.basename(file_part.get("filename") or "")
            tmpfile_path = file_part.get("temp_path")
            if not (filename and tmpfile_path and os.path.isfile(tmpfile_path)):
                tmpfile_path = None
                filename = None

        fields: Dict[str, str] = {}
        for k, vals in fields_b.items():
            if not vals:
                continue
            try:
                fields[k] = (vals[-1] or b"").decode("utf-8", errors="replace")
            except Exception:
                fields[k] = ""

        try:
            base = os.path.dirname(raw_path)
            shutil.rmtree(base, ignore_errors=True)
        except Exception:
            pass

        return filename, fields, tmpfile_path

    def _zip_symlink_member(self, info: zipfile.ZipInfo) -> bool:
        try:
            return (info.external_attr >> 16) & 0o170000 == 0o120000
        except Exception:
            return False

    def _unzip_to_dir(self, zip_path: str, dest_dir: str,
                      progress_cb=None, bytes_cb=None, cancel_cb=None):
        if not os.path.isfile(zip_path) or not zip_path.lower().endswith(".zip"):
            return False, "Keine gültige ZIP-Datei.", 0, []

        dest_dir_canon = os.path.abspath(dest_dir)
        is_kodi_target = is_kodi_home(dest_dir_canon)

        extracted = 0
        skipped = []
        created_dirs = set()

        addons_db_detected = False
        textures_db_detected = False

        FAST_CHUNK = 8 * 1024 * 1024

        try:
            with zipfile.ZipFile(zip_path, "r", allowZip64=True) as zf:
                members = zf.infolist()
                total = len(members)

                if progress_cb:
                    progress_cb(0, total)

                for member in members:
                    if cancel_cb and cancel_cb():
                        return False, f"Abgebrochen. Bereits entpackt: {extracted}", extracted, skipped

                    name = member.filename
                    base = os.path.basename(name)
                    base_l = base.lower()

                    if (
                        base_l.startswith("addons")
                        and base_l.endswith(".db")
                        and base_l[6:-3].isdigit()
                    ):
                        addons_db_detected = True

                    if (
                        base_l.startswith("textures")
                        and base_l.endswith(".db")
                        and base_l[8:-3].isdigit()
                    ):
                        textures_db_detected = True

                    if self._zip_symlink_member(member) and not FOLLOW_SYMLINKS:
                        skipped.append(name + " (symlink)")
                        continue

                    target = os.path.normpath(os.path.join(dest_dir, name))
                    target_abs = os.path.abspath(target)

                    try:
                        common = os.path.commonpath([dest_dir_canon, target_abs])
                    except Exception:
                        common = dest_dir_canon

                    if common != dest_dir_canon:
                        skipped.append(name)
                        continue

                    if is_kodi_target:
                        if "/" not in name and extract_saved_top(name):
                            skipped.append(name)
                            continue
                        if is_protected_path(target_abs):
                            skipped.append(name)
                            continue

                    try:
                        if member.is_dir():
                            if target_abs not in created_dirs:
                                os.makedirs(target_abs, exist_ok=True)
                                created_dirs.add(target_abs)
                        else:
                            dirpath = os.path.dirname(target_abs)
                            if dirpath not in created_dirs:
                                os.makedirs(dirpath, exist_ok=True)
                                created_dirs.add(dirpath)

                            local_bytes = 0
                            with zf.open(member, "r") as src, open(target_abs, "wb") as dst:
                                while True:
                                    buf = src.read(FAST_CHUNK)
                                    if not buf:
                                        break
                                    dst.write(buf)
                                    if bytes_cb:
                                        lb = len(buf)
                                        local_bytes += lb
                                        if local_bytes >= 512 * 1024:
                                            bytes_cb(local_bytes)
                                            local_bytes = 0
                            if bytes_cb and local_bytes:
                                bytes_cb(local_bytes)

                        extracted += 1

                    except Exception as e:
                        skipped.append(f"{name} ({e})")

                    if progress_cb and (extracted & 0x3F) == 0:
                        progress_cb(extracted, total)

            if addons_db_detected or textures_db_detected:
                try:
                    self._activate_all_addons_after_restore()
                except Exception as e:
                    log_err(f"Addon-Aktivierung nach Restore fehlgeschlagen: {e}")

            return True, f"Entpackt: {extracted} Einträge.", extracted, skipped

        except zipfile.BadZipFile:
            return False, "Defekte ZIP-Datei.", 0, []
        except Exception as e:
            log_err(f"_unzip_to_dir Fehler: {e}\n{traceback.format_exc()}")
            return False, f"Fehler beim Entpacken: {e}", extracted, skipped

    def _activate_all_addons_after_restore(self):
        xbmc.executebuiltin("Dialog.Close(all)")
        xbmc.executebuiltin("UpdateLocalAddons")
        xbmc.sleep(1000)
        xbmc.executebuiltin("Dialog.Close(all)")

        try:
            response = xbmc.executeJSONRPC(json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "Addons.GetAddons",
                "params": {
                    "enabled": False
                }
            }))

            data = json.loads(response)
            addons = data.get("result", {}).get("addons", [])

            for addon in addons:
                addon_id = addon.get("addonid")
                if not addon_id:
                    continue

                xbmc.executeJSONRPC(json.dumps({
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "Addons.SetAddonEnabled",
                    "params": {
                        "addonid": addon_id,
                        "enabled": True
                    }
                }))

        except Exception as e:
            log_err(f"Addon-Aktivierung fehlgeschlagen: {e}")

        xbmc.executebuiltin("Dialog.Close(all)")

    # ---- GET
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        rel = qs.get("path", [""])[0] if qs else ""

        try:
            if path == "/shutdown":
                self.send_json({"status": "ok", "message": "Server wird beendet..."})

                def _shutdown():
                    try:
                        self.server.shutdown()
                    except Exception as e:
                        log_err(f"Fehler beim shutdown(): {e}\n{traceback.format_exc()}")

                threading.Thread(target=_shutdown, daemon=True).start()
                return

            if self.auth_enabled() and not self.is_authenticated():
                if path == "/login":
                    err = qs.get("err", [""])[0]
                    return self.handle_login_page(error=(err == "1"))
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header("Location", f"/login?next={urllib.parse.quote(self.path)}")
                self.send_header("Connection", "close")
                self.end_headers()
                return

            if path == "/login":
                if not self.auth_enabled():
                    self.send_response(HTTPStatus.SEE_OTHER)
                    self.send_header("Location", "/")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    return
                return self.handle_login_page()

            if path == "/":
                return self.send_index_html()

            if path == "/setroot":
                root_name = (qs.get("root", [""])[0] or "").strip()
                if root_name not in ROOT_DIRS:
                    return self.send_json_error("Ungültiger Root", HTTPStatus.BAD_REQUEST)

                if root_name == "Android":
                    target = self._resolve_android_root()
                    if not dir_is_readable(target):
                        return self.send_json_error("Android Root ist nicht lesbar.", HTTPStatus.FORBIDDEN)
                    self.server.current_root = target
                    self.server.current_root_name = "Android"
                else:
                    target = ROOT_DIRS["Kodi"]
                    if not dir_is_readable(target):
                        return self.send_json_error("Kodi Root ist nicht lesbar.", HTTPStatus.FORBIDDEN)
                    self.server.current_root = target
                    self.server.current_root_name = "Kodi"

                return self.send_json({"status": "ok", "message": f"Root gewechselt: {self.server.current_root_name}"})

            if path == "/api/info":
                info = {
                    "ips": get_local_ips(),
                    "port": self.server.server_address[1],
                    "current_root": getattr(self.server, "current_root_name", "Android"),
                    "current_root_path": getattr(self.server, "current_root", ROOT_DIRS.get("Android", "/")),
                    "android_root_path": getattr(self.server, "android_root_path", "/"),
                    "follow_symlinks": FOLLOW_SYMLINKS
                }
                return self.send_json(info)

            if path == "/api/list":
                current_root = getattr(self.server, "current_root", self._resolve_android_root())
                current_root_name = getattr(self.server, "current_root_name", "Android")
                try:
                    abs_path = safe_join(current_root, rel)
                except ValueError as e:
                    return self.send_json_error(str(e), HTTPStatus.BAD_REQUEST)
                if not os.path.isdir(abs_path):
                    return self.send_json_error("Verzeichnis nicht gefunden", HTTPStatus.NOT_FOUND)
                items = []
                try:
                    with os.scandir(abs_path) as it:
                        for entry in it:
                            try:
                                is_dir = entry.is_dir(follow_symlinks=FOLLOW_SYMLINKS)
                            except Exception:
                                is_dir = True
                            size = None
                            if not is_dir:
                                try:
                                    size = entry.stat(follow_symlinks=FOLLOW_SYMLINKS).st_size
                                except Exception:
                                    size = None
                            items.append({
                                "name": entry.name,
                                "relpath": os.path.relpath(os.path.join(abs_path, entry.name), current_root),
                                "is_dir": is_dir,
                                "size": size,
                                "is_link": entry.is_symlink()
                            })
                except PermissionError:
                    return self.send_json_error("Keine Berechtigung, Verzeichnis zu lesen", HTTPStatus.FORBIDDEN)
                except Exception as e:
                    log_err(f"Fehler beim Lesen {abs_path}: {e}\n{traceback.format_exc()}")
                    return self.send_json_error("Fehler beim Lesen", HTTPStatus.INTERNAL_SERVER_ERROR)
                items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
                clip_src = self._clip_get()
                clip_name = os.path.basename(clip_src) if clip_src else ""
                return self.send_json({
                    "path": os.path.relpath(abs_path, current_root),
                    "root_name": current_root_name,
                    "items": items,
                    "clip": {"has": bool(clip_src), "name": clip_name}
                })

            if path == "/download":
                current_root = getattr(self.server, "current_root", self._resolve_android_root())
                try:
                    abs_path = safe_join(current_root, rel)
                except ValueError as e:
                    return self.send_json_error(str(e), HTTPStatus.BAD_REQUEST)
                include_root = qs.get("includeRoot", ["1"])[0] == "1"
                if os.path.isdir(abs_path):
                    return self.stream_zip(abs_path, include_root)
                if os.path.isfile(abs_path) or os.path.islink(abs_path):
                    return self.stream_file(abs_path)
                return self.send_json_error("Nicht gefunden", HTTPStatus.NOT_FOUND)

            if path == "/delete":
                current_root = getattr(self.server, "current_root", self._resolve_android_root())
                try:
                    abs_path = safe_join(current_root, rel)
                except ValueError as e:
                    return self.send_json_error(str(e), HTTPStatus.BAD_REQUEST)

                if canonical_path(abs_path) == canonical_path(current_root):
                    log_err(f"Abgelehnte Lösch-Anfrage (Root-Schutz): {abs_path}")
                    return self.send_json_error("Löschen des Root-Verzeichnisses ist nicht erlaubt.", HTTPStatus.FORBIDDEN)

                if os.path.isfile(abs_path) or os.path.islink(abs_path):
                    if _should_skip_delete(abs_path):
                        return self.send_json_error("Geschützte Datei kann nicht gelöscht werden.", HTTPStatus.FORBIDDEN)
                    try:
                        os.remove(abs_path)
                        if self._clip_get() and canonical_path(self._clip_get()) == canonical_path(abs_path):
                            self._clip_set(None)
                        return self.send_json({"status": "ok", "message": f"{rel} gelöscht"})
                    except PermissionError:
                        return self.send_json_error("Keine Berechtigung", HTTPStatus.FORBIDDEN)
                    except FileNotFoundError:
                        return self.send_json_error("Nicht gefunden", HTTPStatus.NOT_FOUND)
                    except Exception as e:
                        log_err(f"Fehler beim Löschen Datei {abs_path}: {e}\n{traceback.format_exc()}")
                        return self.send_json_error("Fehler beim Löschen", HTTPStatus.INTERNAL_SERVER_ERROR)

                if os.path.isdir(abs_path):
                    if PROTECT_DELETE_ENABLED and _should_skip_delete(abs_path):
                        log_err(f"Abgelehnte Lösch-Anfrage (Schutzpfad-Verzeichnis): {abs_path}")
                        return self.send_json_error("Löschen eines geschützten Verzeichnisses ist nicht erlaubt.", HTTPStatus.FORBIDDEN)

                    deleted, skipped, errors = safe_delete_tree(abs_path, delete_self=True)
                    clip = self._clip_get()
                    if clip and is_within(canonical_path(clip), canonical_path(abs_path)):
                        self._clip_set(None)
                    msg = f"Gelöscht: {deleted} Elemente."
                    if skipped:
                        msg += f" Übersprungen: {len(skipped)} (geschützt)."
                    if errors:
                        msg += f" Fehler: {len(errors)}."
                    return self.send_json({"status": "ok", "message": msg, "skipped": skipped, "errors": errors})

                return self.send_json_error("Nicht gefunden", HTTPStatus.NOT_FOUND)

            if path == "/copy":
                current_root = getattr(self.server, "current_root", self._resolve_android_root())
                try:
                    abs_src = safe_join(current_root, rel)
                except ValueError as e:
                    return self.send_json_error(str(e), HTTPStatus.BAD_REQUEST)

                if not os.path.exists(abs_src):
                    return self.send_json_error("Quelle nicht gefunden", HTTPStatus.NOT_FOUND)

                self._clip_set(abs_src)
                return self.send_json({"status": "ok", "message": f"Zur Zwischenablage hinzugefügt: {os.path.basename(abs_src)}"})

            if path == "/api/clip":
                src = self._clip_get()
                return self.send_json({"has": bool(src), "name": os.path.basename(src) if src else ""})

            if path == "/clip_clear":
                self._clip_set(None)
                return self.send_json({"status": "ok", "message": "Zwischenablage geleert"})

            if path == "/paste":
                current_root = getattr(self.server, "current_root", self._resolve_android_root())
                dest_rel = rel
                try:
                    abs_dest_dir = safe_join(current_root, dest_rel)
                except ValueError as e:
                    return self.send_json_error(str(e), HTTPStatus.BAD_REQUEST)

                if not os.path.isdir(abs_dest_dir):
                    return self.send_json_error("Ziel ist kein Verzeichnis.", HTTPStatus.BAD_REQUEST)

                src = self._clip_get()
                if not src or not os.path.exists(src):
                    return self.send_json_error("Zwischenablage ist leer oder Quelle nicht vorhanden.", HTTPStatus.BAD_REQUEST)

                if os.path.isdir(src) and self._same_or_descendant(src, abs_dest_dir):
                    return self.send_json_error("Zirkuläres Kopieren in Unterordner ist nicht erlaubt.", HTTPStatus.BAD_REQUEST)

                ok, msg = self._copy_entry_sync(src, abs_dest_dir)
                if ok:
                    self._clip_set(None)
                    return self.send_json({"status": "ok", "message": msg})
                else:
                    return self.send_json_error(msg, HTTPStatus.BAD_REQUEST)

            if path == "/paste_start":
                current_root = getattr(self.server, "current_root", self._resolve_android_root())
                dest_rel = rel
                try:
                    abs_dest_dir = safe_join(current_root, dest_rel)
                except ValueError as e:
                    return self.send_json_error(str(e), HTTPStatus.BAD_REQUEST)

                if not os.path.isdir(abs_dest_dir):
                    return self.send_json_error("Ziel ist kein Verzeichnis.", HTTPStatus.BAD_REQUEST)

                src = self._clip_get()
                if not src or not os.path.exists(src):
                    return self.send_json_error("Zwischenablage ist leer oder Quelle nicht vorhanden.", HTTPStatus.BAD_REQUEST)

                if os.path.isdir(src) and self._same_or_descendant(src, abs_dest_dir):
                    return self.send_json_error("Zirkuläres Kopieren in Unterordner ist nicht erlaubt.", HTTPStatus.BAD_REQUEST)

                task_id = self._start_copy_task(src, abs_dest_dir)
                if not task_id:
                    return self.send_json_error("Zu viele parallele Tasks. Bitte später erneut versuchen.", HTTPStatus.TOO_MANY_REQUESTS)

                return self.send_json({"status": "ok", "task_id": task_id, "name": os.path.basename(src)})

            if path == "/copy_status":
                task_id = qs.get("task", [""])[0]
                if not task_id:
                    return self.send_json_error("task Parameter fehlt", HTTPStatus.BAD_REQUEST)
                data = self._get_copy_status(task_id)
                if data is None:
                    return self.send_json_error("Task nicht gefunden", HTTPStatus.NOT_FOUND)
                return self.send_json(data)

            if path == "/copy_cancel":
                task_id = qs.get("task", [""])[0]
                if not task_id:
                    return self.send_json_error("task Parameter fehlt", HTTPStatus.BAD_REQUEST)
                ok = self._cancel_copy(task_id)
                if not ok:
                    return self.send_json_error("Task nicht gefunden", HTTPStatus.NOT_FOUND)
                return self.send_json({"status": "ok", "message": "Abbruch angefordert"})

            if path == "/unzip":
                current_root = getattr(self.server, "current_root", self._resolve_android_root())
                try:
                    abs_zip = safe_join(current_root, rel)
                except ValueError as e:
                    return self.send_json_error(str(e), HTTPStatus.BAD_REQUEST)
                if not os.path.isfile(abs_zip) or not abs_zip.lower().endswith(".zip"):
                    return self.send_json_error("Keine ZIP-Datei.", HTTPStatus.BAD_REQUEST)

                if PROTECT_UNZIP_ENABLED and is_kodi_home(os.path.dirname(abs_zip)) and is_protected_path(os.path.dirname(abs_zip)):
                    return self.send_json_error("Entpacken in geschütztes Verzeichnis ist nicht erlaubt.", HTTPStatus.FORBIDDEN)

                dest_dir = os.path.dirname(abs_zip)
                ok, msg, _count, skipped = self._unzip_to_dir(abs_zip, dest_dir)
                if ok:
                    return self.send_json({"status": "ok", "message": msg, "skipped": skipped})
                else:
                    return self.send_json({"status": "error", "message": msg, "skipped": skipped}, status=HTTPStatus.BAD_REQUEST)

            if path == "/unzip_start":
                current_root = getattr(self.server, "current_root", self._resolve_android_root())
                try:
                    abs_zip = safe_join(current_root, rel)
                except ValueError as e:
                    return self.send_json_error(str(e), HTTPStatus.BAD_REQUEST)
                if not os.path.isfile(abs_zip) or not abs_zip.lower().endswith(".zip"):
                    return self.send_json_error("Keine ZIP-Datei.", HTTPStatus.BAD_REQUEST)

                if PROTECT_UNZIP_ENABLED and is_kodi_home(os.path.dirname(abs_zip)) and is_protected_path(os.path.dirname(abs_zip)):
                    return self.send_json_error("Entpacken in geschütztes Verzeichnis ist nicht erlaubt.", HTTPStatus.FORBIDDEN)

                dest_dir = os.path.dirname(abs_zip)
                task_id = self._start_unzip_task(abs_zip, dest_dir)
                if not task_id:
                    return self.send_json_error("Zu viele parallele Tasks. Bitte später erneut versuchen.", HTTPStatus.TOO_MANY_REQUESTS)
                return self.send_json({"status": "ok", "task_id": task_id})

            if path == "/unzip_status":
                task_id = qs.get("task", [""])[0]
                if not task_id:
                    return self.send_json_error("task Parameter fehlt", HTTPStatus.BAD_REQUEST)
                data = self._get_unzip_status(task_id)
                if data is None:
                    return self.send_json_error("Task nicht gefunden", HTTPStatus.NOT_FOUND)
                return self.send_json(data)

            if path == "/unzip_cancel":
                task_id = qs.get("task", [""])[0]
                if not task_id:
                    return self.send_json_error("task Parameter fehlt", HTTPStatus.BAD_REQUEST)
                ok = self._cancel_unzip(task_id)
                if not ok:
                    return self.send_json_error("Task nicht gefunden", HTTPStatus.NOT_FOUND)
                return self.send_json({"status": "ok", "message": "Abbruch angefordert"})

            if path == "/zip_start":
                current_root = getattr(self.server, "current_root", self._resolve_android_root())
                try:
                    abs_dir = safe_join(current_root, rel)
                except ValueError as e:
                    return self.send_json_error(str(e), HTTPStatus.BAD_REQUEST)
                if not os.path.isdir(abs_dir):
                    return self.send_json_error("Kein Verzeichnis.", HTTPStatus.BAD_REQUEST)
                include_root = qs.get("includeRoot", ["1"])[0] == "1"
                base_name = os.path.basename(os.path.normpath(abs_dir)) or "archive"
                filename = f"{base_name}.zip"
                task_id = self._start_zip_task(abs_dir, include_root, filename)
                if not task_id:
                    return self.send_json_error("Zu viele parallele Tasks. Bitte später erneut versuchen.", HTTPStatus.TOO_MANY_REQUESTS)
                return self.send_json({"status": "ok", "task_id": task_id, "filename": filename})

            if path == "/zip_status":
                task_id = qs.get("task", [""])[0]
                if not task_id:
                    return self.send_json_error("task Parameter fehlt", HTTPStatus.BAD_REQUEST)
                data = self._get_zip_status(task_id)
                if data is None:
                    return self.send_json_error("Task nicht gefunden", HTTPStatus.NOT_FOUND)
                return self.send_json(data)

            if path == "/zip_cancel":
                task_id = qs.get("task", [""])[0]
                if not task_id:
                    return self.send_json_error("task Parameter fehlt", HTTPStatus.BAD_REQUEST)
                ok = self._cancel_zip(task_id)
                if not ok:
                    return self.send_json_error("Task nicht gefunden", HTTPStatus.NOT_FOUND)
                return self.send_json({"status": "ok", "message": "Abbruch angefordert"})

            if path == "/zip_get":
                task_id = qs.get("task", [""])[0]
                if not task_id:
                    return self.send_json_error("task Parameter fehlt", HTTPStatus.BAD_REQUEST)
                return self._stream_zip_task(task_id)

            if path == "/deletecontents":
                current_root = getattr(self.server, "current_root", self._resolve_android_root())
                try:
                    abs_dir = safe_join(current_root, rel)
                except ValueError as e:
                    return self.send_json_error(str(e), HTTPStatus.BAD_REQUEST)
                if not os.path.isdir(abs_dir):
                    return self.send_json_error("Kein Verzeichnis.", HTTPStatus.BAD_REQUEST)

                if PROTECT_DELETE_ENABLED and _should_skip_delete(abs_dir):
                    return self.send_json_error("Inhalt eines geschützten Verzeichnisses darf nicht gelöscht werden.", HTTPStatus.FORBIDDEN)

                deleted_total = 0
                skipped_all: List[str] = []
                errors_all: List[str] = []
                try:
                    with os.scandir(abs_dir) as it:
                        for entry in it:
                            target = os.path.join(abs_dir, entry.name)
                            d, skipped, errs = safe_delete_tree(target, delete_self=True)
                            deleted_total += d
                            if skipped:
                                skipped_all.extend(skipped)
                            if errs:
                                errors_all.extend(errs)
                except Exception as e:
                    errors_all.append(str(e))
                msg = f"Inhalt gelöscht: {deleted_total} Elemente."
                if skipped_all:
                    msg += f" Übersprungen: {len(skipped_all)}."
                if errors_all:
                    msg += f" Fehler: {len(errors_all)}."
                return self.send_json({"status": "ok", "message": msg, "skipped": skipped_all, "errors": errors_all})

            if path == "/deletecontents_start":
                current_root = getattr(self.server, "current_root", self._resolve_android_root())
                try:
                    abs_dir = safe_join(current_root, rel)
                except ValueError as e:
                    return self.send_json_error(str(e), HTTPStatus.BAD_REQUEST)
                if not os.path.isdir(abs_dir):
                    return self.send_json_error("Kein Verzeichnis.", HTTPStatus.BAD_REQUEST)

                if PROTECT_DELETE_ENABLED and _should_skip_delete(abs_dir):
                    return self.send_json_error("Inhalt eines geschützten Verzeichnisses darf nicht gelöscht werden.", HTTPStatus.FORBIDDEN)

                task_id = self._start_delete_task(abs_dir)
                if not task_id:
                    return self.send_json_error("Zu viele parallele Tasks. Bitte später erneut versuchen.", HTTPStatus.TOO_MANY_REQUESTS)
                return self.send_json({"status": "ok", "task_id": task_id})

            if path == "/deletecontents_status":
                task_id = qs.get("task", [""])[0]
                if not task_id:
                    return self.send_json_error("task Parameter fehlt", HTTPStatus.BAD_REQUEST)
                data = self._get_delete_status(task_id)
                if data is None:
                    return self.send_json_error("Task nicht gefunden", HTTPStatus.NOT_FOUND)
                return self.send_json(data)

            if path == "/deletecontents_cancel":
                task_id = qs.get("task", [""])[0]
                if not task_id:
                    return self.send_json_error("task Parameter fehlt", HTTPStatus.BAD_REQUEST)
                ok = self._cancel_delete(task_id)
                if not ok:
                    return self.send_json_error("Task nicht gefunden", HTTPStatus.NOT_FOUND)
                return self.send_json({"status": "ok", "message": "Abbruch angefordert"})

            if path == "/quit":
                try:
                    xbmc.executebuiltin("Quit()")
                    return self.write_text("Kodi beendet")
                except Exception as e:
                    log_err(f"Quit() fehlgeschlagen: {e}\n{traceback.format_exc()}")
                    return self.send_json_error("Quit fehlgeschlagen", HTTPStatus.INTERNAL_SERVER_ERROR)

            if path == "/appinfo":
                try:
                    xbmc.executebuiltin('StartAndroidActivity("","android.settings.APPLICATION_DETAILS_SETTINGS","","package:org.xbmc.kodi")')
                    return self.send_json({"status": "ok", "message": "App-Info geöffnet"})
                except Exception as e:
                    log_err(f"App-Info öffnen fehlgeschlagen: {e}\n{traceback.format_exc()}")
                    return self.send_json_error("App-Info öffnen fehlgeschlagen", HTTPStatus.INTERNAL_SERVER_ERROR)

            static_candidate = (RESOURCES_HTML / path.strip("/"))
            if static_candidate.exists() and static_candidate.is_file():
                try:
                    data = static_candidate.read_bytes()
                    return self.send_bytes(data, content_type=guess_content_type(str(static_candidate)))
                except Exception as e:
                    log_err(f"Fehler beim Ausliefern statischer Datei {static_candidate}: {e}\n{traceback.format_exc()}")
                    return self.send_json_error("Serverfehler", HTTPStatus.INTERNAL_SERVER_ERROR)

            return self.send_json_error("Unbekannter Pfad", HTTPStatus.NOT_FOUND)

        except ValueError as e:
            return self.send_json_error(str(e), HTTPStatus.BAD_REQUEST)
        except Exception as e:
            log_err(f"Error in GET {path}: {e}\n{traceback.format_exc()}")
            return self.send_json_error("Serverfehler", HTTPStatus.INTERNAL_SERVER_ERROR)

    # ---- POST
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        rel = qs.get("path", [""])[0] if qs else ""

        try:
            if path == "/login":
                if not self.auth_enabled():
                    self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                    self.send_header("Location", "/")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    return
                return self.try_login()

            if self.auth_enabled() and not self.is_authenticated():
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header("Location", f"/login?next={urllib.parse.quote(self.path)}")
                self.send_header("Connection", "close")
                self.end_headers()
                return

            if path != "/upload":
                return self.send_json_error("Unknown POST path", HTTPStatus.NOT_FOUND)

            current_root = getattr(self.server, "current_root", self._resolve_android_root())
            try:
                abs_path = safe_join(current_root, rel)
            except ValueError as e:
                return self.send_json_error(str(e), HTTPStatus.BAD_REQUEST)
            if not os.path.isdir(abs_path):
                return self.send_json_error("Zielverzeichnis existiert nicht", HTTPStatus.NOT_FOUND)

            try:
                filename, fields, tmpfile_path = self._parse_multipart()
            except Exception as e:
                tb = traceback.format_exc()
                log_err(f"Multipart Fehler: {e}\n{tb}")
                return self.send_json({"status": "error", "message": "Upload parsing failed", "detail": str(e)}, status=HTTPStatus.BAD_REQUEST)

            if not filename or not tmpfile_path:
                return self.send_json_error("Keine Datei ausgewählt", HTTPStatus.BAD_REQUEST)
            base_name = os.path.basename(filename)

            unpack_flag = (fields.get("unpack", "0") or "0").strip()
            if "unpack" not in fields:
                unpack_flag = (qs.get("unpack", ["0"])[0] or "0").strip()
            unpack = (unpack_flag == "1")
            async_flag = (qs.get("async", ["0"])[0] == "1")

            final_candidate = os.path.join(abs_path, base_name)
            if is_insert_protected(final_candidate):
                log_err(f"Abgelehnter Upload (Schutzpfad): {final_candidate}")
                try:
                    shutil.rmtree(os.path.dirname(tmpfile_path), ignore_errors=True)
                except Exception:
                    pass
                return self.send_json_error("Hochladen in geschützte Verzeichnisse nicht erlaubt.", HTTPStatus.FORBIDDEN)

            try:
                if base_name.lower().endswith(".zip") and unpack:
                    if PROTECT_UNZIP_ENABLED and is_kodi_home(abs_path) and is_protected_path(abs_path):
                        try:
                            shutil.rmtree(os.path.dirname(tmpfile_path), ignore_errors=True)
                        except Exception:
                            pass
                        return self.send_json_error("Entpacken in geschütztes Verzeichnis ist nicht erlaubt.", HTTPStatus.FORBIDDEN)
                    if async_flag:
                        task_id = self._start_unzip_task(tmpfile_path, abs_path, cleanup_zip_after=True)
                        if not task_id:
                            try:
                                shutil.rmtree(os.path.dirname(tmpfile_path), ignore_errors=True)
                            except Exception:
                                pass
                            return self.send_json_error("Zu viele parallele Tasks. Bitte später erneut versuchen.", HTTPStatus.TOO_MANY_REQUESTS)
                        return self.send_json({"status": "ok", "message": "Entpacken gestartet", "task_id": task_id})
                    else:
                        ok, msg, _count, skipped = self._unzip_to_dir(tmpfile_path, abs_path)
                        try:
                            shutil.rmtree(os.path.dirname(tmpfile_path), ignore_errors=True)
                        except Exception:
                            pass
                        if ok:
                            return self.send_json({"status": "ok", "message": f"{msg} (Upload-Entpacken).", "skipped": skipped})
                        else:
                            return self.send_json({"status": "error", "message": msg, "skipped": skipped}, status=HTTPStatus.BAD_REQUEST)
                else:
                    final_path = os.path.join(abs_path, base_name)
                    if is_insert_protected(final_path):
                        log_err(f"Abgelehnter Upload final (Schutzpfad): {final_path}")
                        try:
                            shutil.rmtree(os.path.dirname(tmpfile_path), ignore_errors=True)
                        except Exception:
                            pass
                        return self.send_json_error("Hochladen in geschützte Verzeichnisse nicht erlaubt.", HTTPStatus.FORBIDDEN)
                    try:
                        shutil.move(tmpfile_path, final_path)
                    except Exception:
                        with open(tmpfile_path, "rb") as src, open(final_path, "wb") as dst:
                            shutil.copyfileobj(src, dst, length=CHUNK_SIZE)
                        try:
                            os.remove(tmpfile_path)
                        except Exception:
                            pass
                    try:
                        shutil.rmtree(os.path.dirname(tmpfile_path), ignore_errors=True)
                    except Exception:
                        pass
                    if base_name.lower().endswith(".zip") and not unpack:
                        return self.send_json({"status": "ok", "message": f"ZIP {base_name} hochgeladen (nicht entpackt)."})
                    return self.send_json({"status": "ok", "message": f"Datei {base_name} hochgeladen."})
            except Exception as e:
                tb = traceback.format_exc()
                log_err(f"Upload-Verarbeitung Fehler: {e}\n{tb}")
                return self.send_json({"status": "error", "message": "Fehler beim Verarbeiten", "detail": str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            finally:
                if not (base_name.lower().endswith(".zip") and unpack and async_flag):
                    try:
                        if tmpfile_path and os.path.exists(os.path.dirname(tmpfile_path)):
                            shutil.rmtree(os.path.dirname(tmpfile_path), ignore_errors=True)
                    except Exception:
                        pass

        except ValueError as e:
            return self.send_json_error(str(e), HTTPStatus.BAD_REQUEST)
        except Exception as e:
            tb = traceback.format_exc()
            log_err(f"Error in POST {path}: {e}\n{tb}")
            return self.send_json({"status": "error", "message": "Serverfehler", "detail": str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    # ---- Login-Seiten
    def handle_login_page(self, error: bool = False):
        try:
            login_file = RESOURCES_HTML / "login.html"
            if login_file.exists():
                data = login_file.read_bytes()
                return self.send_bytes(data, content_type=guess_content_type("login.html"))
        except Exception as e:
            log_err(f"Fehler beim Laden login.html: {e}\n{traceback.format_exc()}")
        html = f"""<!doctype html><html lang="de"><meta charset="utf-8">
<title>Login</title><body>
<h2>Login</h2>
{'<div style="color:#c00">Anmeldung fehlgeschlagen</div>' if error else ''}
<form method="POST" action="/login">
  <label>Benutzername: <input type="text" name="username" /></label><br/>
  <label>Passwort: <input type="password" name="password" /></label><br/>
  <button type="submit">Anmelden</button>
</form>
</body></html>"""
        return self.send_bytes(html.encode("utf-8"), content_type="text/html; charset=utf-8")

    def try_login(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            next_target = qs.get("next", [""])[0] if qs else ""
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length) if length > 0 else b""
            ctype = self.headers.get("Content-Type", "")

            params: Dict[str, List[str]] = {}
            if "application/x-www-form-urlencoded" in ctype:
                s = body.decode("utf-8", errors="ignore")
                params = urllib.parse.parse_qs(s, keep_blank_values=True)
            elif "multipart/form-data" in ctype:
                _ensure_tempdir()
                tmpdir = tempfile.mkdtemp(prefix="kodi_login_", dir=get_work_tempdir())
                raw_path = os.path.join(tmpdir, "body.bin")
                with open(raw_path, "wb") as out:
                    out.write(body)
                try:
                    fields_b, _files = _parse_multipart_from_file(raw_path, ctype)
                    tmp_params: Dict[str, List[str]] = {}
                    for k, vals in fields_b.items():
                        tmp_params[k] = [(vals[-1] or b"").decode("utf-8", errors="replace")]
                    params = tmp_params
                finally:
                    try:
                        shutil.rmtree(tmpdir, ignore_errors=True)
                    except Exception:
                        pass
            else:
                s = body.decode("utf-8", errors="ignore")
                params = urllib.parse.parse_qs(s, keep_blank_values=True)

            u_in = (params.get("username", [""])[0] or "").strip()
            p_in = (params.get("password", [""])[0] or "").strip()

            username = getattr(self.server, "username", "")
            password = getattr(self.server, "password", "")

            ok = (u_in == username) and (p_in == password)
            time.sleep(0.05)

            if ok:
                sid = secrets.token_urlsafe(24)
                sessions, lock = self._sessions()
                if lock:
                    with lock:
                        sessions.add(sid)
                else:
                    sessions.add(sid)
                self.server.sessions = sessions
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header("Set-Cookie", f"webexplorer_session={sid}; Max-Age=86400; HttpOnly; SameSite=Lax; Path=/")
                self.send_header("Location", next_target or "/")
                self.send_header("Connection", "close")
                self.end_headers()
            else:
                self.send_response(HTTPStatus.UNAUTHORIZED)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Connection", "close")
                self.end_headers()
                self._safe_wfile_write(b"<html><body><h3>Login fehlgeschlagen</h3><a href=\"/login?err=1\">Nochmal versuchen</a></body></html>")
        except Exception as e:
            log_err(f"Login-Fehler: {e}\n{traceback.format_exc()}")
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.send_header("Connection", "close")
            self.end_headers()
            self._safe_wfile_write(b"Serverfehler")

    # ---- Task-Limit / Cleanup
    def _acquire_task_slot(self) -> bool:
        try:
            return self.server.task_semaphore.acquire(blocking=False)
        except Exception as e:
            log_err(f"_acquire_task_slot Fehler: {e}\n{traceback.format_exc()}")
            return True

    def _release_task_slot(self):
        try:
            self.server.task_semaphore.release()
        except Exception as e:
            log_err(f"_release_task_slot Fehler: {e}\n{traceback.format_exc()}")

    # ---- Async Unzip Helpers
    def _start_unzip_task(self, zip_path: str, dest_dir: str, cleanup_zip_after: bool = False) -> Optional[str]:
        if not self._acquire_task_slot():
            return None

        task = UnzipTask(zip_path, dest_dir)

        task_id = secrets.token_urlsafe(16)
        with self.server.unzip_lock:
            self.server.unzip_tasks[task_id] = task

        def run():
            try:
                task.set_state("running", "Entpacken läuft...")
                task.set_progress(0, 0)

                def pcb(done: int, total: int):
                    task.set_progress(done, total)

                def bcb(inc: int):
                    task.inc_bytes(inc)

                def cancel_cb() -> bool:
                    return task.is_canceled()

                ok, msg, extracted, skipped = self._unzip_to_dir(
                    task.zip_path,
                    task.dest_dir,
                    progress_cb=pcb,
                    bytes_cb=bcb,
                    cancel_cb=cancel_cb,
                )

                task.skipped = skipped

                if task.is_canceled():
                    task.set_state("canceled", f"Entpacken abgebrochen. Bereits entpackt: {extracted}")
                elif ok:
                    task.set_state("done", msg or f"Entpackt: {extracted} Einträge.")
                else:
                    task.set_state("error", msg or "Fehler beim Entpacken.")
            except Exception as e:
                log_err(f"Unzip Task Fehler: {e}\n{traceback.format_exc()}")
                task.set_state("error", f"Fehler: {e}")
            finally:
                if cleanup_zip_after:
                    try:
                        tmpdir = os.path.dirname(task.zip_path)
                        if os.path.isfile(task.zip_path):
                            os.remove(task.zip_path)
                        if tmpdir and os.path.isdir(tmpdir):
                            shutil.rmtree(tmpdir, ignore_errors=True)
                    except Exception as e:
                        log_err(f"Cleanup ZIP fehlgeschlagen: {e}\n{traceback.format_exc()}")
                self._release_task_slot()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        return task_id

    def _get_unzip_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.server.unzip_lock:
            task = self.server.unzip_tasks.get(task_id)
        if not task:
            return None
        with task._lock:
            data = {
                "status": "ok",
                "task_id": task_id,
                "total": task.total,
                "done": task.done,
                "bytes_total": task.bytes_total,
                "bytes_done": task.bytes_done,
                "state": task.state,
                "message": task.message,
                "skipped": task.skipped,
            }
            if task.state in ("done", "error", "canceled"):
                with self.server.unzip_lock:
                    try:
                        del self.server.unzip_tasks[task_id]
                    except Exception:
                        pass
        return data

    def _cancel_unzip(self, task_id: str) -> bool:
        with self.server.unzip_lock:
            task = self.server.unzip_tasks.get(task_id)
        if not task:
            return False
        task.request_cancel()
        return True

    # ---- Async ZIP Helpers
    def _start_zip_task(self, src_dir: str, include_root: bool, filename: str) -> Optional[str]:
        if not self._acquire_task_slot():
            return None

        task = ZipTask(src_dir, include_root, filename)

        files: List[Tuple[str, str, int]] = []
        dirs_to_add: set[str] = set()

        try:
            base_for_files = os.path.dirname(src_dir.rstrip(os.sep)) if include_root else src_dir
            root_name = os.path.basename(src_dir.rstrip(os.sep))

            stack: List[str] = [src_dir]
            while stack:
                current = stack.pop()
                try:
                    with os.scandir(current) as it:
                        for entry in it:
                            full = entry.path
                            try:
                                if entry.is_dir(follow_symlinks=FOLLOW_SYMLINKS):
                                    stack.append(full)
                                    if include_root:
                                        rel = os.path.relpath(full, base_for_files)
                                    else:
                                        rel = os.path.relpath(full, src_dir)
                                    if rel in ('.', ''):
                                        if include_root:
                                            rel = root_name
                                        else:
                                            continue
                                    arcdir = rel.replace(os.sep, '/')
                                    if not arcdir.endswith('/'):
                                        arcdir += '/'
                                    dirs_to_add.add(arcdir)
                                else:
                                    try:
                                        st = entry.stat(follow_symlinks=False)
                                        sz = getattr(st, "st_size", 0)
                                    except Exception:
                                        sz = 0
                                    if include_root:
                                        rel = os.path.relpath(full, base_for_files)
                                    else:
                                        rel = os.path.relpath(full, src_dir)
                                    arc = rel.replace(os.sep, '/')
                                    files.append((full, arc, sz))
                            except Exception:
                                continue
                except Exception as e:
                    log_err(f"ZIP Pre-Walk Fehler bei {current}: {e}\n{traceback.format_exc()}")
                    continue
        except Exception as e:
            log_err(f"ZIP Pre-Walk Fehler: {e}\n{traceback.format_exc()}")

        total_bytes = sum(sz for _, _, sz in files)
        task.set_total(len(files))
        task.set_bytes_total(total_bytes)

        def runner():
            try:
                task.set_state("running", "ZIP wird erstellt...")
                task.tmpdir = tempfile.mkdtemp(prefix="kodi_zip_", dir=get_work_tempdir())
                archive_path = os.path.join(task.tmpdir, "archive.zip")
                task.archive_path = archive_path
                done_items = 0

                with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    added_dirs = set()
                    for arcdir in sorted(dirs_to_add):
                        if not arcdir or arcdir in added_dirs:
                            continue
                        try:
                            zinfo = zipfile.ZipInfo(arcdir)
                            zinfo.external_attr = (0o40775 << 16)
                            zf.writestr(zinfo, b'')
                            added_dirs.add(arcdir)
                        except Exception as e:
                            log_dbg(f"ZIP dir entry creation skipped for {arcdir}: {e}")

                    for full, arc, _sz in files:
                        if task.is_canceled():
                            task.set_state("canceled", f"ZIP abgebrochen. Bereits hinzugefügt: {done_items}")
                            return
                        try:
                            with open(full, "rb") as src, zf.open(arc, "w") as dst:
                                while True:
                                    if task.is_canceled():
                                        task.set_state("canceled", f"ZIP abgebrochen. Bereits hinzugefügt: {done_items}")
                                        return
                                    buf = src.read(CHUNK_SIZE)
                                    if not buf:
                                        break
                                    dst.write(buf)
                                    task.inc_bytes(len(buf))
                        except Exception as e:
                            log_dbg(f"ZIP: Fehler bei {full}: {e}")
                        finally:
                            done_items += 1
                            task.set_progress(done_items, None)

                task.set_state("done", "ZIP erstellt.")
            except Exception as e:
                log_err(f"ZIP Task Fehler: {e}\n{traceback.format_exc()}")
                task.set_state("error", f"Fehler: {e}")
            finally:
                self._release_task_slot()

        task_id = secrets.token_urlsafe(16)
        with self.server.zip_lock:
            self.server.zip_tasks[task_id] = task
        t = threading.Thread(target=runner, daemon=True)
        t.start()
        return task_id

    def _get_zip_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.server.zip_lock:
            task = self.server.zip_tasks.get(task_id)
        if not task:
            return None
        with task._lock:
            return {
                "status": "ok",
                "task_id": task_id,
                "total": task.total,
                "done": task.done,
                "bytes_total": task.bytes_total,
                "bytes_done": task.bytes_done,
                "state": task.state,
                "message": task.message,
                "filename": task.filename,
            }

    def _cancel_zip(self, task_id: str) -> bool:
        with self.server.zip_lock:
            task = self.server.zip_tasks.get(task_id)
        if not task:
            return False
        task.request_cancel()
        return True

    def _stream_zip_task(self, task_id: str):
        with self.server.zip_lock:
            task = self.server.zip_tasks.get(task_id)
        if not task:
            return self.send_json_error("Task nicht gefunden", HTTPStatus.NOT_FOUND)
        with task._lock:
            if task.state != "done" or not task.archive_path or not os.path.isfile(task.archive_path):
                return self.send_json_error("ZIP nicht bereit", HTTPStatus.BAD_REQUEST)
            archive_path = task.archive_path
            filename = task.filename or "download.zip"
            tmpdir = task.tmpdir

        try:
            filesize = os.path.getsize(archive_path)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", build_content_disposition(filename))
            self.send_header("Content-Length", str(filesize))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Connection", "close")
            self.end_headers()
            sent = 0
            with open(archive_path, "rb") as f:
                while True:
                    buf = f.read(CHUNK_SIZE)
                    if not buf:
                        break
                    self._safe_wfile_write(buf)
                    try:
                        self.wfile.flush()
                    except Exception:
                        pass
                    sent += len(buf)
                    if (sent // (8 * 1024 * 1024)) != ((sent - len(buf)) // (8 * 1024 * 1024)):
                        try:
                            time.sleep(0)
                        except Exception:
                            pass
        except (BrokenPipeError, ConnectionResetError):
            log_dbg("Client aborted ZIP stream")
        except Exception as e:
            log_err(f"ZIP Task Stream Fehler: {e}\n{traceback.format_exc()}")
            try:
                self.send_json_error("Fehler beim Streamen", HTTPStatus.INTERNAL_SERVER_ERROR)
            except Exception:
                pass
        finally:
            try:
                if archive_path and os.path.isfile(archive_path):
                    os.remove(archive_path)
                if tmpdir and os.path.isdir(tmpdir):
                    shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass
            with self.server.zip_lock:
                try:
                    del self.server.zip_tasks[task_id]
                except Exception:
                    pass

    # ---- Async Copy Helpers
    def _prepare_copy_entries(self, src: str, dest_dir: str):
        base_name = os.path.basename(os.path.normpath(src))
        dest_root = os.path.join(dest_dir, base_name)

        if self._exists_safe(dest_root):
            dest_root = self._unique_dest_name(dest_dir, base_name)

        entries: List[Tuple[str, str, int]] = []

        if os.path.isdir(src):
            stack: List[str] = [src]
            while stack:
                current = stack.pop()
                try:
                    with os.scandir(current) as it:
                        for entry in it:
                            full = entry.path
                            try:
                                if entry.is_dir(follow_symlinks=FOLLOW_SYMLINKS):
                                    stack.append(full)
                                else:
                                    rel = os.path.relpath(full, src)
                                    d = os.path.join(dest_root, rel)
                                    try:
                                        st = entry.stat(follow_symlinks=False)
                                        sz = getattr(st, "st_size", 0)
                                    except Exception:
                                        sz = 0
                                    entries.append((full, d, sz))
                            except Exception:
                                continue
                except Exception:
                    continue
        else:
            try:
                sz = os.path.getsize(src)
            except Exception:
                sz = 0
            entries.append((src, dest_root, sz))

        return dest_root, entries

    def _copy_entry_sync(self, src: str, dest_dir: str) -> Tuple[bool, str]:
        try:
            dest_root, entries = self._prepare_copy_entries(src, dest_dir)
            for s, d, _sz in entries:
                if is_insert_protected(d):
                    return False, "Ziel im geschützten Verzeichnis ist nicht erlaubt."
                os.makedirs(os.path.dirname(d), exist_ok=True)
                with open(s, "rb") as src_f, open(d, "wb") as dst_f:
                    shutil.copyfileobj(src_f, dst_f, length=CHUNK_SIZE)
                try:
                    shutil.copystat(s, d, follow_symlinks=False)
                except Exception:
                    pass
            return True, f"Kopiert nach: {os.path.basename(dest_root)}"
        except Exception as e:
            log_err(f"_copy_entry_sync Fehler: {e}\n{traceback.format_exc()}")
            return False, f"Fehler: {e}"

    def _start_copy_task(self, src: str, dest_dir: str) -> Optional[str]:
        if not self._acquire_task_slot():
            return None

        dest_root, entries = self._prepare_copy_entries(src, dest_dir)

        task = CopyTask(src=src, dest_dir=dest_dir, dest_root=dest_root)
        task.entries = entries
        task.set_total(len(entries))
        task.set_bytes_total(sum(sz for _, _, sz in entries))

        def runner():
            try:
                task.set_state("running", "Kopieren läuft...")
                done_items = 0

                for s, d, _sz in task.entries:
                    if task.is_canceled():
                        task.set_state("canceled", f"Abgebrochen. Bereits kopiert: {done_items}/{task.total}")
                        break

                    d_parent = os.path.dirname(d)

                    try:
                        if is_insert_protected(d):
                            raise RuntimeError("Ziel im geschützten Verzeichnis ist nicht erlaubt.")

                        os.makedirs(d_parent, exist_ok=True)

                        local_bytes = 0
                        with open(s, "rb") as src_f, open(d, "wb") as dst_f:
                            while True:
                                if task.is_canceled():
                                    raise InterruptedError("Abgebrochen")
                                buf = src_f.read(CHUNK_SIZE)
                                if not buf:
                                    break
                                dst_f.write(buf)
                                lb = len(buf)
                                local_bytes += lb
                                if local_bytes >= 512 * 1024:
                                    task.inc_bytes(local_bytes)
                                    local_bytes = 0
                        if local_bytes:
                            task.inc_bytes(local_bytes)

                        try:
                            shutil.copystat(s, d, follow_symlinks=False)
                        except Exception:
                            pass

                        task.created_paths.append(d)
                        done_items += 1

                        with task._lock:
                            task.done = done_items

                    except InterruptedError:
                        try:
                            if os.path.isfile(d):
                                os.remove(d)
                        except Exception:
                            pass
                        task.set_state("canceled", f"Abgebrochen. Bereits kopiert: {done_items}/{task.total}")
                        break

                    except Exception as e:
                        task.set_state("error", f"Fehler bei {os.path.basename(s)}: {e}")
                        break

                if task.state == "running":
                    task.set_state("done", f"Vorgang abgeschlossen. Kopiert: {done_items}/{task.total}")

            except Exception as e:
                log_err(f"Copy Task Fehler: {e}\n{traceback.format_exc()}")
                if task.state not in ("canceled", "error"):
                    task.set_state("error", f"Fehler: {e}")

            finally:
                if task.state in ("canceled", "error"):
                    try:
                        for p in reversed(task.created_paths):
                            try:
                                if os.path.isfile(p) or os.path.islink(p):
                                    os.remove(p)
                                elif os.path.isdir(p):
                                    os.rmdir(p)
                            except Exception:
                                pass

                        if os.path.exists(task.dest_root):
                            try:
                                os.rmdir(task.dest_root)
                            except Exception:
                                pass
                    except Exception as e:
                        log_err(f"Copy Task Cleanup Fehler: {e}\n{traceback.format_exc()}")

                self._release_task_slot()

        task_id = secrets.token_urlsafe(16)
        with self.server.copy_lock:
            self.server.copy_tasks[task_id] = task

        t = threading.Thread(target=runner, daemon=True)
        t.start()
        return task_id

    def _get_copy_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.server.copy_lock:
            task = self.server.copy_tasks.get(task_id)
        if not task:
            return None
        with task._lock:
            data = {
                "status": "ok",
                "task_id": task_id,
                "total": task.total,
                "done": task.done,
                "bytes_total": task.bytes_total,
                "bytes_done": task.bytes_done,
                "state": task.state,
                "message": task.message,
                "name": os.path.basename(task.src)
            }
            if task.state in ("done", "error", "canceled"):
                if task.state == "done":
                    try:
                        self._clip_set(None)
                    except Exception:
                        pass
                with self.server.copy_lock:
                    try:
                        del self.server.copy_tasks[task_id]
                    except Exception:
                        pass
        return data

    def _cancel_copy(self, task_id: str) -> bool:
        with self.server.copy_lock:
            task = self.server.copy_tasks.get(task_id)
        if not task:
            return False
        task.request_cancel()
        return True

    # ---- Async Delete Helpers
    def _start_delete_task(self, dir_path: str) -> Optional[str]:
        if not self._acquire_task_slot():
            return None

        task = DeleteTask(base_dir=dir_path)
        task.set_total(0)
        task.set_bytes_total(0)
        task.set_state("running", "Löschen läuft...")

        def runner():
            try:
                progress_acc = 0
                bytes_acc = 0

                def pcb(inc: int, _total_hint: int):
                    nonlocal progress_acc
                    progress_acc += inc
                    if progress_acc >= 32:
                        with task._lock:
                            task.done += progress_acc
                            if task.total < task.done + 50:
                                task.total = task.done + 50
                        progress_acc = 0

                def bcb(incb: int):
                    nonlocal bytes_acc
                    bytes_acc += incb
                    if bytes_acc >= 512 * 1024:
                        task.inc_bytes(bytes_acc)
                        bytes_acc = 0

                def ccb() -> bool:
                    return task.is_canceled()

                try:
                    with os.scandir(dir_path) as it:
                        for entry in it:
                            if task.is_canceled():
                                if progress_acc:
                                    with task._lock:
                                        task.done += progress_acc
                                        if task.total < task.done + 50:
                                            task.total = task.done + 50
                                if bytes_acc:
                                    task.inc_bytes(bytes_acc)
                                task.set_state("canceled", f"Abgebrochen. Bereits gelöscht: {task.done}")
                                break

                            target = os.path.join(dir_path, entry.name)

                            d, skipped, errors = safe_delete_tree(
                                target,
                                delete_self=True,
                                progress_cb=pcb,
                                bytes_cb=bcb,
                                cancel_cb=ccb
                            )

                            task.skipped.extend(skipped)
                            task.errors.extend(errors)

                except Exception as e:
                    task.errors.append(str(e))

                if progress_acc:
                    with task._lock:
                        task.done += progress_acc
                        if task.total < task.done + 50:
                            task.total = task.done + 50
                if bytes_acc:
                    task.inc_bytes(bytes_acc)

                if task.state == "running":
                    msg = f"Inhalt gelöscht: {task.done} Elemente."
                    if task.skipped:
                        msg += f" Übersprungen: {len(task.skipped)}."
                    if task.errors:
                        msg += f" Fehler: {len(task.errors)}."
                    task.set_state("done", msg)

            except Exception as e:
                log_err(f"Delete Task Fehler: {e}\n{traceback.format_exc()}")
                task.set_state("error", f"Fehler: {e}")

            finally:
                self._release_task_slot()

        task_id = secrets.token_urlsafe(16)
        with self.server.delete_lock:
            self.server.delete_tasks[task_id] = task

        t = threading.Thread(target=runner, daemon=True)
        t.start()

        return task_id

    def _get_delete_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.server.delete_lock:
            task = self.server.delete_tasks.get(task_id)
        if not task:
            return None
        with task._lock:
            data = {
                "status": "ok",
                "task_id": task_id,
                "total": task.total,
                "done": task.done,
                "bytes_total": task.bytes_total,
                "bytes_done": task.bytes_done,
                "state": task.state,
                "message": task.message,
                "skipped": task.skipped,
                "errors": task.errors,
            }
            if task.state in ("done", "error", "canceled"):
                with self.server.delete_lock:
                    try:
                        del self.server.delete_tasks[task_id]
                    except Exception:
                        pass
        return data

    def _cancel_delete(self, task_id: str) -> bool:
        with self.server.delete_lock:
            task = self.server.delete_tasks.get(task_id)
        if not task:
            return False
        task.request_cancel()
        return True

    # ---- Streamer (File with Range)
    def _parse_range(self, header: str, size: int) -> Optional[Tuple[int, int]]:
        try:
            if not header or not header.startswith("bytes="):
                return None
            ranges = header.split("=", 1)[1].strip()
            first = ranges.split(",")[0].strip()
            start_s, _, end_s = first.partition("-")
            if start_s == "" and end_s == "":
                return None
            if start_s == "":
                length = int(end_s)
                if length <= 0:
                    return None
                start = max(0, size - length)
                end = size - 1
            else:
                start = int(start_s)
                end = size - 1
                if end_s != "":
                    end = int(end_s)
                if start > end or start >= size:
                    return None
            return (max(0, start), min(end, size - 1))
        except Exception:
            return None

    def stream_file(self, abs_path: str):
        try:
            size = os.path.getsize(abs_path) if os.path.isfile(abs_path) else 0
            ctype = guess_content_type(abs_path)
            rng = self.headers.get("Range")
            rng_tuple = self._parse_range(rng, size) if rng else None

            with open(abs_path, "rb") as f:
                if rng_tuple:
                    start, end = rng_tuple
                    length = end - start + 1
                    self.send_response(HTTPStatus.PARTIAL_CONTENT)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(length))
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                    self.send_header("Accept-Ranges", "bytes")
                    cd_name = os.path.basename(abs_path)
                    self.send_header("Content-Disposition", build_content_disposition(cd_name))
                    self.send_header("Connection", "close")
                    self.end_headers()
                    f.seek(start)
                    remaining = length
                    sent = 0
                    while remaining > 0:
                        chunk = f.read(min(CHUNK_SIZE, remaining))
                        if not chunk:
                            break
                        self._safe_wfile_write(chunk)
                        try:
                            self.wfile.flush()
                        except Exception:
                            pass
                        remaining -= len(chunk)
                        sent += len(chunk)
                        if (sent // (8 * 1024 * 1024)) != ((sent - len(chunk)) // (8 * 1024 * 1024)):
                            try:
                                time.sleep(0)
                            except Exception:
                                pass
                else:
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(size))
                    self.send_header("Accept-Ranges", "bytes")
                    cd_name = os.path.basename(abs_path)
                    self.send_header("Content-Disposition", build_content_disposition(cd_name))
                    self.send_header("Connection", "close")
                    self.end_headers()
                    sent = 0
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        self._safe_wfile_write(chunk)
                        try:
                            self.wfile.flush()
                        except Exception:
                            pass
                        sent += len(chunk)
                        if (sent // (8 * 1024 * 1024)) != ((sent - len(chunk)) // (8 * 1024 * 1024)):
                            try:
                                time.sleep(0)
                            except Exception:
                                pass
        except (BrokenPipeError, ConnectionResetError):
            log_dbg("Client aborted file stream")
        except FileNotFoundError:
            self.send_json_error("Nicht gefunden", HTTPStatus.NOT_FOUND)
        except PermissionError:
            self.send_json_error("Keine Berechtigung", HTTPStatus.FORBIDDEN)
        except Exception as e:
            log_err(f"Fehler beim Streamen Datei {abs_path}: {e}\n{traceback.format_exc()}")
            self.send_json_error("Fehler beim Streamen", HTTPStatus.INTERNAL_SERVER_ERROR)

    def stream_zip(self, abs_path: str, include_root: bool = True):
        archive_path = None
        tmpdir = None
        try:
            tmpdir = tempfile.mkdtemp(prefix="kodi_webexplorer_", dir=get_work_tempdir())
            archive_path = os.path.join(tmpdir, "archive.zip")
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
                base = os.path.dirname(abs_path.rstrip(os.sep)) if include_root else abs_path
                stack: List[str] = [abs_path]
                while stack:
                    current = stack.pop()
                    try:
                        with os.scandir(current) as it:
                            for entry in it:
                                full = entry.path
                                try:
                                    if entry.is_dir(follow_symlinks=FOLLOW_SYMLINKS):
                                        stack.append(full)
                                    else:
                                        arc = os.path.relpath(full, base)
                                        try:
                                            with open(full, "rb") as src, zf.open(arc, "w") as dst:
                                                while True:
                                                    buf = src.read(CHUNK_SIZE)
                                                    if not buf:
                                                        break
                                                    dst.write(buf)
                                        except Exception as e:
                                            log_dbg(f"ZIP write skip {full}: {e}")
                                except Exception:
                                    continue
                    except Exception as e:
                        log_err(f"ZIP walk Fehler bei {current}: {e}")
                        continue
            filesize = os.path.getsize(archive_path)
            fn = os.path.basename(os.path.normpath(abs_path)) + ".zip"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", build_content_disposition(fn))
            self.send_header("Content-Length", str(filesize))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Connection", "close")
            self.end_headers()
            sent = 0
            with open(archive_path, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    self._safe_wfile_write(chunk)
                    try:
                        self.wfile.flush()
                    except Exception:
                        pass
                    sent += len(chunk)
                    if (sent // (8 * 1024 * 1024)) != ((sent - len(chunk)) // (8 * 1024 * 1024)):
                        try:
                            time.sleep(0)
                        except Exception:
                            pass
        except (BrokenPipeError, ConnectionResetError):
            log_dbg("Client aborted ZIP-on-the-fly stream")
        except Exception as e:
            log_err(f"Fehler beim Erstellen/Streamen ZIP: {e}\n{traceback.format_exc()}")
            self.send_json_error("Fehler beim ZIP erstellen", HTTPStatus.INTERNAL_SERVER_ERROR)
        finally:
            try:
                if archive_path and os.path.isfile(archive_path):
                    os.remove(archive_path)
                if tmpdir and os.path.isdir(tmpdir):
                    shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

    def log_message(self, format: str, *args):
        log_dbg("HTTP: " + (format % args))

    def _detect_mobile_ua(self) -> bool:
        try:
            ua = self.headers.get("User-Agent", "") or ""
            ua_lower = ua.lower()

            desktop_indicators = (
                "smart-tv",
                "smarttv",
                "googletv",
                "appletv",
                "hbbtv",
                "xbox",
                "playstation",
                "crkey",
                "tv",
            )
            if any(tok in ua_lower for tok in desktop_indicators):
                return False

            mobile_indicators = (
                "android",
                "iphone",
                "ipad",
                "mobile",
                "mobi",
                "tablet",
                "silk",
                "bb10",
                "opera mini",
                "windows phone",
                "phone",
                "touch",
            )
            if any(tok in ua_lower for tok in mobile_indicators):
                return True

            sch = self.headers.get("Sec-CH-UA-Mobile", "") or ""
            if sch:
                if "?1" in sch or "true" in sch.lower() or "mobile" in sch.lower():
                    return True

            if self.headers.get("X-OperaMini-Phone") or self.headers.get("X-Wap-Profile"):
                return True

            try:
                parsed = urllib.parse.urlparse(self.path or "")
                if parsed.query and "ui=mobile" in parsed.query:
                    return True
                if parsed.query and "ui=desktop" in parsed.query:
                    return False
            except Exception:
                pass

            accept = (self.headers.get("Accept") or "").lower()
            if "vnd.wap" in accept or "wap" in accept:
                return True

            return False
        except Exception:
            return False

    def send_index_html(self):
        chosen = "index.html"
        mode = UI_MODE
        if mode == "AUTO":
            chosen = "mobile_index.html" if self._detect_mobile_ua() and (RESOURCES_HTML / "mobile_index.html").exists() else "index.html"
        elif mode == "MOBILE":
            chosen = "mobile_index.html" if (RESOURCES_HTML / "mobile_index.html").exists() else "index.html"
        else:
            chosen = "index.html"

        try:
            index_file = RESOURCES_HTML / chosen
            if not index_file.exists():
                index_file = RESOURCES_HTML / "index.html"
                if not index_file.exists():
                    log_err("index.html nicht gefunden: " + str(index_file))
                    return self.send_bytes(b"<html><body><h1>UI fehlt</h1></body></html>", content_type="text/html; charset=utf-8")
        except Exception:
            pass
        try:
            data = index_file.read_bytes()
            return self.send_bytes(data, content_type=guess_content_type(index_file.name))
        except Exception as e:
            log_err(f"Fehler beim Laden {chosen}: {e}\n{traceback.format_exc()}")
            return self.send_bytes(b"<html><body><h1>Fehler beim Laden der UI</h1></body></html>", content_type="text/html; charset=utf-8")


# ----------------------------
# Server
# ----------------------------
def enforce_android_or_quit() -> bool:
    try:
        if hasattr(xbmc, "getCondVisibility") and not xbmc.getCondVisibility("System.Platform.Android"):
            try:
                xbmcgui.Dialog().ok("Kodi Android Web File Explorer", "Dieses Add-on ist nur unter Android verfügbar.")
            except Exception:
                pass
            log_err("Nicht-Android-Plattform erkannt. Abbruch.")
            return False
        return True
    except Exception:
        return True


def run_server_forever():
    if not enforce_android_or_quit():
        return

    initial_root, initial_name, android_root = choose_initial_root()

    port = get_port_from_settings()
    username, password, auth_required = get_credentials_from_settings()
    refresh_settings()
    log(f"Settings: port={port}, user={'<gesetzt>' if username else '<leer>'}, auth_required={auth_required}, max_tasks={MAX_PARALLEL_TASKS}, log={LOG_LEVEL_STR}, symlinks={'ON' if FOLLOW_SYMLINKS else 'OFF'}, ui={UI_MODE}")
    log(f"Protection: delete={'ON' if PROTECT_DELETE_ENABLED else 'OFF'}, unzip={'ON' if PROTECT_UNZIP_ENABLED else 'OFF'}, insert={'ON' if INSERT_PROTECT_ENABLED else 'OFF'}")
    log(f"CleanerSafelist={sorted(CLEANER_SAFELIST)} ExtractSafelist={sorted(EXTRACT_SAFELIST)} InsertSafelist={sorted(INSERT_SAFELIST)}")

    server_address = ("", port)
    try:
        httpd = ThreadingSimpleServer(server_address, ExplorerHandler)
    except Exception as e:
        log_err(f"Server konnte nicht gestartet werden auf Port {port}: {e}\n{traceback.format_exc()}")
        try:
            xbmcgui.Dialog().notification("Kodi Android Web File Explorer", f"Start fehlgeschlagen: {e}", xbmcgui.NOTIFICATION_INFO, 4000)
        except Exception:
            pass
        return

    httpd.android_root_path = android_root
    httpd.current_root = initial_root
    httpd.current_root_name = initial_name

    httpd.auth_required = auth_required
    httpd.username = username
    httpd.password = password
    httpd.sessions = set()
    httpd.sessions_lock = threading.Lock()
    httpd.clip_source = None
    httpd.unzip_tasks = {}
    httpd.unzip_lock = threading.Lock()
    httpd.zip_tasks = {}
    httpd.zip_lock = threading.Lock()
    httpd.copy_tasks = {}
    httpd.copy_lock = threading.Lock()
    httpd.delete_tasks = {}
    httpd.delete_lock = threading.Lock()
    httpd.task_semaphore = threading.Semaphore(MAX_PARALLEL_TASKS)
    httpd.task_limit_lock = threading.Lock()
    httpd.cleanup_stop = False

    def _cleanup_task_dict(reg, lock):
        cutoff = time.time() - 600
        with lock:
            to_del = [tid for tid, t in reg.items() if getattr(t, "finished_at", None) and t.finished_at < cutoff]
            for tid in to_del:
                try:
                    del reg[tid]
                except Exception:
                    pass

    def _cleanup_loop():
        while not httpd.cleanup_stop:
            try:
                _cleanup_task_dict(httpd.unzip_tasks, httpd.unzip_lock)
                _cleanup_task_dict(httpd.copy_tasks, httpd.copy_lock)
                _cleanup_task_dict(httpd.delete_tasks, httpd.delete_lock)
                _cleanup_task_dict(httpd.zip_tasks, httpd.zip_lock)
            except Exception as e:
                log_err(f"Cleanup-Loop Fehler: {e}\n{traceback.format_exc()}")
            time.sleep(60)

    tcl = threading.Thread(target=_cleanup_loop, daemon=True)
    tcl.start()

    log(f"Starte WebExplorer auf Port {port}, Root={httpd.current_root} ({httpd.current_root_name}), AndroidRoot={httpd.android_root_path}, Auth={'AN' if auth_required else 'AUS'}")

    try:
        httpd.serve_forever()
    except Exception as e:
        log_err(f"Server Exception: {e}\n{traceback.format_exc()}")
    finally:
        try:
            httpd.cleanup_stop = True
        except Exception:
            pass
        try:
            httpd.server_close()
        except Exception:
            pass
        log("Server gestoppt.")


# ----------------------------
# Programm-UI (Start/Stop/Info/Settings)
# ----------------------------
def effective_port() -> int:
    return get_port_from_settings()


def is_server_running(timeout: float = 0.4) -> bool:
    port = effective_port()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except Exception:
        return False


def send_shutdown():
    port = effective_port()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1.5)
        conn.request("GET", "/shutdown")
        conn.getresponse()
        conn.close()
    except Exception as e:
        log_err(f"send_shutdown Fehler: {e}\n{traceback.format_exc()}")


def show_info_dialog():
    ips = get_local_ips()
    ip_text = ", ".join(ips)
    port = effective_port()
    xbmcgui.Dialog().ok("Kodi Android Web File Explorer", f"Verbinden im Browser:\nhttp://{ip_text}:{port}/")


def show_settings():
    try:
        xbmcaddon.Addon(id=ADDON_ID).openSettings()
    except Exception as e:
        log_err(f"openSettings fehlgeschlagen: {e}\n{traceback.format_exc()}")


def start_server_background():
    if not enforce_android_or_quit():
        return
    if is_server_running():
        xbmcgui.Dialog().notification("Kodi Android Web File Explorer", "Server läuft bereits", xbmcgui.NOTIFICATION_INFO, 2500)
        return
    xbmc.executebuiltin(f'RunScript("{ADDON_ROOT}/default.py", "action=runserver")')
    xbmcgui.Dialog().notification("Kodi Android Web File Explorer", "Server wird gestartet …", xbmcgui.NOTIFICATION_INFO, 2000)


def stop_server():
    if not is_server_running():
        xbmcgui.Dialog().notification("Kodi Android Web File Explorer", "Server ist nicht aktiv", xbmcgui.NOTIFICATION_INFO, 2500)
        return
    send_shutdown()
    xbmcgui.Dialog().notification("Kodi Android Web File Explorer", "Server wird beendet …", xbmcgui.NOTIFICATION_INFO, 2000)


def list_ui_items(plugin_handle: int):
    base_url = sys.argv[0]

    # Fanart: versuche ein zentrales "item_fanart.png" zu laden, sonst Icon
    fanart_path = RESOURCES_ART / "item_fanart.png"
    if fanart_path.exists():
        fanart = str(fanart_path)
    else:
        fanart = None

    def li(label: str, path: str, is_folder: bool = False, icon: Optional[str] = None):
        item = xbmcgui.ListItem(label=label)
        if icon:
            try:
                item.setArt({"icon": icon, "thumb": icon})
                if fanart:
                    item.setArt({"fanart": fanart})
            except Exception:
                pass
        xbmcplugin.addDirectoryItem(handle=plugin_handle, url=path, listitem=item, isFolder=is_folder)

    start_icon = str(RESOURCES_ART / "start.png")
    stop_icon = str(RESOURCES_ART / "stop.png")
    ip_icon = str(RESOURCES_ART / "ip.png")
    settings_icon = str(RESOURCES_ART / "einstellungen.png")

    li("[COLOR ff2e7d32]Server starten[/COLOR]", f"{base_url}?action=start", is_folder=False, icon=start_icon if os.path.exists(start_icon) else None)
    li("[COLOR ffc62828]Server stoppen[/COLOR]", f"{base_url}?action=stop", is_folder=False, icon=stop_icon if os.path.exists(stop_icon) else None)
    li("[COLOR ff1565c0]IP:Port anzeigen[/COLOR]", f"{base_url}?action=info", is_folder=False, icon=ip_icon if os.path.exists(ip_icon) else None)
    li("[COLOR ffbdbdbd]Einstellungen öffnen[/COLOR]", f"{base_url}?action=settings", is_folder=False, icon=settings_icon if os.path.exists(settings_icon) else None)

    xbmcplugin.endOfDirectory(plugin_handle, succeeded=True)


def parse_action_from_argv() -> Optional[str]:
    if len(sys.argv) >= 3 and sys.argv[2]:
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(sys.argv[2]).query)
            action = qs.get("action", [None])[0]
            if action:
                return action
        except Exception:
            pass
    for arg in sys.argv[1:]:
        if isinstance(arg, str) and "action=" in arg:
            try:
                qs = urllib.parse.parse_qs(arg.replace(";", "&"))
                action = qs.get("action", [None])[0]
                if action:
                    return action
            except Exception:
                if arg.strip() == "action=runserver":
                    return "runserver"
    return None


def router():
    action = parse_action_from_argv()

    if action == "runserver":
        run_server_forever()
        return

    handle = int(sys.argv[1]) if len(sys.argv) > 1 and str(sys.argv[1]).isdigit() else -1

    if action == "start":
        start_server_background()
        list_ui_items(handle)
        return
    elif action == "stop":
        stop_server()
        list_ui_items(handle)
        return
    elif action == "info":
        show_info_dialog()
        list_ui_items(handle)
        return
    elif action == "settings":
        show_settings()
        list_ui_items(handle)
        return

    list_ui_items(handle)


if __name__ == "__main__":
    router()