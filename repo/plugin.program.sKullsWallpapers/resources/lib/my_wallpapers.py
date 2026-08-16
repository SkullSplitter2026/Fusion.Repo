# -*- coding: utf-8 -*-
"""My Wallpapers: browse, view, delete, import, move to genre."""
import os
import xbmcgui
import xbmcplugin
import xbmcvfs
from . import common
from . import genres


def show(params):
    cur = params.get("dir") or common.get_download_dir()
    cur = xbmcvfs.translatePath(cur)
    xbmcplugin.setContent(common.HANDLE, "images")
    imp1 = xbmcgui.ListItem(label="[Import single image...]")
    xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="import_image"), imp1, isFolder=False)
    imp2 = xbmcgui.ListItem(label="[Import multiple images...]")
    xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="import_folder"), imp2, isFolder=False)
    dl = common.get_download_dir().rstrip("/\\")
    if os.path.normpath(cur) != os.path.normpath(dl):
        par = os.path.dirname(cur.rstrip("/\\")) or cur
        pli = xbmcgui.ListItem(label="Parent folder")
        xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="my_wallpapers", dir=par), pli, isFolder=True)
    try:
        dirs, files = xbmcvfs.listdir(cur)
    except Exception:
        dirs, files = [], []
    for d in dirs:
        p = os.path.join(cur, d)
        li = xbmcgui.ListItem(label=f"[{d}]")
        li.setArt({"icon": common.media_icon("mywallpaper"), "thumb": common.media_icon("mywallpaper")})
        xbmcplugin.addDirectoryItem(common.HANDLE, common.url(mode="my_wallpapers", dir=p), li, isFolder=True)
    for f in files:
        if not f.lower().endswith(common.IMG_EXTS):
            continue
        p = os.path.join(cur, f)
        li = xbmcgui.ListItem(label=f)
        li.setArt({"thumb": p, "icon": p, "poster": p, "fanart": p})
        url = common.url(mode="open_context", fp=p)
        cmi = [
            ("View", f'RunPlugin("{common.url(mode="view_file", fp=p)}")'),
            ("Delete", f'RunPlugin("{common.url(mode="delete_file", fp=p)}")'),
            ("Move to Genre...", f'RunPlugin("{common.url(mode="move_to_genre", fp=p)}")'),
        ]
        li.addContextMenuItems(cmi, replaceItems=False)
        li.setProperty("IsPlayable", "false")
        xbmcplugin.addDirectoryItem(common.HANDLE, url, li, isFolder=False)
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def open_context(params):
    xbmc.executebuiltin("Action(ContextMenu)")
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def view_file(params):
    fp = params.get("fp", "")
    if fp:
        xbmc.executebuiltin(f'ShowPicture("{fp}")')
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def delete_file(params):
    fp = params.get("fp", "")
    if not fp or not xbmcvfs.exists(fp):
        xbmcgui.Dialog().notification("sKulls Wallpapers", "File not found", "DefaultAddonsInfo.png", 2500)
    else:
        if xbmcgui.Dialog().yesno("Delete", f"Delete this file?\n{os.path.basename(fp)}"):
            ok = False
            try:
                ok = xbmcvfs.delete(fp)
            except Exception as e:
                common.log(f"delete failed: {e}")
            if ok:
                xbmcgui.Dialog().notification("sKulls Wallpapers", "Deleted", "DefaultAddonsInfo.png", 2000)
            else:
                xbmcgui.Dialog().notification("sKulls Wallpapers", "Delete failed", "DefaultAddonsInfo.png", 2500)
        xbmc.executebuiltin("Container.Refresh")
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def move_to_genre(params):
    fp = params.get("fp", "")
    if not fp or not xbmcvfs.exists(fp):
        xbmcgui.Dialog().notification("sKulls Wallpapers", "File not found", "DefaultAddonsInfo.png", 2500)
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    genre_names = genres.get_names()
    if not genre_names:
        if xbmcgui.Dialog().yesno("No Genres", "No genres exist yet. Create one now?"):
            name = xbmcgui.Dialog().input("Genre Name", type=xbmcgui.INPUT_ALPHANUM)
            if name:
                ok, msg = genres.create(name)
                if ok:
                    genre_names = genres.get_names()
                    xbmcgui.Dialog().notification("sKulls Wallpapers", f"Created: {name}", "DefaultAddonsInfo.png", 2000)
                else:
                    xbmcgui.Dialog().notification("sKulls Wallpapers", f"Failed: {msg}", "DefaultAddonsInfo.png", 3000)
            xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
            return
    genre_names = genres.get_names()
    options = genre_names + ["[Create new genre]"]
    idx = xbmcgui.Dialog().select("Move to genre", options)
    if idx < 0:
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    if idx >= len(genre_names):
        new_name = xbmcgui.Dialog().input("New Genre Name", type=xbmcgui.INPUT_ALPHANUM)
        if not new_name:
            xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
            return
        ok, msg = genres.create(new_name)
        if not ok:
            xbmcgui.Dialog().notification("sKulls Wallpapers", f"Failed: {msg}", "DefaultAddonsInfo.png", 3000)
            xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
            return
        target_genre = new_name
    else:
        target_genre = genre_names[idx]
    success, msg = genres.move_file(fp, target_genre)
    if success:
        try:
            xbmcvfs.delete(fp)
        except Exception:
            pass
        xbmcgui.Dialog().notification("sKulls Wallpapers", f"Moved to {target_genre}", "DefaultAddonsInfo.png", 2000)
    else:
        xbmcgui.Dialog().notification("sKulls Wallpapers", f"Move failed: {msg}", "DefaultAddonsInfo.png", 3000)
    xbmc.executebuiltin("Container.Refresh")
    xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)


