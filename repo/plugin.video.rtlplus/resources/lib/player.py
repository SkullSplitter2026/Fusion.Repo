import sys
import urllib.parse
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from .api import BedrockAPI
from .auth import USER_AGENT
from .evil import drm as _drm

DRM_LICENSE_URL = 'https://lic.drmtoday.com/license-proxy-widevine/cenc/'

def _log(msg):
    xbmc.log(f'[RTL+ Player] {msg}', xbmc.LOGDEBUG)

def _q(value):
    return urllib.parse.quote(str(value).encode('utf8'))

def _auto_max_resolution():

    wv_max_h = 1080
    wv_max_w = 1920

    try:
        scr_w = int(xbmc.getInfoLabel('System.ScreenWidth') or 0)
        scr_h = int(xbmc.getInfoLabel('System.ScreenHeight') or 0)
        if scr_w > 0 and scr_h > 0:
            _log(f'_auto_max_resolution: Bildschirm {scr_w}x{scr_h}')
            cap_h = min(wv_max_h, scr_h)
            cap_w = min(wv_max_w, scr_w)
            return cap_h, cap_w
    except Exception as e:
        _log(f'_auto_max_resolution: Bildschirmauflösung nicht lesbar ({e})')

    return wv_max_h, wv_max_w


def _software_decode_cap():
    try:
        is_windows = xbmc.getCondVisibility('System.Platform.Windows')
        if is_windows and not _drm.is_wv_secure():
            _log('Windows + Widevine L3 (Software-Decoder): Qualität auf 360p begrenzt')
            return 360, 640
    except Exception as e:
        _log(f'_software_decode_cap: Prüfung fehlgeschlagen ({e})')
    return None, None


