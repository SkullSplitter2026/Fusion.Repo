# -*- coding: utf-8 -*-
"""UI functions: root menu, search, categories, wallpaper display, slideshow."""
import os
import sys
import time
import random as _random
import urllib.parse as up
import urllib.request as urlreq
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

from . import common
from . import favorites
from . import wallpaper_set
from . import history
from . import cache
from . import genres

try:
    import resources.lib.skulls_source as skulls_source
except Exception:
    skulls_source = None

try:
    from resources.lib import wc_scraper as wc
except Exception:
    _LIBDIR = os.path.join(common.addon_path(), "resources", "lib")
    if _LIBDIR not in sys.path:
        sys.path.insert(0, _LIBDIR)
    import wc_scraper as wc

def _parallel_load_thumbs(items, max_workers=4):
    import queue
    import threading
    results = {}
    q = queue.Queue()
    for i, it in enumerate(items):
        q.put((i, it))
    lock = threading.Lock()

    def worker():
        while True:
            try:
                idx, it = q.get(timeout=0.1)
            except queue.Empty:
                return
            thumb = it.get("thumb", "")
            if thumb:
                try:
                    req = urlreq.Request(thumb, headers={"User-Agent": "Mozilla/5.0"})
                    with urlreq.urlopen(req, timeout=5) as r:
                        data = r.read()
                        with lock:
                            results[idx] = data
                except Exception:
                    pass
            q.task_done()

    threads = []
    for _ in range(min(max_workers, len(items))):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return results


def _is_source_available(source_name):
    if source_name == "wallpaperscraft":
        try:
            req = urlreq.Request(common.BASE_SITE, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
            with urlreq.urlopen(req, timeout=5) as r:
                return r.getcode() < 400
        except Exception:
            return False
    return True


def show_root():
    xbmcplugin.setContent(common.HANDLE, "files")
    icon_path = common.addon_path("icon.png")
    fanart_path = common.addon_path("fanart.jpg")

    for lbl in ("[B]========================[/B]", "[B]sKulls Fusion Wallpapers[/B]", "[B]========================[/B]"):
        li = xbmcgui.ListItem(label=lbl)
        li.setArt({"icon": icon_path, "thumb": icon_path, "fanart": fanart_path})
        xbmcplugin.addDirectoryItem(common.HANDLE, "", li, isFolder=False)

    li = xbmcgui.ListItem(label="[COLOR deepskyblue]Search Wallpapers[/COLOR]")
    li.setArt({"icon": common.media_icon("search"), "thumb": common.media_icon("search")})
    xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="search_prompt"), li, isFolder=False)

    hist = history.get_all()
    if hist:
        hi = xbmcgui.ListItem(label="[COLOR grey]Search History[/COLOR]")
        hi.setArt({"icon": common.media_icon("history"), "thumb": common.media_icon("history")})
        xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="show_history"), hi, isFolder=True)

    ri = xbmcgui.ListItem(label="[COLOR orange]Random Wallpaper[/COLOR]")
    ri.setArt({"icon": common.media_icon("random"), "thumb": common.media_icon("random")})
    xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="random_wallpaper"), ri, isFolder=True)

    favs = favorites.get_all()
    fi = xbmcgui.ListItem(label=f"[COLOR gold]My Favorites ({len(favs)})[/COLOR]")
    fi.setArt({"icon": common.media_icon("favorites"), "thumb": common.media_icon("favorites")})
    xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="show_favorites"), fi, isFolder=True)

    si = xbmcgui.ListItem(label=f"[COLOR violet]Wallpaper Set ({wallpaper_set.count()})[/COLOR]")
    si.setArt({"icon": common.media_icon("set"), "thumb": common.media_icon("set")})
    xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="show_set"), si, isFolder=True)

    li = xbmcgui.ListItem(label="-------------------")
    xbmcplugin.addDirectoryItem(common.HANDLE, "", li, isFolder=False)

    mi = xbmcgui.ListItem(label="[COLOR lime]My Wallpapers[/COLOR]")
    mi.setArt({"icon": common.media_icon("mywallpaper"), "thumb": common.media_icon("mywallpaper")})
    xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="my_wallpapers", dir=common.get_download_dir()), mi, isFolder=True)

    gi = xbmcgui.ListItem(label="[COLOR springgreen]Genre Manager[/COLOR]")
    gi.setArt({"icon": common.media_icon("categories"), "thumb": common.media_icon("categories")})
    xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="manage_genres"), gi, isFolder=True)

    dl_path = xbmcgui.ListItem(label="[COLOR grey]Set Download Path[/COLOR]")
    dl_path.setArt({"icon": common.media_icon("download"), "thumb": common.media_icon("download")})
    xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="set_download_path"), dl_path, isFolder=False)

    dl_browse = xbmcgui.ListItem(label="[COLOR grey]Browse Download Path[/COLOR]")
    dl_browse.setArt({"icon": common.media_icon("download"), "thumb": common.media_icon("download")})
    xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="browse_download_path"), dl_browse, isFolder=False)

    di = xbmcgui.ListItem(label="[COLOR red]sKulls Archive[/COLOR]")
    di.setArt({"icon": common.media_icon("archive"), "thumb": common.media_icon("archive")})
    xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="skulls_root"), di, isFolder=True)

    custom = sources_mod.load() if hasattr(sources_mod, 'load') else []
    for src in custom:
        name = src.get("name", "Unknown")
        url_str = src.get("url", "")
        li = xbmcgui.ListItem(label=f"[COLOR violet]{name}[/COLOR]")
        li.setArt({"icon": common.media_icon("archive"), "thumb": common.media_icon("archive")})
        xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="browse_custom_source", url=url_str, name=name), li, isFolder=True)

    li = xbmcgui.ListItem(label="[COLOR grey]Manage Custom Sources[/COLOR]")
    li.setArt({"icon": common.media_icon("favorites"), "thumb": common.media_icon("favorites")})
    xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="manage_custom_sources"), li, isFolder=True)

    li = xbmcgui.ListItem(label="-------------------")
    xbmcplugin.addDirectoryItem(common.HANDLE, "", li, isFolder=False)

    li = xbmcgui.ListItem(label="[COLOR cyan]Categories[/COLOR]")
    li.setArt({"icon": common.media_icon("categories"), "thumb": common.media_icon("categories")})
    xbmcplugin.addDirectoryItem(common.HANDLE, "", li, isFolder=False)

    entries = common.CATEGORY_ENTRIES
    for title, slug, kind in entries:
        li = xbmcgui.ListItem(label=title)
        thumb = common.cat_thumb(slug)
        if thumb:
            li.setArt({"thumb": thumb, "icon": thumb, "poster": thumb, "fanart": thumb})
        url = common.url(mode="category", kind=kind, slug=slug, page="1", title=title)
        xbmcplugin.addDirectoryItem(common.HANDLE, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)

    if not common.get_bool("use_static_thumbs", False):
        xbmc.executebuiltin("CancelAlarm(wcthumbs,true)")
        xbmc.executebuiltin(f'AlarmClock(wcthumbs,RunPlugin("{common.url(mode="warm_thumbs", idx="0")}"),00:00:01,true)')


