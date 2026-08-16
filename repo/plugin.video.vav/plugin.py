
import re
import sys
import os
import uuid
import time
import gzip
import json
import html
import threading
import urllib.parse
import unicodedata
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmcvfs
import requests

addon        = xbmcaddon.Addon()
addon_handle = int(sys.argv[1])
base_url     = sys.argv[0]

ADDON_DATA  = xbmcvfs.translatePath("special://userdata/addon_data/plugin.video.vav/")
CACHE_FILE  = os.path.join(ADDON_DATA, "catalog_cache.json")
FAV_FILE    = os.path.join(ADDON_DATA, "favourites.json")
ORDER_FILE  = os.path.join(ADDON_DATA, "country_order.json")
EPG_INDEX_FILE = os.path.join(ADDON_DATA, "epg_index.json")

os.makedirs(ADDON_DATA, exist_ok=True)

PING_URLS   = [
    "https://www.vypn.net/api/app/ping",
    "https://cache.vypn.net/api/app/ping",
]
BASE_SITES  = ["https://huhu.to", "https://www.huhu.to"]
BROWSER_UA  = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/124.0.0.0 Safari/537.36")
MEDIAURL_UA = "MediaUrl/2"
PING_HEADERS = {"accept": "*/*", "user-agent": BROWSER_UA,
                "Accept-Encoding": "gzip, deflate", "Connection": "close"}
CATALOG_TTL = 3600
SIG_TTL     = 480
IPTV_ORG_CHANNELS_URL = "https://iptv-org.github.io/api/channels.json"
EPG_INDEX_TTL = 7 * 24 * 3600

DOWNLOAD_DIRS = [
    "/storage/emulated/0/Download",
    "/storage/emulated/0/Downloads",
    "/storage/self/primary/Download",
    "/sdcard/Download",
    "/sdcard/Downloads",
    "/storage/sdcard0/Download",
]

def _writable_download_dir():
    for d in DOWNLOAD_DIRS:
        test = os.path.join(d, ".vav_test")
        if _vfs_write(test, "x"):
            xbmcvfs.delete(test)
            return d
    return None

COUNTRY_LOGOS = {
    "albania":              "special://home/addons/plugin.video.vav/resources/country/al.png",
    "arabia":               "special://home/addons/plugin.video.vav/resources/country/ae.png",
    "azerbaijan":           "special://home/addons/plugin.video.vav/resources/country/az.png",
    "balkans":              "special://home/addons/plugin.video.vav/resources/country/yu.png",
    "belgium":              "special://home/addons/plugin.video.vav/resources/country/be.png",
    "bulgaria":             "special://home/addons/plugin.video.vav/resources/country/bg.png",
    "croatia":              "special://home/addons/plugin.video.vav/resources/country/hr.png",
    "denmark":              "special://home/addons/plugin.video.vav/resources/country/dk.png",
    "france":               "special://home/addons/plugin.video.vav/resources/country/fr.png",
    "france sport":         "special://home/addons/plugin.video.vav/resources/country/fr.png",
    "germany":              "special://home/addons/plugin.video.vav/resources/country/de.png",
    "greece":               "special://home/addons/plugin.video.vav/resources/country/gr.png",
    "iran":                 "special://home/addons/plugin.video.vav/resources/country/ir.png",
    "italy":                "special://home/addons/plugin.video.vav/resources/country/it.png",
    "netherlands":          "special://home/addons/plugin.video.vav/resources/country/nl.png",
    "poland":               "special://home/addons/plugin.video.vav/resources/country/pl.png",
    "portugal":             "special://home/addons/plugin.video.vav/resources/country/pt.png",
    "romania":              "special://home/addons/plugin.video.vav/resources/country/ro.png",
    "russia":               "special://home/addons/plugin.video.vav/resources/country/ru.png",
    "spain":                "special://home/addons/plugin.video.vav/resources/country/es.png",
    "sports international": "special://home/addons/plugin.video.vav/resources/country/eu.png",
    "sweden":               "special://home/addons/plugin.video.vav/resources/country/se.png",
    "turkey":               "special://home/addons/plugin.video.vav/resources/country/tr.png",
    "united kingdom":       "special://home/addons/plugin.video.vav/resources/country/gb.png",
}

DEFAULT_COUNTRY_ORDER = [
    "Germany", "Turkey", "Denmark", "Sports International",
    "United Kingdom", "France", "Italy", "Spain", "Portugal",
    "Netherlands", "Poland", "Romania", "Bulgaria", "Russia",
    "Greece", "Sweden", "Belgium", "Albania", "Arabia",
    "Azerbaijan", "Balkans", "Croatia", "Iran",
]

COUNTRY_CODES = {k: os.path.splitext(os.path.basename(v))[0].upper()
                for k, v in COUNTRY_LOGOS.items()}

_SEPARATORS     = ["=>", "->", "|"]
_SEPARATORS_UNI = ["\u27be", "\u27fe", "\u2192", "\u00bb", "\u203a"]

_sig_cache = {"sig": None, "ts": 0}
_sig_lock  = threading.Lock()
_base_idx  = [0]

def _log(msg, level=xbmc.LOGDEBUG):
    xbmc.log("[plugin.video.vav] " + str(msg), level)

def _build_url(q):
    return base_url + "?" + urllib.parse.urlencode(q)

