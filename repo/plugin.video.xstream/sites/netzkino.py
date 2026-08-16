# -*- coding: utf-8 -*-
# Python 3
# Always pay attention to the translations in the menu!
# Seite vollständig mit JSON erstellt (Next.js __NEXT_DATA__)
# Browse (Hauptseite/Neu/Highlights/Genres): __NEXT_DATA__ JSON der Website
# Suche: simplecache-API (liefert custom_fields mit Stream)
# HTML LangzeitCache:
# showEntries:   6 Stunden
# showSearch:    keine (live)


import json
import re

import xbmcgui
from resources.lib.handler.parameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.logger import logger
from resources.lib.tools import cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui

SITE_IDENTIFIER = 'netzkino'
SITE_NAME = 'NetzKino'
SITE_ICON = 'netzkino.png'

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'netzkino.de') # Domain Auswahl über die xStream Einstellungen möglich
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht

URL_MAIN = 'https://' + DOMAIN + '/'
# Frontpage (featured Filme der Startseite)
URL_FRONTPAGE = URL_MAIN
# Kategorie-Listing nach Slug (Neu, Highlights, einzelne Genres ...)
URL_CATEGORY = URL_MAIN + 'kategorie/%s'
# Genre-Übersicht (liefert die einzelnen Genre-Kategorien)
URL_GENRE = URL_MAIN + 'genre'
# Film-Detailseite nach Slug (liefert MovieDetails mit videoSource.pmdUrl)
URL_DETAIL = URL_MAIN + 'details/%s'
# Suche über die simplecache-API (liefert custom_fields mit Stream)
URL_SEARCH = 'https://api.netzkino.de.simplecache.net/capi-2.0a/search?q=%s&d=www&l=de-DE'
# Stream-Host (pmdUrl wird angehängt)
URL_STREAM = 'https://pmd.netzkino-seite.netzkino.de/'


def load(): # Menu structure of the site plugin
    logger.info('Load %s' % SITE_NAME)
    xbmcgui.Window(10000).clearProperty('xstream.netzkino.lastSearchText')
    # Hauptseite (Startseite mit den Kategorie-Reihen)
    cGui().addFolder(cGuiElement('Hauptseite', SITE_IDENTIFIER, 'showStart'))
    # Genres (dynamisch)
    cGui().addFolder(cGuiElement('Genres', SITE_IDENTIFIER, 'showGenres'))
    # Suche
    cGui().addFolder(cGuiElement('Suche', SITE_IDENTIFIER, 'showSearch'))
    cGui().setEndOfDirectory()


def showStart():
    # Startseite: listet die Kategorie-Reihen der Frontpage (Neu, Highlights, Actionfilme ...)
    oGui = cGui()
    params = ParameterHandler()
    oNext = _getNextData(URL_FRONTPAGE)
    data = _findQuery(oNext, 'AllContent') if oNext else None
    nodes = []
    if data:
        try:
            nodes = data['parentCategory']['subcategories']['nodes']
        except (KeyError, TypeError):
            nodes = []
    if not nodes:
        oGui.showInfo()
        return
    for cat in nodes:
        sTitle = str(cat.get('title') or '')
        sSlug = cat.get('slug') or ''
        if not sTitle or not sSlug:
            continue
        params.setParam('sUrl', URL_CATEGORY % sSlug)
        oGui.addFolder(cGuiElement(sTitle, SITE_IDENTIFIER, 'showEntries'), params)
    oGui.setEndOfDirectory()


