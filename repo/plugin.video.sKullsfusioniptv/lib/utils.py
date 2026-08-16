"""Utility classes and methods"""
from __future__ import absolute_import, division, unicode_literals
import json
import os
import zipfile
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
from .globals import G
from .loggers import Logger

__addon__ = xbmcaddon.Addon()


def backup_settings():
    """Sichert den Profil-Ordner in eine ZIP-Datei"""
    profile_path = xbmcvfs.translatePath(__addon__.getAddonInfo('profile'))
    dest_path = xbmcgui.Dialog().browse(3, __addon__.getLocalizedString(32401), 'files', '', False, False, '')

    if not dest_path:
        return

    backup_zip = os.path.join(dest_path, 'sKullsfusioniptv_backup.zip')

    try:
        with zipfile.ZipFile(backup_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(profile_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, profile_path)

                    # Die Backup-Datei selbst ignorieren, falls im gleichen Ordner
                    if 'sKullsfusioniptv_backup.zip' in full_path:
                        continue

                    try:
                        zf.write(full_path, rel_path)
                    except Exception:
                        continue

        xbmcgui.Dialog().ok(G.addon_config.name, "Backup erfolgreich erstellt.")
    except Exception as e:
        xbmcgui.Dialog().error(G.addon_config.name, "Backup fehlgeschlagen: " + str(e))

        # Busy Dialog explizit schließen, falls er noch da ist
    xbmc.executebuiltin('Dialog.Close(busydialog)')


def restore_settings():
    """Stellt die Einstellungen aus einer ZIP-Datei wieder her"""
    zip_file = xbmcgui.Dialog().browse(1, __addon__.getLocalizedString(32403), 'files', '.zip')

    if not zip_file:
        return

    if xbmcgui.Dialog().yesno(G.addon_config.name, "Einstellungen überschreiben?"):
        profile_path = xbmcvfs.translatePath(__addon__.getAddonInfo('profile'))

        try:
            # Kodi-VFS (nfs://, smb://, ...) kann zipfile nicht direkt öffnen -> erst lokal kopieren
            local_zip = zip_file
            if "://" in zip_file and not zip_file.startswith(("special://", "file://")):
                import time
                tmp_name = f"restore_tmp_{int(time.time())}.zip"
                local_zip = os.path.join(profile_path, tmp_name)

                src = xbmcvfs.File(zip_file, "rb")
                try:
                    dst = xbmcvfs.File(local_zip, "wb")
                    try:
                        while True:
                            chunk = src.readBytes(1024 * 1024)  # 1 MiB
                            if not chunk:
                                break
                            dst.write(chunk)
                    finally:
                        dst.close()
                finally:
                    src.close()

            with zipfile.ZipFile(local_zip, 'r') as zf:
                zf.extractall(profile_path)

            xbmcgui.Dialog().ok(G.addon_config.name, "Restore erfolgreich.")
            xbmc.executebuiltin('UnloadAddon(plugin.video.svod)')
            xbmc.executebuiltin('RunAddon(plugin.video.svod)')

        except Exception as e:
            xbmcgui.Dialog().ok(G.addon_config.name, "Restore fehlgeschlagen: " + str(e))

def ask_for_input(category):
    """Input dialog box"""
    return xbmcgui.Dialog().input(
        defaultt='',
        heading='Search in ' + category,
        type=xbmcgui.INPUT_ALPHANUM) or None


def ask_for_category_selection(categories, heading):
    """Category selection dialog box"""
    if not categories:
        return None

    category_titles = [category['title'] for category in categories]
    dialog = xbmcgui.Dialog()
    selected_index = dialog.select(heading, category_titles)

    if selected_index >= 0:
        return categories[selected_index]
    return None


def get_int_value(dictionary, key):
    """Helper method to get int value"""
    if key in dictionary:
        val = str(dictionary[key])
        if val.isnumeric():
            return int(val)
    return 0


def get_next_info_and_send_signal(params, next_episode_url):
    """Send a signal to Kodi using JSON RPC"""
    next_info = get_next_info(params, next_episode_url)
    upnext_signal(next_info)


def upnext_signal(next_info):
    """Send a signal to Kodi using JSON RPC"""
    from base64 import b64encode
    from json import dumps
    data = [to_unicode(b64encode(dumps(next_info).encode()))]
    notify(sender='plugin.video.stalkervod.SIGNAL', message='upnext_data', data=data)


def notify(sender, message, data):
    """Send a notification to Kodi using JSON RPC"""
    result = jsonrpc(method='JSONRPC.NotifyAll', params=dict(
        sender=sender,
        message=message,
        data=data,
    ))
    if result.get('result') != 'OK':
        Logger.warn('Failed to send notification: ' + result.get('error').get('message'))
        return False
    Logger.debug('Notification sent to upnext')
    return True


def jsonrpc(**kwargs):
    """Perform JSONRPC calls"""
    from json import dumps, loads
    if kwargs.get('id') is None:
        kwargs.update(id=0)
    if kwargs.get('jsonrpc') is None:
        kwargs.update(jsonrpc='2.0')
    return loads(xbmc.executeJSONRPC(dumps(kwargs)))


def to_unicode(text, encoding='utf-8', errors='strict'):
    """Force text to Unicode"""
    if isinstance(text, bytes):
        return text.decode(encoding, errors=errors)
    return text


def get_next_info(params, next_episode_url):
    """Send a signal to Kodi using JSON RPC"""
    return dict(
        current_episode=dict(
            episodeid=params['video_id'] + str(get_int_value(params, 'series') - 1),
            tvshowid=params['video_id'],
            title=params['title'],
            art={
                'thumb': '',
                'tvshow.clearart': params.get('poster_url', ''),
                'tvshow.clearlogo': params.get('poster_url', ''),
                'tvshow.fanart': params.get('poster_url', ''),
                'tvshow.landscape': params.get('poster_url', ''),
                'tvshow.poster': params.get('poster_url', ''),
            },
            season=params['season_no'],
            episode=get_int_value(params, 'series') - 1,
            showtitle=params['title'],
            plot='',
            playcount=0,
            rating=None,
            firstaired=''
        ),
        next_episode=dict(
            episodeid=params['video_id'] + str(get_int_value(params, 'series')),
            tvshowid=params['video_id'],
            title=params['title'],
            art={
                'thumb': '',
                'tvshow.clearart': params.get('poster_url', ''),
                'tvshow.clearlogo': params.get('poster_url', ''),
                'tvshow.fanart': params.get('poster_url', ''),
                'tvshow.landscape': params.get('poster_url', ''),
                'tvshow.poster': params.get('poster_url', ''),
            },
            season=params['season_no'],
            episode=get_int_value(params, 'series'),
            showtitle=params['title'],
            plot='',
            playcount=0,
            rating=None,
            firstaired=''
        ),
        play_url=next_episode_url
    )