def search_prompt(_params):
    dlg = xbmcgui.Dialog()
    query = dlg.input("Search Wallpapers", type=xbmcgui.INPUT_ALPHANUM)
    if not query:
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    history.add(query)
    try:
        xbmc.executebuiltin(f'Container.Update("{common.url(mode="search", q=query, page="1")}")')
    except Exception:
        pass
    try:
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
    except Exception:
        pass


def show_history(_params):
    xbmcplugin.setContent(common.HANDLE, "files")
    hist = history.get_all()
    if not hist:
        li = xbmcgui.ListItem(label="No recent searches")
        xbmcplugin.addDirectoryItem(common.HANDLE, "", li, isFolder=False)
    else:
        for q in hist:
            li = xbmcgui.ListItem(label=q)
            li.setArt({"icon": common.media_icon("search"), "thumb": common.media_icon("search")})
            url = common.url(mode="search", q=q, page="1")
            xbmcplugin.addDirectoryItem(common.HANDLE, url, li, isFolder=True)
        cli = xbmcgui.ListItem(label="[Clear History]")
        cli.setArt({"icon": common.media_icon("favorites"), "thumb": common.media_icon("favorites")})
        xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="clear_history"), cli, isFolder=False)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def clear_history(_params):
    history.clear()
    try:
        xbmcgui.Dialog().notification("sKulls Wallpapers", "History cleared", "DefaultAddonsInfo.png", 2000)
    except Exception:
        pass
    xbmc.executebuiltin("Container.Refresh")


def warm_thumbs(params):
    try:
        xbmc.executebuiltin("CancelAlarm(wcthumbs,true)")
    except Exception:
        pass
    try:
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
    except Exception:
        pass


def list_search_results(params):
    query = params.get("q", "")
    page = int(params.get("page", "1"))
    xbmcplugin.setContent(common.HANDLE, "movies")
    common.log(f"Search '{query}' page={page}")
    if common.should_abort():
        return
    items, has_next = [], False
    max_wait_s = 10
    start = time.time()
    attempts = 0
    try:
        xbmc.executebuiltin("ActivateWindow(busydialog)")
    except Exception:
        pass
    while not items:
        attempts += 1
        try:
            items, has_next = wc.list_search(query, page)
        except Exception as e:
            common.log(f"list_search error (attempt {attempts}): {e}")
            items, has_next = [], False
        if items or (time.time() - start) >= max_wait_s or attempts >= 2:
            break
        xbmc.sleep(800)
    try:
        xbmc.executebuiltin("Dialog.Close(busydialog)")
    except Exception:
        pass
    if not items:
        try:
            xbmcgui.Dialog().notification("sKulls Wallpapers", f"No results for '{query}'", "DefaultAddonsInfo.png", 3000)
        except Exception:
            pass
    items = common.apply_resolution_filter(items)
    if not items:
        try:
            xbmcgui.Dialog().notification("sKulls Wallpapers", "No wallpapers match resolution filter", "DefaultAddonsInfo.png", 3000)
        except Exception:
            pass
    for it in items:
        lbl = it.get("title") or "Wallpaper"
        li = xbmcgui.ListItem(label=lbl)
        th = it.get("thumb")
        if th:
            li.setArt({"thumb": th, "icon": th, "poster": th, "fanart": th})
        common.set_video_title(li, lbl)
        url = common.url(mode="wallpaper", page_url=it.get("href", ""), title=lbl)
        xbmcplugin.addDirectoryItem(common.HANDLE, url, li, isFolder=True)
    if has_next:
        nli = xbmcgui.ListItem(label=f"Next (page {page+1})")
        common.set_video_title(nli, f"{query} -- page {page+1}")
        nurl = common.url(mode="search", q=query, page=str(page+1))
        xbmcplugin.addDirectoryItem(common.HANDLE, nurl, nli, isFolder=True)
    xbmcplugin.endOfDirectory(common.HANDLE, updateListing=(page > 1), cacheToDisc=False)