def _current_base():
    return BASE_SITES[_base_idx[0] % len(BASE_SITES)]

def _switch_base():
    _base_idx[0] += 1

def _decode(resp):
    raw = resp.content
    try:
        raw = gzip.decompress(raw)
    except Exception:
        pass
    return json.loads(raw.decode("utf-8", errors="replace"))

def _extract_country(group_str):
    s = (group_str or "").strip()
    for sep in _SEPARATORS_UNI + _SEPARATORS:
        if sep in s:
            s = s.split(sep)[0].strip()
            break
    s = s or "Other"
    return s.title()

def _clean_logo(url):
    if not url:
        return ""
    if "logo.huhu.to" in url:
        return ""
    return url

def _m3u_escape(s):
    return (s or "").replace('"', "'").replace("\n", " ").replace("\r", "")

def _vfs_write(path, content):
    try:
        f = xbmcvfs.File(path, 'w')
        result = f.write(content.encode("utf-8"))
        f.close()
        return result is not False
    except Exception as e:
        _log("VFS write %s: %s" % (path, e), xbmc.LOGWARNING)
        return False

_NORM_DROP = {"hd", "fhd", "uhd", "sd", "4k", "hevc", "h265", "tv"}

def _normalize_name(name):
    s = (name or "").lower()
    s = s.replace("ß", "ss").replace("ı", "i")
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    words = [w for w in s.split() if w not in _NORM_DROP]
    return "".join(words)

def _load_epg_index(force=False):
    if not force:
        try:
            with open(EPG_INDEX_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if time.time() - data.get("ts", 0) < EPG_INDEX_TTL:
                return data["by_country"], data["by_name"]
        except Exception:
            pass
    try:
        r = requests.get(IPTV_ORG_CHANNELS_URL, timeout=60, verify=False)
        r.raise_for_status()
        channels  = r.json()
        by_country, by_name = {}, {}
        for c in channels:
            cid = c.get("id")
            if not cid:
                continue
            country = (c.get("country") or "").upper()
            names = [c.get("name")] + (c.get("alt_names") or [])
            for n in names:
                norm = _normalize_name(n)
                if not norm:
                    continue
                by_country.setdefault(country + "|" + norm, cid)
                by_name.setdefault(norm, cid)
        with open(EPG_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "by_country": by_country, "by_name": by_name}, f)
        return by_country, by_name
    except Exception as e:
        _log("EPG index: " + str(e), xbmc.LOGWARNING)
        return {}, {}

def _auto_tvg_id(ch, by_country, by_name):
    norm = _normalize_name(ch["name"])
    if not norm:
        return ""
    code = COUNTRY_CODES.get(ch["country"].lower(), "")
    if code:
        tid = by_country.get(code + "|" + norm)
        if tid:
            return tid
    return by_name.get(norm, "")

def _notify(msg, error=False):
    icon = xbmcgui.NOTIFICATION_ERROR if error else xbmcgui.NOTIFICATION_INFO
    xbmcgui.Dialog().notification("VAVOO", msg, icon, 3000)

def _refresh_container():
    xbmc.executebuiltin("Container.Refresh")

