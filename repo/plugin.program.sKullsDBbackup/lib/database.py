"""Kodi database path detection and management"""
from __future__ import absolute_import, division, unicode_literals

import os
import glob
import xbmcvfs

from .globals import G


class KodiDatabase:
    KODI_DB_FILES = {
        'addons27': 'addons27.db',
        'Textures13': 'Textures13.db',
        'Epg11': 'Epg11.db',
    }

    SETTINGS_FILES = [
        'guisettings.xml',
        'advancedsettings.xml',
        'sources.xml',
        'sources.xml.backup',
    ]

    @staticmethod
    def get_database_path():
        return os.path.join(G.addon_config.kodi_profile_path, 'Database')

    @staticmethod
    def get_addon_db_files():
        db_dir = KodiDatabase.get_database_path()
        db_files = []
        for name, filename in KodiDatabase.KODI_DB_FILES.items():
            path = os.path.join(db_dir, filename)
            if xbmcvfs.exists(path):
                db_files.append({'name': name, 'filename': filename, 'path': path})
        return db_files

    @staticmethod
    def get_video_db_files():
        db_dir = KodiDatabase.get_database_path()
        db_files = []
        pattern = os.path.join(db_dir, 'MyVideos*.db')
        for path in glob.glob(pattern):
            filename = os.path.basename(path)
            db_files.append({'name': 'MyVideos', 'filename': filename, 'path': path})
        return db_files

    @staticmethod
    def get_music_db_files():
        db_dir = KodiDatabase.get_database_path()
        db_files = []
        pattern = os.path.join(db_dir, 'MyMusic*.db')
        for path in glob.glob(pattern):
            filename = os.path.basename(path)
            db_files.append({'name': 'MyMusic', 'filename': filename, 'path': path})
        return db_files

    @staticmethod
    def get_all_db_files():
        all_files = []
        all_files.extend(KodiDatabase.get_addon_db_files())
        all_files.extend(KodiDatabase.get_video_db_files())
        all_files.extend(KodiDatabase.get_music_db_files())
        return all_files

    @staticmethod
    def get_settings_files():
        settings_files = []
        for filename in KodiDatabase.SETTINGS_FILES:
            path = os.path.join(G.addon_config.kodi_profile_path, filename)
            if xbmcvfs.exists(path):
                settings_files.append({'name': filename, 'filename': filename, 'path': path})
        return settings_files

    @staticmethod
    def get_all_backup_files():
        files = []
        files.extend(KodiDatabase.get_all_db_files())
        files.extend(KodiDatabase.get_settings_files())
        return files