"""
Stalker API Calls
"""
from __future__ import absolute_import, division, unicode_literals
import datetime
import json
import math
import time
import traceback
import requests
import xbmcaddon
from .globals import G
from .auth import Auth
from .loggers import Logger
from .utils import get_int_value


class Api:
    """API calls"""

    @staticmethod
    def __call_stalker_portal(params, return_response_body=True):
        """Method to call portal"""
        response = Api.__call_stalker_portal_return_response(params)
        if return_response_body:
            try:
                return response.json()
            except Exception as e:
                Logger.error("Failed to decode JSON response: {}".format(str(e)))
                return {}
        return None

    @staticmethod
    def __call_stalker_portal_return_response(params):
        """Method to call portal"""
        retries = 0
        url = G.portal_config.portal_url
        mac_cookie = G.portal_config.mac_cookie
        referrer = G.portal_config.server_address
        # Sicherstellen, dass der Referrer auf /c/ endet, wenn es ein EPG Call ist
        if params.get('action') in ['get_short_epg', 'get_simple_data_table', 'get_epg_info']:
            if not referrer.endswith('/'):
                referrer += '/'

        auth = Auth()
        while True:
            token = auth.get_token(retries > 0)
            Logger.debug("Calling Stalker portal {} with params {}".format(url, json.dumps(params)))

            headers = {
                'Cookie': mac_cookie,
                'SN': G.portal_config.serial_number,
                'Authorization': 'Bearer ' + token,
                'Accept': '*/*',
                'X-User-Agent': 'Model: MAG250; Link: WiFi',
                'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3',
                'Referer': referrer
            }

            response = requests.get(url=url,
                                    headers=headers,
                                    params=params,
                                    timeout=30
                                    )
            if response.text.find('Authorization failed') == -1 or retries == G.addon_config.max_retries:
                break
            if retries > 1:
                auth.clear_cache()
            retries += 1
        return response

    @staticmethod
    def get_vod_categories():
        """Get video categories mit Cache pro Portal"""
        p_id = G.active_portal
        if p_id in G.cache_vod_categories:
            return G.cache_vod_categories[p_id]

        params = {'type': 'vod', 'action': 'get_categories'}
        response = Api.__call_stalker_portal(params)
        js = response.get('js', []) if isinstance(response, dict) else []
        G.cache_vod_categories[p_id] = js if isinstance(js, list) else []
        return G.cache_vod_categories[p_id]

    @staticmethod
    def get_series_categories():
        """Get series categories mit Cache pro Portal"""
        p_id = G.active_portal
        if p_id in G.cache_series_categories:
            return G.cache_series_categories[p_id]

        params = {'type': 'series', 'action': 'get_categories'}
        response = Api.__call_stalker_portal(params)
        js = response.get('js', []) if isinstance(response, dict) else []
        G.cache_series_categories[p_id] = js if isinstance(js, list) else []
        return G.cache_series_categories[p_id]

    @staticmethod
    def get_tv_genres():
        """Get tv genres mit Cache pro Portal"""
        p_id = G.active_portal
        if p_id in G.cache_tv_genres:
            return G.cache_tv_genres[p_id]

        params = {'type': 'itv', 'action': 'get_genres'}
        response = Api.__call_stalker_portal(params)
        js = response.get('js', []) if isinstance(response, dict) else []
        G.cache_tv_genres[p_id] = js if isinstance(js, list) else []
        return G.cache_tv_genres[p_id]

    @staticmethod
    def get_short_epg(channel_id):
        """Get short EPG with multi-portal caching and expiration check"""
        p_id = G.active_portal
        ch_id_str = str(channel_id)

        if p_id not in G.cache_short_epg:
            G.cache_short_epg[p_id] = {}

        # Cache-Check: Falls vorhanden und jünger als 15 Minuten (900 Sek)
        if ch_id_str in G.cache_short_epg[p_id]:
            cache_entry = G.cache_short_epg[p_id][ch_id_str]
            if isinstance(cache_entry, dict) and (time.time() - cache_entry.get('timestamp', 0)) < 900:
                return cache_entry.get('data', [])

        params = {'type': 'itv', 'action': 'get_short_epg', 'ch_id': channel_id}
        response = Api.__call_stalker_portal(params)

        result = []
        if response and isinstance(response, dict) and 'js' in response:
            result = response['js'] if isinstance(response['js'], list) else []

        # Speichere Daten zusammen mit aktuellem Zeitstempel
        G.cache_short_epg[p_id][ch_id_str] = {
            'data': result,
            'timestamp': time.time()
        }
        return result

    @staticmethod
    def get_epg_batch(channel_ids):
        """EPG für mehrere Kanäle gleichzeitig laden und portal-spezifisch cachen"""

        if xbmcaddon.Addon().getSetting('epg_enabled') != 'true':
            return

        p_id = G.active_portal
        now_ts = time.time()

        if p_id not in G.cache_short_epg:
            G.cache_short_epg[p_id] = {}

        # Nur IDs anfragen, die fehlen ODER älter als 15 Min sind
        missing_ids = []
        for cid in channel_ids:
            cid_str = str(cid)
            is_old = False
            if cid_str in G.cache_short_epg[p_id]:
                cache_entry = G.cache_short_epg[p_id][cid_str]
                if not isinstance(cache_entry, dict) or (now_ts - cache_entry.get('timestamp', 0)) > 900:
                    is_old = True

            if cid_str not in G.cache_short_epg[p_id] or is_old:
                missing_ids.append(cid_str)

        if missing_ids:
            now_date = datetime.datetime.now().strftime('%Y-%m-%d')
            params = {
                'type': 'itv',
                'action': 'get_epg_info',
                'ch_id': ','.join(missing_ids),
                'date': now_date
            }
            response = Api.__call_stalker_portal(params)

            if response and isinstance(response, dict) and 'js' in response:
                js = response.get('js')

                epg_dict = {}
                if isinstance(js, dict):
                    epg_dict = js.get('data', {})
                    # Manche Portale liefern in "data" keine dict-Struktur -> absichern
                    if not isinstance(epg_dict, dict):
                        epg_dict = {}
                else:
                    epg_dict = {}

                for ch_id in missing_ids:
                    # Daten dauerhaft im Speicher dieses Portals ablegen
                    data = epg_dict.get(ch_id, [])
                    # Als Dictionary mit Zeitstempel cachen
                    G.cache_short_epg[p_id][ch_id] = {
                        'data': data if isinstance(data, list) else [],
                        'timestamp': now_ts
                    }

    @staticmethod
    def get_epg_for_channel(channel_id):
        """Get full EPG with multi-portal caching and flexible response parsing"""
        p_id = G.active_portal
        ch_id_str = str(channel_id)

        if p_id not in G.cache_epg:
            G.cache_epg[p_id] = {}

        # WICHTIG: Prüfe ZUERST den vollständigen Cache
        if ch_id_str in G.cache_epg[p_id]:
            return G.cache_epg[p_id][ch_id_str]

        # Falls nicht im vollständigen Cache, prüfe SHORT EPG Cache
        if p_id in G.cache_short_epg and ch_id_str in G.cache_short_epg[p_id]:
            cached_short = G.cache_short_epg[p_id][ch_id_str]
            if isinstance(cached_short, dict) and 'data' in cached_short:
                data = cached_short['data']
                G.cache_epg[p_id][ch_id_str] = data
                return data

        now_date = datetime.datetime.now().strftime('%Y-%m-%d')
        data = []

        # Methode 1: get_epg_info (Dictionary-Struktur)
        params = {
            'type': 'itv',
            'action': 'get_epg_info',
            'ch_id': channel_id,
            'date': now_date
        }
        response = Api.__call_stalker_portal(params)

        if response and isinstance(response, dict) and 'js' in response:
            js_data = response['js']
            if isinstance(js_data, dict):
                epg_dict = js_data.get('data', {})
                if ch_id_str in epg_dict:
                    data = epg_dict[ch_id_str]
                elif ch_id_str in js_data:
                    data = js_data[ch_id_str]
            elif isinstance(js_data, list):
                data = js_data

        # Methode 2: Fallback auf get_simple_data_table
        if not data:
            params['action'] = 'get_simple_data_table'
            response = Api.__call_stalker_portal(params)
            if response and isinstance(response, dict) and 'js' in response:
                js_data = response['js']
                if isinstance(js_data, dict):
                    data = js_data.get('data', [])
                elif isinstance(js_data, list):
                    data = js_data

        # Methode 3: Fallback auf Short EPG (ABER von CACHE, nicht neuer Request!)
        if not data:
            if p_id in G.cache_short_epg and ch_id_str in G.cache_short_epg[p_id]:
                cached_short = G.cache_short_epg[p_id][ch_id_str]
                if isinstance(cached_short, dict) and 'data' in cached_short:
                    data = cached_short['data']
            else:
                # Nur wenn auch das nicht da ist, dann einen neuen Request machen
                data = Api.get_short_epg(channel_id)

        G.cache_epg[p_id][ch_id_str] = data
        return data

    @staticmethod
    def _set_portal_error(portal_id: int, is_error: bool, reason: str = ""):
        """Persistenter Status für Portal (für rote Markierung im Startmenü)."""
        try:
            addon = xbmcaddon.Addon()
            suffix = '' if int(portal_id) == 1 else f'_{int(portal_id)}'
            addon.setSetting(f'portal_error{suffix}', 'true' if is_error else 'false')
            if is_error and reason:
                Logger.error(f"Portal {portal_id} marked as error: {reason}")
        except Exception as e:
            Logger.debug(f"Could not set portal_error for portal {portal_id}: {str(e)}")

    @staticmethod
    def preload_epg_for_portal(portal_id, mode):
        """Hintergrund-Preload ohne die globalen Einstellungen permanent zu verbiegen"""
        old_portal_id = G.active_portal
        try:
            if mode == 0:
                return

            # Initialisiere das Zielportal (lädt URL, MAC, Token)
            G.init_globals(portal_id)

            ch_ids = []

            if mode == 1:
                fav_data = Api.get_tv_favorites(1)
                if fav_data and 'data' in fav_data:
                    ch_ids = [str(ch['id']) for ch in fav_data['data']]
            elif mode == 2:
                genres = Api.get_tv_genres()
                if isinstance(genres, list) and len(genres) > 0:
                    for genre in genres[:5]:
                        if isinstance(genre, dict) and 'id' in genre:
                            genre_data = Api.get_tv_channels(genre['id'], 1, "", 0)
                            if genre_data and 'data' in genre_data:
                                ch_ids.extend([str(ch['id']) for ch in genre_data['data'] if 'id' in ch])

            if not ch_ids:
                Logger.info(f"Preload: No channels found for Portal {portal_id}")
                Api._set_portal_error(int(portal_id), False)
                return

            now_date = datetime.datetime.now().strftime('%Y-%m-%d')

            for i in range(0, len(ch_ids), 50):
                batch = ch_ids[i:i + 50]
                params = {'type': 'itv', 'action': 'get_epg_info', 'ch_id': ','.join(batch), 'date': now_date}
                response = Api.__call_stalker_portal(params)

                if response and isinstance(response, dict) and 'js' in response:
                    js_data = response['js']
                    epg_dict = {}
                    if isinstance(js_data, dict):
                        epg_dict = js_data.get('data', {})
                        if not isinstance(epg_dict, dict):
                            epg_dict = js_data

                    if portal_id not in G.cache_epg:
                        G.cache_epg[portal_id] = {}
                    if portal_id not in G.cache_short_epg:
                        G.cache_short_epg[portal_id] = {}

                    for ch_id in batch:
                        ch_id_str = str(ch_id)
                        if ch_id_str in epg_dict:
                            data = epg_dict[ch_id_str]
                            if isinstance(data, list):
                                G.cache_epg[portal_id][ch_id_str] = data
                                G.cache_short_epg[portal_id][ch_id_str] = {
                                    'data': data,
                                    'timestamp': time.time()
                                }
                            else:
                                G.cache_short_epg[portal_id][ch_id_str] = {'data': [], 'timestamp': time.time()}

            Logger.info(f"Preload finished for Portal {portal_id} ({len(ch_ids)} channels).")

            # Erfolg => Portal wieder "ok"
            Api._set_portal_error(int(portal_id), False)

        except Exception as e:
            Logger.error(f"Preload failed for portal {portal_id}: {str(e)}")
            Logger.error(traceback.format_exc())

            # Fehler => Portal rot markieren
            Api._set_portal_error(int(portal_id), True, reason=str(e))

        finally:
            try:
                G.init_globals(old_portal_id)
            except Exception:
                pass


    @staticmethod
    def remove_favorites(video_id, _type):
        """Remove from favorites"""
        if _type == 'itv':
            Api.__remove_tv_favorites(video_id)
        else:
            params = {'type': _type, 'action': 'del_fav', 'video_id': video_id}
            Api.__call_stalker_portal(params, False)

    @staticmethod
    def add_favorites(video_id, _type):
        """Add to favorites"""
        if _type == 'itv':
            Api.__add_tv_favorites(video_id)
        else:
            params = {'type': _type, 'action': 'set_fav', 'video_id': video_id}
            Api.__call_stalker_portal(params, False)

    @staticmethod
    def __add_tv_favorites(video_id):
        """Add to tv favorites"""
        params = {'type': 'itv', 'action': 'get_all_fav_channels'}
        response = Api.__call_stalker_portal(params)
        js = response.get('js', {}) if isinstance(response, dict) else {}
        fav_channels = js.get('data', []) if isinstance(js, dict) else []
        if not isinstance(fav_channels, list):
            fav_channels = []
        fav_ch = [video_id]
        for fav_channel in fav_channels:
            fav_ch.append(fav_channel['id'])
        params = {'type': 'itv', 'action': 'set_fav', 'fav_ch': ','.join(fav_ch)}
        Api.__call_stalker_portal(params, False)

    @staticmethod
    def __remove_tv_favorites(video_id):
        """Add to tv favorites"""
        params = {'type': 'itv', 'action': 'get_all_fav_channels'}
        response = Api.__call_stalker_portal(params)
        js = response.get('js', {}) if isinstance(response, dict) else {}
        fav_channels = js.get('data', []) if isinstance(js, dict) else []
        if not isinstance(fav_channels, list):
            fav_channels = []
        fav_ch = []
        for fav_channel in fav_channels:
            if video_id != fav_channel['id']:
                fav_ch.append(fav_channel['id'])
        params = {'type': 'itv', 'action': 'set_fav', 'fav_ch': ','.join(fav_ch)}
        Api.__call_stalker_portal(params, False)

    @staticmethod
    def get_vod_favorites(page):
        """Get favorites"""
        params = {'type': 'vod', 'action': 'get_ordered_list', 'fav': '1', 'sortby': 'added'}
        return Api.get_listing(params, page)

    @staticmethod
    def get_series_favorites(page):
        """Get favorites"""
        params = {'type': 'series', 'action': 'get_ordered_list', 'fav': '1', 'sortby': 'added'}
        return Api.get_listing(params, page)

    @staticmethod
    def get_tv_favorites(page):
        """Get favorites"""
        params = {'type': 'itv', 'action': 'get_ordered_list', 'fav': '1', 'sortby': 'number'}
        return Api.get_listing(params, page)

    @staticmethod
    def get_seasons(video_id):
        """Get seasons for a series"""
        params = {'type': 'series', 'action': 'get_ordered_list', 'movie_id': video_id, 'sortby': 'added'}
        response = Api.__call_stalker_portal(params)
        if response and 'js' in response:
            return response['js']
        return {'data': []}  # Fallback, falls keine Staffeln gefunden werden

    @staticmethod
    def get_tv_channels(category_id, page, search_term, fav):
        """Get videos for a category"""
        params = {'type': 'itv', 'action': 'get_ordered_list', 'genre': category_id, 'sortby': 'number', 'fav': fav}
        if bool(search_term.strip()):
            params.update({'search': search_term})
        return Api.get_listing(params, page)

    @staticmethod
    def get_videos(category_id, page, search_term, fav):
        """Get videos for a category"""
        params = {'type': 'vod', 'action': 'get_ordered_list', 'category': category_id, 'sortby': 'added', 'fav': fav}
        if bool(search_term.strip()):
            params.update({'search': search_term})
        return Api.get_listing(params, page)

    @staticmethod
    def get_series(category_id, page, search_term, fav):
        """Get videos for a category"""
        params = {'type': 'series', 'action': 'get_ordered_list', 'category': category_id, 'sortby': 'added', 'fav': fav}
        if bool(search_term.strip()):
            params.update({'search': search_term})
        return Api.get_listing(params, page)

    @staticmethod
    def get_listing(params, page):
        """Generic method to get listing"""
        try:
            params.update({'p': str(page)})
            raw_resp = Api.__call_stalker_portal(params)

            if not isinstance(raw_resp, dict) or 'js' not in raw_resp:
                return {'max_page_items': 999, 'total_items': 0, 'data': []}

            response = raw_resp['js']
            if not isinstance(response, dict):
                return {'max_page_items': 999, 'total_items': 0, 'data': []}

            videos = response.get('data', [])
            if not isinstance(videos, list): videos = []

            total_items = int(response.get('total_items', 0))
            max_page_items = int(response.get('max_page_items', 999))
            if max_page_items <= 0: max_page_items = 999

            total_pages = int(math.ceil(float(total_items) / float(max_page_items)))

            # Sicherheits-Check für max_page_limit (Service Kontext)
            limit = 2  # Standard-Fallback für Service
            try:
                limit = G.addon_config.max_page_limit
            except:
                pass

            for page_no in range(int(page) + 1, min(int(page) + limit, total_pages + 1)):
                params.update({'p': str(page_no)})
                p_resp = Api.__call_stalker_portal(params)
                if isinstance(p_resp, dict) and 'js' in p_resp:
                    p_data = p_resp['js'].get('data', [])
                    if isinstance(p_data, list):
                        videos += p_data

            return {'max_page_items': max_page_items, 'total_items': total_items, 'data': videos}
        except Exception as e:
            Logger.error(f"Get_listing failed: {str(e)}")
            return {'max_page_items': 999, 'total_items': 0, 'data': []}

    @staticmethod
    def get_vod_stream_url(video_id, series, cmd, use_cmd):
        """Get VOD stream url"""
        if use_cmd == '0':
            response = Api.__get_vod_stream_url_video_id(video_id, series)
            if response.status_code != 200:
                stream_url = Api.__get_vod_stream_url_cmd(cmd, series)
            else:
                stream_url = response.json()['js']['cmd']
        else:
            stream_url = Api.__get_vod_stream_url_cmd(cmd, series)
        if stream_url.find(' ') != -1:
            stream_url = stream_url[(stream_url.find(' ') + 1):]
        return stream_url

    @staticmethod
    def __get_vod_stream_url_cmd(cmd, series):
        """Get VOD stream url"""
        return Api.__call_stalker_portal({'type': 'vod', 'action': 'create_link', 'cmd': cmd, 'series': str(series)})['js']['cmd']

    @staticmethod
    def __get_vod_stream_url_video_id(video_id, series):
        """Get VOD stream url"""
        return Api.__call_stalker_portal_return_response({'type': 'vod', 'action': 'create_link', 'cmd': '/media/' + video_id + '.mpg', 'series': str(series)}
                                                         )

    @staticmethod
    def get_tv_stream_url(params):
        """Get TV Channel stream url"""
        if bool(get_int_value(params, 'use_http_tmp_link')) or bool(get_int_value(params, 'use_load_balancing')):
            cmd = Api.__call_stalker_portal(
                {'type': 'itv', 'action': 'create_link', 'cmd': params['cmd']}
            )['js']['cmd']
        else:
            cmd = params['cmd']
        if cmd.find(' ') != -1:
            cmd = cmd[(cmd.find(' ') + 1):]
        return cmd
