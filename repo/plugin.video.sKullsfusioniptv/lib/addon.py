"""
Compatible with Kodi 19.x "Matrix" and above
"""
from __future__ import absolute_import, division, unicode_literals
import re
import math
import datetime
import time
from multiprocessing.pool import ThreadPool
from urllib.parse import parse_qsl
import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
from .globals import G
from .utils import ask_for_input, get_int_value, ask_for_category_selection
from .api import Api
from .loggers import Logger
from .fav_database_handler import FavDatabase


class StalkerAddon:
    """Stalker Addon"""

    @staticmethod
    def __should_filter(title, filter_string):
        """Hilfsmethode für Multi-Filter und Wildcards (implizit durch Teilstring-Suche)"""
        if not filter_string:
            return False

        # Splitte bei Kommas, entferne Leerzeichen und ignoriere leere Einträge
        filters = [f.strip().lower() for f in filter_string.split(',') if f.strip()]

        if not filters:
            return False

        title_lower = title.lower()

        # Wenn einer der Filter im Titel vorkommt, wird er NICHT ausgefiltert (return False)
        for f in filters:
            if f in title_lower:
                return False

        # Keiner der Filter passt -> ausfiltern
        return True

    @staticmethod
    def __toggle_favorites(params, add, ):
        """Remove/add favorites (Portal + lokale DB) and refresh"""
        video_id = params['video_id']
        _type = params['_type']
        portal_id = int(params.get('portal_id', G.active_portal))

        Logger.debug(f'Toggle Favorites video_id={video_id}, add={add}, _type={_type}, portal_id={portal_id}')

        # 1) Portal-Favoriten (Standard)
        if add:
            Api.add_favorites(video_id, _type)
        else:
            Api.remove_favorites(video_id, _type)

        # 2) Lokale Favoriten (SQLite)
        try:
            db = FavDatabase()
            if add:
                title = params.get('title', '') or params.get('name', '')
                logo = params.get('logo', '')
                cmd = params.get('cmd', '')
                description = params.get('description', '')
                if title:
                    db.add_favorite(
                        video_id=video_id,
                        portal_id=portal_id,
                        _type=_type,
                        name=title,
                        logo=logo,
                        cmd=cmd,
                        description=description
                    )
            else:
                db.remove_favorite(video_id=video_id, portal_id=portal_id, _type=_type)
        except Exception as e:
            Logger.error(f"SQLite favorites update failed: {str(e)}")

        xbmc.executebuiltin('Container.Refresh')

    @staticmethod
    def __get_portal_label(portal_id: int) -> str:
        """Get portal label from JSON configuration"""
        portals = G.get_available_portals()
        for p in portals:
            if int(p.get('id', 0)) == int(portal_id):
                name = p.get('name', '')
                server = p.get('server_address', '')
                if name:
                    return name
                if server:
                    return server
        return f"Portal {portal_id}"

    @staticmethod
    def __list_local_favorites_portals(_type):
        """Zeigt Portale als Ordner an, gruppiert nach portal_id."""
        db = FavDatabase()
        items = db.list_favorites(_type)

        # portal_id -> count
        counts = {}
        for fav in items:
            p = int(fav.get('portal_id', 1))
            counts[p] = counts.get(p, 0) + 1

        xbmcplugin.setContent(G.get_handle(), 'files')
        directory_items = []

        # sortiert nach Portalnummer
        for portal_id in sorted(counts.keys()):
            portal_label = StalkerAddon.__get_portal_label(portal_id)
            label = f"{portal_label} ({counts[portal_id]})"
            list_item = xbmcgui.ListItem(label=label)

            portal_icon = G.get_custom_thumb_path(f'iptv_portal_{int(portal_id)}.png')
            list_item.setArt({'thumb': portal_icon, 'icon': portal_icon})

            url = G.get_plugin_url({
                'action': 'local_favorites_portal',
                '_type': _type,
                'portal_id': portal_id
            })
            directory_items.append((url, list_item, True))

        xbmcplugin.addDirectoryItems(G.get_handle(), directory_items, len(directory_items))
        xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True, updateListing=False, cacheToDisc=False)

    @staticmethod
    def __list_local_favorites_for_portal(_type, portal_id):
        """Listet lokale Favoriten eines Typs für genau ein Portal."""
        addon = xbmcaddon.Addon()
        db = FavDatabase()
        items = [x for x in db.list_favorites(_type) if int(x.get('portal_id', 1)) == int(portal_id)]

        # Kontext (Portal) aktivieren, damit z.B. EPG/URLs korrekt sind
        try:
            G.init_globals(int(portal_id))
        except Exception:
            pass

        xbmcplugin.setContent(G.get_handle(), 'files')
        xbmcplugin.setPluginCategory(G.get_handle(), f"{StalkerAddon.__get_portal_label(int(portal_id))}")

        epg_enabled = addon.getSetting('epg_enabled') == 'true'

        # Für TV: EPG vorladen
        if _type == 'itv' and epg_enabled and items:
            try:
                Api.get_epg_batch([i['id'] for i in items])
            except Exception:
                pass

        directory_items = []
        for fav in items:
            name = fav.get('name', '')
            label = f"{name} ★"
            list_item = xbmcgui.ListItem(label=label)

            # Description/Plot setzen (vor allem für VOD + SERIES)
            try:
                vi = list_item.getVideoInfoTag()
                vi.setTitle(name)
                if _type in ('vod', 'series'):
                    vi.setPlot(fav.get('description', '') or '')
            except Exception:
                pass

            # optional Logo
            if fav.get('logo'):
                list_item.setArt(
                    {'thumb': fav['logo'], 'icon': fav['logo'], 'poster': fav['logo'], 'clearlogo': fav['logo']})

            # TV: EPG in Zeile
            if _type == 'itv' and epg_enabled:
                try:
                    short_epg = Api.get_short_epg(fav['id']) or []
                    if short_epg:
                        now = short_epg[0]
                        epg_title = now.get('name', '')
                        if epg_title:
                            list_item.setLabel(f"{label} - [COLOR orange]{epg_title}[/COLOR]")
                except Exception:
                    pass

            # Watched/Overlay neutralisieren (optional)
            try:
                vi = list_item.getVideoInfoTag()
                vi.setPlaycount(0)
            except Exception:
                pass
            list_item.setProperty('Overlay', '0')

            if _type == 'itv':
                list_item.setProperty('IsPlayable', 'true')
                url = G.get_plugin_url({'action': 'tv_play', 'cmd': fav.get('cmd', ''), 'portal_id': int(portal_id)})
                directory_items.append((url, list_item, False))

            elif _type == 'vod':
                list_item.setProperty('IsPlayable', 'true')
                url = G.get_plugin_url({
                    'action': 'play',
                    'video_id': fav['id'],
                    'series': 0,
                    'title': name,
                    'cmd': fav.get('cmd', ''),
                    'portal_id': int(portal_id)
                })
                directory_items.append((url, list_item, False))

            elif _type == 'series':
                url = G.get_plugin_url(
                    {'action': 'season_listing', 'video_id': fav['id'], 'name': name, 'poster_url': fav.get('logo', ''),
                     'portal_id': int(portal_id)})
                directory_items.append((url, list_item, True))

        xbmcplugin.addDirectoryItems(G.get_handle(), directory_items, len(directory_items))
        xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True, updateListing=False, cacheToDisc=False)

    @staticmethod
    def __normalize_logo_url(logo: str) -> str:
        """Macht aus relativen Portal-Logos eine vollständige URL (für aktuelles G.portal_config)."""
        if not logo:
            return ''
        if isinstance(logo, str) and logo.startswith('http'):
            return logo
        # Viele Portale liefern relative Pfade wie "/misc/logos/..png" oder "misc/logos/..png"
        base = getattr(G.portal_config, 'portal_base_url', '') or ''
        if not base:
            return logo
        if logo.startswith('/'):
            return base + logo
        return base + '/' + logo

    @staticmethod
    def __list_local_favorites(_type):
        """Listet lokale (portalübergreifende) Favoriten aus SQLite"""
        addon = xbmcaddon.Addon()
        db = FavDatabase()

        # Wichtig: 'files' reduziert/entfernt in vielen Skins den "gesehen/ungesehen"-Indikator
        # (Sammellisten sollen meist neutral aussehen).
        if _type == 'itv':
            xbmcplugin.setPluginCategory(G.get_handle(), addon.getLocalizedString(32205))
        elif _type == 'vod':
            xbmcplugin.setPluginCategory(G.get_handle(), addon.getLocalizedString(32203))
        elif _type == 'series':
            xbmcplugin.setPluginCategory(G.get_handle(), addon.getLocalizedString(32204))
        xbmcplugin.setContent(G.get_handle(), 'files')

        items = db.list_favorites(_type)
        directory_items = []

        original_portal = G.active_portal

        try:
            # Für TV: EPG portalweise vorladen (Batch), weil EPG/Cache am aktiven Portal hängt
            if _type == 'itv' and items:
                ids_by_portal = {}
                for fav in items:
                    p = int(fav.get('portal_id', 1))
                    ids_by_portal.setdefault(p, []).append(fav['id'])

                for p_id, ch_ids in ids_by_portal.items():
                    try:
                        G.init_globals(p_id)
                        Api.get_epg_batch(ch_ids)
                    except Exception as e:
                        Logger.debug(f"EPG batch preload failed for portal {p_id}: {str(e)}")

            # Jetzt Items rendern
            for fav in items:
                portal_id = int(fav.get('portal_id', 1))

                # Pro Item aufs passende Portal schalten, damit:
                # - Logo normalisiert werden kann (portal_base_url)
                # - short_epg / epg cache korrekt ist
                try:
                    G.init_globals(portal_id)
                except Exception:
                    pass

                portal_label = StalkerAddon.__get_portal_label(portal_id)
                display_name = fav.get('name', '')

                logo_url = StalkerAddon.__normalize_logo_url(fav.get('logo', ''))

                # Label mit Portal-Hinweis
                label = f"[COLOR gray]{portal_label}[/COLOR]  {display_name} ★"

                # TV: Kurzes EPG in die Zeile aufnehmen
                epg_plot = ""
                if _type == 'itv':
                    try:
                        epg_enabled = addon.getSetting('epg_enabled') == 'true'
                        if epg_enabled:
                            short_epg = Api.get_short_epg(fav['id']) or []
                            if short_epg:
                                now = short_epg[0]
                                epg_title = now.get('name', '')
                                epg_plot = now.get('descr', '')
                                if epg_title:
                                    label = f"{label} - [COLOR orange]{epg_title}[/COLOR]"
                    except Exception:
                        pass

                list_item = xbmcgui.ListItem(label=label)

                # VideoInfoTag setzen (Titel, Plot für VOD/Series/TV-EPG)
                try:
                    video_info = list_item.getVideoInfoTag()
                    video_info.setTitle(display_name)
                    if _type in ('vod', 'series'):
                        video_info.setPlot(fav.get('description', '') or '')
                    elif _type == 'itv' and epg_plot:
                        video_info.setPlot(epg_plot)
                    video_info.setPlaycount(0)
                except Exception:
                    pass
                list_item.setProperty('Overlay', '0')

                if logo_url:
                    list_item.setArt({'thumb': logo_url, 'icon': logo_url, 'poster': logo_url, 'clearlogo': logo_url})

                if _type == 'itv':
                    list_item.setProperty('IsPlayable', 'true')

                    # EPG Kontextmenü wie in der Portalansicht
                    context_menu = []
                    if addon.getSetting('epg_enabled') == 'true':
                        url_epg = G.get_plugin_url({
                            'action': 'tv_epg',
                            'channel_id': fav['id'],
                            'channel_name': display_name,
                            'portal_id': portal_id
                        })
                        context_menu.append(('EPG', f'Container.Update({url_epg})'))
                    if context_menu:
                        list_item.addContextMenuItems(context_menu)

                    url = G.get_plugin_url({
                        'action': 'tv_play',
                        'cmd': fav.get('cmd', ''),
                        'portal_id': portal_id
                    })
                    directory_items.append((url, list_item, False))

                elif _type == 'vod':
                    list_item.setProperty('IsPlayable', 'true')
                    url = G.get_plugin_url({
                        'action': 'play',
                        'video_id': fav['id'],
                        'series': 0,
                        'title': display_name,
                        'portal_id': portal_id
                    })
                    directory_items.append((url, list_item, False))

                elif _type == 'series':
                    url = G.get_plugin_url({
                        'action': 'season_listing',
                        'video_id': fav['id'],
                        'name': display_name,
                        'poster_url': logo_url,
                        'portal_id': portal_id
                    })
                    directory_items.append((url, list_item, True))

        finally:
            # Portal wieder zurücksetzen, damit danach nichts "komisch" ist
            try:
                G.init_globals(original_portal)
            except Exception:
                pass

        xbmcplugin.addDirectoryItems(G.get_handle(), directory_items, len(directory_items))
        xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True, updateListing=False, cacheToDisc=False)

    @staticmethod
    def __list_local_favorites_with_categories(_type):
        """Listet Kategorien als Ordner + unkategorisierte Favoriten"""
        addon = xbmcaddon.Addon()
        db = FavDatabase()

        if _type == 'itv':
            xbmcplugin.setPluginCategory(G.get_handle(), addon.getLocalizedString(32205))
        elif _type == 'vod':
            xbmcplugin.setPluginCategory(G.get_handle(), addon.getLocalizedString(32203))
        elif _type == 'series':
            xbmcplugin.setPluginCategory(G.get_handle(), addon.getLocalizedString(32204))
        xbmcplugin.setContent(G.get_handle(), 'files')

        directory_items = []
        categories = db.list_categories(_type)

        # Kategorien als Ordner anzeigen
        for cat in categories:
            count = db.get_category_count(cat['id'])
            label = f"📁 {cat['name']} ({count})"
            list_item = xbmcgui.ListItem(label=label)

            # Kontextmenü für Kategorie
            rename_url = G.get_plugin_url({'action': 'rename_category', 'category_id': cat['id'], '_type': _type})
            delete_url = G.get_plugin_url({'action': 'delete_category', 'category_id': cat['id'], '_type': _type})
            context_menu = [
                (addon.getLocalizedString(32601), f'RunPlugin({rename_url})'),
                (addon.getLocalizedString(32602), f'RunPlugin({delete_url})')
            ]
            list_item.addContextMenuItems(context_menu)

            url = G.get_plugin_url({
                'action': 'local_favorites_category',
                '_type': _type,
                'category_id': cat['id']
            })
            directory_items.append((url, list_item, True))

        # Unkategorisierte Favoriten direkt anzeigen
        uncategorized = db.list_favorites_uncategorized(_type)
        original_portal = G.active_portal

        try:
            # Für TV: EPG portalweise vorladen
            if _type == 'itv' and uncategorized:
                ids_by_portal = {}
                for fav in uncategorized:
                    p = int(fav.get('portal_id', 1))
                    ids_by_portal.setdefault(p, []).append(fav['id'])

                for p_id, ch_ids in ids_by_portal.items():
                    try:
                        G.init_globals(p_id)
                        Api.get_epg_batch(ch_ids)
                    except Exception as e:
                        Logger.debug(f"EPG batch preload failed for portal {p_id}: {str(e)}")

            # Unkategorisierte Items rendern
            for fav in uncategorized:
                portal_id = int(fav.get('portal_id', 1))
                try:
                    G.init_globals(portal_id)
                except Exception:
                    pass

                portal_label = StalkerAddon.__get_portal_label(portal_id)
                display_name = fav.get('name', '')
                logo_url = StalkerAddon.__normalize_logo_url(fav.get('logo', ''))
                label = f"[COLOR gray]{portal_label}[/COLOR]  {display_name} ★"

                # TV: EPG hinzufügen
                if _type == 'itv':
                    try:
                        epg_enabled = addon.getSetting('epg_enabled') == 'true'
                        if epg_enabled:
                            short_epg = Api.get_short_epg(fav['id']) or []
                            if short_epg:
                                now = short_epg[0]
                                epg_title = now.get('name', '')
                                epg_plot = now.get('descr', '')
                                if epg_title:
                                    label = f"{label} - [COLOR orange]{epg_title}[/COLOR]"
                    except Exception:
                        pass

                list_item = xbmcgui.ListItem(label=label)

                # VideoInfoTag setzen (Titel, Plot für VOD/Series)
                try:
                    video_info = list_item.getVideoInfoTag()
                    video_info.setTitle(display_name)
                    if _type in ('vod', 'series'):
                        video_info.setPlot(fav.get('description', '') or '')
                    elif _type == 'itv' and epg_plot:
                        video_info.setPlot(epg_plot)
                    video_info.setPlaycount(0)
                except Exception:
                    pass
                list_item.setProperty('Overlay', '0')

                if logo_url:
                    list_item.setArt({'thumb': logo_url, 'icon': logo_url, 'poster': logo_url, 'clearlogo': logo_url})

                # Kontextmenü: Zu Kategorie hinzufügen + Sortierung
                assign_url = G.get_plugin_url({'action': 'assign_to_category', 'video_id': fav['id'], 'portal_id': portal_id, '_type': _type})
                move_up_url = G.get_plugin_url({'action': 'move_favorite_up', 'video_id': fav['id'], 'portal_id': portal_id, '_type': _type})
                move_down_url = G.get_plugin_url({'action': 'move_favorite_down', 'video_id': fav['id'], 'portal_id': portal_id, '_type': _type})
                set_pos_url = G.get_plugin_url({'action': 'set_favorite_position', 'video_id': fav['id'], 'portal_id': portal_id, '_type': _type})
                context_menu = [
                    (addon.getLocalizedString(32603), f'RunPlugin({assign_url})'),
                    (addon.getLocalizedString(32620), f'RunPlugin({move_up_url})'),
                    (addon.getLocalizedString(32621), f'RunPlugin({move_down_url})'),
                    (addon.getLocalizedString(32622), f'RunPlugin({set_pos_url})')
                ]

                if _type == 'itv':
                    list_item.setProperty('IsPlayable', 'true')
                    if addon.getSetting('epg_enabled') == 'true':
                        url_epg = G.get_plugin_url({
                            'action': 'tv_epg',
                            'channel_id': fav['id'],
                            'channel_name': display_name,
                            'portal_id': portal_id
                        })
                        context_menu.append(('EPG', f'Container.Update({url_epg})'))
                    list_item.addContextMenuItems(context_menu)
                    url = G.get_plugin_url({
                        'action': 'tv_play',
                        'cmd': fav.get('cmd', ''),
                        'portal_id': portal_id
                    })
                    directory_items.append((url, list_item, False))
                elif _type == 'vod':
                    list_item.setProperty('IsPlayable', 'true')
                    list_item.addContextMenuItems(context_menu)
                    url = G.get_plugin_url({
                        'action': 'play',
                        'video_id': fav['id'],
                        'series': 0,
                        'title': display_name,
                        'portal_id': portal_id
                    })
                    directory_items.append((url, list_item, False))
                elif _type == 'series':
                    list_item.addContextMenuItems(context_menu)
                    url = G.get_plugin_url({
                        'action': 'season_listing',
                        'video_id': fav['id'],
                        'name': display_name,
                        'poster_url': logo_url,
                        'portal_id': portal_id
                    })
                    directory_items.append((url, list_item, True))

        finally:
            try:
                G.init_globals(original_portal)
            except Exception:
                pass

        # "Neue Kategorie erstellen" am Ende
        list_item = xbmcgui.ListItem(label=f"➕ {addon.getLocalizedString(32604)}")
        url = G.get_plugin_url({'action': 'create_category', '_type': _type})
        directory_items.append((url, list_item, False))

        xbmcplugin.addDirectoryItems(G.get_handle(), directory_items, len(directory_items))
        xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True, updateListing=False, cacheToDisc=False)

    @staticmethod
    def __list_local_favorites_in_category(_type, category_id):
        """Zeigt alle Favoriten einer bestimmten Kategorie"""
        addon = xbmcaddon.Addon()
        db = FavDatabase()

        xbmcplugin.setContent(G.get_handle(), 'files')

        # Kategorie-Info holen
        categories = db.list_categories(_type)
        cat_name = None
        for cat in categories:
            if cat['id'] == int(category_id):
                cat_name = cat['name']
                break

        if cat_name:
            xbmcplugin.setPluginCategory(G.get_handle(), cat_name)

        items = db.list_favorites(_type, category_id)
        directory_items = []
        original_portal = G.active_portal

        try:
            # Für TV: EPG portalweise vorladen
            if _type == 'itv' and items:
                ids_by_portal = {}
                for fav in items:
                    p = int(fav.get('portal_id', 1))
                    ids_by_portal.setdefault(p, []).append(fav['id'])

                for p_id, ch_ids in ids_by_portal.items():
                    try:
                        G.init_globals(p_id)
                        Api.get_epg_batch(ch_ids)
                    except Exception as e:
                        Logger.debug(f"EPG batch preload failed for portal {p_id}: {str(e)}")

            # Items rendern
            for fav in items:
                portal_id = int(fav.get('portal_id', 1))
                try:
                    G.init_globals(portal_id)
                except Exception:
                    pass

                portal_label = StalkerAddon.__get_portal_label(portal_id)
                display_name = fav.get('name', '')
                logo_url = StalkerAddon.__normalize_logo_url(fav.get('logo', ''))
                label = f"[COLOR gray]{portal_label}[/COLOR]  {display_name} ★"

                # TV: EPG hinzufügen
                epg_plot = ""
                if _type == 'itv':
                    try:
                        epg_enabled = addon.getSetting('epg_enabled') == 'true'
                        if epg_enabled:
                            short_epg = Api.get_short_epg(fav['id']) or []
                            if short_epg:
                                now = short_epg[0]
                                epg_title = now.get('name', '')
                                epg_plot = now.get('descr', '')
                                if epg_title:
                                    label = f"{label} - [COLOR orange]{epg_title}[/COLOR]"
                    except Exception:
                        pass

                list_item = xbmcgui.ListItem(label=label)

                # VideoInfoTag setzen (Titel, Plot für VOD/Series)
                try:
                    video_info = list_item.getVideoInfoTag()
                    video_info.setTitle(display_name)
                    if _type in ('vod', 'series'):
                        video_info.setPlot(fav.get('description', '') or '')
                    elif _type == 'itv' and epg_plot:
                        video_info.setPlot(epg_plot)
                    video_info.setPlaycount(0)
                except Exception:
                    pass
                list_item.setProperty('Overlay', '0')

                if logo_url:
                    list_item.setArt({'thumb': logo_url, 'icon': logo_url, 'poster': logo_url, 'clearlogo': logo_url})

                # Kontextmenü: Aus Kategorie entfernen + Sortierung
                remove_url = G.get_plugin_url({'action': 'remove_from_category', 'video_id': fav['id'], 'portal_id': portal_id, '_type': _type})
                move_up_url = G.get_plugin_url({'action': 'move_favorite_up', 'video_id': fav['id'], 'portal_id': portal_id, '_type': _type, 'category_id': category_id})
                move_down_url = G.get_plugin_url({'action': 'move_favorite_down', 'video_id': fav['id'], 'portal_id': portal_id, '_type': _type, 'category_id': category_id})
                set_pos_url = G.get_plugin_url({'action': 'set_favorite_position', 'video_id': fav['id'], 'portal_id': portal_id, '_type': _type, 'category_id': category_id})
                context_menu = [
                    (addon.getLocalizedString(32605), f'RunPlugin({remove_url})'),
                    (addon.getLocalizedString(32620), f'RunPlugin({move_up_url})'),
                    (addon.getLocalizedString(32621), f'RunPlugin({move_down_url})'),
                    (addon.getLocalizedString(32622), f'RunPlugin({set_pos_url})')
                ]

                if _type == 'itv':
                    list_item.setProperty('IsPlayable', 'true')
                    if addon.getSetting('epg_enabled') == 'true':
                        url_epg = G.get_plugin_url({
                            'action': 'tv_epg',
                            'channel_id': fav['id'],
                            'channel_name': display_name,
                            'portal_id': portal_id
                        })
                        context_menu.append(('EPG', f'Container.Update({url_epg})'))
                    list_item.addContextMenuItems(context_menu)
                    url = G.get_plugin_url({
                        'action': 'tv_play',
                        'cmd': fav.get('cmd', ''),
                        'portal_id': portal_id
                    })
                    directory_items.append((url, list_item, False))
                elif _type == 'vod':
                    list_item.setProperty('IsPlayable', 'true')
                    list_item.addContextMenuItems(context_menu)
                    url = G.get_plugin_url({
                        'action': 'play',
                        'video_id': fav['id'],
                        'series': 0,
                        'title': display_name,
                        'portal_id': portal_id
                    })
                    directory_items.append((url, list_item, False))
                elif _type == 'series':
                    list_item.addContextMenuItems(context_menu)
                    url = G.get_plugin_url({
                        'action': 'season_listing',
                        'video_id': fav['id'],
                        'name': display_name,
                        'poster_url': logo_url,
                        'portal_id': portal_id
                    })
                    directory_items.append((url, list_item, True))

        finally:
            try:
                G.init_globals(original_portal)
            except Exception:
                pass

        xbmcplugin.addDirectoryItems(G.get_handle(), directory_items, len(directory_items))
        xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True, updateListing=False, cacheToDisc=False)

    @staticmethod
    def __create_category(params):
        """Erstellt eine neue Kategorie via Dialog"""
        _type = params.get('_type', 'itv')
        addon = xbmcaddon.Addon()

        # Dialog für Kategoriename
        dialog = xbmcgui.Dialog()
        cat_name = dialog.input(addon.getLocalizedString(32606), type=xbmcgui.INPUT_ALPHANUM)

        if cat_name:
            db = FavDatabase()
            db.add_category(cat_name, _type)
            xbmc.executebuiltin('Container.Refresh')

    @staticmethod
    def __rename_category(params):
        """Benennt eine Kategorie um"""
        category_id = int(params.get('category_id', 0))
        _type = params.get('_type', 'itv')
        addon = xbmcaddon.Addon()

        db = FavDatabase()
        categories = db.list_categories(_type)
        current_name = None
        for cat in categories:
            if cat['id'] == category_id:
                current_name = cat['name']
                break

        if current_name:
            dialog = xbmcgui.Dialog()
            new_name = dialog.input(addon.getLocalizedString(32607), defaultt=current_name, type=xbmcgui.INPUT_ALPHANUM)

            if new_name and new_name != current_name:
                db.rename_category(category_id, new_name)
                xbmc.executebuiltin('Container.Refresh')

    @staticmethod
    def __delete_category(params):
        """Löscht eine Kategorie nach Bestätigung"""
        category_id = int(params.get('category_id', 0))
        _type = params.get('_type', 'itv')
        addon = xbmcaddon.Addon()

        db = FavDatabase()
        categories = db.list_categories(_type)
        cat_name = None
        for cat in categories:
            if cat['id'] == category_id:
                cat_name = cat['name']
                break

        if cat_name:
            dialog = xbmcgui.Dialog()
            if dialog.yesno(addon.getLocalizedString(32608), addon.getLocalizedString(32609).format(cat_name)):
                db.remove_category(category_id)
                xbmc.executebuiltin('Container.Refresh')

    @staticmethod
    def __assign_to_category(params):
        """Weist einen Favoriten einer Kategorie zu"""
        video_id = params.get('video_id')
        portal_id = int(params.get('portal_id', 1))
        _type = params.get('_type', 'itv')
        addon = xbmcaddon.Addon()

        db = FavDatabase()
        categories = db.list_categories(_type)

        if not categories:
            dialog = xbmcgui.Dialog()
            dialog.ok(addon.getLocalizedString(32610), addon.getLocalizedString(32611))
            return

        # Dialog mit Kategorieliste
        cat_names = [cat['name'] for cat in categories]
        dialog = xbmcgui.Dialog()
        selected = dialog.select(addon.getLocalizedString(32612), cat_names)

        if selected >= 0:
            category_id = categories[selected]['id']
            db.assign_favorite_to_category(video_id, portal_id, _type, category_id)
            xbmc.executebuiltin('Container.Refresh')

    @staticmethod
    def __remove_from_category(params):
        """Entfernt einen Favoriten aus seiner Kategorie"""
        video_id = params.get('video_id')
        portal_id = int(params.get('portal_id', 1))
        _type = params.get('_type', 'itv')

        db = FavDatabase()
        db.assign_favorite_to_category(video_id, portal_id, _type, None)
        xbmc.executebuiltin('Container.Refresh')

    @staticmethod
    def __move_favorite_up(params):
        """Verschiebt einen Favoriten in der Kategorie nach oben"""
        video_id = params.get('video_id')
        portal_id = int(params.get('portal_id', 1))
        _type = params.get('_type', 'itv')
        category_id = params.get('category_id')

        db = FavDatabase()
        # Hole alle Favoriten der Kategorie
        if category_id is None:
            favorites = db.list_favorites_uncategorized(_type)
        else:
            favorites = db.list_favorites(_type, int(category_id))

        # Finde aktuellen Index
        current_idx = None
        for idx, fav in enumerate(favorites):
            if fav['id'] == video_id and fav['portal_id'] == portal_id:
                current_idx = idx
                break

        if current_idx is not None and current_idx > 0:
            # Tausche sort_order mit vorherigem Element
            prev_fav = favorites[current_idx - 1]
            curr_fav = favorites[current_idx]

            db.move_favorite_in_category(prev_fav['id'], prev_fav['portal_id'], _type, current_idx)
            db.move_favorite_in_category(curr_fav['id'], curr_fav['portal_id'], _type, current_idx - 1)
            xbmc.executebuiltin('Container.Refresh')

    @staticmethod
    def __move_favorite_down(params):
        """Verschiebt einen Favoriten in der Kategorie nach unten"""
        video_id = params.get('video_id')
        portal_id = int(params.get('portal_id', 1))
        _type = params.get('_type', 'itv')
        category_id = params.get('category_id')

        db = FavDatabase()
        # Hole alle Favoriten der Kategorie
        if category_id is None:
            favorites = db.list_favorites_uncategorized(_type)
        else:
            favorites = db.list_favorites(_type, int(category_id))

        # Finde aktuellen Index
        current_idx = None
        for idx, fav in enumerate(favorites):
            if fav['id'] == video_id and fav['portal_id'] == portal_id:
                current_idx = idx
                break

        if current_idx is not None and current_idx < len(favorites) - 1:
            # Tausche sort_order mit nächstem Element
            curr_fav = favorites[current_idx]
            next_fav = favorites[current_idx + 1]

            db.move_favorite_in_category(curr_fav['id'], curr_fav['portal_id'], _type, current_idx + 1)
            db.move_favorite_in_category(next_fav['id'], next_fav['portal_id'], _type, current_idx)
            xbmc.executebuiltin('Container.Refresh')

    @staticmethod
    def __set_favorite_position(params):
        """Setzt einen Favoriten auf eine bestimmte Position"""
        video_id = params.get('video_id')
        portal_id = int(params.get('portal_id', 1))
        _type = params.get('_type', 'itv')
        category_id = params.get('category_id')
        addon = xbmcaddon.Addon()

        db = FavDatabase()
        # Hole alle Favoriten der Kategorie
        if category_id is None:
            favorites = db.list_favorites_uncategorized(_type)
        else:
            favorites = db.list_favorites(_type, int(category_id))

        max_pos = len(favorites)
        dialog = xbmcgui.Dialog()
        position_str = dialog.input(addon.getLocalizedString(32623) % max_pos, type=xbmcgui.INPUT_NUMERIC)

        if position_str and position_str.isdigit():
            new_pos = int(position_str) - 1  # 0-basiert
            if 0 <= new_pos < max_pos:
                # Finde aktuellen Index
                current_idx = None
                for idx, fav in enumerate(favorites):
                    if fav['id'] == video_id and fav['portal_id'] == portal_id:
                        current_idx = idx
                        break

                if current_idx is not None and current_idx != new_pos:
                    # Verschiebe alle dazwischenliegenden Elemente
                    if new_pos < current_idx:
                        # Nach oben verschieben
                        for i in range(current_idx, new_pos, -1):
                            fav = favorites[i - 1]
                            db.move_favorite_in_category(fav['id'], fav['portal_id'], _type, i)
                    else:
                        # Nach unten verschieben
                        for i in range(current_idx, new_pos):
                            fav = favorites[i + 1]
                            db.move_favorite_in_category(fav['id'], fav['portal_id'], _type, i)

                    # Setze Element auf neue Position
                    db.move_favorite_in_category(video_id, portal_id, _type, new_pos)
                    xbmc.executebuiltin('Container.Refresh')

    @staticmethod
    def __play_video(params):
        """Play video"""
        Logger.debug('Play video {}'.format(params))
        stream_url = Api.get_vod_stream_url(params['video_id'], params['series'], params.get('cmd', ''), params.get('use_cmd', '0'))
        play_item = xbmcgui.ListItem(path=stream_url)
        video_info = play_item.getVideoInfoTag()
        title = params.get('title', '')
        video_info.setTitle(title)
        video_info.setOriginalTitle(title)
        video_info.setMediaType('movie')
        episode_no = get_int_value(params, 'series')
        if episode_no > 0:
            video_info.setEpisode(episode_no)
            video_info.setSeason(get_int_value(params, 'season_no'))
            video_info.setMediaType('episode')
            video_info.setTvShowTitle(title)
        xbmcplugin.setResolvedUrl(G.get_handle(), True, listitem=play_item)

    @staticmethod
    def __play_tv(params):
        """Play TV Channel"""
        Logger.debug('Play TV {}'.format(params))

        cmd = params.get('cmd', '') or ''
        cmd = cmd.strip()

        # 1) Wenn cmd eine direkte URL enthält, spiele sie direkt (verhindert "stream=" Verlust)
        #    Beispiele: "ffmpeg http://.../play/live.php?...&stream=123..."
        direct_url = ''
        if cmd.startswith('ffmpeg '):
            direct_url = cmd[len('ffmpeg '):].strip()
        elif cmd.startswith('http://') or cmd.startswith('https://'):
            direct_url = cmd

        if direct_url.startswith('http'):
            # Wenn es localhost ist, ist es meist nicht direkt erreichbar -> dann via API auflösen
            if 'http://localhost/' not in direct_url:
                play_item = xbmcgui.ListItem(path=direct_url)
                xbmcplugin.setResolvedUrl(G.get_handle(), True, listitem=play_item)
                return

        # 2) Fallback: über Portal-Logik auflösen (tmp-link etc.)
        params.setdefault('use_http_tmp_link', '1')
        params.setdefault('use_load_balancing', '0')
        stream_url = Api.get_tv_stream_url(params)

        play_item = xbmcgui.ListItem(path=stream_url)
        xbmcplugin.setResolvedUrl(G.get_handle(), True, listitem=play_item)

    @staticmethod
    def __list_tv_genres():
        """List the TV channel genres"""
        Logger.debug('List TV Genres')
        category_filter = (G.portal_config.category_filter or xbmcaddon.Addon().getSetting('category_filter')).lower()

        xbmcplugin.setPluginCategory(G.get_handle(), 'TV CHANNELS')
        xbmcplugin.setContent(G.get_handle(), 'videos')

        list_item = xbmcgui.ListItem(label=xbmcaddon.Addon().getLocalizedString(32205))
        list_item.setArt({'thumb': G.get_custom_thumb_path('tv_favorites.png'),
                          'icon': G.get_custom_thumb_path('tv_favorites.png')})
        url = G.get_plugin_url(
            {'action': 'tv_favorites', 'page': 1, 'update_listing': False, 'portal_id': G.active_portal})
        xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)

        # Add a search option
        list_item = xbmcgui.ListItem(label=xbmcaddon.Addon().getLocalizedString(32206))
        list_item.setArt({'thumb': G.get_custom_thumb_path('search.png')})
        url = G.get_plugin_url({'action': 'tv_search', 'fav': 0, 'isContextMenuSearch': False, 'portal_id': G.active_portal}) # neu
        xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)

        genres = Api.get_tv_genres()
        for genre in genres:
            title = genre['title']
            if StalkerAddon.__should_filter(title, category_filter):
                continue

            list_item = xbmcgui.ListItem(label=title.upper())
            fav_url = G.get_plugin_url({'action': 'tv_listing', 'category': genre['title'], 'category_id': genre['id'], 'page': 1,
                                        'update_listing': False, 'search_term': '', 'fav': 1, 'portal_id': G.active_portal})
            search_url = G.get_plugin_url({'action': 'tv_search', 'category': genre['title'], 'category_id': genre['id'], 'fav': 0, 'portal_id': G.active_portal})
            list_item.addContextMenuItems(
                [('Favorites', f'Container.Update({fav_url})'), ('Search', f'RunPlugin({search_url})')])
            url = G.get_plugin_url({'action': 'tv_listing', 'category': genre['title'].upper(), 'category_id': genre['id'], 'page': 1,
                                    'update_listing': False, 'portal_id': G.active_portal})
            xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)
        xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True, updateListing=False, cacheToDisc=False)

    @staticmethod
    def __list_vod_categories():
        """List vod categories"""
        Logger.debug('List VOD Categories')
        category_filter = (G.portal_config.category_filter or xbmcaddon.Addon().getSetting('category_filter')).lower()

        xbmcplugin.setPluginCategory(G.get_handle(), 'VOD')
        xbmcplugin.setContent(G.get_handle(), 'videos')

        list_item = xbmcgui.ListItem(label=xbmcaddon.Addon().getLocalizedString(32203))
        list_item.setArt({'thumb': G.get_custom_thumb_path('vod_favorites.png'),
                          'icon': G.get_custom_thumb_path('vod_favorites.png')})
        url = G.get_plugin_url(
            {'action': 'vod_favorites', 'page': 1, 'update_listing': False, 'portal_id': G.active_portal})
        xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)

        # Add a search option
        list_item = xbmcgui.ListItem(label=xbmcaddon.Addon().getLocalizedString(32207))
        list_item.setArt({'thumb': G.get_custom_thumb_path('search.png')})
        url = G.get_plugin_url({'action': 'vod_search', 'fav': 0, 'isContextMenuSearch': False, 'portal_id': G.active_portal}) # neu
        xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)

        categories = Api.get_vod_categories()
        for category in categories:
            title = category['title']
            if StalkerAddon.__should_filter(title, category_filter):
                continue

            list_item = xbmcgui.ListItem(label=title)
            fav_url = G.get_plugin_url({'action': 'vod_listing', 'category': category['title'], 'category_id': category['id'], 'page': 1,
                                        'update_listing': False, 'search_term': '', 'fav': 1, 'portal_id': G.active_portal})
            search_url = G.get_plugin_url({'action': 'vod_search', 'category': category['title'], 'category_id': category['id'], 'fav': 0, 'portal_id': G.active_portal})
            list_item.addContextMenuItems([('Favorites', f'Container.Update({fav_url})'), ('Search', f'RunPlugin({search_url})')])
            url = G.get_plugin_url({'action': 'vod_listing', 'category': category['title'], 'category_id': category['id'], 'page': 1,
                                    'update_listing': False, 'search_term': '', 'fav': 0, 'portal_id': G.active_portal})
            xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)
        xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True, updateListing=False, cacheToDisc=False)

    @staticmethod
    def __list_series_categories():
        """List series categories"""
        Logger.debug('List Series Categories')
        category_filter = (G.portal_config.category_filter or xbmcaddon.Addon().getSetting('category_filter')).lower()

        xbmcplugin.setPluginCategory(G.get_handle(), 'SERIES')
        xbmcplugin.setContent(G.get_handle(), 'videos')

        list_item = xbmcgui.ListItem(label=xbmcaddon.Addon().getLocalizedString(32204))
        list_item.setArt({'thumb': G.get_custom_thumb_path('series_favorites.png'),
                          'icon': G.get_custom_thumb_path('series_favorites.png')})
        url = G.get_plugin_url(
            {'action': 'series_favorites', 'page': 1, 'update_listing': False, 'portal_id': G.active_portal})
        xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)

        # Add a search option
        list_item = xbmcgui.ListItem(label=xbmcaddon.Addon().getLocalizedString(32208))
        list_item.setArt({'thumb': G.get_custom_thumb_path('search.png')})
        url = G.get_plugin_url({'action': 'series_search', 'fav': 0, 'isContextMenuSearch': False, 'portal_id': G.active_portal}) # neu
        xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)

        categories = Api.get_series_categories()
        for category in categories:
            title = category['title']
            if StalkerAddon.__should_filter(title, category_filter):
                continue

            list_item = xbmcgui.ListItem(label=title)
            fav_url = G.get_plugin_url({'action': 'series_listing', 'category': category['title'], 'category_id': category['id'], 'page': 1,
                                        'update_listing': False, 'search_term': '', 'fav': 1, 'portal_id': G.active_portal})
            search_url = G.get_plugin_url({'action': 'series_search', 'category': category['title'], 'category_id': category['id'], 'fav': 0, 'portal_id': G.active_portal})
            list_item.addContextMenuItems([('Favorites', f'Container.Update({fav_url})'), ('Search', f'RunPlugin({search_url})')])
            url = G.get_plugin_url({'action': 'series_listing', 'category': category['title'], 'category_id': category['id'], 'page': 1,
                                    'update_listing': False, 'search_term': '', 'fav': 0, 'portal_id': G.active_portal})
            xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)
        xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True, updateListing=False, cacheToDisc=False)

    @staticmethod
    def __list_channels(params):
        """List the TV Channels"""
        Logger.debug('List Channels {}'.format(params))

        # WICHTIG: Sicherstellen, dass wir auf dem richtigen Portal sind!
        portal_id = int(params.get('portal_id', G.active_portal))
        G.init_globals(portal_id)

        search_term = params.get('search_term', '')
        page = params['page']
        plugin_category = 'TV - ' + params['category'] if params.get('fav', '0') != '1' else 'TV - ' + params['category'] + ' - FAVORITES'
        xbmcplugin.setPluginCategory(G.get_handle(), plugin_category)
        xbmcplugin.setContent(G.get_handle(), 'videos')
        videos = Api.get_tv_channels(params['category_id'], page, search_term, params.get('fav', 0))
        StalkerAddon.__create_tv_listing(videos, params)

    @staticmethod
    def __prefetch_short_epg_parallel(channel_ids, pool_size=8):
        """
        Lädt short_epg für mehrere Kanäle vor.
        Versucht parallel (ThreadPool), fällt bei fehlender Unterstützung sauber auf sequentiell zurück.
        """
        if not channel_ids:
            return

        # 1) Versuch: multiprocessing.pool.ThreadPool
        try:
            from multiprocessing.pool import ThreadPool  # local import für Plattform-Kompatibilität
            pool = ThreadPool(processes=int(pool_size))
            try:
                pool.map(Api.get_short_epg, channel_ids)
                return
            finally:
                pool.close()
                pool.join()
        except Exception as e:
            Logger.debug(f"EPG prefetch: ThreadPool not available/failed, fallback. Reason: {str(e)}")

        # 2) Versuch: concurrent.futures (falls vorhanden)
        try:
            from concurrent.futures import ThreadPoolExecutor  # local import
            with ThreadPoolExecutor(max_workers=int(pool_size)) as ex:
                futures = [ex.submit(Api.get_short_epg, cid) for cid in channel_ids]
                for f in futures:
                    try:
                        f.result()
                    except Exception:
                        pass
            return
        except Exception as e:
            Logger.debug(f"EPG prefetch: ThreadPoolExecutor not available/failed, fallback. Reason: {str(e)}")

        # 3) Letzter Fallback: sequentiell (funktioniert überall)
        for cid in channel_ids:
            try:
                Api.get_short_epg(cid)
            except Exception:
                pass


    @staticmethod
    def __create_tv_listing(videos, params):
        update_listing = params['update_listing']
        item_count = len(videos['data'])
        directory_items = []

        # Erst prüfen: Haben wir die Daten für diese Sender schon im Speicher dieses Portals?
        # Falls nein, EINMAL kurz laden.
        all_ids = [video['id'] for video in videos['data']]

        # Texte laden
        addon = xbmcaddon.Addon()
        epg_enabled = addon.getSetting('epg_enabled') == 'true'
        text_add = addon.getLocalizedString(32201)
        text_remove = addon.getLocalizedString(32202)

        # Statt get_epg_info (Batch) hier ausschließlich short_epg vorladen
        if epg_enabled:
            try:
                p_id = G.active_portal
                now_ts = time.time()

                # nur Sender laden, die nicht im Cache sind oder deren Cache abgelaufen ist
                to_fetch = []
                for cid in all_ids:
                    ch_id_str = str(cid)
                    cache_entry = None
                    if p_id in G.cache_short_epg and ch_id_str in G.cache_short_epg[p_id]:
                        cache_entry = G.cache_short_epg[p_id][ch_id_str]
                    is_fresh = (
                            isinstance(cache_entry, dict)
                            and (now_ts - cache_entry.get('timestamp', 0)) < 900
                    )
                    if not is_fresh:
                        to_fetch.append(cid)

                # parallelisieren (kleiner Pool, damit Portal/Kodi nicht überfahren wird)
                if to_fetch:
                    try:
                        pool_size = int(addon.getSetting('epg_preload_pool_size') or 8)
                    except Exception:
                        pool_size = 8
                    pool_size = max(4, min(16, pool_size))

                    StalkerAddon.__prefetch_short_epg_parallel(to_fetch, pool_size=pool_size)
            except Exception:
                pass


        for video in videos['data']:
            label = video['name']
            if video.get('fav', 0) == 1:
                label = label + ' ★'

            # Kurzes EPG abrufen - Nur wenn EPG aktiviert ist
            # WICHTIG: Direkter Cache-Zugriff, um KEINE neuen Requests zu machen!
            short_epg = []
            if epg_enabled:
                p_id = G.active_portal
                ch_id_str = str(video['id'])
                if p_id in G.cache_short_epg and ch_id_str in G.cache_short_epg[p_id]:
                    cache_entry = G.cache_short_epg[p_id][ch_id_str]
                    if isinstance(cache_entry, dict) and 'data' in cache_entry:
                        short_epg = cache_entry['data']

            plot = ""
            if short_epg and len(short_epg) > 0:
                now = short_epg[0]
                label = f"{label} - [COLOR orange]{now.get('name', '')}[/COLOR]"
                plot = now.get('descr', '')

            list_item = xbmcgui.ListItem(label, label)
            video_info = list_item.getVideoInfoTag()
            video_info.setPlaycount(0)
            if plot:
                video_info.setPlot(plot)

            list_item.setProperty('IsPlayable', 'true')

            # Kontextmenü erweitern
            context_menu = []
            if video.get('fav', 0) == 1:
                url_fav = G.get_plugin_url({
                    'action': 'remove_fav',
                    'video_id': video['id'],
                    '_type': 'itv',
                    'portal_id': G.active_portal,
                    'title': video.get('name', ''),
                    'logo': video.get('logo', ''),
                    'cmd': video.get('cmd', '')
                })
                context_menu.append((text_remove, f'RunPlugin({url_fav}, False)'))
            else:
                url_fav = G.get_plugin_url({
                    'action': 'add_fav',
                    'video_id': video['id'],
                    '_type': 'itv',
                    'portal_id': G.active_portal,
                    'title': video.get('name', ''),
                    'logo': video.get('logo', ''),
                    'cmd': video.get('cmd', '')
                })
                context_menu.append((text_add, f'RunPlugin({url_fav}, False)'))

            # EPG Action ins Kontextmenü - Nur wenn EPG aktiviert ist
            if epg_enabled:
                url_epg = G.get_plugin_url({
                    'action': 'tv_epg',
                    'channel_id': video['id'],
                    'channel_name': video['name'],
                    'channel_logo': video.get('logo', ''),
                    'portal_id': G.active_portal
                })
                context_menu.append(('EPG', f'Container.Update({url_epg})'))

            list_item.addContextMenuItems(context_menu)

            if 'logo' in video:
                list_item.setArt({'icon': video['logo'], 'thumb': video['logo'], 'clearlogo': video['logo']})

            url = G.get_plugin_url(
                {'action': 'tv_play', 'cmd': video['cmd'], 'use_http_tmp_link': video.get('use_http_tmp_link', 0),
                 'use_load_balancing': video.get('use_load_balancing', 0), 'portal_id': G.active_portal})
            directory_items.append((url, list_item, False))

        total_items = get_int_value(videos, 'total_items')
        if total_items > item_count:
            StalkerAddon.__add_navigation_items(params, videos, directory_items)
            item_count = item_count + 2
        xbmcplugin.addDirectoryItems(G.get_handle(), directory_items, item_count)
        xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True, updateListing=update_listing == 'True',
                                  cacheToDisc=False)

    @staticmethod
    def __list_vod(params):
        """List videos for a category"""
        Logger.debug('List VOD {}'.format(params))
        search_term = params.get('search_term', '')
        plugin_category = 'VOD - ' + params['category'] if params.get('fav', '0') != '1' else 'VOD - ' + params['category'] + ' - FAVORITES'
        xbmcplugin.setPluginCategory(G.get_handle(), plugin_category)
        xbmcplugin.setContent(G.get_handle(), 'videos')
        videos = Api.get_videos(params['category_id'], params['page'], search_term, params.get('fav', 0))
        StalkerAddon.__create_video_listing(videos, params)

    @staticmethod
    def __list_vod_favorites(params):
        """List Favorites Channels"""
        Logger.debug('List VOD Favorites {}'.format(params))
        xbmcplugin.setPluginCategory(G.get_handle(), xbmcaddon.Addon().getLocalizedString(32203))
        xbmcplugin.setContent(G.get_handle(), 'videos')
        videos = Api.get_vod_favorites(params['page'])
        StalkerAddon.__create_video_listing(videos, params)

    @staticmethod
    def __list_series_favorites(params):
        """List Favorites Channels"""
        xbmcplugin.setPluginCategory(G.get_handle(), xbmcaddon.Addon().getLocalizedString(32204))
        xbmcplugin.setContent(G.get_handle(), 'videos')
        series = Api.get_series_favorites(params['page'])
        StalkerAddon.__create_series_listing(series, params)

    @staticmethod
    def __list_tv_favorites(params):
        """List Favorites Channels"""
        Logger.debug('List TV favorites {}'.format(params))
        xbmcplugin.setPluginCategory(G.get_handle(), xbmcaddon.Addon().getLocalizedString(32205))
        xbmcplugin.setContent(G.get_handle(), 'videos')
        videos = Api.get_tv_favorites(params['page'])
        StalkerAddon.__create_tv_listing(videos, params)

    @staticmethod
    def __list_epg(params):
        """List EPG for a specific channel"""
        # WICHTIG: Sicherstellen, dass wir auf dem richtigen Portal sind!
        portal_id = int(params.get('portal_id', G.active_portal))
        G.init_globals(portal_id)

        channel_id = params['channel_id']
        channel_name = params['channel_name']

        # Optional: Senderlogo (kann fehlen, z.B. wenn aus anderen Listen aufgerufen)
        channel_logo = params.get('channel_logo', '') or ''
        channel_logo = StalkerAddon.__normalize_logo_url(channel_logo) if channel_logo else ''

        xbmcplugin.setPluginCategory(G.get_handle(), f'EPG - {channel_name}')
        xbmcplugin.setContent(G.get_handle(), 'files')

        epg_data = Api.get_epg_for_channel(channel_id)

        if not epg_data:
            # Falls keine Daten da sind, zeigen wir einen Info-Eintrag
            list_item = xbmcgui.ListItem(label="Keine EPG Daten verfügbar")
            if channel_logo:
                list_item.setArt({'thumb': channel_logo, 'icon': channel_logo, 'clearlogo': channel_logo})
            xbmcplugin.addDirectoryItem(G.get_handle(), "", list_item, False)
            xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True)
            return

        directory_items = []
        for entry in epg_data:
            if not isinstance(entry, dict):
                continue

            # Zeit auslesen
            raw_start = entry.get('t_time') or entry.get('t_start_show') or entry.get('t_start') or entry.get('start') or ""

            # Wenn es ein Zeitstempel ist (Zahl oder String aus Zahlen), formatieren
            start_display = str(raw_start)
            try:
                # Fall 1: UNIX Timestamp
                if str(raw_start).isdigit() and int(raw_start) > 1000000:
                    start_display = datetime.datetime.fromtimestamp(int(raw_start)).strftime('%H:%M')
                # Fall 2: Volles Datum-String (Y-m-d H:i:s)
                elif " " in str(raw_start) and ":" in str(raw_start):
                    start_display = str(raw_start).split(" ")[1][:5]
            except Exception:
                pass

            # Probiere verschiedene Feldnamen für die Startzeit
            #start = entry.get('t_start_show') or entry.get('t_start') or entry.get('start') or ""
            title = entry.get('name') or entry.get('title') or ""
            descr = entry.get('descr') or entry.get('description') or ""

            label = f"[COLOR orange]{start_display}[/COLOR] {title}"
            list_item = xbmcgui.ListItem(label=label)

            if channel_logo:
                list_item.setArt({'thumb': channel_logo, 'icon': channel_logo, 'clearlogo': channel_logo})

            video_info = list_item.getVideoInfoTag()
            video_info.setTitle(title)
            video_info.setPlot(descr)

            # Wir setzen die URL auf eine Aktion, die nichts tut (kein Fenster, kein Player)
            # 'action': 'none' wird vom Router einfach ignoriert
            url = G.get_plugin_url({'action': 'none', 'portal_id': G.active_portal})

            # In manchen Skins verhindert das den Klick-Effekt
            list_item.setProperty('Selectable', 'false')

            directory_items.append((url, list_item, False))

        xbmcplugin.addDirectoryItems(G.get_handle(), directory_items, len(directory_items))
        xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True)

    @staticmethod
    def __list_series(params):
        """List series"""
        Logger.debug('List TV favorites {}'.format(params))
        search_term = params.get('search_term', '')
        plugin_category = 'SERIES - ' + params['category'] if params.get('fav', '0') != '1' else 'SERIES - ' + params['category'] + ' - FAVORITES'
        xbmcplugin.setPluginCategory(G.get_handle(), plugin_category)
        xbmcplugin.setContent(G.get_handle(), 'videos')
        series = Api.get_series(params['category_id'], params['page'], search_term, params.get('fav', 0))
        StalkerAddon.__create_series_listing(series, params)

    @staticmethod
    def __list_season(params):
        """List season"""
        xbmcplugin.setPluginCategory(G.get_handle(), params['name'])
        xbmcplugin.setContent(G.get_handle(), 'videos')
        seasons = Api.get_seasons(params['video_id'])
        directory_items = []
        for season in seasons['data']:
            label = season['name']
            list_item = xbmcgui.ListItem(label=label, label2=label)
            match = re.match("^Season [0-9]+$", season['name'])
            name = params['name'] + ' ' + season['name']
            if match:
                temp = season['name'].split(' ')
                name = params['name'] + ' S' + temp[-1]
            url = G.get_plugin_url({'action': 'sub_folder', 'video_id': season['id'], 'start': season['series'][0],
                                    'end': season['series'][-1], 'name': name, 'poster_url': params['poster_url'], 'portal_id': G.active_portal}) #neu
            video_info = list_item.getVideoInfoTag()
            video_info.setMediaType('season')
            video_info.setTitle(season['name'])
            video_info.setOriginalTitle(season['name'])
            video_info.setSortTitle(season['name'])
            video_info.setPlot(season.get('description', ''))
            video_info.setPlotOutline(season.get('description', ''))
            actors = [xbmc.Actor(actor) for actor in season['actors'].split(',') if actor]  # pylint: disable=maybe-no-member
            video_info.setCast(actors)
            list_item.setArt({'poster': params['poster_url']})
            directory_items.append((url, list_item, True))
        xbmcplugin.addDirectoryItems(G.get_handle(), directory_items, len(seasons['data']))
        xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True, updateListing=False, cacheToDisc=False)

    @staticmethod
    def __create_video_listing(videos, params):
        """Create paginated listing"""
        update_listing = params['update_listing']
        item_count = len(videos['data'])
        directory_items = []

        addon = xbmcaddon.Addon()
        text_add = addon.getLocalizedString(32201)
        text_remove = addon.getLocalizedString(32202)

        for video in videos['data']:
            label = video['name'] if video.get('hd', 1) == 1 else video['name'] + ' (SD)'
            if video.get('fav', 0) == 1:
                label = label + ' ★'
            list_item = xbmcgui.ListItem(label=label, label2=label)

            poster_url = None
            if 'screenshot_uri' in video and isinstance(video['screenshot_uri'], str):
                if video['screenshot_uri'].startswith('http'):
                    poster_url = video['screenshot_uri']
                else:
                    poster_url = G.portal_config.portal_base_url + video['screenshot_uri']

            if video.get('fav', 0) == 1:
                url = G.get_plugin_url({
                    'action': 'remove_fav',
                    'video_id': video['id'],
                    '_type': 'vod',
                    'portal_id': G.active_portal,
                    'title': video.get('name', ''),
                    'logo': poster_url or '',
                    'cmd': video.get('cmd', ''),
                    'description': video.get('description', '')
                })
                list_item.addContextMenuItems([(text_remove, f'RunPlugin({url}, False)')], replaceItems=False)
            else:
                url = G.get_plugin_url({
                    'action': 'add_fav',
                    'video_id': video['id'],
                    '_type': 'vod',
                    'portal_id': G.active_portal,
                    'title': video.get('name', ''),
                    'logo': poster_url or '',
                    'cmd': video.get('cmd', ''),
                    'description': video.get('description', '')
                })
                list_item.addContextMenuItems([(text_add, f'RunPlugin({url}, False)')], replaceItems=False)

            is_folder = False
            video_info = list_item.getVideoInfoTag()
            if video['series']:
                url = G.get_plugin_url({'action': 'sub_folder', 'video_id': video['id'], 'start': video['series'][0],
                                        'end': video['series'][-1],
                                        'name': video['name'], 'poster_url': poster_url, 'portal_id': G.active_portal})
                is_folder = True
                video_info.setMediaType('season')
            else:
                url = G.get_plugin_url({'action': 'play', 'video_id': video['id'], 'series': 0, 'title': video['name'],
                                        'cmd': video.get('cmd', ''), 'portal_id': G.active_portal})
                time = get_int_value(video, 'time')
                if time != 0:
                    video_info.setDuration(time * 60)
                video_info.setMediaType('movie')
                list_item.setProperty('IsPlayable', 'true')

            video_info.setTitle(video['name'])
            video_info.setOriginalTitle(video['name'])
            video_info.setSortTitle(video['name'])
            if 'country' in video:
                video_info.setCountries([video['country']])
            video_info.setDirectors([video['director']])
            video_info.setPlot(video.get('description', ''))
            video_info.setPlotOutline(video.get('description', ''))
            actors = [xbmc.Actor(actor) for actor in video['actors'].split(',') if
                      actor]  # pylint: disable=maybe-no-member
            video_info.setCast(actors)
            video_info.setLastPlayed(video['last_played'])
            video_info.setDateAdded(video['added'])
            year = get_int_value(video, 'year')
            if year != 0:
                video_info.setYear(year)
            list_item.setArt({'poster': poster_url})
            directory_items.append((url, list_item, is_folder))

        total_items = get_int_value(videos, 'total_items')
        if total_items > item_count:
            StalkerAddon.__add_navigation_items(params, videos, directory_items)
            item_count = item_count + 2
        xbmcplugin.addDirectoryItems(G.get_handle(), directory_items, item_count)
        xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True, updateListing=update_listing == 'True',
                                  cacheToDisc=False)

    @staticmethod
    def __create_series_listing(series, params):
        """Create paginated listing"""
        update_listing = params['update_listing']
        item_count = len(series['data'])
        directory_items = []

        addon = xbmcaddon.Addon()
        text_add = addon.getLocalizedString(32201)
        text_remove = addon.getLocalizedString(32202)

        for video in series['data']:
            label = video['name'] if video.get('hd', 1) == 1 else video['name'] + ' (SD)'
            if video.get('fav', 0) == 1:
                label = label + ' ★'
            list_item = xbmcgui.ListItem(label=label, label2=label)

            poster_url = None
            if 'screenshot_uri' in video and isinstance(video['screenshot_uri'], str):
                if video['screenshot_uri'].startswith('http'):
                    poster_url = video['screenshot_uri']
                else:
                    poster_url = G.portal_config.portal_base_url + video['screenshot_uri']

            if video.get('fav', 0) == 1:
                url = G.get_plugin_url({
                    'action': 'remove_fav',
                    'video_id': video['id'],
                    '_type': 'series',
                    'portal_id': G.active_portal,
                    'title': video.get('name', ''),
                    'logo': poster_url or '',
                    'cmd': video.get('cmd', ''),
                    'description': video.get('description', '')
                })
                list_item.addContextMenuItems([(text_remove, f'RunPlugin({url}, False)')], replaceItems=False)
            else:
                url = G.get_plugin_url({
                    'action': 'add_fav',
                    'video_id': video['id'],
                    '_type': 'series',
                    'portal_id': G.active_portal,
                    'title': video.get('name', ''),
                    'logo': poster_url or '',
                    'cmd': video.get('cmd', ''),
                    'description': video.get('description', '')
                })
                list_item.addContextMenuItems([(text_add, f'RunPlugin({url}, False)')], replaceItems=False)

            video_info = list_item.getVideoInfoTag()
            url = G.get_plugin_url(
                {'action': 'season_listing', 'video_id': video['id'], 'name': video['name'], 'poster_url': poster_url,
                 'portal_id': G.active_portal})
            video_info.setMediaType('season')

            video_info.setTitle(video['name'])
            video_info.setOriginalTitle(video['name'])
            video_info.setSortTitle(video['name'])
            if 'country' in video:
                video_info.setCountries([video['country']])
            video_info.setDirectors([video['director']])
            video_info.setPlot(video.get('description', ''))
            video_info.setPlotOutline(video.get('description', ''))
            actors = [xbmc.Actor(actor) for actor in video['actors'].split(',') if
                      actor]  # pylint: disable=maybe-no-member
            video_info.setCast(actors)
            video_info.setLastPlayed(video['last_played'])
            video_info.setDateAdded(video['added'])
            year = get_int_value(video, 'year')
            if year != 0:
                video_info.setYear(year)
            list_item.setArt({'poster': poster_url})
            directory_items.append((url, list_item, True))

        total_items = get_int_value(series, 'total_items')
        if total_items > item_count:
            StalkerAddon.__add_navigation_items(params, series, directory_items)
            item_count = item_count + 2
        xbmcplugin.addDirectoryItems(G.get_handle(), directory_items, item_count)
        xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True, updateListing=update_listing == 'True',
                                  cacheToDisc=False)

    @staticmethod
    def __add_navigation_items(params, videos, directory_items):
        """Add navigation list items"""
        page = int(params['page'])
        total_items = get_int_value(videos, 'total_items')
        max_page_items = get_int_value(videos, 'max_page_items')
        total_pages = int(math.ceil(float(total_items) / float(max_page_items)))
        _max_page_limit = G.addon_config.max_page_limit
        if _max_page_limit > 1:
            total_pages = total_pages if (total_pages % _max_page_limit) == 0 else total_pages + _max_page_limit - (
                    total_pages % _max_page_limit)

        # Lokalisierung für "Letzte Seite" und "Vorherige Seite"
        last_page_label = f"<< {G._GlobalVariables__addon.getLocalizedString(32413)}"
        prev_page_label = f"<< {G._GlobalVariables__addon.getLocalizedString(32414)}"
        label = last_page_label if page == 1 else prev_page_label

        list_item = xbmcgui.ListItem(label)
        list_item.setArt({'thumb': G.get_custom_thumb_path('pagePrevious.png')})
        list_item.setProperty('specialsort', 'top')
        prev_page = total_pages - _max_page_limit + 1 if page == 1 else page - _max_page_limit
        params.update({'page': prev_page, 'update_listing': True})
        url = G.get_plugin_url(params)
        directory_items.insert(0, (url, list_item, True))

        # Lokalisierung für "Erste Seite" und "Nächste Seite"
        first_page_label = f"{G._GlobalVariables__addon.getLocalizedString(32415)} >>"
        next_page_label = f"{G._GlobalVariables__addon.getLocalizedString(32416)} >>"
        label = first_page_label if page == total_pages - _max_page_limit + 1 else next_page_label

        list_item = xbmcgui.ListItem(label)
        list_item.setArt({'thumb': G.get_custom_thumb_path('pageNext.png')})
        list_item.setProperty('specialsort', 'bottom')
        next_page = 1 if page == total_pages - _max_page_limit + 1 else page + _max_page_limit
        params.update({'page': next_page, 'update_listing': True})
        url = G.get_plugin_url(params)
        directory_items.append((url, list_item, True))

    @staticmethod
    def __list_episodes(params):
        """List episodes for a series"""
        name = params['name']
        xbmcplugin.setPluginCategory(G.get_handle(), name)
        xbmcplugin.setContent(G.get_handle(), 'videos')
        temp = name.split(' ')
        match = re.match("^S[0-9]+$", temp[-1])
        season = None
        if match:
            season = int(match.string[1:])
            name = ' '.join(temp[:-1])
        start = get_int_value(params, 'start')
        end = get_int_value(params, 'end')
        for episode_no in range(start, end + 1):
            list_item = xbmcgui.ListItem(label='Episode ' + str(episode_no))
            video_info = list_item.getVideoInfoTag()
            video_info.setTitle(name)
            video_info.setOriginalTitle(name)
            if match:
                video_info.setEpisode(episode_no)
                video_info.setSeason(season)
                video_info.setSortSeason(season)
                video_info.setMediaType('episode')
                video_info.setTvShowTitle(name)
            else:
                video_info.setMediaType('movie')
            list_item.setProperties({'IsPlayable': 'true'})
            list_item.setArt({'poster': params['poster_url']})
            url = G.get_plugin_url({'action': 'play', 'video_id': params['video_id'], 'series': episode_no, 'season_no': season,
                                    'title': name, 'total_episodes': end, 'poster_url': params['poster_url'], 'portal_id': G.active_portal}) # neu
            xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, False)
        xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True, updateListing=False, cacheToDisc=False)

    def __search_vod(self, params):
        """Search for videos"""
        Logger.debug('Search VOD {}'.format(params))

        # If the category is missing, show the category selection popup
        if not params.get('category'):
            categories = Api.get_vod_categories()
            selected_category = ask_for_category_selection(categories,
                                                           G._GlobalVariables__addon.getLocalizedString(32417))
            if not selected_category:
                # User cancelled category selection - end directory properly
                xbmcplugin.endOfDirectory(G.get_handle(), succeeded=False, updateListing=False, cacheToDisc=False)
                return
            params.update({
                'category': selected_category['title'],
                'category_id': selected_category['id']
            })

        search_term = ask_for_input(params['category'])
        if search_term:
            params.update({'action': 'vod_listing', 'update_listing': False, 'search_term': search_term, 'page': 1})
            is_context = str(params.get('isContextMenuSearch', 'true')).lower() == 'true'
            if is_context:
                url = G.get_plugin_url(params)
                func_str = f'Container.Update({url})'
                xbmc.executebuiltin(func_str)
            else:
                self.__list_vod(params)

    @staticmethod
    def __search_series(params):
        """Search for series"""

        # If the category is missing, show the category selection popup
        if not params.get('category'):
            categories = Api.get_series_categories()
            selected_category = ask_for_category_selection(categories,
                                                           G._GlobalVariables__addon.getLocalizedString(32418))
            if not selected_category:
                # User cancelled category selection - end directory properly
                xbmcplugin.endOfDirectory(G.get_handle(), succeeded=False, updateListing=False, cacheToDisc=False)
                return
            params.update({
                'category': selected_category['title'],
                'category_id': selected_category['id']
            })

        search_term = ask_for_input(params['category'])
        if search_term:
            params.update({'action': 'series_listing', 'update_listing': False, 'search_term': search_term, 'page': 1})
            url = G.get_plugin_url(params)
            func_str = f'Container.Update({url})'
            xbmc.executebuiltin(func_str)

    def __search_tv(self, params):
        """Search for videos"""

        # If the category is missing, show the category selection popup
        if not params.get('category'):
            genres = Api.get_tv_genres()
            selected_genre = ask_for_category_selection(genres, G._GlobalVariables__addon.getLocalizedString(32419))
            if not selected_genre:
                # User cancelled category selection - end directory properly
                xbmcplugin.endOfDirectory(G.get_handle(), succeeded=False, updateListing=False, cacheToDisc=False)
                return
            params.update({
                'category': selected_genre['title'],
                'category_id': selected_genre['id']
            })

        search_term = ask_for_input(params['category'])
        if search_term:
            params.update({'action': 'tv_listing', 'update_listing': False, 'search_term': search_term, 'page': 1})
            is_context = str(params.get('isContextMenuSearch', 'true')).lower() == 'true'
            if is_context:
                url = G.get_plugin_url(params)
                func_str = f'Container.Update({url})'
                xbmc.executebuiltin(func_str)
            else:
                self.__list_channels(params)

    def __list_portal_content(self):
        """Zeigt die Inhalte (TV, VOD, Serien) für das aktuell gewählte Portal an"""
        # Erst hier ist es sicher, die API aufzurufen, da G.portal_config geladen ist

        # TV CHANNELS
        list_item = xbmcgui.ListItem(label='TV CHANNELS')
        url = G.get_plugin_url({'action': 'tv', 'page': 1, 'update_listing': False, 'portal_id': G.active_portal})
        xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)

        # VOD
        list_item = xbmcgui.ListItem(label='VOD')
        url = G.get_plugin_url({'action': 'vod', 'page': 1, 'update_listing': False, 'portal_id': G.active_portal})
        xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)

        # SERIES - Wir prüfen hier, ob das Portal Serien unterstützt
        try:
            series_categories = Api.get_series_categories()
            if isinstance(series_categories, list) and len(series_categories) > 0:
                list_item = xbmcgui.ListItem(label='SERIES')
                url = G.get_plugin_url(
                    {'action': 'series', 'page': 1, 'update_listing': False, 'portal_id': G.active_portal})
                xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)
        except Exception:
            Logger.debug("Portal does not support series or connection failed")

        xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True, updateListing=False, cacheToDisc=False)

    @staticmethod
    def __list_main_menu():
        """Das neue Startmenü zur Auswahl der Portale (aus JSON)"""
        import xbmcaddon
        addon = xbmcaddon.Addon()

        # Globale Favoriten (außerhalb der Portale)
        list_item = xbmcgui.ListItem(label=f"[COLOR white]{addon.getLocalizedString(32205)}[/COLOR]")
        list_item.setArt({'thumb': G.get_custom_thumb_path('tv_favorites.png'),
                          'icon': G.get_custom_thumb_path('tv_favorites.png')})
        url = G.get_plugin_url({'action': 'local_favorites', '_type': 'itv', 'portal_id': 1})
        xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)

        list_item = xbmcgui.ListItem(label=f"[COLOR white]{addon.getLocalizedString(32203)}[/COLOR]")
        list_item.setArt({'thumb': G.get_custom_thumb_path('vod_favorites.png'),
                          'icon': G.get_custom_thumb_path('vod_favorites.png')})
        url = G.get_plugin_url({'action': 'local_favorites', '_type': 'vod', 'portal_id': 1})
        xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)

        list_item = xbmcgui.ListItem(label=f"[COLOR white]{addon.getLocalizedString(32204)}[/COLOR]")
        list_item.setArt({'thumb': G.get_custom_thumb_path('series_favorites.png'),
                          'icon': G.get_custom_thumb_path('series_favorites.png')})
        url = G.get_plugin_url({'action': 'local_favorites', '_type': 'series', 'portal_id': 1})
        xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)

        # ── Separator before PORTALS ──
        sep_item = xbmcgui.ListItem(label=f"[COLOR gray]{'─' * 40}[/COLOR]")
        sep_item.setArt({'icon': 'DefaultAddon.png', 'thumb': 'DefaultAddon.png'})
        xbmcplugin.addDirectoryItem(G.get_handle(), '', sep_item, False)

        # Portale aus JSON laden
        portals = G.get_available_portals()
        is_error = False

        if not portals:
            # Keine Portale konfiguriert -> Info-Eintrag anzeigen
            list_item = xbmcgui.ListItem(label=f"[COLOR orange]{addon.getLocalizedString(32315)}[/COLOR]")
            list_item.setArt({'thumb': G.get_custom_thumb_path('settings.png')})
            url = G.get_plugin_url({'action': 'open_settings'})
            xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, False)
        else:
            # Portale-Header
            header_label = f"[COLOR skyblue]{addon.getLocalizedString(32314)}[/COLOR]"
            header_item = xbmcgui.ListItem(label=header_label)
            header_item.setArt({'icon': 'DefaultAddonPVR.png', 'thumb': 'DefaultAddonPVR.png'})
            xbmcplugin.addDirectoryItem(G.get_handle(), '', header_item, False)

            for portal in portals:
                portal_id = int(portal.get('id', 0))
                portal_name = portal.get('name', '')
                server_url = portal.get('server_address', '')

                if portal_name:
                    label = portal_name
                elif server_url:
                    label = server_url
                else:
                    label = f'Portal {portal_id}'

                # Prüfe auf Fehler-Status (aus portal_error Setting)
                suffix = '' if portal_id == 1 else f'_{portal_id}'
                try:
                    is_error = addon.getSetting(f'portal_error{suffix}') == 'true'
                except Exception:
                    is_error = False

                # Wenn Token-Fehler beim letzten Versuch -> rot einfärben
                if is_error:
                    label = f"[COLOR orangered]{label}[/COLOR]"
                else:
                    label = f"[COLOR white]{label}[/COLOR]"

                list_item = xbmcgui.ListItem(label=label)

                portal_icon = G.get_custom_thumb_path(f'iptv_portal_{portal_id}.png')
                list_item.setArt({'thumb': portal_icon, 'icon': portal_icon})

                url = G.get_plugin_url({'action': 'select_portal', 'portal_id': portal_id})
                xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)

            # ── Separator after PORTALS ──
            sep_item = xbmcgui.ListItem(label=f"[COLOR gray]{'─' * 40}[/COLOR]")
            sep_item.setArt({'icon': 'DefaultAddon.png', 'thumb': 'DefaultAddon.png'})
            xbmcplugin.addDirectoryItem(G.get_handle(), '', sep_item, False)

        # Einstellungen & Backup
        settings_label = f"[COLOR lightgreen]{addon.getLocalizedString(32209)}[/COLOR]"
        list_item = xbmcgui.ListItem(label=settings_label)
        list_item.setArt({'thumb': G.get_custom_thumb_path('settings.png')})
        url = G.get_plugin_url({'action': 'open_settings'})
        xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, False)

        list_item = xbmcgui.ListItem(label=f"[COLOR powderblue]{addon.getLocalizedString(32401)}[/COLOR]")
        list_item.setArt({'thumb': G.get_custom_thumb_path('backup_create.png')})
        url = G.get_plugin_url({'action': 'backup_settings'})
        xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)

        list_item = xbmcgui.ListItem(label=f"[COLOR powderblue]{addon.getLocalizedString(32402)}[/COLOR]")
        list_item.setArt({'thumb': G.get_custom_thumb_path('backup_restore.png')})
        url = G.get_plugin_url({'action': 'restore_settings'})
        xbmcplugin.addDirectoryItem(G.get_handle(), url, list_item, True)

        xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True, updateListing=False, cacheToDisc=False)

    def router(self, param_string):
        """Route calls"""
        params = dict(parse_qsl(param_string))

        portal_id = params.get('portal_id', 1)
        G.init_globals(portal_id)

        # Lokale Favoriten DB: verwaiste/ausgetauschte Portale bereinigen
        try:
            FavDatabase().cleanup_orphaned_or_changed_portals(max_portals=10)
        except Exception as e:
            Logger.error(f"SQLite favorites cleanup in router failed: {str(e)}")

        if params and 'action' in params:
            if params['action'] == 'tv':
                self.__list_tv_genres()
            elif params['action'] == 'vod':
                self.__list_vod_categories()
            elif params['action'] == 'series':
                self.__list_series_categories()
            elif params['action'] == 'vod_favorites':
                self.__list_vod_favorites(params)
            elif params['action'] == 'series_favorites':
                self.__list_series_favorites(params)
            elif params['action'] == 'tv_favorites':
                self.__list_tv_favorites(params)
            elif params['action'] == 'local_favorites':
                _type = params.get('_type', 'vod')
                addon = xbmcaddon.Addon()
                use_categories = addon.getSetting('global_fav_use_categories') == 'true'
                group_by_portal = addon.getSetting('global_fav_group_by_portal') == 'true'

                if use_categories:
                    self.__list_local_favorites_with_categories(_type)
                elif group_by_portal:
                    self.__list_local_favorites_portals(_type)
                else:
                    self.__list_local_favorites(_type)
            elif params['action'] == 'local_favorites_portals':
                self.__list_local_favorites_portals(params.get('_type', 'vod'))
            elif params['action'] == 'local_favorites_portal':
                self.__list_local_favorites_for_portal(
                    params.get('_type', 'vod'),
                    int(params.get('portal_id', 1))
                )
            elif params['action'] == 'local_favorites_category':
                self.__list_local_favorites_in_category(
                    params.get('_type', 'vod'),
                    int(params.get('category_id', 0))
                )
            elif params['action'] == 'create_category':
                self.__create_category(params)
            elif params['action'] == 'rename_category':
                self.__rename_category(params)
            elif params['action'] == 'delete_category':
                self.__delete_category(params)
            elif params['action'] == 'assign_to_category':
                self.__assign_to_category(params)
            elif params['action'] == 'remove_from_category':
                self.__remove_from_category(params)
            elif params['action'] == 'move_favorite_up':
                self.__move_favorite_up(params)
            elif params['action'] == 'move_favorite_down':
                self.__move_favorite_down(params)
            elif params['action'] == 'set_favorite_position':
                self.__set_favorite_position(params)
            elif params['action'] == 'tv_listing':
                self.__list_channels(params)
            elif params['action'] == 'tv_epg':
                self.__list_epg(params)
            elif params['action'] == 'vod_listing':
                self.__list_vod(params)
            elif params['action'] == 'series_listing':
                self.__list_series(params)
            elif params['action'] == 'season_listing':
                self.__list_season(params)
            elif params['action'] == 'sub_folder':
                self.__list_episodes(params)
            elif params['action'] == 'play':
                self.__play_video(params)
            elif params['action'] == 'tv_play':
                self.__play_tv(params)
            elif params['action'] == 'vod_search':
                self.__search_vod(params)
            elif params['action'] == 'series_search':
                self.__search_series(params)
            elif params['action'] == 'tv_search':
                self.__search_tv(params)
            elif params['action'] == 'remove_fav':
                self.__toggle_favorites(params, add=False)
            elif params['action'] == 'add_fav':
                self.__toggle_favorites(params, add=True)
            elif params['action'] == 'select_portal':
                self.__list_portal_content()
            elif params['action'] == 'open_settings':
                xbmcaddon.Addon().openSettings()
            elif params['action'] == 'backup_settings':
                xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True)
                from .utils import backup_settings
                backup_settings()
                return
            elif params['action'] == 'restore_settings':
                xbmcplugin.endOfDirectory(G.get_handle(), succeeded=True)
                from .utils import restore_settings
                restore_settings()
                return
            elif params['action'] == 'none':
                return
            else:
                raise ValueError('Invalid param string: {}!'.format(param_string))
        else:
            self.__list_main_menu()

def run(argv):
    """Run"""
    #G.init_globals()
    stalker_addon = StalkerAddon()
    stalker_addon.router(argv[2][1:])