def list_category(params):
    kind = params.get("kind", "catalog")
    slug = params.get("slug", "")
    title = params.get("title", slug or "Wallpapers")
    page = int(params.get("page", "1"))
    use_cache = common.get_bool("use_cache", True)
    if common.should_abort():
        return
    common.log(f"Opening '{title}' ({kind}:{slug}) page={page}")
    xbmcplugin.setContent(common.HANDLE, "movies")
    items, has_next = [], False
    if use_cache:
        cached = cache.get(kind, slug, page)
        if cached:
            common.log(f"Using cache for {kind}:{slug}:{page}")
            items = cached.get("items", [])
            has_next = cached.get("has_next", False)
    if not items:
        try:
            items, has_next = wc.list_wallpapers(kind, slug, page)
        except Exception as e:
            common.log(f"list_wallpapers error for {kind}:{slug} p{page}: {e}")
    if not items and skulls_source:
        common.log("WallpapersCraft unavailable, trying sKulls archive as backup...")
        try:
            cats = skulls_source.list_categories()
            for c in cats:
                if c.get("title", "").lower() == slug.lower() or slug.lower() in c.get("title", "").lower():
                    imgs = skulls_source.list_images(c.get("href", ""))
                    for img in imgs:
                        items.append({"title": img.get("title", "Wallpaper"), "thumb": img.get("thumb", ""), "href": img.get("img", "")})
                    has_next = False
                    break
        except Exception as e:
            common.log(f"Backup source failed: {e}")
    if not items:
        aliases = {
            "black_and_white": ["black-and-white", "bw"],
            "tv-series": ["tv_series", "tvseries", "serials", "tv"],
            "hi-tech": ["technologies", "technology", "tech"],
            "sport": ["sports"],
        }
        candidates = [(kind, slug)]
        if slug in aliases:
            for s in aliases[slug]:
                candidates.append((kind, s))
        for s in [slug] + aliases.get(slug, []):
            candidates.append(("tag", s))
        seen = set()
        for k, s in candidates:
            key = f"{k}:{s}"
            if key in seen:
                continue
            seen.add(key)
            try:
                tmp_items, tmp_next = wc.list_wallpapers(k, s, page)
                if tmp_items:
                    kind, slug = k, s
                    items, has_next = tmp_items, tmp_next
                    break
            except Exception:
                continue
    if not items:
        try:
            xbmcgui.Dialog().notification("sKulls Wallpapers", f"{title}: No results or timed out", "DefaultAddonsInfo.png", 3000)
        except Exception:
            pass
    items = common.apply_resolution_filter(items)
    for it in items:
        lbl = it.get("title") or title
        li = xbmcgui.ListItem(label=lbl)
        th = it.get("thumb")
        if th:
            li.setArt({"thumb": th, "icon": th, "poster": th, "fanart": th})
        common.set_video_title(li, lbl)
        url = common.url(mode="wallpaper", page_url=it.get("href", ""), title=lbl)
        xbmcplugin.addDirectoryItem(common.HANDLE, url, li, isFolder=True)
    if has_next:
        nli = xbmcgui.ListItem(label=f"Next (page {page+1})")
        common.set_video_title(nli, f"{title} -- page {page+1}")
        nurl = common.url(mode="category", kind=kind, slug=slug, page=str(page+1), title=title)
        xbmcplugin.addDirectoryItem(common.HANDLE, nurl, nli, isFolder=True)
    if use_cache and items:
        cache.set_cache(kind, slug, page, {"items": items, "has_next": has_next})
    xbmcplugin.endOfDirectory(common.HANDLE, updateListing=(page > 1), cacheToDisc=False)


