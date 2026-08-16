# -*- coding: utf-8 -*-
""" Background service code """

from __future__ import absolute_import, division, unicode_literals

from urllib.parse import urlsplit, parse_qsl, urlencode
import xbmc
from xbmc import Monitor, Player, getInfoLabel
import xbmcaddon
from .loggers import Logger
from .utils import get_int_value, get_next_info_and_send_signal
from .globals import G
from .api import Api


class StalkerService:
    def __init__(self):
        self.addon = xbmcaddon.Addon()

    def run(self):
        Logger.info("Stalker Service started")

        # Warte kurz, bis Kodi stabil läuft (5 Sek)
        monitor = xbmc.Monitor()
        if monitor.waitForAbort(5):
            return

        # Portal Precheck beim Start ausführen
        self.perform_portal_precheck()

        # EPG Preload beim Start ausführen
        self.perform_preload()

        # Der Service muss am Leben bleiben, damit Kodi ihn nicht neu startet
        # oder wir nutzen ihn nur als "One-Shot" beim Start.
        # Hier halten wir ihn aktiv, falls wir später Interval-Updates wollen:
        while not monitor.waitForAbort(3600):  # Prüfe alle Stunde
            pass

    def _is_portal_reachable(self, portal_id: int) -> bool:
        """
        Schneller Reachability-Check:
        - G.init_globals(portal_id)
        - Token holen (Handshake)
        Markiert portal_error automatisch über Api.preload_epg_for_portal / Api._set_portal_error beim späteren Preload,
        aber hier können wir bereits aussortieren.
        """
        old_portal = G.active_portal
        try:
            G.init_globals(int(portal_id))
            # Token-Handshake (kurz & schmerzlos). Wenn das Portal hängt, fliegt hier eine Exception.
            from .auth import Auth
            Auth().get_token(refresh_token=False)

            try:
                Api._set_portal_error(int(portal_id), False)
            except Exception:
                pass

            return True
        except Exception as e:
            Logger.error(f"Portal {portal_id} unreachable (precheck): {str(e)}")
            # Portal markieren
            try:
                Api._set_portal_error(int(portal_id), True, reason=f"precheck: {str(e)}")
            except Exception:
                pass
            return False
        finally:
            try:
                G.init_globals(old_portal)
            except Exception:
                pass

    def perform_portal_precheck(self):
        """
        Wird bei JEDEM Kodi-Start ausgeführt.
        Prüft alle konfigurierten Portale auf Erreichbarkeit und setzt portal_error entsprechend.
        """
        try:
            # Portale aus JSON laden
            portals = G.get_available_portals()
            if not portals:
                Logger.info("Portal Precheck: no portals configured (JSON empty or URL not set)")
                return

            configured = [int(p.get('id', 0)) for p in portals if p.get('server_address')]
            if not configured:
                Logger.info("Portal Precheck: no portals with server_address configured")
                return

            working = []
            for pid in configured:
                if self._is_portal_reachable(pid):
                    working.append(pid)

            Logger.info(f"Portal Precheck: {len(working)}/{len(configured)} portals reachable: {working}")

        except Exception as e:
            Logger.error(f"Portal precheck failed: {str(e)}")

    def perform_preload(self):
        try:
            mode_raw = self.addon.getSetting('epg_preload_mode')
            if not mode_raw or mode_raw == '0':
                Logger.info("EPG Preload is disabled in settings")
                return

            if self.addon.getSetting('epg_enabled') != 'true':
                Logger.info("EPG is disabled globally (epg_enabled=false)")
                return

            mode = int(mode_raw)

            original_user_portal = G.active_portal
            Logger.info(f"Starting EPG Preload for all portals (Mode: {mode})")

            # 1) Portale aus JSON laden
            portals = G.get_available_portals()
            configured = [int(p.get('id', 0)) for p in portals if p.get('server_address')]

            if not configured:
                Logger.info("EPG Preload: no portals configured")
                return

            # 2) Vorab prüfen, welche Portale antworten
            working = []
            for pid in configured:
                if self._is_portal_reachable(pid):
                    working.append(pid)

            Logger.info(f"EPG Precheck: {len(working)}/{len(configured)} portals reachable: {working}")

            # 3) Preload nur für funktionierende Portale
            for pid in working:
                Logger.debug(f"Preloading EPG for Portal {pid}...")
                Api.preload_epg_for_portal(pid, mode)
                xbmc.Monitor().waitForAbort(2)

            G.init_globals(original_user_portal)

        except Exception as e:
            Logger.error(f"Service preload failed: {str(e)}")