def _load_order():
    try:
        with open(ORDER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            return data
    except Exception:
        pass
    return list(DEFAULT_COUNTRY_ORDER)

def _save_order(order):
    try:
        with open(ORDER_FILE, "w", encoding="utf-8") as f:
            json.dump(order, f, ensure_ascii=False, indent=2)
    except Exception as e:
        _log("Order save: " + str(e), xbmc.LOGWARNING)

def _sorted_countries(countries):
    order = _load_order()
    out, seen = [], set()
    for name in order:
        for c in countries:
            if c.lower() == name.lower() and c not in seen:
                out.append(c)
                seen.add(c)
    for c in sorted(countries):
        if c not in seen:
            out.append(c)
    return out

def _move_country(country, direction):
    channels = _get_catalog()
    all_ctry = list(set(ch["country"] for ch in channels))
    order    = _sorted_countries(all_ctry)
    if country not in order:
        order.append(country)
    idx = order.index(country)
    if direction == "up"     and idx > 0:
        order[idx], order[idx - 1] = order[idx - 1], order[idx]
    elif direction == "down" and idx < len(order) - 1:
        order[idx], order[idx + 1] = order[idx + 1], order[idx]
    elif direction == "top":
        order.insert(0, order.pop(idx))
    elif direction == "bottom":
        order.append(order.pop(idx))
    _save_order(order)
    _refresh_container()

def _reset_order():
    try:
        os.remove(ORDER_FILE)
    except Exception:
        pass
    _refresh_container()

def _load_favs():
    try:
        with open(FAV_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _save_favs(favs):
    try:
        with open(FAV_FILE, "w", encoding="utf-8") as f:
            json.dump(favs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        _log("Fav save: " + str(e), xbmc.LOGWARNING)

def _fav_exists(ch_id):
    return any(f["id"] == ch_id for f in _load_favs())

def _add_fav(ch):
    favs = _load_favs()
    if not _fav_exists(ch["id"]):
        favs.append({"id": ch["id"], "name": ch["name"],
                     "url": ch["url"], "logo": ch.get("logo", "")})
        _save_favs(favs)
        _notify('"%s" zu VAV Favoriten hinzugefuegt' % ch["name"])

def _remove_fav(ch_id):
    _save_favs([f for f in _load_favs() if f["id"] != ch_id])
    _notify("Aus VAV Favoriten entfernt")
    _refresh_container()

def _rename_fav(ch_id):
    favs  = _load_favs()
    entry = next((f for f in favs if f["id"] == ch_id), None)
    if not entry:
        return
    kb = xbmc.Keyboard(entry["name"], "Neuer Name")
    kb.doModal()
    if kb.isConfirmed():
        new_name = kb.getText().strip()
        if new_name:
            entry["name"] = new_name
            _save_favs(favs)
            _notify('Umbenannt zu "%s"' % new_name)
            _refresh_container()

def _move_fav(ch_id, direction):
    favs = _load_favs()
    idx  = next((i for i, f in enumerate(favs) if f["id"] == ch_id), None)
    if idx is None:
        return
    if direction == "up"     and idx > 0:
        favs[idx], favs[idx - 1] = favs[idx - 1], favs[idx]
    elif direction == "down" and idx < len(favs) - 1:
        favs[idx], favs[idx + 1] = favs[idx + 1], favs[idx]
    elif direction == "top":
        favs.insert(0, favs.pop(idx))
    elif direction == "bottom":
        favs.append(favs.pop(idx))
    _save_favs(favs)
    _refresh_container()

def _get_sig(force=False):
    with _sig_lock:
        now = time.time()
        if not force and _sig_cache["sig"] and (now - _sig_cache["ts"]) < SIG_TTL:
            return _sig_cache["sig"]
    uid = str(uuid.uuid4())
    ts  = int(time.time() * 1000)
    payload = {
        "reason": "app-focus", "locale": "en", "theme": "dark",
        "metadata": {
            "device":  {"type": "desktop", "uniqueId": uid},
            "os":      {"name": "win32", "version": "Windows 10 Pro",
                        "abis": ["x64"], "host": "Lenovo"},
            "app":     {"platform": "electron"},
            "version": {"package": "net.vypn.app", "binary": "3.1.0", "js": "3.1.0"},
        },
        "appFocusTime": 0, "playerActive": False, "playDuration": 0,
        "devMode": False, "hasAddon": True, "castConnected": False,
        "package": "net.vypn.app", "version": "3.1.0", "process": "app",
        "firstAppStart": ts, "lastAppStart": ts, "ipLocation": None,
        "adblockEnabled": True,
        "proxy": {"supported": ["ss"], "engine": "Mu",
                  "enabled": False, "autoServer": True},
        "iap": {"supported": False},
    }
    sig = None
    for url in PING_URLS:
        try:
            r = requests.post(url, json=payload, headers=PING_HEADERS,
                              timeout=15, verify=False)
            r.raise_for_status()
            data = _decode(r)
            sig = data.get("addonSig") or data.get("sig") or data.get("token")
            if sig:
                break
        except Exception as e:
            _log("Ping %s: %s" % (url, e), xbmc.LOGWARNING)
    if sig:
        with _sig_lock:
            _sig_cache["sig"] = sig
            _sig_cache["ts"]  = time.time()
    return sig

def _save_catalog(channels):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "channels": channels}, f)
    except Exception as e:
        _log("Cache write: " + str(e), xbmc.LOGWARNING)

def _load_catalog_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - data.get("ts", 0) < CATALOG_TTL:
            return data["channels"]
    except Exception:
        pass
    return None

MAX_PAGES   = 60
MAX_WORKERS = 8

def _catalog_headers(sig):
    return {
        "content-type":       "application/json; charset=utf-8",
        "mediaurl-signature": sig or "",
        "user-agent":         MEDIAURL_UA,
        "accept":             "*/*",
        "Accept-Language":    "en",
        "Accept-Encoding":    "gzip, deflate",
        "Connection":         "close",
    }

def _fetch_one_page(base, sig, cursor):
    payload = {
        "language": "en", "region": "US",
        "catalogId": "iptv", "id": "iptv",
        "adult": False, "search": "", "sort": "", "filter": {},
        "cursor": cursor, "clientVersion": "3.1.0",
    }
    r = requests.post(base + "/mediaurl-catalog.json",
                      json=payload, headers=_catalog_headers(sig),
                      timeout=30, verify=False)
    r.raise_for_status()
    return _decode(r)

def _parse_items(items):
    result = []
    for item in items:
        if item.get("type") != "iptv":
            continue
        group = item.get("group", "")
        ids   = item.get("ids") or {}
        ch_id = ids.get("id") or item.get("id", "")
        result.append({
            "id":      ch_id,
            "name":    item.get("name") or item.get("title", "Unbekannt"),
            "url":     item.get("url", ""),
            "logo":    _clean_logo(item.get("logo") or item.get("artwork", "")),
            "country": _extract_country(group),
            "group":   group,
        })
    return result

def _fetch_catalog(sig, pd=None):
    base, mirror_tried = _current_base(), False
    session = requests.Session()

    def _fetch_page_s(cursor):
        payload = {
            "language": "en", "region": "US",
            "catalogId": "iptv", "id": "iptv",
            "adult": False, "search": "", "sort": "", "filter": {},
            "cursor": cursor, "clientVersion": "3.1.0",
        }
        r = session.post(base + "/mediaurl-catalog.json",
                         json=payload, headers=_catalog_headers(sig),
                         timeout=30, verify=False)
        r.raise_for_status()
        return _decode(r)

    try:
        data0 = _fetch_page_s(None)
    except Exception as e:
        if "451" in str(e) and not mirror_tried:
            _switch_base()
            base = _current_base()
            mirror_tried = True
            try:
                data0 = _fetch_page_s(None)
            except Exception as e2:
                _log("Catalog p1: %s" % e2, xbmc.LOGWARNING)
                return []
        else:
            _log("Catalog p1: %s" % e, xbmc.LOGWARNING)
            return []

    items0 = data0.get("items", [])
    if not items0:
        return []

    channels    = _parse_items(items0)
    cursor0     = data0.get("nextCursor")
    total_items = data0.get("totalCount") or data0.get("total") or 0
    page_size   = len(items0) or 1
    total_pages = min(MAX_PAGES, max(1, (total_items + page_size - 1) // page_size)
                      if total_items else MAX_PAGES)

    if pd:
        pd.update(max(1, int(100 / total_pages)),
                  "Lade Kanalliste... Seite 1  (%d Kanaele)" % len(channels))

    if not cursor0:
        return channels

    remaining = total_pages - 1
    canceled  = threading.Event()

    if isinstance(cursor0, int) and cursor0 > 0:
        step    = cursor0
        cursors = [step * (i + 1) for i in range(remaining)]

        lock = threading.Lock()
        done = [1]

        def _worker(cursor, page_num):
            if canceled.is_set():
                return []
            try:
                data = _fetch_page_s(cursor)
                return _parse_items(data.get("items", []))
            except Exception as e:
                _log("Catalog p%d: %s" % (page_num, e), xbmc.LOGWARNING)
                return []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futs = {ex.submit(_worker, c, i + 2): i for i, c in enumerate(cursors)}
            for fut in as_completed(futs):
                if pd and pd.iscanceled():
                    canceled.set()
                    break
                batch = fut.result()
                with lock:
                    channels.extend(batch)
                    done[0] += 1
                    if pd:
                        pct = min(99, int(done[0] * 100 / total_pages))
                        pd.update(pct, "Lade Kanalliste... (%d Kanaele)" % len(channels))

    else:
        cursor   = cursor0
        page     = 1
        next_fut = None

        with ThreadPoolExecutor(max_workers=1) as ex:
            next_fut = ex.submit(_fetch_page_s, cursor)

            while page < MAX_PAGES:
                page += 1
                if pd and pd.iscanceled():
                    canceled.set()
                    break
                try:
                    data = next_fut.result(timeout=35)
                except Exception as e:
                    _log("Catalog p%d: %s" % (page, e), xbmc.LOGWARNING)
                    break

                items  = data.get("items", [])
                cursor = data.get("nextCursor")

                if cursor and not canceled.is_set():
                    next_fut = ex.submit(_fetch_page_s, cursor)

                if not items:
                    break
                channels.extend(_parse_items(items))

                if pd:
                    pct = min(99, int(page * 100 / total_pages))
                    pd.update(pct, "Lade Kanalliste... Seite %d  (%d Kanaele)" % (page, len(channels)))

                if not cursor:
                    break

    return channels

def _get_catalog():
    cached = _load_catalog_cache()
    if cached:
        return cached
    sig = _get_sig()
    if not sig:
        _notify("Kein Token – erneut versuchen", error=True)
        return []
    pd = xbmcgui.DialogProgress()
    pd.create("VAVOO", "Lade Kanalliste...")
    pd.update(0)
    channels = _fetch_catalog(sig, pd=pd)
    pd.update(100)
    pd.close()
    if channels:
        _save_catalog(channels)
    return channels

def _resolve(channel_url, sig):
    for attempt in range(2):
        headers = {
            "content-type":       "application/json; charset=utf-8",
            "mediaurl-signature": sig or "",
            "user-agent":         MEDIAURL_UA,
            "accept":             "*/*",
            "Accept-Language":    "en",
            "Accept-Encoding":    "gzip, deflate",
            "Connection":         "close",
        }
        payload = {"language": "en", "region": "US",
                   "url": channel_url, "clientVersion": "3.1.0"}
        try:
            r = requests.post(_current_base() + "/mediaurl-resolve.json",
                              json=payload, headers=headers,
                              timeout=30, verify=False)
            if r.status_code == 451:
                _switch_base()
                continue
            r.raise_for_status()
            result = _decode(r)
            stream_url = None
            if isinstance(result, list) and result:
                stream_url = result[0].get("url")
            elif isinstance(result, dict):
                stream_url = result.get("url") or result.get("streamUrl")
            if stream_url:
                return stream_url
        except Exception as e:
            _log("Resolve %d: %s" % (attempt + 1, e), xbmc.LOGWARNING)
        if attempt == 0:
            sig = _get_sig(force=True)
            if not sig:
                break
    return None

def _make_channel_li(ch, context="channel"):
    li   = xbmcgui.ListItem(label=ch["name"])
    logo = ch.get("logo") or ""
    if logo:
        li.setArt({"thumb": logo, "icon": logo})
    li.setProperty("IsPlayable", "true")

    play_url = _build_url({"mode": "play",
                           "channel_url": ch["url"],
                           "channel_id":  ch["id"]})
    ctx = []

    if context == "fav":
        ctx += [
            ("Nach oben",
             "RunPlugin(%s)" % _build_url({"mode": "fav_move", "id": ch["id"], "dir": "up"})),
            ("Nach unten",
             "RunPlugin(%s)" % _build_url({"mode": "fav_move", "id": ch["id"], "dir": "down"})),
            ("Ganz nach oben",
             "RunPlugin(%s)" % _build_url({"mode": "fav_move", "id": ch["id"], "dir": "top"})),
            ("Ganz nach unten",
             "RunPlugin(%s)" % _build_url({"mode": "fav_move", "id": ch["id"], "dir": "bottom"})),
            ("Umbenennen",
             "RunPlugin(%s)" % _build_url({"mode": "fav_rename", "id": ch["id"]})),
            ("Aus VAV Favoriten entfernen",
             "RunPlugin(%s)" % _build_url({"mode": "fav_remove", "id": ch["id"]})),
        ]
    else:
        if _fav_exists(ch["id"]):
            ctx += [("Aus VAV Favoriten entfernen",
                     "RunPlugin(%s)" % _build_url({"mode": "fav_remove", "id": ch["id"]}))]
        else:
            ctx += [("Zu VAV Favoriten hinzufuegen",
                     "RunPlugin(%s)" % _build_url({"mode": "fav_add", "id": ch["id"]}))]

    li.addContextMenuItems(ctx)
    return li, play_url

def list_groups():
    channels = _get_catalog()
    if not channels:
        xbmcplugin.endOfDirectory(addon_handle)
        return

    fav_count = len(_load_favs())
    fav_label = "VAV Favoriten (%d)" % fav_count if fav_count else "VAV Favoriten"
    fav_icon  = "special://home/addons/plugin.video.vav/resources/favourites.png"
    li_fav = xbmcgui.ListItem(label=fav_label)
    li_fav.setArt({"thumb": fav_icon, "icon": fav_icon})
    xbmcplugin.addDirectoryItem(handle=addon_handle,
                                url=_build_url({"mode": "list_favs"}),
                                listitem=li_fav, isFolder=True)

    search_icon = "special://home/addons/plugin.video.vav/resources/search.png"
    li_search = xbmcgui.ListItem(label="Suche...")
    li_search.setArt({"thumb": search_icon, "icon": search_icon})
    xbmcplugin.addDirectoryItem(handle=addon_handle,
                                url=_build_url({"mode": "search"}),
                                listitem=li_search, isFolder=True)

    settings_icon = "DefaultAddonProgram.png"
    li_settings = xbmcgui.ListItem(label="Einstellungen")
    li_settings.setArt({"thumb": settings_icon, "icon": settings_icon})

    countries = set(ch["country"] for ch in channels)
    for country in _sorted_countries(countries):
        li   = xbmcgui.ListItem(label=country)
        logo = COUNTRY_LOGOS.get(country.lower(), "")
        if logo:
            li.setArt({"thumb": logo, "icon": logo})
        ctx = [
            ("Nach oben",
             "RunPlugin(%s)" % _build_url({"mode": "ctry_move", "country": country, "dir": "up"})),
            ("Nach unten",
             "RunPlugin(%s)" % _build_url({"mode": "ctry_move", "country": country, "dir": "down"})),
            ("Ganz nach oben",
             "RunPlugin(%s)" % _build_url({"mode": "ctry_move", "country": country, "dir": "top"})),
            ("Ganz nach unten",
             "RunPlugin(%s)" % _build_url({"mode": "ctry_move", "country": country, "dir": "bottom"})),
            ("Reihenfolge zuruecksetzen",
             "RunPlugin(%s)" % _build_url({"mode": "ctry_reset"})),
        ]
        li.addContextMenuItems(ctx)
        xbmcplugin.addDirectoryItem(handle=addon_handle,
                                    url=_build_url({"mode": "list_channels", "group": country}),
                                    listitem=li, isFolder=True)

    xbmcplugin.addDirectoryItem(handle=addon_handle,
                                url=_build_url({"mode": "settings"}),
                                listitem=li_settings, isFolder=False)

    xbmcplugin.endOfDirectory(addon_handle)

def list_channels(group):
    channels = _get_catalog()
    matches = [ch for ch in channels if ch["country"].lower() == group.lower() and ch.get("url")]
    epg_enabled = addon.getSetting("epg_enabled") != "false"
    epg_ids = _load_epg_ids({group}) if matches and epg_enabled else {}
    programmes = _load_epg_programmes(group) if epg_ids else {}
    matched = 0
    name_matched = 0
    misses = []
    for ch in matches:
        li, url = _make_channel_li(ch, context="channel")
        entry, has_id = _epg_plot_for_channel(ch, epg_ids, programmes)
        if has_id:
            name_matched += 1
        elif len(misses) < 15:
            misses.append(ch["name"])
        if entry:
            matched += 1
            plot = entry["title"]
            if entry.get("desc"):
                plot += "\n\n" + entry["desc"]
            li.setInfo("video", {"title": ch["name"], "plot": plot, "plotoutline": entry["title"]})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url,
                                    listitem=li, isFolder=False)
    _log("EPG %s: enabled=%s names=%d programmes=%d channels=%d name_matched=%d now_matched=%d misses=%s" % (
        group, epg_enabled, len(epg_ids), len(programmes), len(matches), name_matched, matched, misses
    ), xbmc.LOGINFO)
    xbmcplugin.endOfDirectory(addon_handle)

def list_favs():
    favs = _load_favs()
    if not favs:
        xbmcgui.Dialog().ok("VAV Favoriten", "Noch keine VAV Favoriten gespeichert.")
        xbmcplugin.endOfDirectory(addon_handle)
        return
    for fav in favs:
        li, url = _make_channel_li(fav, context="fav")
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url,
                                    listitem=li, isFolder=False)
    xbmcplugin.endOfDirectory(addon_handle)