def wallpaper_menu(params):
    page_url = params.get("page_url", "")
    title = params.get("title", "Wallpaper")
    xbmcplugin.setContent(common.HANDLE, "files")
    try:
        sizes = wc.list_sizes(page_url)
    except Exception as e:
        common.log(f"list_sizes failed: {e}")
        sizes = []
    if not sizes:
        try:
            xbmcgui.Dialog().notification("sKulls Wallpapers", "No sizes found", "DefaultAddonsInfo.png", 3000)
        except Exception:
            pass
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    preview_url = sizes[0].get("url", "")
    if preview_url:
        pli = xbmcgui.ListItem(label="PREVIEW")
        pli.setArt({"thumb": sizes[0].get("thumb", ""), "icon": common.media_icon("preview")})
        purl = common.url(mode="preview_image", img=preview_url, title=title)
        xbmcplugin.addDirectoryItem(common.HANDLE, purl, pli, isFolder=False)

    fav_url = common.url(mode="add_favorite", title=title, url=page_url, thumb=sizes[0].get("thumb", ""))
    fav_li = xbmcgui.ListItem(label="ADD TO FAVORITES")
    fav_li.setArt({"icon": common.media_icon("favorites"), "thumb": common.media_icon("favorites")})
    xbmcplugin.addDirectoryItem(common.HANDLE, fav_url, fav_li, isFolder=False)

    set_url = common.url(mode="add_to_set", title=title, url=page_url, thumb=sizes[0].get("thumb", ""))
    set_li = xbmcgui.ListItem(label="ADD TO SET")
    set_li.setArt({"icon": common.media_icon("set"), "thumb": common.media_icon("set")})
    xbmcplugin.addDirectoryItem(common.HANDLE, set_url, set_li, isFolder=False)

    li = xbmcgui.ListItem(label="--- Available Resolutions ---")
    xbmcplugin.addDirectoryItem(common.HANDLE, "", li, isFolder=False)

    def res_sort(s):
        lbl = s.get("label", "0x0")
        try:
            w, h = lbl.split("x")
            return int(w) * int(h)
        except Exception:
            return 0

    sizes_sorted = sorted(sizes, key=res_sort, reverse=True)
    for s in sizes_sorted:
        label = s.get("label", "Unknown")
        img_url = s.get("url", "")
        if not img_url:
            continue
        if "3840" in label or "4096" in label:
            icon = "DefaultStar.png"
        else:
            icon = "DefaultDownload.png"
        li = xbmcgui.ListItem(label=f"DOWNLOAD {label}")
        th = s.get("thumb", "")
        if th:
            li.setArt({"thumb": th, "icon": icon})
        url = common.url(mode="download_image", img=img_url, title=title, label=label, ref=page_url)
        li.setProperty("IsPlayable", "false")
        xbmcplugin.addDirectoryItem(common.HANDLE, url, li, isFolder=False)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def preview_image(params):
    img_url = params.get("img", "")
    if img_url:
        xbmc.executebuiltin(f'ShowPicture("{img_url}")')
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def download_image(params):
    img_url = params.get("img", "")
    title = params.get("title", "Wallpaper")
    label = params.get("label", "")
    referer = params.get("ref", "")
    genre_name = params.get("genre", "")
    if not img_url:
        xbmcgui.Dialog().notification("sKulls Wallpapers", "Missing image URL", "DefaultAddonsInfo.png", 2500)
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    dest_dir = common.get_download_dir()
    genre_names = genres.get_names()
    if genre_name:
        dest_dir = genres.get_path(genre_name)
    elif genre_names:
        options = ["Default folder"] + genre_names + ["[New genre...]"]
        idx = xbmcgui.Dialog().select("Save to genre", options)
        if idx > 0 and idx <= len(genre_names):
            dest_dir = genres.get_path(genre_names[idx - 1])
        elif idx == len(genre_names) + 1:
            new_name = xbmcgui.Dialog().input("New Genre Name", type=xbmcgui.INPUT_ALPHANUM)
            if new_name:
                ok, _ = genres.create(new_name)
                if ok:
                    dest_dir = genres.get_path(new_name)
    base = common.sanitize_name(f"{title}_{label}" if label else title)
    p = up.urlparse(img_url)
    ext = os.path.splitext(os.path.basename(p.path))[1].lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png"):
        ext = ".jpg"
    i = 0
    while True:
        name = f"{base}{'' if i == 0 else f'_{i}'}{ext}"
        full = os.path.join(dest_dir, name)
        if not xbmcvfs.exists(full):
            dest_path = full
            break
        i += 1
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
        "Accept": "*/*",
    }
    if referer:
        headers["Referer"] = referer
    dp = xbmcgui.DialogProgress()
    dp.create("sKulls Wallpapers", "Starting download...")
    try:
        req = urlreq.Request(img_url, headers=headers)
        with urlreq.urlopen(req, timeout=20) as r:
            total = int(r.headers.get("Content-Length", "0")) or 0
            f = xbmcvfs.File(dest_path, "w")
            try:
                chunk = 1024 * 1024
                read = 0
                last = 0
                while True:
                    if dp.iscanceled():
                        return
                    buf = r.read(chunk)
                    if not buf:
                        break
                    f.write(buf)
                    read += len(buf)
                    now = time.time()
                    if now - last > 0.1:
                        pct = int((read * 100) / total) if total else 0
                        dp.update(max(0, min(100, pct)), f"Downloading...\n{read // 1024 // 1024} / {total // 1024 // 1024} MB")
                        last = now
            finally:
                f.close()
        dp.update(100, "Finishing...")
        xbmcgui.Dialog().notification("sKulls Wallpapers", f"Saved to:\n{dest_dir}", "DefaultAddonsInfo.png", 3500)
    except Exception as e:
        common.log(f"Download failed: {e}")
        xbmcgui.Dialog().notification("sKulls Wallpapers", "Download failed", "DefaultAddonsInfo.png", 3000)
    finally:
        try:
            dp.close()
        except Exception:
            pass
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def custom_wallpaper(params):
    img_url = params.get("img", "")
    title = params.get("title", "Wallpaper")
    if not img_url:
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    thumb = img_url
    xbmcplugin.setContent(common.HANDLE, "images")
    pli = xbmcgui.ListItem(label="[COLOR deepskyblue]PREVIEW[/COLOR]")
    pli.setArt({"thumb": thumb, "icon": common.media_icon("preview")})
    purl = common.url(mode="preview_image", img=img_url, title=title)
    xbmcplugin.addDirectoryItem(common.HANDLE, purl, pli, isFolder=False)
    fav_url = common.url(mode="add_favorite", title=title, url=img_url, thumb=thumb)
    fav_li = xbmcgui.ListItem(label="[COLOR gold]ADD TO FAVORITES[/COLOR]")
    fav_li.setArt({"icon": common.media_icon("favorites"), "thumb": common.media_icon("favorites")})
    xbmcplugin.addDirectoryItem(common.HANDLE, fav_url, fav_li, isFolder=False)
    set_url = common.url(mode="add_to_set", title=title, url=img_url, thumb=thumb)
    set_li = xbmcgui.ListItem(label="[COLOR violet]ADD TO SET[/COLOR]")
    set_li.setArt({"icon": common.media_icon("set"), "thumb": common.media_icon("set")})
    xbmcplugin.addDirectoryItem(common.HANDLE, set_url, set_li, isFolder=False)
    dl_li = xbmcgui.ListItem(label="[COLOR lime]DOWNLOAD[/COLOR]")
    dl_li.setArt({"thumb": thumb, "icon": common.media_icon("download")})
    dl_url = common.url(mode="download_image", img=img_url, title=title, label="custom", ref="custom")
    dl_li.setProperty("IsPlayable", "false")
    xbmcplugin.addDirectoryItem(common.HANDLE, dl_url, dl_li, isFolder=False)
    li = xbmcgui.ListItem(label=f"--- {title} ---")
    xbmcplugin.addDirectoryItem(common.HANDLE, "", li, isFolder=False)
    li = xbmcgui.ListItem(label=f"[COLOR cyan]View Image[/COLOR]")
    li.setArt({"thumb": thumb, "icon": thumb, "fanart": thumb})
    xbmcplugin.addDirectoryItem(common.HANDLE, img_url, li, isFolder=False)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def skulls_root(_params):
    if not skulls_source:
        xbmcgui.Dialog().notification("sKulls Wallpapers", "sKulls source not available", "DefaultAddonsInfo.png", 3000)
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    xbmcplugin.setContent(common.HANDLE, "files")
    try:
        cats = skulls_source.list_categories()
    except Exception as e:
        common.log(f"sKulls list_categories failed: {e}")
        xbmcgui.Dialog().notification("sKulls Wallpapers", "Failed to load sKulls categories", "DefaultAddonsInfo.png", 3000)
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    show_adult = common.get_bool("show_adult", False)
    adult_keywords = ["xxx", "adult", "porn", "sex", "18+", "nsfw"]
    for c in cats:
        title = c.get("title") or "Folder"
        href = c.get("href") or ""
        if not show_adult:
            if any(kw in title.lower() for kw in adult_keywords):
                continue
        li = xbmcgui.ListItem(label=title)
        li.setArt({"icon": common.media_icon("categories"), "thumb": common.media_icon("categories")})
        url = common.url(mode="skulls_category", path=href, title=title)
        xbmcplugin.addDirectoryItem(common.HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def list_skulls_category(params):
    if not skulls_source:
        xbmcgui.Dialog().notification("sKulls Wallpapers", "sKulls source not available", "DefaultAddonsInfo.png", 3000)
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    path = params.get("path", "")
    title = params.get("title", "sKulls")
    xbmcplugin.setContent(common.HANDLE, "images")
    show_adult = common.get_bool("show_adult", False)
    adult_keywords = ["xxx", "adult", "porn", "sex", "18+", "nsfw"]
    if any(kw in title.lower() for kw in adult_keywords) and not show_adult:
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    try:
        imgs = skulls_source.list_images(path)
    except Exception as e:
        common.log(f"sKulls list_images failed: {e}")
        xbmcgui.Dialog().notification("sKulls Wallpapers", "Failed to load images", "DefaultAddonsInfo.png", 3000)
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    for it in imgs:
        name = it.get("title") or "Wallpaper"
        img = it.get("img") or ""
        thumb = it.get("thumb") or img
        li = xbmcgui.ListItem(label=name)
        li.setArt({"thumb": thumb, "icon": thumb, "fanart": thumb, "poster": thumb})
        li.setInfo("image", {"title": name})
        url = common.url(mode="skulls_wallpaper_menu", img=img, title=name, thumb=thumb)
        xbmcplugin.addDirectoryItem(common.HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def skulls_wallpaper_menu(params):
    img_url = params.get("img", "")
    title = params.get("title", "Wallpaper")
    thumb = params.get("thumb", "")
    xbmcplugin.setContent(common.HANDLE, "files")
    if not img_url:
        xbmcgui.Dialog().notification("sKulls Wallpapers", "No image URL", "DefaultAddonsInfo.png", 2500)
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    pli = xbmcgui.ListItem(label="PREVIEW")
    pli.setArt({"thumb": thumb, "icon": common.media_icon("preview")})
    purl = common.url(mode="preview_image", img=img_url, title=title)
    xbmcplugin.addDirectoryItem(common.HANDLE, purl, pli, isFolder=False)
    fav_url = common.url(mode="add_favorite", title=title, url=img_url, thumb=thumb)
    fav_li = xbmcgui.ListItem(label="ADD TO FAVORITES")
    fav_li.setArt({"icon": common.media_icon("favorites"), "thumb": common.media_icon("favorites")})
    xbmcplugin.addDirectoryItem(common.HANDLE, fav_url, fav_li, isFolder=False)
    set_url = common.url(mode="add_to_set", title=title, url=img_url, thumb=thumb)
    set_li = xbmcgui.ListItem(label="ADD TO SET")
    set_li.setArt({"icon": common.media_icon("set"), "thumb": common.media_icon("set")})
    xbmcplugin.addDirectoryItem(common.HANDLE, set_url, set_li, isFolder=False)
    li = xbmcgui.ListItem(label="DOWNLOAD")
    li.setArt({"thumb": thumb, "icon": common.media_icon("download")})
    url = common.url(mode="download_image", img=img_url, title=title, label="sKulls", ref="skulls")
    li.setProperty("IsPlayable", "false")
    xbmcplugin.addDirectoryItem(common.HANDLE, url, li, isFolder=False)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def random_wallpaper(_params):
    xbmcplugin.setContent(common.HANDLE, "movies")
    entries = common.CATEGORY_ENTRIES
    _random.shuffle(entries)
    items = []
    cat_title = "Unknown"
    for cat in entries[:5]:
        title, slug, kind = cat[0], cat[1], cat[2]
        try:
            items, _ = wc.list_wallpapers(kind, slug, 1)
            if items:
                cat_title = title
                break
        except Exception:
            continue
    if not items:
        xbmcgui.Dialog().notification("sKulls Wallpapers", "No wallpapers found", "DefaultAddonsInfo.png", 3000)
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    common.log(f"Random wallpaper from {cat_title}")
    xbmcgui.Dialog().notification("sKulls Wallpapers", f"Random from {cat_title}", "DefaultAddonsInfo.png", 1500)
    item = _random.choice(items)
    it_title = item.get("title") or "Random"
    it_url = item.get("href", "")
    li = xbmcgui.ListItem(label=f"RANDOM: {it_title}")
    th = item.get("thumb", "")
    if th:
        li.setArt({"thumb": th, "icon": th, "poster": th, "fanart": th})
    url = common.url(mode="wallpaper", page_url=it_url, title=it_title)
    xbmcplugin.addDirectoryItem(common.HANDLE, url, li, isFolder=True)
    for _ in range(min(9, len(items))):
        if items:
            r = _random.choice(items)
            rt = r.get("title") or "Wallpaper"
            rl = r.get("href", "")
            li = xbmcgui.ListItem(label=rt)
            if r.get("thumb"):
                li.setArt({"thumb": r.get("thumb"), "icon": r.get("thumb")})
            url = common.url(mode="wallpaper", page_url=rl, title=rt)
            xbmcplugin.addDirectoryItem(common.HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def show_favorites(_params):
    xbmcplugin.setContent(common.HANDLE, "images")
    favs = favorites.get_all()
    if not favs:
        li = xbmcgui.ListItem(label="No favorites yet - add some from wallpaper menu!")
        xbmcplugin.addDirectoryItem(common.HANDLE, "", li, isFolder=False)
    else:
        sli = xbmcgui.ListItem(label="Start Slideshow")
        sli.setArt({"icon": common.media_icon("slideshow"), "thumb": common.media_icon("slideshow")})
        xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="slideshow", source="favorites"), sli, isFolder=False)
        for f in favs:
            name = f.get("title", "Wallpaper")
            url_str = f.get("url", "")
            thumb = f.get("thumb", "")
            li = xbmcgui.ListItem(label=name)
            li.setArt({"thumb": thumb, "icon": thumb, "fanart": thumb, "poster": thumb})
            li.setInfo("image", {"title": name})
            cm = [("Remove from Favorites", f'RunPlugin("{common.url(mode="remove_favorite", url=url_str)}")')]
            try:
                li.addContextMenuItems(cm, replaceItems=False)
            except Exception:
                pass
            xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="wallpaper", page_url=url_str, title=name), li, isFolder=True)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def add_favorite(params):
    title = params.get("title", "Wallpaper")
    url_str = params.get("url", "")
    thumb = params.get("thumb", "")
    result = favorites.add(title, url_str, thumb)
    if result:
        xbmcgui.Dialog().notification("sKulls Wallpapers", "Added to favorites!", "DefaultAddonsInfo.png", 2000)
    else:
        xbmcgui.Dialog().notification("sKulls Wallpapers", "Already in favorites", "DefaultAddonsInfo.png", 2000)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def remove_favorite(params):
    url_str = params.get("url", "")
    favorites.remove(url_str)
    xbmc.executebuiltin("Container.Refresh")