class BackgroundService(Monitor):
    """ Background service code """

    def __init__(self):
        Monitor.__init__(self)
        self._player = PlayerMonitor()

    def run(self):
        Logger.debug('Service started - Waiting for network...')

        # Kurz warten, bis das Netzwerk sicher da ist
        if self.waitForAbort(5): return

        # EPG Preload für alle konfigurierten Portale
        addon = G._GlobalVariables__addon  # Zugriff auf das Addon-Objekt
        try:
            # Nur fortfahren wenn EPG generell aktiviert ist
            if addon.getSetting('epg_enabled') == 'true':
                # Holen als String und konvertieren zu Int
                mode = int(addon.getSetting('epg_preload_mode') or 0)

                # Wir merken uns, welches Portal der User eigentlich gerade nutzt (meistens 1 beim Start)
                original_user_portal = G.active_portal

                if mode > 0:
                    # Portale aus JSON laden
                    portals = G.get_available_portals()
                    configured = [int(p.get('id', 0)) for p in portals if p.get('server_address')]

                    for pid in configured:
                        if self.abortRequested(): break

                        Logger.debug(f"Preloading EPG for Portal {pid}...")
                        Api.preload_epg_for_portal(pid, mode)
                        # Kleine Pause zwischen den Portalen, um den Server nicht zu stressen
                        self.waitForAbort(2)
                        G.init_globals(original_user_portal)
        except Exception as e:
            Logger.error(f"Error during background preload: {str(e)}")

        while not self.abortRequested():
            # Stop when abort requested
            if self.waitForAbort(10):
                break

        Logger.debug('Service stopped')


class PlayerMonitor(Player):
    """ A custom Player object to check subtitles """

    def __init__(self):
        """ Initialises a custom Player object """
        self.__listen = False
        self.__av_started = False
        self.__path = None
        Player.__init__(self)

    def onPlayBackStarted(self):  # pylint: disable=invalid-name
        """ Will be called when Kodi player starts """
        self.__path = getInfoLabel('Player.FilenameAndPath')
        if not self.__path.startswith('plugin://plugin.video.svod/'):
            self.__listen = False
            return
        self.__listen = True
        self.__av_started = False
        Logger.debug('Stalker Player: [onPlayBackStarted] called')

    def onAVStarted(self):  # pylint: disable=invalid-name
        """ Will be called when Kodi has a video or audiostream """
        if not self.__listen:
            return
        Logger.debug('Stalker Player: [onAVStarted] called')
        self.__av_started = True
        params = dict(parse_qsl(urlsplit(self.__path).query))
        episode_no = get_int_value(params, 'series')
        total_episodes = get_int_value(params, 'total_episodes')
        if episode_no != 0 and episode_no < total_episodes:
            params.update({'series': episode_no + 1})
            next_episode_url = '{}?{}'.format('plugin://plugin.video.svod/', urlencode(params))
            get_next_info_and_send_signal(params, next_episode_url)

    def onPlayBackError(self):  # pylint: disable=invalid-name
        """ Will be called when playback stops due to an error. """
        if not self.__listen:
            return
        self.__av_started = False
        self.__listen = False
        Logger.debug('Stalker Player: [onPlayBackError] called')

    def onPlayBackEnded(self):  # pylint: disable=invalid-name
        """ Will be called when [Kodi] stops playing a file """
        if not self.__listen:
            return
        Logger.debug('Stalker Player: [onPlayBackEnded] called')
        self.__listen = False
        self.__av_started = False

    def onPlayBackStopped(self):  # pylint: disable=invalid-name
        """ Will be called when [user] stops Kodi playing a file """
        if not self.__listen:
            return
        self.__listen = False
        if not self.__av_started:
            params = dict(parse_qsl(urlsplit(self.__path).query))
            if 'cmd' in params and params.get('use_cmd', '0') == '0':
                Logger.debug('Stalker Player: [onPlayBackStopped] playback failed? retrying with cmd {}'.format(self.__path + "&use_cmd=1"))
                xbmc.executebuiltin("Dialog.Close(all, true)")
                func_str = f'PlayMedia({self.__path + "&use_cmd=1"})'
                xbmc.executebuiltin(func_str)
                return
        self.__av_started = False
        Logger.debug('Stalker Player: [onPlayBackStopped] called')


def run():
    """ Run the BackgroundService """
    BackgroundService().run()