def do_search(query=None):
    if not query:
        kb = xbmc.Keyboard("", "Kanal suchen")
        kb.doModal()
        if not kb.isConfirmed():
            xbmcplugin.endOfDirectory(addon_handle)
            return
        query = kb.getText().strip()
    if not query:
        xbmcplugin.endOfDirectory(addon_handle)
        return
    channels = _get_catalog()
    q        = query.lower()
    found    = [ch for ch in channels
                if q in ch["name"].lower() or q in ch["country"].lower()]
    if not found:
        xbmcgui.Dialog().ok("Suche", 'Keine Ergebnisse fuer "%s".' % query)
        xbmcplugin.endOfDirectory(addon_handle)
        return
    country_order = _load_order()
    order_map     = {c.lower(): i for i, c in enumerate(country_order)}

    def _sort_key(ch):
        ctry_idx = order_map.get(ch["country"].lower(), len(country_order))
        return (ctry_idx, ch["name"].lower())

    found.sort(key=_sort_key)

    xbmcplugin.setPluginCategory(addon_handle, "Suche: " + query)
    for ch in found:
        li, url = _make_channel_li(ch, context="channel")
        li.setLabel("%s  [%s]" % (ch["name"], ch["country"]))
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url,
                                    listitem=li, isFolder=False)
    xbmcplugin.endOfDirectory(addon_handle)