def show_set(_params):
    xbmcplugin.setContent(common.HANDLE, "files")
    items = wallpaper_set.load()
    if not items:
        li = xbmcgui.ListItem(label="Wallpaper Set is empty")
        xbmcplugin.addDirectoryItem(common.HANDLE, "", li, isFolder=False)
    else:
        sli = xbmcgui.ListItem(label="Start Slideshow")
        sli.setArt({"icon": common.media_icon("slideshow"), "thumb": common.media_icon("slideshow")})
        xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="slideshow", source="set"), sli, isFolder=False)
        if items:
            li = xbmcgui.ListItem(label=f"[Download All ({len(items)} images)]")
            li.setArt({"icon": common.media_icon("download"), "thumb": common.media_icon("download")})
            xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="download_set"), li, isFolder=False)
        cli = xbmcgui.ListItem(label="[Clear Set]")
        cli.setArt({"icon": common.media_icon("favorites"), "thumb": common.media_icon("favorites")})
        xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="clear_set"), cli, isFolder=False)
        for it in items:
            name = it.get("title", "Wallpaper")
            url_str = it.get("url", "")
            thumb = it.get("thumb", "")
            li = xbmcgui.ListItem(label=name)
            li.setArt({"thumb": thumb, "icon": thumb})
            cm = [("Remove from Set", f'RunPlugin("{common.url(mode="remove_from_set", url=url_str)}")')]
            try:
                li.addContextMenuItems(cm, replaceItems=False)
            except Exception:
                pass
            xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="wallpaper", page_url=url_str, title=name), li, isFolder=True)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def add_to_set(params):
    title = params.get("title", "Wallpaper")
    url_str = params.get("url", "")
    thumb = params.get("thumb", "")
    if wallpaper_set.add(title, url_str, thumb):
        xbmcgui.Dialog().notification("sKulls Wallpapers", f"Added to Set ({wallpaper_set.count()})", "DefaultAddonsInfo.png", 2000)
    else:
        xbmcgui.Dialog().notification("sKulls Wallpapers", "Already in Set", "DefaultAddonsInfo.png", 2000)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def remove_from_set(params):
    url_str = params.get("url", "")
    wallpaper_set.remove(url_str)
    xbmc.executebuiltin("Container.Refresh")


