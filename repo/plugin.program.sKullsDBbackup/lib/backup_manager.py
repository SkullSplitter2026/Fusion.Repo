"""Backup Manager - List, view, and delete backups"""
from __future__ import absolute_import, division, unicode_literals

import os
import xbmcvfs
import xbmcgui
import xbmcplugin

from .globals import G
from .loggers import Logger
from .utils import (
    get_backup_display_name, get_file_size_display,
    delete_file, show_notification, show_yesno_dialog
)


class BackupManager:
    @staticmethod
    def list_backups():
        """List all available backups"""
        backup_path = G.backup_path
        backups = []

        if not xbmcvfs.exists(backup_path):
            return backups

        dirs, files = xbmcvfs.listdir(backup_path)

        for filename in files:
            if filename.endswith('.zip'):
                filepath = os.path.join(backup_path, filename)
                try:
                    stat = xbmcvfs.Stat(filepath)
                    size = stat.st_size()
                    timestamp = stat.st_mtime()
                    backups.append({
                        'filename': filename,
                        'filepath': filepath,
                        'size': size,
                        'size_display': get_file_size_display(size),
                        'display_name': get_backup_display_name(filename),
                        'timestamp': timestamp
                    })
                except Exception as e:
                    Logger.warning('Fehler beim Lesen von {}: {}'.format(filename, str(e)))

        backups.sort(key=lambda x: x['timestamp'], reverse=True)
        return backups

    @staticmethod
    def show_backup_list(handle, fanart=None):
        """Show backup list in Kodi UI"""
        backups = BackupManager.list_backups()

        if not backups:
            xbmcgui.Dialog().ok(G.addon_config.addon_name, G.get_localized_string(32015))
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        for backup in backups:
            label = '[COLOR gold][B]{}[/B][/COLOR]'.format(backup['display_name'])
            list_item = xbmcgui.ListItem(label=label)
            list_item.setInfo('video', {
                'title': backup['display_name'],
                'size': backup['size'],
                'plot': 'Größe: {}'.format(backup['size_display'])
            })
            art = {
                'icon': 'DefaultFolder.png',
                'thumb': 'DefaultFolder.png'
            }
            if fanart:
                art['fanart'] = fanart
            list_item.setArt(art)

            context_menu = [
                (
                    G.get_localized_string(32002),
                    'RunPlugin({})'.format(
                        G.get_plugin_url({
                            'action': 'restore_backup',
                            'file': backup['filepath']
                        })
                    )
                ),
                (
                    G.get_localized_string(32017),
                    'RunPlugin({})'.format(
                        G.get_plugin_url({
                            'action': 'delete_backup',
                            'file': backup['filepath']
                        })
                    )
                ),
            ]
            list_item.addContextMenuItems(context_menu)

            url = G.get_plugin_url({
                'action': 'restore_backup',
                'file': backup['filepath']
            })

            xbmcplugin.addDirectoryItem(
                handle=handle,
                url=url,
                listitem=list_item,
                isFolder=False
            )

        xbmcplugin.setContent(handle, 'files')
        xbmcplugin.endOfDirectory(handle)
    @staticmethod
    def delete_backup(backup_file):
        """Delete a backup file"""
        try:
            if not xbmcvfs.exists(backup_file):
                show_notification(G.get_localized_string(32025), xbmcgui.NOTIFICATION_ERROR)
                return False

            filename = os.path.basename(backup_file)

            if show_yesno_dialog(
                G.get_localized_string(32017),
                G.get_localized_string(32034).format(filename)
            ):
                if delete_file(backup_file):
                    show_notification(G.get_localized_string(32035))
                    Logger.info('Backup gelöscht: {}'.format(filename))
                    return True

            return False

        except Exception as e:
            Logger.error('Fehler beim Löschen: {}'.format(str(e)))
            show_notification(G.get_localized_string(32036), xbmcgui.NOTIFICATION_ERROR)
            return False

    @staticmethod
    def cleanup_old_backups():
        """Delete old backups if max_backups is exceeded"""
        try:
            backups = BackupManager.list_backups()
            max_backups = G.max_backups

            if len(backups) > max_backups:
                to_delete = backups[max_backups:]
                for backup in to_delete:
                    delete_file(backup['filepath'])
                    Logger.info('Altes Backup gelöscht: {}'.format(backup['filename']))

                Logger.info('{} alte Backups gelöscht'.format(len(to_delete)))

        except Exception as e:
            Logger.error('Fehler beim Aufräumen: {}'.format(str(e)))