_EPG_STRIP = re.compile(
    r'^\[.*?\]\s*'
    r'|\s*\|[A-Z0-9+]+$'
    r'|\s+\[.*?\]'
    r'|\s+\(.*?\)'
    r'|\s+\b(FHD|UHD|HD\+?|SD|4K|HEVC|RAW|SAT|BACKUP\s*\d*)\b',
    re.IGNORECASE
)

def _epg_name(raw):
    name = raw.strip()
    prev = None
    while name != prev:
        prev = name
        name = _EPG_STRIP.sub("", name).strip()
    return name


def browse_export_path():
    current = addon.getSetting("export_path").strip()
    if not current or current.startswith("special://"):
        start = "/storage"
    else:
        start = current
    chosen = xbmcgui.Dialog().browse(0, "Export-Ordner auswaehlen", "local", "", False, False, start)
    if chosen and chosen != start:
        addon.setSetting("export_path", chosen)
        _notify("Export-Ordner geaendert: " + chosen)

EPG_BASE = "https://epgshare01.online/epgshare01/"


_epg_id_cache = {}
_epg_id_cache_lock = threading.Lock()

def _load_epg_ids(countries):
    result = {}
    xml_urls = set()
    for c in countries:
        u = COUNTRY_EPG.get(c.lower())
        if u:
            xml_urls.add(u)
    for url in xml_urls:
        with _epg_id_cache_lock:
            cached = _epg_id_cache.get(url)
        if cached is not None:
            result.update(cached)
            continue
        try:
            r = requests.get(url, timeout=60, verify=False)
            r.raise_for_status()
            try:
                raw = gzip.decompress(r.content).decode("utf-8", errors="replace")
            except Exception:
                raw = r.text
            mapping = {}
            for cm in re.finditer(r'<channel id="([^"]+)"[^>]*>(.*?)</channel>', raw, re.DOTALL):
                ch_id = cm.group(1)
                body  = cm.group(2)
                for nm in re.finditer(r'<display-name[^>]*>([^<]*)</display-name>', body):
                    ch_name = html.unescape(nm.group(1)).strip()
                    if not ch_name:
                        continue
                    mapping.setdefault(ch_name.lower(), ch_id)
                    norm = _normalize_name(ch_name)
                    if norm:
                        mapping.setdefault(norm, ch_id)
            with _epg_id_cache_lock:
                _epg_id_cache[url] = mapping
            result.update(mapping)
        except Exception as e:
            _log("EPG xml %s: %s" % (url, e), xbmc.LOGWARNING)
    return result


