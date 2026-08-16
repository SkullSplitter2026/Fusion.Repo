"""Global variables and configuration for sKulls DB Backup"""
from __future__ import absolute_import, division, unicode_literals

import os
import dataclasses
import xbmcaddon
import xbmcvfs

from .loggers import Logger


@dataclasses.dataclass
class AddOnConfig:
    addon_id: str = 'plugin.program.sKullsDBbackup'
    addon_name: str = 'sKulls DB Backup'
    addon_version: str = ''
    addon_path: str = None
    addon_data_path: str = None
    kodi_profile_path: str = None


class GlobalVariables:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.addon_config = AddOnConfig()
        self.__addon = xbmcaddon.Addon(self.addon_config.addon_id)
        self.addon_config.addon_version = self.__addon.getAddonInfo('version')
        self.addon_config.addon_path = self.__addon.getAddonInfo('path')
        self.addon_config.addon_data_path = xbmcvfs.translatePath(
            self.__addon.getAddonInfo('profile')
        )
        self.addon_config.kodi_profile_path = xbmcvfs.translatePath('special://profile')

    def get_setting(self, setting_id):
        return self.__addon.getSetting(setting_id)

    def set_setting(self, setting_id, value):
        self.__addon.setSetting(setting_id, str(value))

    def get_localized_string(self, string_id):
        return self.__addon.getLocalizedString(string_id)

    def get_plugin_url(self, params):
        param_string = '&'.join(['{}={}'.format(k, v) for k, v in params.items()])
        return 'plugin://{}?{}'.format(self.addon_config.addon_id, param_string)

    @property
    def backup_path(self):
        path = self.get_setting('backup_path')
        if not path:
            path = os.path.join(self.addon_config.addon_data_path, 'backups')
        if not xbmcvfs.exists(path):
            xbmcvfs.mkdir(path)
        return path

    @property
    def max_backups(self):
        try:
            return int(self.get_setting('max_backups'))
        except (ValueError, TypeError):
            return 10

    @property
    def auto_backup_enabled(self):
        return self.get_setting('auto_backup_enabled') == 'true'

    @property
    def auto_backup_interval(self):
        try:
            return int(self.get_setting('auto_backup_interval'))
        except (ValueError, TypeError):
            return 24


G = GlobalVariables()