class RTLPlayer:
    def __init__(self, handle):
        self.handle = handle
        self.api = BedrockAPI()
        self._addon = xbmcaddon.Addon()

    def _no_assets_error(self, reason=None):
        if reason == 'not_found':
            xbmcgui.Dialog().ok(
                'RTL+',
                'Dieser Inhalt ist auf RTL+ nicht verfügbar.\n\n'
                'Der JustWatch-Eintrag ist möglicherweise veraltet '
                'oder der Inhalt wurde entfernt.'
            )
        elif reason == 'geo_blocked':
            xbmcgui.Dialog().ok(
                'RTL+',
                'Dieser Inhalt ist in deiner Region gesperrt (Geo-Block).'
            )
        else:
            try:
                is_free = not self.api.auth.is_premium()
            except Exception:
                is_free = False
            if is_free:
                xbmcgui.Dialog().ok('RTL+', 'Premium Inhalt im Free Modus nicht verfuegbar.\n\nBitte upgraden Sie Ihren Account auf RTL+ Premium.')
            else:
                xbmcgui.Dialog().notification('RTL+', 'Stream nicht gefunden', xbmcgui.NOTIFICATION_ERROR, 5000)
        xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())

    def play_vod (self ,video_id ,title ='Video',video_seo ='',program_seo ='',program_id ='',
                 thumb ='',fanart ='',poster ='',series_title =''):
        _log (f'play_vod id={video_id}')

        layout =self .api .get_video_layout (video_id ,video_seo =video_seo ,program_seo =program_seo ,program_id =program_id )
        if not layout or (isinstance (layout ,dict )and '_error'in layout ):
            self ._no_assets_error (reason =layout .get ('_error')if isinstance (layout ,dict )else None )
            return

        if title =='Video':
            api_title =self .api ._extract_title (layout )
            if api_title :
                title =api_title

        if self ._addon .getSettingBool ('weiterschauen_enabled'):
            self ._save_resume_info (video_id ,title ,
                thumb =thumb ,fanart =fanart ,poster =poster ,series_title =series_title )

        assets =self .api ._extract_assets (layout )
        if not assets :
            self ._no_assets_error ()
            return

        asset ,max_height ,_ =self ._best_asset (assets )
        _log (f'Asset: quality={asset ["quality"]} drm_type={asset ["drm_type"]}')

        drm_cfg =asset .get ('drm_config',{})
        service_code =drm_cfg .get ('serviceCode','video_tv')
        content_id =drm_cfg .get ('contentId',video_id )

        drm_token =self .api .auth .get_drm_token (service_code ,'video',content_id )
        self ._resolve (asset ['path'],drm_token ,title ,is_live =False ,max_height =max_height )

    def _save_resume_info(self, video_id, title, thumb='', fanart='', poster='', series_title=''):
        from .evil import bookmarks as _bookmarks
        from .evil.constants import ADDON_ID

        current_path = f'plugin://{ADDON_ID}/?mode=play_vod&video_id={video_id}'

        data = _bookmarks.get()
        data = [x for x in data if x.get('path') != current_path]
        entry = {
            'path': current_path,
            'label': title,
            'thumb': thumb or '',
            'folder': 0,
            'playable': 1,
        }
        if fanart:
            entry['fanart'] = fanart
        if poster:
            entry['poster'] = poster
        if series_title:
            entry['series_title'] = series_title
        data.insert(0, entry)
        data = data[:5]
        from .evil.util import save_json
        from .evil.constants import BOOKMARK_FILE
        save_json(BOOKMARK_FILE, data, pretty=True)
        _log(f'Weiterschauen gespeichert: {title}')

    def play_audio(self, audio_id, title='Audio'):
        _log(f'play_audio id={audio_id}')

        assets = self.api.get_audio_assets(audio_id)
        if not assets:
            self._no_assets_error()
            return

        def _audio_score(a):
            fmt = a.get('format', '')
            return {'mp3': 10, 'passthrough_mp3_mpeg': 9, 'aac': 7, 'hls': 5, 'hlsfp': 5, 'm3u8': 5}.get(fmt, 3)

        asset = max(assets, key=_audio_score)
        _log(f'Audio asset: format={asset["format"]} drm_type={asset.get("drm_type", "none")} path={asset["path"][:80]}')

        drm_cfg = asset.get('drm_config', {})
        if drm_cfg:
            service_code = drm_cfg.get('serviceCode', 'video_tv')
            content_id = drm_cfg.get('contentId', audio_id)
            drm_token = self.api.auth.get_drm_token(service_code, 'video', content_id)
            _log(f'Audio DRM-Token: {"OK" if drm_token else "FEHLT"} serviceCode={service_code}')
        else:
            drm_token = None

        self._resolve_audio(asset['path'], title, fmt=asset.get('format', ''), drm_token=drm_token)

    def play_radio(self, radio_id, title='Radio'):
        _log(f'play_radio id={radio_id}')

        assets = self.api.get_radio_assets(radio_id)

        if assets:
            def _radio_score(a):
                fmt = a.get('format', '')
                return {'hls': 10, 'm3u8': 10, 'mp3': 8, 'aac': 7, 'dash': 3, 'dashcenc': 2}.get(fmt, 5)

            asset = max(assets, key=_radio_score)
            stream_url = asset['path']
            fmt = asset.get('format', '')
            _log(f'Radio asset: format={fmt} url={stream_url[:80]}')

            if fmt in ('hls', 'hlsfp', 'm3u8', 'mp3', 'aac', 'passthrough_mp3_mpeg'):
                self._resolve_audio(stream_url, title, fmt=fmt)
                return

            drm_cfg = asset.get('drm_config', {})
            service_code = drm_cfg.get('serviceCode', 'rtlplus_root')
            content_id = drm_cfg.get('contentId', radio_id)
            drm_token = self.api.auth.get_drm_token(service_code, 'live', content_id) if drm_cfg else None
            self._resolve(stream_url, drm_token, title, is_live=True)
        else:
            self._no_assets_error()

    def play_live(self, channel_id, service_code='rtlplus_root', content_id='', title='Live'):
        _log(f'play_live channel={channel_id}')

        if not content_id:
            content_id = f'dashcenc_rtlde_{channel_id}'

        assets = self.api.get_live_assets(channel_id)

        if assets:
            asset, _, pref_idx = self._best_asset(assets, is_live=True)
            mpd_url = asset['path']
            drm_cfg = asset.get('drm_config', {})
            service_code = drm_cfg.get('serviceCode', service_code)
            live_content_id = drm_cfg.get('contentId', content_id)
            use_drm = bool(drm_cfg)
        else:
            _log('No assets, using fallback URL')
            channel_slug_dash = channel_id.replace('_', '-')
            if channel_id.startswith('fast'):
                mpd_url = (
                    f'https://origin.live.rtlde.bedrock.tech/out/v1/rtlde/'
                    f'rtlde-{channel_slug_dash}/cmaf_cenc00/dash-short-sd.mpd'
                )
            else:
                mpd_url = (
                    f'https://origin.live.rtlde.bedrock.tech/out/v1/rtlde/'
                    f'rtlde-{channel_slug_dash}/cmaf_cenc71/dash-short-hd720.mpd'
                )
            live_content_id = content_id
            use_drm = True
            try:
                pref_idx = int(self._addon.getSetting('quality_preferred') or '0')
            except Exception:
                pref_idx = 0

        if 'cmaf_cenc00' in mpd_url and 'yospace.com' not in mpd_url:
            is_fast_channel = f'rtlde-{channel_id}' in mpd_url and channel_id.startswith('fast')
            if not is_fast_channel:
                mpd_url = mpd_url.replace('cmaf_cenc00', 'cmaf_cenc71')
                _log(f'cenc00 -> cenc71 (Origin, nicht-FAST): {mpd_url}')
            else:
                _log(f'cenc00 beibehalten (FAST-Kanal): {mpd_url}')
            if not service_code:
                service_code = 'rtlplus_root'
            if not live_content_id:
                live_content_id = f'dashcenc_rtlde_{channel_id}'
            _log(f'DRM: service={service_code}, cid={live_content_id}')

        _log(f'Live MPD: {mpd_url}')
        is_encrypted = 'cenc00' not in mpd_url
        if pref_idx == 0:
            is_fast = channel_id.startswith('fast')
            drm_active = use_drm and (is_encrypted or is_fast)
            _log(f'DRM-Pruefung (Automatisch): use_drm={use_drm} is_encrypted={is_encrypted} is_fast={is_fast} -> drm_active={drm_active}')

        else:
            drm_active = use_drm
            _log(f'DRM-Pruefung (Qualitaet manuell, pref_idx={pref_idx}): use_drm={use_drm} -> drm_active={drm_active}')

        if drm_active:
            drm_token = self.api.auth.get_drm_token(service_code, 'live', live_content_id)
        else:
            drm_token = None
            _log(f'DRM deaktiviert: cenc00-Stream oder kein DRM-Asset (channel={channel_id})')

        try:
            tier = str(self.api.auth.get_subscription_tier())
        except Exception:
            tier = 'Gast'

        if not tier == 'Gast':
            if not tier == 'Free':
                self._resolve(mpd_url, drm_token, title, is_live=True)
            else:
                if 'fast' in str(live_content_id):
                    self._resolve(mpd_url, drm_token, title, is_live=True)
                else:
                    xbmcgui.Dialog().notification('RTL+ Fehler','Live Tv mit Free Account nicht möglich')

        else:
            xbmcgui.Dialog().notification('RTL+ Fehler','Bitte Anmelden')

    def _resolve(self, mpd_url, drm_token, title, is_live=False, max_height=1080):
        li = xbmcgui.ListItem(label=title, path=mpd_url)
        li.setInfo('video', {'title': title, 'mediatype': 'video'})

        li.setProperty('inputstream', 'inputstream.adaptive')
        li.setProperty('inputstream.adaptive.manifest_type', 'mpd')

        lang_index = int(self._addon.getSetting('audio_language') or '0')
        lang_map = {1: 'deu', 2: 'eng'}
        if lang_index in lang_map:
            li.setProperty('inputstream.adaptive.audio_language', lang_map[lang_index])
            _log(f'Bevorzugte Audiosprache: {lang_map[lang_index]}')

        _QUALITY_RES = [(1080, 1920), (720, 1280), (576, 1024), (360, 640)]
        try:
            _pref_idx = int(self._addon.getSetting('quality_preferred') or '0')
            _max_idx  = int(self._addon.getSetting('quality_max')       or '0')
        except Exception:
            _pref_idx = 0
            _max_idx  = 0

        if _pref_idx > 0:
            _eff = max(_pref_idx - 1, _max_idx)
            _eff = min(_eff, len(_QUALITY_RES) - 1)
            _force_h, _force_w = _QUALITY_RES[_eff]
            li.setProperty('inputstream.adaptive.max_resolution', f'{_force_w}x{_force_h}')
            _log(f'isa.max_resolution erzwungen: {_force_w}x{_force_h} (pref_idx={_pref_idx} max_idx={_max_idx})')
        else:
            auto_h, auto_w = _auto_max_resolution()
            cap_h = min(auto_h, max_height)
            cap_w = min(auto_w, 7680)
            sw_h, sw_w = _software_decode_cap()
            if sw_h is not None:
                cap_h = min(cap_h, sw_h)
                cap_w = min(cap_w, sw_w)
            li.setProperty('inputstream.adaptive.max_resolution', f'{cap_w}x{cap_h}')
            _log(f'isa.max_resolution (auto): {cap_w}x{cap_h} (widevine+screen cap, max_height={max_height})')

        stream_headers = (
            f'User-Agent={_q(USER_AGENT)}'
            f'&Origin={_q("https://plus.rtl.de")}'
            f'&Referer={_q("https://plus.rtl.de/")}'
        )
        li.setProperty('inputstream.adaptive.stream_headers', stream_headers)
        li.setProperty('inputstream.adaptive.manifest_headers', stream_headers)

        if drm_token:
            lic_headers = (
                f'Content-Type=application%2Foctet-stream'
                f'&User-Agent={_q(USER_AGENT)}'
                f'&Origin={_q("https://plus.rtl.de")}'
                f'&Referer={_q("https://plus.rtl.de/")}'
                f'&x-dt-auth-token={_q(drm_token)}'
            )
            license_key = f'{DRM_LICENSE_URL}|{lic_headers}|R{{SSM}}|JBlicense'
            li.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
            li.setProperty('inputstream.adaptive.license_key', license_key)
            _log('DRM: license_key mit JBlicense Response-Filter gesetzt')
        else:
            _log('Kein DRM-Token: Stream ohne Widevine')

        xbmcplugin.setResolvedUrl(self.handle, True, li)

    def _resolve_audio(self, url, title, fmt='', drm_token=None):
        _log(f'_resolve_audio fmt={fmt} drm={"ja" if drm_token else "nein"} url={url[:100]}')

        headers = {
            'User-Agent': USER_AGENT,
            'Referer': 'https://plus.rtl.de/',
            'Origin': 'https://plus.rtl.de',
        }
        stream_headers_pipe = urllib.parse.urlencode(headers)

        if fmt in ('hls', 'hlsfp') or url.split('?')[0].endswith('.m3u8'):
            if fmt == 'hlsfp':
                _log('Audio HLS: Format hlsfp (HE-AAC) wird von Kodi nicht unterstuetzt')
                xbmcgui.Dialog().ok('RTL+', 'Stream mit Kodi nicht unterstuetzt.[CR][CR]Das Audioformat (HE-AAC) wird von Kodi leider nicht dekodiert.')
                xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
                return

            full_url = f'{url}|{stream_headers_pipe}'
            li = xbmcgui.ListItem(label=title, path=full_url)
            li.setInfo('video', {'title': title})
            li.setProperty('IsPlayable', 'true')
        else:
            full_url = f'{url}|{stream_headers_pipe}'
            li = xbmcgui.ListItem(label=title, path=full_url)
            li.setInfo('music', {'title': title})
            li.setProperty('IsPlayable', 'true')

        xbmcplugin.setResolvedUrl(self.handle, True, li)

    def _best_asset(self, assets, is_live=False):
        addon = self._addon

        QUALITY_LEVELS = [
            ('fhd', 1080),
            ('hd',   720),
            ('sd',   576),
            ('low',  360),
        ]

        def quality_index(a):
            q = a.get('video_quality', a.get('quality', 'sd')).lower()
            mapping = {
                'fhd': 0, '1080p': 0, '1080': 0,
                'hd2': 0,
                'hd': 1, 'hd720': 1, '720p': 1, '720': 1,
                'sd': 2, '576p': 2, '576': 2,
                '360p': 3, '360': 3,
            }
            return mapping.get(q, 1)

        if not is_live:
            try:
                if not self.api.auth.is_premium():
                    sd_assets = [a for a in assets if quality_index(a) >= 2]
                    if sd_assets:
                        assets = sd_assets
                        _log('Free-Account: Stream auf SD/576p begrenzt')
                    else:
                        _log('Free-Account: Kein SD-Asset gefunden, nehme verfügbares Asset')
            except Exception as e:
                _log(f'is_premium check in _best_asset fehlgeschlagen: {e}')

        try:
            max_idx = int(addon.getSetting('quality_max') or '0')
        except Exception:
            max_idx = 0
        max_height = QUALITY_LEVELS[min(max_idx, len(QUALITY_LEVELS) - 1)][1]

        filtered = [a for a in assets if quality_index(a) >= max_idx]
        if filtered:
            assets = filtered
            _log(f'Maximale Qualität: {QUALITY_LEVELS[max_idx][0]} ({max_height}p) — {len(assets)} Asset(s) verbleiben')
        else:
            worst_idx = max(quality_index(a) for a in assets)
            assets = [a for a in assets if quality_index(a) == worst_idx]
            max_height = QUALITY_LEVELS[min(worst_idx, len(QUALITY_LEVELS) - 1)][1]
            _log(f'Kein Asset für max. Qualität Index {max_idx}, nehme schlechtestes verfügbares: {QUALITY_LEVELS[min(worst_idx,3)][0]} ({max_height}p)')

        try:
            pref_idx = int(addon.getSetting('quality_preferred') or '0')
        except Exception:
            pref_idx = 0

        if pref_idx == 0:
            sw_h, _ = _software_decode_cap()
            if sw_h is not None:
                sw_min_idx = next(
                    (i for i, (_, h) in enumerate(QUALITY_LEVELS) if h <= sw_h),
                    len(QUALITY_LEVELS) - 1
                )
                best_cap_idx = None
                for cap_idx in range(len(QUALITY_LEVELS) - 1, -1, -1):
                    if cap_idx > sw_min_idx:
                        continue
                    candidate = [a for a in assets if quality_index(a) == cap_idx]
                    if candidate:
                        best_cap_idx = cap_idx
                        assets = candidate
                        max_height = QUALITY_LEVELS[cap_idx][1]
                        _log(f'Software-Decoder-Cap: Assets auf max. {max_height}p begrenzt (Windows L3, cap_idx={cap_idx})')
                        break
                if best_cap_idx is None:
                    best_cap_idx_fallback = min(quality_index(a) for a in assets)
                    assets = [a for a in assets if quality_index(a) == best_cap_idx_fallback]
                    max_height = QUALITY_LEVELS[min(best_cap_idx_fallback, len(QUALITY_LEVELS) - 1)][1]
                    _log(f'Software-Decoder-Cap: Kein Asset ≤{sw_h}p, nehme niedrigstes verfügbares: {max_height}p')

        def score(a):
            qi = quality_index(a)
            is_hw = a.get('drm_type') == 'hardware'
            drm_score = 1 if is_hw else 2
            if pref_idx == 0:
                quality_score = (3 - qi) * 10
            else:
                target = pref_idx - 1
                quality_score = 100 - abs(qi - target) * 10

            path = a.get('path', '')
            origin_score = 5 if (is_live and 'origin.live' in path) else 0
            return quality_score + drm_score + origin_score

        best = max(assets, key=score)
        _log(f'Gewähltes Asset: quality={best.get("video_quality") or best.get("quality")} drm={best.get("drm_type")} pref_idx={pref_idx} max_idx={max_idx} max_height={max_height}')
        return best, max_height, pref_idx