def clear_set(_params):
    wallpaper_set.clear()
    xbmcgui.Dialog().notification("sKulls Wallpapers", "Wallpaper Set cleared", "DefaultAddonsInfo.png", 2000)
    xbmc.executebuiltin("Container.Refresh")


def download_set(_params):
    items = wallpaper_set.load()
    if not items:
        xbmcgui.Dialog().notification("sKulls Wallpapers", "Set is empty", "DefaultAddonsInfo.png", 2000)
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    genre_names = genres.get_names()
    dest_dir = common.get_download_dir()
    if genre_names:
        options = ["Default folder"] + genre_names
        idx = xbmcgui.Dialog().select("Download set to genre", options)
        if idx > 0:
            dest_dir = genres.get_path(genre_names[idx - 1])
    dp = xbmcgui.DialogProgress()
    dp.create("sKulls Wallpapers", f"Downloading {len(items)} images...")
    downloaded = 0
    failed = 0
    for idx, it in enumerate(items):
        if dp.iscanceled():
            break
        dp.update(int((idx * 100) / len(items)), f"Downloading {idx+1}/{len(items)}")
        page_url = it.get("url", "")
        title = it.get("title", "wallpaper")
        if not page_url:
            failed += 1
            continue
        img_url = None
        try:
            sizes = wc.list_sizes(page_url)
            if sizes:
                def res_sort(s):
                    lbl = s.get("label", "0x0")
                    try:
                        w, h = lbl.split("x")
                        return int(w) * int(h)
                    except Exception:
                        return 0
                sizes_sorted = sorted(sizes, key=res_sort, reverse=True)
                img_url = sizes_sorted[0].get("url", "")
        except Exception as e:
            common.log(f"Get sizes failed: {e}")
        if not img_url:
            failed += 1
            continue
        try:
            base = common.sanitize_name(title)
            p = up.urlparse(img_url)
            ext = os.path.splitext(os.path.basename(p.path))[1].lower() or ".jpg"
            if ext not in (".jpg", ".jpeg", ".png"):
                ext = ".jpg"
            dest_path = os.path.join(dest_dir, f"{base}{ext}")
            i = 1
            while xbmcvfs.exists(dest_path):
                dest_path = os.path.join(dest_dir, f"{base}_{i}{ext}")
                i += 1
            req = urlreq.Request(img_url, headers={"User-Agent": "Mozilla/5.0", "Referer": page_url})
            with urlreq.urlopen(req, timeout=30) as r:
                total = int(r.headers.get("Content-Length", 0)) or 0
                f = xbmcvfs.File(dest_path, "w")
                try:
                    while True:
                        buf = r.read(1024 * 1024)
                        if not buf:
                            break
                        f.write(buf)
                finally:
                    f.close()
            downloaded += 1
        except Exception as e:
            common.log(f"Set download failed: {e}")
            failed += 1
    try:
        dp.close()
    except Exception:
        pass
    wallpaper_set.clear()
    xbmcgui.Dialog().notification("sKulls Wallpapers", f"Downloaded: {downloaded}, Failed: {failed}", "DefaultAddonsInfo.png", 4000)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def slideshow(params):
    mode = params.get("source", "favorites")
    common.log(f"Slideshow started, mode={mode}")
    image_urls = []
    slide_dir = xbmcvfs.translatePath(os.path.join(common.PROFILE_DIR, "slideshow"))
    try:
        if not xbmcvfs.exists(slide_dir):
            xbmcvfs.mkdirs(slide_dir)
    except Exception:
        pass
    dp = xbmcgui.DialogProgress()
    dp.create("Preparing slideshow...", "Loading images...")
    if mode == "favorites":
        favs = favorites.get_all()
        for idx, f in enumerate(favs):
            if dp.iscanceled():
                break
            dp.update(int((idx * 100) / len(favs)), f"Loading {idx+1}/{len(favs)}")
            page_url = f.get("url", "")
            fav_title = f.get("title", "")
            img_url = None
            if page_url and ("archive.org" in page_url or page_url.endswith((".jpg", ".jpeg", ".png", ".webp"))):
                img_url = page_url
            elif page_url:
                try:
                    sizes = wc.list_sizes(page_url)
                    if sizes:
                        def res_sort(s):
                            lbl = s.get("label", "0x0")
                            try:
                                w, h = lbl.split("x")
                                return int(w) * int(h)
                            except Exception:
                                return 0
                        sizes_sorted = sorted(sizes, key=res_sort, reverse=True)
                        img_url = sizes_sorted[0].get("url", "")
                except Exception as e:
                    common.log(f"Slideshow error for {fav_title}: {e}")
            if img_url:
                image_urls.append((fav_title, img_url))
    elif mode == "set":
        set_items = wallpaper_set.load()
        for idx, it in enumerate(set_items):
            if dp.iscanceled():
                break
            dp.update(int((idx * 100) / len(set_items)), f"Loading {idx+1}/{len(set_items)}")
            page_url = it.get("url", "")
            if page_url:
                try:
                    sizes = wc.list_sizes(page_url)
                    if sizes:
                        def res_sort(s):
                            lbl = s.get("label", "0x0")
                            try:
                                w, h = lbl.split("x")
                                return int(w) * int(h)
                            except Exception:
                                return 0
                        sizes_sorted = sorted(sizes, key=res_sort, reverse=True)
                        img_url = sizes_sorted[0].get("url", "")
                        if img_url:
                            image_urls.append((it.get("title", "img"), img_url))
                except Exception as e:
                    common.log(f"Slideshow set error: {e}")
    local_files = []
    dp.update(0, "Downloading images for slideshow...")
    for idx, (name, img_url) in enumerate(image_urls):
        if dp.iscanceled():
            break
        dp.update(int((idx * 100) / len(image_urls)), f"Downloading {idx+1}/{len(image_urls)}")
        try:
            ext = os.path.splitext(os.path.basename(up.urlparse(img_url).path))[1] or ".jpg"
            if ext not in (".jpg", ".jpeg", ".png"):
                ext = ".jpg"
            local_path = os.path.join(slide_dir, f"slide_{idx}{ext}")
            req = urlreq.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
            with urlreq.urlopen(req, timeout=15) as r:
                with xbmcvfs.File(local_path, "w") as f:
                    f.write(r.read())
            local_files.append(local_path)
        except Exception as e:
            common.log(f"Download slide error: {e}")
    try:
        dp.close()
    except Exception:
        pass
    if not local_files:
        xbmcgui.Dialog().notification("sKulls Wallpapers", "No images ready", "DefaultAddonsInfo.png", 2000)
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    if len(local_files) == 1:
        xbmc.executebuiltin(f'ShowPicture("{local_files[0]}")')
    else:
        xbmc.executebuiltin(f'ShowPicture("{local_files[0]}")')
        xbmc.sleep(1500)
        xbmc.executebuiltin(f'SlideShow({slide_dir})')
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def clear_cache(_params):
    cache.clear()
    try:
        xbmcgui.Dialog().notification("sKulls Wallpapers", "Cache cleared", "DefaultAddonsInfo.png", 2000)
    except Exception:
        pass
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