def import_image(_params):
    try:
        src = xbmcgui.Dialog().browse(2, "Select image", "files", ".jpg|.jpeg|.png|.webp")
    except TypeError:
        src = xbmcgui.Dialog().browse(1, "Select image", "files")
    if not src:
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    if not xbmcvfs.exists(src):
        xbmcgui.Dialog().notification("sKulls Wallpapers", "Source not found", "DefaultAddonsInfo.png", 2500)
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    if not src.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        xbmcgui.Dialog().notification("sKulls Wallpapers", "Not an image file", "DefaultAddonsInfo.png", 2500)
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    genre_names = genres.get_names()
    dest_dir = common.get_download_dir()
    if genre_names:
        options = ["Default folder"] + genre_names
        idx = xbmcgui.Dialog().select("Save to", options)
        if idx > 0:
            dest_dir = genres.get_path(genre_names[idx - 1])
    base = common.sanitize_name(os.path.splitext(os.path.basename(src))[0])
    ext = os.path.splitext(src)[1].lower() or ".jpg"
    i = 0
    while True:
        name = f"{base}{'' if i == 0 else f'_{i}'}{ext}"
        dest = os.path.join(dest_dir, name)
        if not xbmcvfs.exists(dest):
            break
        i += 1
    ok = False
    try:
        ok = xbmcvfs.copy(src, dest)
    except Exception as e:
        common.log(f"copy failed: {e}")
    if ok:
        xbmcgui.Dialog().notification("sKulls Wallpapers", "Imported", "DefaultAddonsInfo.png", 2000)
    else:
        xbmcgui.Dialog().notification("sKulls Wallpapers", "Import failed", "DefaultAddonsInfo.png", 2500)
    xbmc.executebuiltin(f'Container.Update("{common.url(mode="my_wallpapers", dir=dest_dir)}", replace)')


def import_folder(_params):
    try:
        src_dir = xbmcgui.Dialog().browse(3, "Select folder", "files")
    except TypeError:
        src_dir = xbmcgui.Dialog().browse(0, "Select folder", "files")
    if not src_dir:
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    if not xbmcvfs.exists(src_dir):
        xbmcgui.Dialog().notification("sKulls Wallpapers", "Folder not found", "DefaultAddonsInfo.png", 2500)
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    dest_dir = common.get_download_dir()
    genre_names = genres.get_names()
    if genre_names:
        options = ["Default folder"] + genre_names
        idx = xbmcgui.Dialog().select("Save to", options)
        if idx > 0:
            dest_dir = genres.get_path(genre_names[idx - 1])
    try:
        dirs, files = xbmcvfs.listdir(src_dir)
    except Exception:
        dirs, files = [], []
    images = [f for f in files if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    if not images:
        xbmcgui.Dialog().notification("sKulls Wallpapers", "No images in folder", "DefaultAddonsInfo.png", 2500)
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
        return
    dp = xbmcgui.DialogProgress()
    dp.create("Importing", f"{len(images)} image(s)...")
    copied, failed = 0, 0
    for idx, fname in enumerate(images, 1):
        if dp.iscanceled():
            break
        dp.update(int((idx * 100) / len(images)), f"{fname}")
        src = os.path.join(src_dir, fname)
        base = common.sanitize_name(os.path.splitext(fname)[0])
        ext = os.path.splitext(fname)[1].lower()
        j = 0
        while True:
            name = f"{base}{'' if j == 0 else f'_{j}'}{ext}"
            dest = os.path.join(dest_dir, name)
            if not xbmcvfs.exists(dest):
                break
            j += 1
        try:
            if xbmcvfs.copy(src, dest):
                copied += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    try:
        dp.close()
    except Exception:
        pass
    xbmcgui.Dialog().notification("sKulls Wallpapers", f"Imported: {copied}, Failed: {failed}", "DefaultAddonsInfo.png", 3500)
    xbmc.executebuiltin(f'Container.Update("{common.url(mode="my_wallpapers", dir=dest_dir)}", replace)')
