# -*- coding: utf-8 -*-
"""Custom wallpaper sources management."""
import json
import os
import re
import urllib.parse as up
import urllib.request as urlreq
import xbmcgui
import xbmcplugin
from . import common


def load():
    data = common.get("custom_sources", "")
    if not data:
        return []
    try:
        sources = json.loads(data)
        return sources if isinstance(sources, list) else []
    except Exception:
        return []


def save(sources):
    try:
        common.ADDON.setSetting("custom_sources", json.dumps(sources))
    except Exception as e:
        common.log(f"Failed to save custom sources: {e}")


def add(params):
    kb = xbmcgui.Dialog()
    name = kb.input("Custom Source Name", type=xbmcgui.INPUT_ALPHANUM)
    if not name:
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    url_str = kb.input("Wallpaper Folder URL", type=xbmcgui.INPUT_ALPHANUM)
    if not url_str:
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    if not url_str.startswith("http"):
        url_str = "https://" + url_str
    sources = load()
    sources.append({"name": name, "url": url_str})
    save(sources)
    xbmcgui.Dialog().notification("sKulls Wallpapers", f"Added: {name}", common.media_icon("favorites"), 2000)
    xbmc.executebuiltin("Container.Refresh")


def manage(params):
    common.log("manage_custom_sources called")
    sources = load()
    common.log(f"Loaded sources: {sources}")
    if not sources:
        xbmcgui.Dialog().notification("sKulls Wallpapers", "No custom sources", common.media_icon("favorites"), 2000)
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    xbmcplugin.setContent(common.HANDLE, "files")
    li = xbmcgui.ListItem(label="Manage Custom Sources")
    li.setArt({"icon": common.media_icon("categories"), "thumb": common.media_icon("categories")})
    xbmcplugin.addDirectoryItem(common.HANDLE, "", li, isFolder=False)
    for i, src in enumerate(sources):
        name = src.get("name", "Unknown")
        url_str = src.get("url", "")
        common.log(f"Source {i}: {name} - {url_str}")
        li = xbmcgui.ListItem(label=name)
        li.setArt({"icon": common.media_icon("archive"), "thumb": common.media_icon("archive")})
        cm = [("Delete", f'RunPlugin("{common.url(mode="delete_custom_source", index=str(i))}")')]
        li.addContextMenuItems(cm, replaceItems=False)
        xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="browse_custom_source", url=url_str, name=name), li, isFolder=True)
    li = xbmcgui.ListItem(label="[COLOR deepskyblue]+ Add New Source[/COLOR]")
    li.setArt({"icon": common.media_icon("search"), "thumb": common.media_icon("search")})
    xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="add_custom_source"), li, isFolder=False)
    common.log("Calling endOfDirectory")
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=True)


def delete(params):
    try:
        idx = int(params.get("index", "-1"))
    except Exception:
        idx = -1
    sources = load()
    if 0 <= idx < len(sources):
        name = sources[idx].get("name", "Unknown")
        del sources[idx]
        save(sources)
        xbmcgui.Dialog().notification("sKulls Wallpapers", f"Deleted: {name}", common.media_icon("favorites"), 2000)
    xbmc.executebuiltin("Container.Refresh")


def browse(params):
    url_str = params.get("url", "")
    name = params.get("name", "Custom Source")
    if not url_str:
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    xbmcplugin.setContent(common.HANDLE, "images")
    common.log(f"Browsing custom source: {name} - {url_str}")
    found = set()
    try:
        req = urlreq.Request(url_str, headers={"User-Agent": "Mozilla/5.0"})
        with urlreq.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            common.log(f"Fetched {len(html)} bytes")
    except Exception as e:
        common.log(f"Failed to fetch: {e}")
        xbmcgui.Dialog().notification("sKulls Wallpapers", "Cannot load URL", common.media_icon("favorites"), 3000)
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    common.log(f"HTML sample: {html[:500]}")
    if "archive.org" in url_str:
        common.log("Processing archive.org URL...")
        base = url_str.rstrip("/")
        for m in re.finditer(r'href="([^"#]+)"', html):
            link = m.group(1)
            if link.startswith("#") or link.startswith("?") or link == "../":
                continue
            if any(link.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
                if link.startswith("http"):
                    found.add(link)
                elif link.startswith("/"):
                    found.add("https://archive.org" + link)
                else:
                    found.add(base + "/" + link.lstrip("/"))
        if not found:
            common.log("No images found, looking for subfolders...")
            for m in re.finditer(r'href="([^"/]+/)"', html):
                folder = m.group(1)
                if folder and folder not in ["../"]:
                    folder_url = base + "/" + folder
                    li = xbmcgui.ListItem(label=f"[COLOR cyan]{folder}[/COLOR]")
                    li.setArt({"icon": common.media_icon("archive"), "thumb": common.media_icon("archive")})
                    xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="browse_custom_source", url=folder_url, name=name + "/" + folder), li, isFolder=True)
            if found:
                common.log(f"Archive.org: found {len(found)} images directly")
            else:
                xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
                return
    else:
        patterns = [
            r'src="([^"]+\.(?:jpg|jpeg|png|gif|webp))"',
            r'src=\'([^\']+\.(?:jpg|jpeg|png|gif|webp))\'',
            r'href="([^"]+\.(?:jpg|jpeg|png))"',
            r'data-src="([^"]+\.(?:jpg|jpeg|png|gif|webp))"',
        ]
        for pat in patterns:
            for m in re.finditer(pat, html, re.I):
                img_url = m.group(1)
                if img_url.startswith("//"):
                    img_url = "https:" + img_url
                elif img_url.startswith("/"):
                    parsed = up.urlparse(url_str)
                    img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"
                if "://" in img_url and img_url not in found:
                    found.add(img_url)
        common.log(f"Regular site: found {len(found)} images")
    common.log(f"Found {len(found)} images")
    if not found:
        li = xbmcgui.ListItem(label="[Open in browser]")
        li.setArt({"icon": common.media_icon("archive"), "thumb": common.media_icon("archive")})
        xbmcplugin.addDirectoryItem(common.HANDLE, url_str, li, isFolder=False)
    else:
        for img_url in list(found)[:50]:
            fname = img_url.split("/")[-1][:50] or "image"
            li = xbmcgui.ListItem(label=fname)
            li.setArt({"thumb": img_url, "icon": img_url})
            xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="custom_wallpaper", img=img_url, title=fname), li, isFolder=True)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