def _getNextData(sUrl, sGui=False):
    # Holt das __NEXT_DATA__-JSON einer Netzkino-Seite und gibt das geparste dict zurück (oder None).
    # URL absichern: Slugs können Nicht-ASCII enthalten (z.B. "Teenie-Komödien-frontpage" mit ö).
    # Der ParameterHandler dekodiert eingehende sUrl via parse_qsl wieder zu rohem ö -> hier am
    # Request-Rand percent-encoden, sonst crasht http.client beim request.encode('ascii').
    sUrl = cParser.urlEncode(sUrl, "%:/?#[]@!$&'()*+,;=~")  # nur Nicht-ASCII kodieren, %XX/Struktur unberührt
    oRequest = cRequestHandler(sUrl, ignoreErrors=(sGui is not False))
    oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    sHtmlContent = oRequest.request()
    isMatch, sJson = cParser.parseSingleResult(sHtmlContent, r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>')
    if not isMatch:
        return None
    try:
        return json.loads(sJson)
    except ValueError:
        return None


def _findQuery(oNext, sQueryName):
    # Sucht in __dehydratedState.queries nach der ersten Query mit passendem Namen und gibt deren state.data.data zurück.
    try:
        queries = oNext['props']['__dehydratedState']['queries']
    except (KeyError, TypeError):
        return None
    for q in queries:
        key = q.get('queryKey') or []
        if key and key[0] == sQueryName:
            try:
                return q['state']['data']['data']
            except (KeyError, TypeError):
                return None
    return None


def _getMovieNodes(oNext):
    # Liefert die Film-Nodes einer Seite, egal ob Frontpage (AllContent.featured.content)
    # oder Kategorie (CategoryDataBySlug.category.content).
    data = _findQuery(oNext, 'CategoryDataBySlug')
    if data:
        try:
            return data['category']['content']['nodes']
        except (KeyError, TypeError):
            pass
    data = _findQuery(oNext, 'AllContent')
    if data:
        try:
            return data['featured']['content']['nodes']
        except (KeyError, TypeError):
            pass
    return []


def _imageUrl(oMovie, *keys):
    # Gibt die masterUrl des ersten vorhandenen Bild-Feldes zurück.
    for k in keys:
        img = oMovie.get(k)
        if isinstance(img, dict) and img.get('masterUrl'):
            return img['masterUrl']
    return ''


def showEntries(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl:
        entryUrl = params.getValue('sUrl')
    oNext = _getNextData(entryUrl, sGui)
    if not oNext:
        if not sGui: oGui.showInfo()
        return
    nodes = _getMovieNodes(oNext)
    if not nodes:
        if not sGui: oGui.showInfo()
        return

    total = len(nodes)
    for node in nodes:
        try:
            movie = node.get('contentMovie')
            if not movie:
                continue  # contentSeries o.ä. überspringen (Netzkino = Filme)
            sSlug = movie.get('slug') or ''
            if not sSlug:
                continue  # ohne Slug keine Detailseite abrufbar
            sTitle = str(movie.get('title') or '')
            if sSearchText and not cParser.search(sSearchText, sTitle):
                continue
            oGuiElement = cGuiElement(sTitle, SITE_IDENTIFIER, 'showHosters')
            oGuiElement.setMediaType('movie')
            sThumb = _imageUrl(movie, 'coverImage', 'widescreenImage', 'headerImage')
            if sThumb:
                oGuiElement.setThumbnail(sThumb)
            sFanart = _imageUrl(movie, 'widescreenImage', 'headerImage', 'coverImage')
            if sFanart:
                oGuiElement.setFanart(sFanart)
            if movie.get('longSynopsis') or movie.get('shortSynopsis'):
                oGuiElement.setDescription(str(movie.get('longSynopsis') or movie.get('shortSynopsis')))
            if movie.get('productionYear'):
                oGuiElement.setYear(str(movie.get('productionYear')))
            # Slug an showHosters -> dort wird die Detailseite fuer die pmdUrl geladen
            params.setParam('sSlug', sSlug)
            params.setParam('mediaType', 'movie')
            oGui.addFolder(oGuiElement, params, False, total)
        except Exception:
            continue

    if not sGui:
        oGui.setView('movies')
        oGui.setEndOfDirectory()


def showGenres():
    oGui = cGui()
    params = ParameterHandler()
    oNext = _getNextData(URL_GENRE)
    data = _findQuery(oNext, 'AllContent') if oNext else None
    nodes = []
    if data:
        try:
            nodes = data['parentCategory']['subcategories']['nodes']
        except (KeyError, TypeError):
            nodes = []
    if not nodes:
        oGui.showInfo()
        return
    for cat in nodes:
        sTitle = str(cat.get('title') or '')
        sSlug = cat.get('slug') or ''
        if not sTitle or not sSlug:
            continue
        params.setParam('sUrl', URL_CATEGORY % sSlug)
        params.setParam('sMode', 'category')
        oGui.addFolder(cGuiElement(sTitle, SITE_IDENTIFIER, 'showEntries'), params)
    oGui.setEndOfDirectory()


def showHosters():
    hosters = []
    params = ParameterHandler()
    sSlug = params.getValue('sSlug')
    # Direkter Stream (z.B. aus der Suche) hat Vorrang
    sDirect = params.getValue('entryUrl')
    if sDirect:
        for sUrl in sDirect.split('#'):
            if not sUrl:
                continue
            sName = 'Netzkino' if 'netzkino' in sUrl else 'Youtube'
            hosters.append({'link': sUrl, 'name': sName, 'resolveable': True})
        if hosters:
            hosters.append('getHosterUrl')
        return hosters
    # Sonst: Detailseite per Slug laden und pmdUrl ziehen
    if sSlug:
        oNext = _getNextData(URL_DETAIL % sSlug)
        data = _findQuery(oNext, 'MovieDetails') if oNext else None
        if data:
            movie = data.get('movie') or {}
            vs = movie.get('videoSource') or {}
            pmdUrl = vs.get('pmdUrl') or ''
            if pmdUrl:
                # Next.js-pmdUrl enthaelt bereits die Dateiendung -> direkt anhaengen
                # Pfad kann Leerzeichen enthalten (z.B. "OneGate Media/...") -> kodieren, / behalten
                hosters.append({'link': URL_STREAM + cParser.urlEncode(pmdUrl, safe='/'), 'name': 'Netzkino', 'resolveable': True})
    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def getHosterUrl(sUrl=False):
    return [{'streamUrl': sUrl, 'resolved': True}]


def showSearch():
    win = xbmcgui.Window(10000)
    sSearchText = win.getProperty('xstream.netzkino.lastSearchText')
    if not sSearchText:
        sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30287))
        if not sSearchText:
            return
        win.setProperty('xstream.netzkino.lastSearchText', sSearchText)
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    _showSearchEntries(URL_SEARCH % cParser.quotePlus(sSearchText), oGui, sSearchText)


