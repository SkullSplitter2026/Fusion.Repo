"""
Portal Loader - Loads portal configurations from a remote JSON file.

JSON format:
{
    "portals": [
        {
            "id": 1,
            "name": "My Portal",
            "server_address": "http://example.com/c/",
            "mac_address": "00:1A:79:XX:XX:XX",
            "serial_number": "12345678",
            "device_id": "...",
            "device_id_2": "...",
            "signature": "...",
            "alternative_context_path": false,
            "category_filter": ""
        }
    ]
}
"""
from __future__ import absolute_import, division, unicode_literals
import json
import os
import time
import xbmcvfs
import xbmcaddon
from .loggers import Logger

# Hardcoded fallback URL (used if settings URL is empty)
FALLBACK_PORTAL_URL = ""

# Cache settings
CACHE_FILE = "portals_cache.json"
CACHE_MAX_AGE = 3600  # 1 hour


class PortalLoader:
    """Loads portal configurations from remote JSON"""

    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.profile_path = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        self.cache_path = os.path.join(self.profile_path, CACHE_FILE)

    def get_portal_url(self):
        """Get the portal list URL from settings or fallback"""
        url = self.addon.getSetting('portal_list_url')
        if url and url.strip():
            return url.strip()
        return FALLBACK_PORTAL_URL

    def load_portals(self, force_refresh=False):
        """
        Load portals from remote JSON.
        Returns list of portal dicts, or empty list on error.
        """
        url = self.get_portal_url()
        if not url:
            Logger.error("No portal list URL configured")
            return []

        # Try to load from cache first (unless forced refresh)
        if not force_refresh:
            cached = self._load_cache()
            if cached is not None:
                Logger.debug(f"Loaded {len(cached)} portals from cache")
                return cached

        # Fetch from remote
        portals = self._fetch_portals(url)
        if portals:
            self._save_cache(portals)
            Logger.info(f"Loaded {len(portals)} portals from remote URL")
        else:
            # Fallback to cache even if stale
            cached = self._load_cache()
            if cached:
                Logger.warn("Remote fetch failed, using stale cache")
                return cached
            Logger.error("Failed to load portals from any source")

        return portals

    def _fetch_portals(self, url):
        """Fetch portal list from URL"""
        try:
            import requests
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                Logger.error(f"Portal URL returned status {response.status_code}")
                return []

            data = response.json()
            if not isinstance(data, dict) or 'portals' not in data:
                Logger.error("Invalid portal JSON format: missing 'portals' key")
                return []

            portals = data['portals']
            if not isinstance(portals, list):
                Logger.error("Invalid portal JSON: 'portals' is not a list")
                return []

            # Validate and normalize each portal
            valid_portals = []
            for i, portal in enumerate(portals):
                validated = self._validate_portal(portal, i + 1)
                if validated:
                    valid_portals.append(validated)

            return valid_portals

        except ImportError:
            Logger.error("requests module not available")
            return []
        except json.JSONDecodeError as e:
            Logger.error(f"Invalid JSON from portal URL: {str(e)}")
            return []
        except Exception as e:
            Logger.error(f"Failed to fetch portals: {str(e)}")
            return []

    def _validate_portal(self, portal, index):
        """Validate and normalize a single portal entry"""
        if not isinstance(portal, dict):
            return None

        # server_address is required
        server = str(portal.get('server_address', '')).strip()
        if not server:
            Logger.debug(f"Portal {index}: no server_address, skipping")
            return None

        # Ensure server ends with /c/ or /c
        if not server.endswith('/c/') and not server.endswith('/c'):
            if not server.endswith('/'):
                server += '/'
            server += 'c/'

        return {
            'id': int(portal.get('id', index)),
            'name': str(portal.get('name', f'Portal {index}')),
            'server_address': server,
            'mac_address': str(portal.get('mac_address', '')),
            'serial_number': str(portal.get('serial_number', '')),
            'device_id': str(portal.get('device_id', '')),
            'device_id_2': str(portal.get('device_id_2', '')),
            'signature': str(portal.get('signature', '')),
            'alternative_context_path': bool(portal.get('alternative_context_path', False)),
            'category_filter': str(portal.get('category_filter', '')),
        }

    def _load_cache(self):
        """Load cached portal data if valid"""
        try:
            if not os.path.exists(self.cache_path):
                return None

            # Check cache age
            file_age = time.time() - os.path.getmtime(self.cache_path)
            if file_age > CACHE_MAX_AGE:
                return None

            with open(self.cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, list) and len(data) > 0:
                return data
            return None

        except Exception as e:
            Logger.debug(f"Cache load failed: {str(e)}")
            return None

    def _save_cache(self, portals):
        """Save portal data to cache"""
        try:
            if not os.path.exists(self.profile_path):
                os.makedirs(self.profile_path)

            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(portals, f, indent=2, ensure_ascii=False)

        except Exception as e:
            Logger.debug(f"Cache save failed: {str(e)}")

    def clear_cache(self):
        """Clear the portal cache"""
        try:
            if os.path.exists(self.cache_path):
                os.remove(self.cache_path)
        except Exception:
            pass