EPG_PROG_TTL = 6 * 3600

def _epg_prog_cache_file(country):
    safe = re.sub(r"[^a-z0-9]+", "_", country.lower())
    return os.path.join(ADDON_DATA, "epg_prog_%s.json" % safe)

def _parse_xmltv_datetime(s):
    s = s.strip()
    for fmt in ("%Y%m%d%H%M%S %z", "%Y%m%d%H%M%S%z"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None

def _parse_xmltv_programmes(raw):
    programmes = {}
    for m in re.finditer(
        r'<programme start="([^"]+)" stop="([^"]+)" channel="([^"]+)"[^>]*>(.*?)</programme>',
        raw, re.DOTALL
    ):
        start, stop, ch_id, body = m.groups()
        title_m = re.search(r'<title[^>]*>([^<]*)</title>', body)
        desc_m  = re.search(r'<desc[^>]*>([^<]*)</desc>', body)
        title = html.unescape(title_m.group(1)).strip() if title_m else ""
        if not title:
            continue
        desc = html.unescape(desc_m.group(1)).strip() if desc_m else ""
        programmes.setdefault(ch_id, []).append({
            "start": start, "stop": stop, "title": title, "desc": desc,
        })
    return programmes

def _load_epg_programmes(country):
    url = COUNTRY_EPG.get(country.lower())
    if not url:
        return {}
    cache_file = _epg_prog_cache_file(country)
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - data.get("ts", 0) < EPG_PROG_TTL:
            return data["programmes"]
    except Exception:
        pass
    try:
        r = requests.get(url, timeout=60, verify=False)
        r.raise_for_status()
        try:
            raw = gzip.decompress(r.content).decode("utf-8", errors="replace")
        except Exception:
            raw = r.text
        programmes = _parse_xmltv_programmes(raw)
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"ts": time.time(), "programmes": programmes}, f)
        except Exception as e:
            _log("EPG prog cache write: " + str(e), xbmc.LOGWARNING)
        return programmes
    except Exception as e:
        _log("EPG prog fetch %s: %s" % (url, e), xbmc.LOGWARNING)
        return {}

