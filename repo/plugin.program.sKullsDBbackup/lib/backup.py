"""Backup and restore functionality"""
from __future__ import absolute_import, division, unicode_literals

import os
import zipfile
import xbmcvfs
import xbmcgui
import xbmc

from .globals import G
from .database import KodiDatabase
from .loggers import Logger
from .utils import (
    get_timestamp, get_file_size_display,
    copy_file, delete_file, create_directory, show_notification, show_yesno_dialog
)


class Backup:
    @staticmethod
    def create_backup(name=None):
        """Create a backup of all Kodi databases and settings"""
        try:
            backup_path = G.backup_path
            create_directory(backup_path)

            if not name:
                name = 'backup_{}'.format(get_timestamp())

            zip_path = os.path.join(backup_path, '{}.zip'.format(name))

            if xbmcvfs.exists(zip_path):
                show_notification(G.get_localized_string(32018), xbmcgui.NOTIFICATION_WARNING)
                return False

            files_to_backup = KodiDatabase.get_all_backup_files()
            total_files = len(files_to_backup)

            if total_files == 0:
                show_notification(G.get_localized_string(32024), xbmcgui.NOTIFICATION_WARNING)
                return False

            progress = xbmcgui.DialogProgress()
            progress.create(G.addon_config.addon_name, G.get_localized_string(32022))

            temp_dir = xbmcvfs.translatePath('special://temp/skulls_backup/')
            create_directory(temp_dir)

            try:
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for i, file_info in enumerate(files_to_backup):
                        if progress.iscanceled():
                            progress.close()
                            zipf.close()
                            delete_file(zip_path)
                            show_notification(G.get_localized_string(32021), xbmcgui.NOTIFICATION_WARNING)
                            return False

                        progress.update(
                            int((i / total_files) * 100),
                            G.get_localized_string(32023).format(file_info['name'])
                        )

                        filepath = file_info['path']
                        if xbmcvfs.exists(filepath):
                            try:
                                temp_path = os.path.join(
                                    temp_dir, os.path.basename(filepath)
                                )
                                if copy_file(filepath, temp_path):
                                    zipf.write(temp_path, os.path.basename(filepath))
                                    delete_file(temp_path)
                            except Exception as e:
                                Logger.warning('Fehler beim Sichern von {}: {}'.format(
                                    file_info['name'], str(e)
                                ))
            finally:
                progress.close()

            file_size = xbmcvfs.Stat(zip_path).st_size()
            size_display = get_file_size_display(file_size)

            show_notification(G.get_localized_string(32019).format(size_display))
            Logger.info('Backup erstellt: {} ({})'.format(zip_path, size_display))
            return True

        except Exception as e:
            Logger.error('Backup fehlgeschlagen: {}'.format(str(e)))
            show_notification(G.get_localized_string(32020), xbmcgui.NOTIFICATION_ERROR)
            return False

    @staticmethod
    def restore_backup(backup_file):
        """Restore a backup from a zip file"""
        try:
            if not xbmcvfs.exists(backup_file):
                show_notification(G.get_localized_string(32025), xbmcgui.NOTIFICATION_ERROR)
                return False

            if not show_yesno_dialog(
                G.get_localized_string(32002),
                G.get_localized_string(32032),
                G.get_localized_string(32033)
            ):
                return False

            progress = xbmcgui.DialogProgress()
            progress.create(G.addon_config.addon_name, G.get_localized_string(32026))

            temp_dir = xbmcvfs.translatePath('special://temp/skulls_restore/')
            create_directory(temp_dir)

            with zipfile.ZipFile(backup_file, 'r') as zipf:
                zipf.extractall(temp_dir)

            db_dir = KodiDatabase.get_database_path()
            profile_dir = G.addon_config.kodi_profile_path
            restored = 0

            for filename in os.listdir(temp_dir):
                src = os.path.join(temp_dir, filename)

                if filename.endswith('.db'):
                    dst = os.path.join(db_dir, filename)
                else:
                    dst = os.path.join(profile_dir, filename)

                if xbmcvfs.exists(src):
                    if copy_file(src, dst):
                        restored += 1
                        Logger.info('Wiederhergestellt: {}'.format(filename))

                delete_file(src)

            progress.close()

            show_notification(G.get_localized_string(32027).format(restored))
            Logger.info('Backup wiederhergestellt: {} Dateien'.format(restored))

            if show_yesno_dialog(
                G.get_localized_string(32029),
                G.get_localized_string(32030),
                G.get_localized_string(32031)
            ):
                xbmc.executebuiltin('RestartApp')

            return True

        except Exception as e:
            Logger.error('Wiederherstellung fehlgeschlagen: {}'.format(str(e)))
            show_notification(G.get_localized_string(32028), xbmcgui.NOTIFICATION_ERROR)
            return False