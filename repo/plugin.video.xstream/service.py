# -*- coding: utf-8 -*-
# Python 3

import os
import xbmc
import time
from concurrent.futures import ThreadPoolExecutor

from resources.lib.config import cConfig
from resources.lib import tools
from resources.lib.logger import logger
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.handler.pluginHandler import cPluginHandler
from resources.lib import updateManager
from resources.lib.utils import translatePath
from resources.lib.cache import cCache
from resources.lib.tools import infoDialog


# ResolverUrl Addon Data
RESOLVE_ADDON_DATA_PATH = translatePath(os.path.join('special://home/userdata/addon_data/script.module.resolveurl'))

# Pfad der update.sha
RESOLVE_SHA = os.path.join(translatePath(RESOLVE_ADDON_DATA_PATH), "update_sha")

# xStream Installationspfad
ADDON_PATH = translatePath(os.path.join('special://home/addons/', '%s'))

def delHtmlCache():
    # Cache nach X Tagen löschen (ohne Notification - läuft im Hintergrund beim Start)
    deltaDay = int(cConfig().getSetting('cacheDeltaDay', 1))
    if deltaDay == 0:  # 0 = aus
        return
    deltaTime = 60 * 60 * 24 * deltaDay
    currentTime = int(time.time())
    if currentTime >= int(cConfig().getSetting('lastdelhtml', 0)) + deltaTime:
        cRequestHandler('').clearCache(silent=True)  # ohne Notification (Auto-Cleanup)
        cConfig().setSetting('lastdelhtml', str(currentTime))


def _resolverUpdate():
    """Resolver Update im Hintergrund - gibt Status zurück für Notification."""
    try:
        if not os.path.isfile(RESOLVE_SHA) or cConfig().getSetting('githubUpdateResolver') == 'true':
            status = updateManager.resolverUpdate()
            return status
    except Exception:
        import traceback
        logger.error('Resolver update error: %s' % traceback.format_exc())
        return False
    return 'skipped'


def main():
    cCache().set(cConfig().getAddonInfo('id') + '_main', 'running')

    # Resolver Update und Domain Check parallel starten
    with ThreadPoolExecutor(max_workers=1) as executor:
        # Resolver läuft im Hintergrund
        resolver_future = executor.submit(_resolverUpdate)

        # Domain Check läuft gleichzeitig im Main Thread
        # show_notify=False: silent beim Auto-Check beim Kodi-Start (User hat nicht aktiv angefragt).
        # Manueller Button-Click in xstream.py behaelt den Notify (Default-Parameter).
        cPluginHandler().checkDomain(show_notify=False)

        # Warte auf Resolver (falls noch nicht fertig auf false setzen = fehler bei update meldung)
        try:
            resolver_status = resolver_future.result(timeout=13)
        except Exception:
            resolver_status = False

    # Wenn neue settings vorhanden oder geändert in addon_data dann starte Pluginhandler und aktualisiere die PluginDB um Daten von checkDomain mit aufzunehmen
    try:
        if cConfig().getSetting('newSetting') == 'true':
            cPluginHandler().getAvailablePlugins()
    except Exception:
        pass

    # getAvailablePlugins must be finished before the main menu can be started!
    cCache().set(cConfig().getAddonInfo('id') + '_main', 'finished')

    # Resolver Notification (nach Domain Check damit sich Notifications nicht überschneiden)
    # Nur anzeigen wenn ein Update Check tatsächlich stattfand (nicht 'skipped')
    # None ("kein Update verfuegbar") wird still abgehandelt, da uninteressant fuer User beim Auto-Check.
    # Bei manualResolverUpdate() bleibt der Notify fuer None erhalten (User hat aktiv geklickt).
    if resolver_status != 'skipped':
        if resolver_status == True: infoDialog(cConfig().getLocalizedString(30116), sound=False, icon='INFO', time=6000)
        if resolver_status == False: infoDialog(cConfig().getLocalizedString(30117), sound=True, icon='ERROR')

    # Html Cache beim KodiStart nach (X) Tage löschen
    delHtmlCache()

    # YouTube API Keys sicherstellen (Built-in Key für Video-Details/Alterscheck)
    ensure_youtube_api_keys()


def ensure_youtube_api_keys():
    """Write bundled YouTube API keys to api_keys.json if not already configured.
    Only writes if no user key exists — never overwrites an existing configured key."""
    import json, base64
    try:
        yt_keys_path = translatePath('special://home/userdata/addon_data/plugin.video.youtube/api_keys.json')

        # If file exists, check whether a user key is already present
        if os.path.exists(yt_keys_path):
            try:
                with open(yt_keys_path, 'r') as f:
                    existing = json.load(f)
                if existing.get('keys', {}).get('user', {}).get('api_key', ''):
                    return  # user key already configured — do not touch
            except Exception:
                pass  # unreadable — fall through and write fresh

        # Write bundled fallback keys to api_keys.json.
        # JSON structure is visible as-is; values prefixed 'b64:' are decoded before writing.
        _template = """{
    "keys": {
        "user": {
            "api_key":       "b64:QUl6YVN5RG5sSjBlX0NabExvWm03Q01Obk80MXhJblpnVkZ5T2Jv",
            "client_id":     "b64:ODY5OTIyMDgxNzY5LWQzOTJkdTN2dTZjOGNwbXRsbDExcnBkN2YwOWRldTFuLmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29t",
            "client_secret": "b64:R09DU1BYLVpPSWYwSnM3cUFCN3FsTWNvRkFDTlpqVWhfQ2o="
        },
        "developer": {}
    }
}"""

        def _resolve(obj):
            if isinstance(obj, dict):
                return {k: _resolve(v) for k, v in obj.items()}
            if isinstance(obj, str) and obj.startswith('b64:'):
                return base64.b64decode(obj[4:].encode()).decode()
            return obj

        yt_dir = os.path.dirname(yt_keys_path)
        if not os.path.exists(yt_dir):
            os.makedirs(yt_dir)

        with open(yt_keys_path, 'w') as f:
            json.dump(_resolve(json.loads(_template)), f, indent=4)
        logger.info('[service]: YouTube api_keys.json written')
    except Exception as e:
        logger.warning('[service]: Failed to write YouTube api_keys.json: %s' % str(e))

if __name__ == "__main__":
    main()