def _current_programme(programmes, ch_id):
    entries = programmes.get(ch_id)
    if not entries:
        return None
    now = datetime.now(timezone.utc)
    for entry in entries:
        start = _parse_xmltv_datetime(entry["start"])
        stop  = _parse_xmltv_datetime(entry["stop"])
        if start and stop and start <= now <= stop:
            return entry
    return None

def _epg_plot_for_channel(ch, epg_ids, programmes):
    if not epg_ids:
        return None, False
    clean = _epg_name(ch["name"])
    ch_id = (epg_ids.get(clean.lower())
             or epg_ids.get(clean.lower().replace(" ", "_"))
             or epg_ids.get(_normalize_name(clean))
             or epg_ids.get(_normalize_name(ch["name"])))
    if not ch_id:
        return None, False
    return _current_programme(programmes, ch_id), True

COUNTRY_EPG = {
    "albania":              EPG_BASE + "epg_ripper_AL1.xml.gz",
    "arabia":               EPG_BASE + "epg_ripper_AE1.xml.gz",
    "azerbaijan":           None,
    "balkans":              EPG_BASE + "epg_ripper_RS1.xml.gz",
    "belgium":              EPG_BASE + "epg_ripper_BE2.xml.gz",
    "bulgaria":             EPG_BASE + "epg_ripper_BG1.xml.gz",
    "croatia":              EPG_BASE + "epg_ripper_HR1.xml.gz",
    "denmark":              EPG_BASE + "epg_ripper_DK1.xml.gz",
    "france":               EPG_BASE + "epg_ripper_FR1.xml.gz",
    "france sport":         EPG_BASE + "epg_ripper_FR1.xml.gz",
    "germany":              EPG_BASE + "epg_ripper_DE1.xml.gz",
    "greece":               EPG_BASE + "epg_ripper_GR1.xml.gz",
    "iran":                 None,
    "italy":                EPG_BASE + "epg_ripper_IT1.xml.gz",
    "netherlands":          EPG_BASE + "epg_ripper_NL1.xml.gz",
    "poland":               EPG_BASE + "epg_ripper_PL1.xml.gz",
    "portugal":             EPG_BASE + "epg_ripper_PT1.xml.gz",
    "romania":              EPG_BASE + "epg_ripper_RO1.xml.gz",
    "russia":               EPG_BASE + "epg_ripper_viva-russia.ru.xml.gz",
    "spain":                EPG_BASE + "epg_ripper_ES1.xml.gz",
    "sports international": EPG_BASE + "epg_ripper_BEIN1.xml.gz",
    "sweden":               EPG_BASE + "epg_ripper_SE1.xml.gz",
    "turkey":               EPG_BASE + "epg_ripper_TR1.xml.gz",
    "united kingdom":       EPG_BASE + "epg_ripper_UK1.xml.gz",
}