# Genre Manager UI
def manage_genres(_params):
    xbmcplugin.setContent(common.HANDLE, "files")
    genre_names = genres.get_names()
    li = xbmcgui.ListItem(label="[COLOR springgreen]+ Create New Genre[/COLOR]")
    li.setArt({"icon": common.media_icon("categories"), "thumb": common.media_icon("categories")})
    xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="create_genre"), li, isFolder=False)
    if not genre_names:
        li = xbmcgui.ListItem(label="No genres yet. Create one above!")
        xbmcplugin.addDirectoryItem(common.HANDLE, "", li, isFolder=False)
    else:
        for name in genre_names:
            li = xbmcgui.ListItem(label=name)
            li.setArt({"icon": common.media_icon("categories"), "thumb": common.media_icon("categories")})
            cm = [
                ("Rename", f'RunPlugin("{common.url(mode="rename_genre", genre=name)}")'),
                ("Delete", f'RunPlugin("{common.url(mode="delete_genre", genre=name)}")'),
            ]
            li.addContextMenuItems(cm, replaceItems=False)
            xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="browse_genre", genre=name), li, isFolder=True)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def create_genre(_params):
    name = xbmcgui.Dialog().input("Genre Name", type=xbmcgui.INPUT_ALPHANUM)
    if not name:
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    ok, msg = genres.create(name)
    if ok:
        xbmcgui.Dialog().notification("sKulls Wallpapers", f"Created: {name}", "DefaultAddonsInfo.png", 2000)
    else:
        xbmcgui.Dialog().notification("sKulls Wallpapers", f"Failed: {msg}", "DefaultAddonsInfo.png", 3000)
    xbmc.executebuiltin("Container.Refresh")