def _showSearchEntries(entryUrl, sGui=False, sSearchText=False):
    # Suche läuft über die simplecache-API (anderes JSON-Format als die Website).
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    sResponse = oRequest.request()
    if not sResponse:
        if not sGui: oGui.showInfo()
        return
    try:
        jSearch = json.loads(sResponse)
    except ValueError:
        if not sGui: oGui.showInfo()
        return
    if not jSearch or 'posts' not in jSearch or len(jSearch['posts']) == 0:
        if not sGui: oGui.showInfo()
        return

    total = len(jSearch['posts'])
    for item in jSearch['posts']:
        try:
            sTitle = str(item['title'])
            cf = item.get('custom_fields') or {}
            sStreaming = ''
            if cf.get('Streaming') and cf['Streaming'][0]:
                sStreaming = cf['Streaming'][0]
            sYoutube = ''
            if cf.get('Youtube_Delivery_Id') and cf['Youtube_Delivery_Id'][0]:
                sYoutube = cf['Youtube_Delivery_Id'][0]
            if not sStreaming and not sYoutube:
                continue
            oGuiElement = cGuiElement(sTitle, SITE_IDENTIFIER, 'showHosters')
            oGuiElement.setMediaType('movie')
            if item.get('thumbnail'):
                oGuiElement.setThumbnail(str(item['thumbnail']))
            if item.get('content'):
                oGuiElement.setDescription(str(item['content']))
            if cf.get('featured_img_all') and cf['featured_img_all'][0]:
                oGuiElement.setFanart(str(cf['featured_img_all'][0]))
            if cf.get('Jahr') and cf['Jahr'][0]:
                oGuiElement.setYear(str(cf['Jahr'][0]))
            if cf.get('Adaptives_Streaming') and cf['Adaptives_Streaming'][0]:
                oGuiElement.setQuality(str(cf['Adaptives_Streaming'][0]))
            urls = ''
            if sStreaming:
                # Alte API liefert pmdUrl OHNE .mp4 -> hier anhängen
                # Pfad kann Leerzeichen enthalten -> kodieren, / behalten, .mp4 danach
                urls += URL_STREAM + cParser.urlEncode(sStreaming, safe='/') + '.mp4'
            if sYoutube:
                urls += ('#' if urls else '') + 'plugin://plugin.video.youtube/play/?video_id=%s' % sYoutube
            params.setParam('entryUrl', urls)
            params.setParam('mediaType', 'movie')
            oGui.addFolder(oGuiElement, params, False, total)
        except Exception:
            continue

    if not sGui:
        oGui.setView('movies')
        oGui.setEndOfDirectory()
