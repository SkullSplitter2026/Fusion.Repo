"""Module to initializes global setting for the plugin"""

from __future__ import absolute_import, division, unicode_literals
import os
import sys
from urllib.parse import urlencode, urlsplit
import dataclasses
import xbmcaddon
import xbmcvfs
from .loggers import Logger


@dataclasses.dataclass
class PortalConfig:
    """Portal config"""
    mac_cookie: str = None
    portal_url: str = None
    category_filter: str = None
    device_id: str = None
    device_id_2: str = None
    signature: str = None
    serial_number: str = None
    portal_base_url: str = None
    server_address: str = None
    alternative_context_path: bool = False


@dataclasses.dataclass
class AddOnConfig:
    """Addon config"""
    url: str = None
    addon_id: str = None
    name: str = None
    handle: str = None
    addon_data_path: str = None
    max_page_limit: int = 2
    max_retries: int = 3
    token_path: str = None


class GlobalVariables:
    """Class initializes global settings used by the plugin"""

    def __init__(self):
        """Init class"""
        self.__addon = xbmcaddon.Addon()
        self.__is_addd_on_first_run = None
        self.addon_config = AddOnConfig()
        self.portal_config = PortalConfig()
        self.active_portal = 1
        self._loaded_portal_id = None  # Tracking für den Cache
        self._portals_cache = None  # Cached portal list from JSON
        # Inhalts-Cache
        self.cache_vod_categories = {}
        self.cache_series_categories = {}
        self.cache_tv_genres = {}
        self.cache_epg = {}  # {portal_id: {channel_id: data}}
        self.cache_short_epg = {}  # {portal_id: {channel_id: data}}

    def _get_portal_loader(self):
        """Lazy import of PortalLoader to avoid circular imports"""
        from .portal_loader import PortalLoader
        return PortalLoader()

    def _load_portals_from_json(self):
        """Load portals from JSON URL and cache the result"""
        if self._portals_cache is not None:
            return self._portals_cache

        loader = self._get_portal_loader()
        self._portals_cache = loader.load_portals()
        return self._portals_cache

    def _get_portal_by_id(self, portal_id):
        """Get a specific portal config from JSON by ID"""
        portals = self._load_portals_from_json()
        portal_id = int(portal_id)
        for p in portals:
            if int(p.get('id', 0)) == portal_id:
                return p
        return None

    def get_available_portals(self):
        """Get list of all configured portals"""
        return self._load_portals_from_json()

    def init_globals(self, portal_id=1):
        """Init global settings mit JSON-basierten Portals"""
        portal_id = int(portal_id)

        # Wenn das Portal bereits geladen ist, überspringen wir das erneute Einlesen
        if self._loaded_portal_id == portal_id:
            return

        # Wenn wir hier ankommen, findet ein Portalwechsel statt!

        self.active_portal = portal_id

        # Sicherer Zugriff auf sys.argv
        self.addon_config.url = sys.argv[0] if len(sys.argv) > 0 else ""

        Logger.debug("Switching to Portal {}. Loading settings...".format(self.active_portal))

        # Initialize addon info (nur beim ersten Mal)
        if self._loaded_portal_id is None:
            self.addon_config.addon_id = self.__addon.getAddonInfo('id')
            self.addon_config.name = self.__addon.getAddonInfo('name')
            self.addon_config.addon_data_path = self.__addon.getAddonInfo('path')
            token_path = xbmcvfs.translatePath(self.__addon.getAddonInfo('profile'))
            if not xbmcvfs.exists(token_path):
                xbmcvfs.mkdirs(token_path)
            self.addon_config.token_path = token_path

            # Handle nur setzen, wenn wir im UI-Modus sind (argv vorhanden)
            if len(sys.argv) > 1:
                self.addon_config.handle = int(sys.argv[1])
            else:
                self.addon_config.handle = -1  # -1 signalisiert: Kein UI-Handle vorhanden

        # Portal aus JSON laden
        portal_data = self._get_portal_by_id(portal_id)

        if portal_data:
            # Portal aus JSON-Datei
            server_address = portal_data.get('server_address', '')
            mac_address = portal_data.get('mac_address', '')
            self.portal_config.mac_cookie = 'mac=' + mac_address if mac_address else ''
            self.portal_config.category_filter = portal_data.get('category_filter', '')
            self.portal_config.device_id = portal_data.get('device_id', '')
            self.portal_config.device_id_2 = portal_data.get('device_id_2', '')
            self.portal_config.signature = portal_data.get('signature', '')
            self.portal_config.serial_number = portal_data.get('serial_number', '')
            self.portal_config.alternative_context_path = portal_data.get('alternative_context_path', False)
            self.portal_config.server_address = server_address

            if server_address:
                self.portal_config.portal_base_url = self.__get_portal_base_url()
                self.portal_config.portal_url = self.get_portal_url()
        else:
            Logger.error(f"Portal {portal_id} not found in JSON configuration")
            # Leere Portal-Konfiguration
            self.portal_config.mac_cookie = ''
            self.portal_config.category_filter = ''
            self.portal_config.device_id = ''
            self.portal_config.device_id_2 = ''
            self.portal_config.signature = ''
            self.portal_config.serial_number = ''
            self.portal_config.alternative_context_path = False
            self.portal_config.server_address = ''
            self.portal_config.portal_base_url = ''
            self.portal_config.portal_url = ''

        # WICHTIG: Nur beim tatsächlichen WECHSEL den Token-Cache leeren
        from .auth import Auth
        Auth().clear_cache()

        # Jetzt markieren wir dieses Portal als geladen
        self._loaded_portal_id = portal_id

    def get_handle(self):
        """Get addon handle"""
        return self.addon_config.handle

    def get_custom_thumb_path(self, thumb_file_name):
        """Get thumb file path"""
        return os.path.join(self.addon_config.addon_data_path, 'resources', 'media', thumb_file_name)

    def get_plugin_url(self, params):
        """Get plugin url"""
        return '{}?{}'.format(self.addon_config.url, urlencode(params))

    def __get_portal_base_url(self):
        """Get portal base url"""
        split_url = urlsplit(self.portal_config.server_address)
        return split_url.scheme + '://' + split_url.netloc

    def get_portal_url(self):
        """Get portal url"""
        context_path = '/portal.php' if self.portal_config.alternative_context_path else '/server/load.php'
        portal_url = self.portal_config.portal_base_url + '/stalker_portal' + context_path
        if self.portal_config.server_address.endswith('/c/'):
            portal_url = self.portal_config.server_address.replace('/c/', '') + context_path
        elif self.portal_config.server_address.endswith('/c'):
            portal_url = self.portal_config.server_address.replace('/c', '') + context_path
        return portal_url

    def reload_portals(self):
        """Force reload portals from JSON (clears cache)"""
        self._portals_cache = None
        self._loaded_portal_id = None
        loader = self._get_portal_loader()
        loader.clear_cache()
        Logger.debug("Portal cache cleared, reloading...")


G = GlobalVariables()