def rename_genre(params):
    old_name = params.get("genre", "")
    if not old_name:
        return
    new_name = xbmcgui.Dialog().input(f"Rename '{old_name}' to:", defaultt=old_name, type=xbmcgui.INPUT_ALPHANUM)
    if not new_name or new_name == old_name:
        return
    ok, msg = genres.rename(old_name, new_name)
    if ok:
        xbmcgui.Dialog().notification("sKulls Wallpapers", f"Renamed to: {new_name}", "DefaultAddonsInfo.png", 2000)
    else:
        xbmcgui.Dialog().notification("sKulls Wallpapers", f"Failed: {msg}", "DefaultAddonsInfo.png", 3000)
    xbmc.executebuiltin("Container.Refresh")


def delete_genre(params):
    name = params.get("genre", "")
    if not name:
        return
    if xbmcgui.Dialog().yesno("Delete Genre", f"Delete genre '{name}'?\n(Files will be kept in original location)"):
        ok, msg = genres.delete(name, delete_files=False)
        if ok:
            xbmcgui.Dialog().notification("sKulls Wallpapers", f"Deleted: {name}", "DefaultAddonsInfo.png", 2000)
        else:
            xbmcgui.Dialog().notification("sKulls Wallpapers", f"Failed: {msg}", "DefaultAddonsInfo.png", 3000)
        xbmc.executebuiltin("Container.Refresh")


def browse_genre(params):
    name = params.get("genre", "")
    if not name:
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    xbmcplugin.setContent(common.HANDLE, "images")
    contents = genres.list_contents(name)
    if not contents:
        li = xbmcgui.ListItem(label="Genre folder is empty")
        xbmcplugin.addDirectoryItem(common.HANDLE, "", li, isFolder=False)
    for item in contents:
        item_name = item["name"]
        item_path = item["path"]
        if item["is_dir"]:
            li = xbmcgui.ListItem(label=f"[{item_name}]")
            li.setArt({"icon": common.media_icon("mywallpaper"), "thumb": common.media_icon("mywallpaper")})
            xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="browse_genre", genre=name, subdir=item_name), li, isFolder=True)
        else:
            li = xbmcgui.ListItem(label=item_name)
            li.setArt({"thumb": item_path, "icon": item_path, "poster": item_path, "fanart": item_path})
            cm = [
                ("View", f'RunPlugin("{common.url(mode="view_file", fp=item_path)}")'),
                ("Delete", f'RunPlugin("{common.url(mode="delete_file", fp=item_path)}")'),
            ]
            li.addContextMenuItems(cm, replaceItems=False)
            xbmcplugin.addDirectoryItem(common.HANDLE, item_path, li, isFolder=False)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def set_download_path(_params):
    current = common.get("download_path", "special://profile/Wallpaper")
    resolved = xbmcvfs.translatePath(current)
    kb = xbmcgui.Dialog()
    new_path = kb.input("Enter download path", defaultt=resolved, type=xbmcgui.INPUT_ALPHANUM)
    if not new_path:
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    new_path = new_path.strip()
    if not new_path:
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    try:
        if not xbmcvfs.exists(new_path):
            xbmcvfs.mkdirs(new_path)
    except Exception:
        pass
    common.ADDON.setSetting("download_path", new_path)
    xbmcgui.Dialog().notification("sKulls Wallpapers", f"Download path set to:\n{new_path}", "DefaultAddonsInfo.png", 3000)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def browse_download_path(_params):
    try:
        new_path = xbmcgui.Dialog().browse(3, "Select download folder", "files")
    except TypeError:
        new_path = xbmcgui.Dialog().browse(0, "Select download folder", "files")
    if not new_path:
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    new_path = new_path.strip()
    try:
        if not xbmcvfs.exists(new_path):
            xbmcvfs.mkdirs(new_path)
    except Exception:
        pass
    common.ADDON.setSetting("download_path", new_path)
    xbmcgui.Dialog().notification("sKulls Wallpapers", f"Download path set to:\n{new_path}", "DefaultAddonsInfo.png", 3000)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