def export_m3u():
    channels = _get_catalog()
    if not channels:
        _notify("Keine Kanaele geladen", error=True)
        return

    all_countries = _sorted_countries(list(set(ch["country"] for ch in channels)))
    selected = xbmcgui.Dialog().multiselect("Laender auswaehlen", all_countries, preselect=[])
    if selected is None:
        return
    if not selected:
        _notify("Kein Land ausgewaehlt", error=True)
        return
    chosen_countries = set(all_countries[i] for i in selected)

    epg_enabled  = addon.getSetting("epg_enabled") != "false"
    auto_map     = addon.getSetting("auto_map") != "false"
    custom_url   = addon.getSetting("epg_url").strip()
    export_dir   = addon.getSetting("export_path").strip() or ADDON_DATA
    export_dir   = xbmcvfs.translatePath(export_dir)
    xbmcvfs.mkdirs(export_dir)
    path = os.path.join(export_dir, "vavoo.m3u")

    epg_urls   = []
    epg_ids    = {}
    by_country = {}
    by_name    = {}

    if epg_enabled:
        pd = xbmcgui.DialogProgress()
        pd.create("VAVOO", "Lade EPG-Daten...")
        pd.update(0)

        if custom_url:
            epg_urls.append(custom_url)

        for c in chosen_countries:
            url = COUNTRY_EPG.get(c.lower())
            if url and url not in epg_urls:
                epg_urls.append(url)

        pd.update(20, "Lade EPG-Kanalnamen...")
        epg_ids = _load_epg_ids(chosen_countries)

        if auto_map:
            pd.update(60, "Lade iptv-org Zuordnung...")
            by_country, by_name = _load_epg_index()

        pd.update(100)
        pd.close()

    if epg_urls:
        header = '#EXTM3U url-tvg="%s"' % epg_urls[0]
        if len(epg_urls) > 1:
            header += ' x-tvg-url="%s"' % ",".join(epg_urls[1:])
        lines = [header]
    else:
        lines = ["#EXTM3U"]

    matched = 0
    for ch in channels:
        if not ch.get("url"):
            continue
        if ch["country"] not in chosen_countries:
            continue
        name    = _m3u_escape(ch["name"])
        country = _m3u_escape(ch["country"])
        logo    = _m3u_escape(ch.get("logo") or "") if epg_enabled else ""
        clean   = _epg_name(ch["name"])
        tvg_id  = ""

        if epg_enabled:
            tvg_id = (epg_ids.get(clean.lower())
                      or epg_ids.get(clean.lower().replace(" ", "_"))
                      or epg_ids.get(_normalize_name(clean))
                      or "")
            if not tvg_id and auto_map:
                tvg_id = _auto_tvg_id(ch, by_country, by_name)
            if tvg_id:
                matched += 1
            else:
                tvg_id = clean

        tvg_id   = _m3u_escape(tvg_id)
        tvg_name = _m3u_escape(clean) if epg_enabled else name
        lines.append('#EXTINF:-1 tvg-id="%s" tvg-name="%s" tvg-logo="%s" group-title="%s",%s' %
                      (tvg_id, tvg_name, logo, country, name))
        plugin_url = "plugin://plugin.video.vav/?mode=play&channel_url=%s&channel_id=%s" % (
            urllib.parse.quote(ch["url"], safe=""), urllib.parse.quote(ch["id"], safe=""))
        lines.append(plugin_url)

    content = "\n".join(lines) + "\n"
    written = []
    if _vfs_write(path, content):
        written.append(path)

    dl_dir = _writable_download_dir()
    if dl_dir:
        dl_path = os.path.join(dl_dir, "vavoo.m3u")
        if os.path.normpath(dl_path) != os.path.normpath(path) and _vfs_write(dl_path, content):
            written.append(dl_path)

    if not written:
        _notify("Export fehlgeschlagen (keine Schreibrechte)", error=True)
        return

    ch_count = (len(lines) - 1) // 2
    if epg_enabled:
        _notify("M3U exportiert (%d Kanaele, %d EPG-Treffer): %s" % (ch_count, matched, ", ".join(written)))
    else:
        _notify("M3U exportiert (%d Kanaele): %s" % (ch_count, ", ".join(written)))

def epg_refresh():
    by_country, by_name = _load_epg_index(force=True)
    if by_name:
        _notify("EPG-Datenbank aktualisiert (%d Kanaele)" % len(by_name))
    else:
        _notify("EPG-Datenbank Update fehlgeschlagen", error=True)

def play_stream(channel_url, channel_id):
    sig = _get_sig()
    if not sig:
        _notify("Kein Token", error=True)
        xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem())
        return
    stream_url = None
    max_attempts = 3
    for attempt in range(max_attempts):
        stream_url = _resolve(channel_url, sig)
        if stream_url:
            break
        if attempt < max_attempts - 1:
            xbmc.sleep(2000)
    if not stream_url:
        _notify("Stream konnte nicht aufgeloest werden", error=True)
        xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem())
        return

    li = xbmcgui.ListItem(path=stream_url)
    li.setMimeType("application/x-mpegURL")
    li.setContentLookup(False)
    li.setProperty("inputstream",                                "inputstream.adaptive")
    li.setProperty("inputstream.adaptive.manifest_type",         "hls")
    li.setProperty("inputstream.adaptive.stream_headers",        "verifypeer=false")
    li.setProperty("inputstream.adaptive.manifest_headers",      "verifypeer=false")
    li.setProperty("inputstream.adaptive.license_flags",         "persistent_storage")
    xbmcplugin.setResolvedUrl(addon_handle, True, listitem=li)

params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
mode   = params.get("mode", "")

if   mode == "list_channels":   list_channels(params.get("group", ""))
elif mode == "list_favs":        list_favs()
elif mode == "search":           do_search(params.get("query"))
elif mode == "play":             play_stream(params.get("channel_url", ""), params.get("channel_id", ""))
elif mode == "fav_add":          _add_fav(next((c for c in _get_catalog() if c["id"] == params.get("id", "")), {}))
elif mode == "fav_remove":       _remove_fav(params.get("id", ""))
elif mode == "fav_rename":       _rename_fav(params.get("id", ""))
elif mode == "fav_move":         _move_fav(params.get("id", ""), params.get("dir", "up"))
elif mode == "ctry_move":        _move_country(params.get("country", ""), params.get("dir", "up"))
elif mode == "settings":
    addon.openSettings()
    xbmcplugin.endOfDirectory(addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
elif mode == "epg_refresh":      epg_refresh()
elif mode == "browse_export_path": browse_export_path()
elif mode == "export_m3u":      export_m3u()
elif mode == "ctry_reset":       _reset_order()
else:                            list_groups()
