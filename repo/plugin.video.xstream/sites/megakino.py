# -*- coding: utf-8 -*-
# Python 3
# Always pay attention to the translations in the menu!
# HTML LangzeitCache hinzugefuegt
# showGenre/Collection: 48 Stunden
# showEntries:    6 Stunden
# showEpisodes:   4 Stunden

import re
import xbmcgui

from resources.lib.handler.parameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.logger import logger
from resources.lib.tools import cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui


SITE_IDENTIFIER = 'megakino'
SITE_NAME = 'Megakino'
SITE_ICON = 'megakino.png'

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'megakino11.com')
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status')
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER)

URL_MAIN = 'https://' + DOMAIN + '/'
URL_KINO = URL_MAIN + 'kinofilme/'
URL_MOVIES = URL_MAIN + 'films/'
URL_SERIES = URL_MAIN + 'serials/'


def load():  # Menu structure of the site plugin
    logger.info('Load %s' % SITE_NAME)
    xbmcgui.Window(10000).clearProperty('xstream.megakino.lastSearchText')
    params = ParameterHandler()
    params.setParam('sUrl', URL_KINO)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30501), SITE_IDENTIFIER, 'showEntries'), params)  # Aktuelle Releases
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30500), SITE_IDENTIFIER, 'showLatest'))  # Neues / Zuletzt hinzugefuegt
    params.setParam('sUrl', URL_MOVIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30502), SITE_IDENTIFIER, 'showEntries'), params)  # Filme
    params.setParam('sUrl', URL_SERIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511), SITE_IDENTIFIER, 'showEntries'), params)  # Serien
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showGenre'))  # Genre
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30543), SITE_IDENTIFIER, 'showCollection'))  # Sammlung
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'))  # Suche
    cGui().setEndOfDirectory()


def getHtmlContent(url):
    """Hilfsfunktion zum Abrufen von HTML-Inhalten mit yg_token Cookie-Bypass.
    Megakino liefert bei erstem Hit ein JS-Stub das einen Token-Endpoint hittet.
    Token setzt Cookie, bei zweitem Request kommt echtes HTML.

    UA-Sticky: Alle 3 Requests im Token-Flow MUESSEN identischen UA nutzen
    (Cookie an UA gebunden, Anti-Bot prueft UA-Konsistenz zwischen Token+HTML).
    Drum einmal RandomUA() aufrufen und an alle 3 Requests weitergeben.
    """
    sessionUA = cRequestHandler.RandomUA()
    oRequest = cRequestHandler(url)
    oRequest.cacheTime = 0
    oRequest.addHeaderEntry('User-Agent', sessionUA)
    oRequest.addHeaderEntry('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')
    oRequest.addHeaderEntry('Accept-Language', 'de-DE,de;q=0.9,en;q=0.8')
    oRequest.addHeaderEntry('Referer', URL_MAIN)
    sHtmlContent = oRequest.request()

    # Token-Stub erkannt -> Token holen + Original-URL retry
    if sHtmlContent and 'yg=token' in sHtmlContent and len(sHtmlContent) < 1000:
        logger.info('[megakino] Token-Stub erkannt, hole Token...')
        oTokenRequest = cRequestHandler(URL_MAIN + 'index.php?yg=token')
        oTokenRequest.cacheTime = 0
        oTokenRequest.addHeaderEntry('User-Agent', sessionUA)
        oTokenRequest.addHeaderEntry('Accept', '*/*')
        oTokenRequest.addHeaderEntry('Accept-Language', 'de-DE,de;q=0.9,en;q=0.8')
        oTokenRequest.addHeaderEntry('Referer', url)
        oTokenRequest.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
        oTokenRequest.request()

        # Original-URL nochmal abrufen mit Cookie
        oRequest2 = cRequestHandler(url)
        oRequest2.cacheTime = 0
        oRequest2.addHeaderEntry('User-Agent', sessionUA)
        oRequest2.addHeaderEntry('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')
        oRequest2.addHeaderEntry('Accept-Language', 'de-DE,de;q=0.9,en;q=0.8')
        oRequest2.addHeaderEntry('Referer', URL_MAIN)
        sHtmlContent = oRequest2.request()

    return sHtmlContent if sHtmlContent and len(sHtmlContent) > 1000 else None


def showGenre():
    params = ParameterHandler()
    sHtmlContent = getHtmlContent(URL_MAIN)
    if not sHtmlContent:
        cGui().showInfo()
        return

    # Sidebar: <div class="side-block__title">Genres</div>...<ul class="side-block__content side-block__menu">...</ul>
    pattern = r'<div class="side-block__title">Genres</div>.*?<ul class="side-block__content side-block__menu"(.*?)</ul>'
    isMatch, sContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if not isMatch:
        cGui().showInfo()
        return

    pattern = r'href="([^"]+)">([^<]+)</a>'
    isMatch, aResult = cParser.parse(sContainer, pattern)
    if not isMatch:
        cGui().showInfo()
        return

    for sUrl, sName in aResult:
        if sUrl.startswith('/'):
            sUrl = URL_MAIN.rstrip('/') + sUrl
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName.strip(), SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showCollection():
    params = ParameterHandler()
    sHtmlContent = getHtmlContent(URL_MAIN)
    if not sHtmlContent:
        cGui().showInfo()
        return

    # Sammlung-Sidebar mit collection-scroll
    pattern = r'<div class="side-block__title">Sammlung</div>.*?<div class="side-block__content collection-scroll">(.*?)</div>\s*</div>'
    isMatch, sContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if not isMatch:
        cGui().showInfo()
        return

    pattern = r'href="([^"]+)"[^>]*>.*?<div class="custom-collection-title">([^<]+)</div>'
    isMatch, aResult = cParser.parse(sContainer, pattern)
    if not isMatch:
        cGui().showInfo()
        return

    for sUrl, sName in aResult:
        if sUrl.startswith('/'):
            sUrl = URL_MAIN.rstrip('/') + sUrl
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName.strip(), SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showLatest():
    """Zeigt die 'Zuletzt hinzugefuegt' Sektion von der Megakino-Homepage.
    Andere HTML-Struktur als poster grid-item: 'listItem' Container ohne Cover-Bilder.
    Cover kommt nicht aus dem Megakino-HTML (gibts nicht in dieser Sektion) — TMDB
    handelt das via Title+Year automatisch.
    """
    params = ParameterHandler()
    sHtmlContent = getHtmlContent(URL_MAIN)
    if not sHtmlContent:
        cGui().showInfo()
        return

    # Section isolieren: <h2>Zuletzt hinzugefuegt</h2> bis zum naechsten <section>
    isMatch, sContainer = cParser.parseSingleResult(
        sHtmlContent,
        r'<h2 class="sect__title[^"]*"[^>]*>Zuletzt hinzugefügt</h2>(.*?)(?=<section class="|$)'
    )
    if not isMatch:
        cGui().showInfo()
        return

    # listItem Pattern: Quality + URL + Title + Genre
    pattern = r'<div class="listItem">\s*<div class="listItem-badges">\s*<div class="listItem-badge listItem-quality">([^<]+)</div>.*?<div class="listItem-title">\s*<a href="([^"]+)">([^<]+)</a>\s*</div>\s*<div class="listItem-genre">([^<]+)</div>'
    isMatch, aResult = cParser.parse(sContainer, pattern)
    if not isMatch:
        cGui().showInfo()
        return

    total = len(aResult)
    isTvshow = False
    for sQuality, sUrl, sTitle, sGenre in aResult:
        # Year aus Title extrahieren: "They Will Kill You (2026)"
        sYear = ''
        isYear, aYear = cParser.parseSingleResult(sTitle, r'\((\d{4})\)')
        if isYear:
            sYear = aYear

        # Title cleanen (Year-Suffix raus, Display-Name bleibt mit "- Staffel N")
        sName = re.sub(r'\s*\(\d{4}\)\s*$', '', sTitle).strip()
        sName = sName.replace('&amp;', '&').replace('&#039;', "'").replace('&quot;', '"').strip()

        # Movie vs TV-Show via URL-Pfad
        isTvshow = sUrl.startswith('/serials/')
        if sUrl.startswith('/'):
            sUrl = URL_MAIN.rstrip('/') + sUrl

        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showEpisodes' if isTvshow else 'showHosters')
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        if sQuality:
            oGuiElement.setQuality(sQuality.strip())
        if sYear:
            oGuiElement.setYear(sYear)
        # Genre als Description (besser als nichts ohne Cover)
        if sGenre:
            oGuiElement.setDescription(sGenre.strip())
        params.setParam('entryUrl', sUrl)
        params.setParam('sName', sName)
        params.setParam('sDesc', sGenre.strip() if sGenre else '')
        if sYear:
            params.setParam('sYear', sYear)
        cGui().addFolder(oGuiElement, params, isTvshow, total)

    cGui().setView('tvshows' if isTvshow else 'movies')
    cGui().setEndOfDirectory()


def _parsePage(sHtmlContent):
    """Parst eine einzelne Seite mit dem Full-Poster-Pattern und gibt (isMatch, aResult) zurueck."""
    pattern = r'<a class="poster grid-item[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*data-src="([^"]+)"[^>]*alt="([^"]+)"[^>]*>.*?<div class="poster__label">([^<]*)</div>.*?<h3 class="poster__title[^>]*>([^<]*)</h3>.*?<div class="poster__text[^>]*>([^<]*)</div>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    return isMatch, aResult if isMatch else []


def _getNextPageUrl(sHtmlContent):
    """Extrahiert die Next-Page-URL aus pagination__btn-loader oder gibt False zurueck."""
    pattern = r'<div class="pagination__btn-loader[^>]*>\s*<a href="([^"]+)"'
    isMatch, sNextUrl = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        if sNextUrl.startswith('/'):
            sNextUrl = URL_MAIN.rstrip('/') + sNextUrl
        return sNextUrl
    return False


def _fetchAllSearchPages(startUrl, sGui=False):
    """Holt ALLE Seiten einer Suche und gibt kombinierte Ergebnisse zurueck.
    Megakino-Suche zeigt bei vielen Treffern mehrere Seiten — Kodi-User soll alle sehen.
    """
    allResults = []
    currentUrl = startUrl
    maxPages = 10  # Sicherheitslimit

    for page in range(maxPages):
        sHtmlContent = getHtmlContent(currentUrl)
        if not sHtmlContent:
            break

        isMatch, aResult = _parsePage(sHtmlContent)
        if isMatch:
            allResults.extend(aResult)

        nextUrl = _getNextPageUrl(sHtmlContent)
        if not nextUrl:
            break
        currentUrl = nextUrl

    return allResults


def showEntries(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl:
        entryUrl = params.getValue('sUrl')

    # Search nutzt DLE-URL Format
    if sSearchText:
        entryUrl = URL_MAIN + '?do=search&subaction=search&story=' + sSearchText.replace(' ', '+')

    # Bei Suche: ALLE Seiten auf einmal holen + zusammenfuehren
    if sSearchText:
        aResult = _fetchAllSearchPages(entryUrl, sGui)
        isMatch = len(aResult) > 0
        sHtmlContent = None  # nicht mehr noetig fuer Pagination
    else:
        sHtmlContent = getHtmlContent(entryUrl)
        if not sHtmlContent:
            if not sGui:
                oGui.showInfo()
            return
        isMatch, aResult = _parsePage(sHtmlContent)

    if not isMatch:
        if not sGui:
            oGui.showInfo()
        return

    total = len(aResult)
    isTvshow = True if 'serials' in entryUrl else False  # default basierend auf URL
    for sUrl, sThumb, sAlt, sQuality, sTitle, sDesc in aResult:
        sName = sTitle if sTitle else sAlt
        if sSearchText and not cParser.search(sSearchText, sName):
            continue
        # Serien-Erkennung: URL hat /serials/ ODER "Staffel" im Titel
        isTvshow = True if 'serials' in sUrl or 'Staffel' in sName else False
        # Absolute URLs
        if sUrl.startswith('/'):
            sUrl = URL_MAIN.rstrip('/') + sUrl
        if sThumb.startswith('/'):
            sThumb = URL_MAIN.rstrip('/') + sThumb
        # HTML-Entities decoden
        sName = sName.replace('&amp;', '&').replace('&#039;', "'").replace('&quot;', '"').strip()
        sDesc = sDesc.replace('&amp;', '&').replace('&#039;', "'").replace('&quot;', '"').strip()

        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showEpisodes' if isTvshow else 'showHosters')
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        oGuiElement.setThumbnail(sThumb)
        if sQuality:
            oGuiElement.setQuality(sQuality.strip())
        if sDesc:
            oGuiElement.setDescription(sDesc[:500])
        params.setParam('entryUrl', sUrl)
        params.setParam('sThumbnail', sThumb)
        params.setParam('sName', sName)
        params.setParam('sDesc', sDesc)
        oGui.addFolder(oGuiElement, params, isTvshow, total)

    if not sGui:
        # Pagination nur bei normalen Listen — Search holt schon alle Seiten via _fetchAllSearchPages
        if not sSearchText and sHtmlContent:
            sNextUrl = _getNextPageUrl(sHtmlContent)
            if sNextUrl:
                params.setParam('sUrl', sNextUrl)
                oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        oGui.setView('tvshows' if isTvshow else 'movies')
        oGui.setEndOfDirectory()


def showEpisodes():
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    sName = params.getValue('sName')
    sThumb = params.getValue('sThumbnail') if params.exist('sThumbnail') else ''
    sDesc = params.getValue('sDesc') if params.exist('sDesc') else ''
    sYear = params.getValue('sYear') if params.exist('sYear') else ''
    sHtmlContent = getHtmlContent(sUrl)
    if not sHtmlContent:
        cGui().showInfo()
        return

    # Pattern: <option value="epN">Episode-Name</option>
    pattern = r'<option\s+value="ep(\d+)"[^>]*>([^<]+)</option>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        cGui().showInfo()
        return

    # Falls kein Parent-Thumbnail uebergeben (z.B. aus showLatest): aus Movie-Detail-Page extrahieren
    if not sThumb:
        isMatchOg, sOgImage = cParser.parseSingleResult(sHtmlContent, r'<meta property="og:image" content="([^"]+)"')
        if isMatchOg and sOgImage:
            sThumb = sOgImage
            if sThumb.startswith('/'):
                sThumb = URL_MAIN.rstrip('/') + sThumb

    total = len(aResult)
    for sEpisode, sEpName in aResult:
        oGuiElement = cGuiElement(sEpName.strip(), SITE_IDENTIFIER, 'showEpisodeHosters')
        oGuiElement.setMediaType('episode')
        oGuiElement.setEpisode(sEpisode)
        if sThumb:
            oGuiElement.setThumbnail(sThumb)
        if sDesc:
            oGuiElement.setDescription(sDesc[:500])
        if sYear:
            oGuiElement.setYear(sYear)
        params.setParam('episodeId', sEpisode)
        params.setParam('entryUrl', sUrl)
        cGui().addFolder(oGuiElement, params, False, total)
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def showHosters():
    """Movie-Hoster: <iframe data-src OR src="HOSTER_URL">"""
    hosters = []
    sUrl = ParameterHandler().getValue('entryUrl')
    sHtmlContent = getHtmlContent(sUrl)
    if not sHtmlContent:
        return hosters

    # data-src (lazy-load) UND src matchen — Megakino nutzt beide Varianten
    pattern = r'<iframe[^>]*(?:data-src|src)="(https?://[^"]+)"'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if isMatch:
        for sHosterUrl in aResult:
            if 'youtube' in sHosterUrl:
                continue  # YouTube-Trailer skippen
            sName = cParser.urlparse(sHosterUrl).split('.')[0].replace('https://', '').replace('http://', '').strip()
            # GXPlayer-Mapping (URL ist watch.gxplayer.xyz)
            if sName.lower() == 'watch':
                sName = 'GXPlayer'
            if cConfig().isBlockedHoster(sName)[0]:
                continue
            sQuality = '720'
            hoster = {'link': sHosterUrl, 'name': sName, 'displayedName': '%s [I][%sp][/I]' % (sName, sQuality), 'quality': sQuality}
            hosters.append(hoster)
    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def showEpisodeHosters():
    """Episode-Hoster: <select id="epN">...<option value="HOSTER_URL">Name</option>...</select>"""
    hosters = []
    sUrl = ParameterHandler().getValue('entryUrl')
    sEpisodeId = 'ep' + ParameterHandler().getValue('episodeId')
    sHtmlContent = getHtmlContent(sUrl)
    if not sHtmlContent:
        return hosters

    # Container fuer diese Episode finden
    pattern = r'<select[^>]*id="%s"[^>]*>(.*?)</select>' % sEpisodeId
    isMatch, sContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if not isMatch:
        return hosters

    # Hoster-URLs aus options
    pattern = r'<option[^>]*value="(https?://[^"]+)"[^>]*>([^<]+)</option>'
    isMatch, aResult = cParser.parse(sContainer, pattern)
    if not isMatch:
        # Fallback: nur value=
        isMatch, urls = cParser.parse(sContainer, r'value="(https?://[^"]+)"')
        if isMatch:
            aResult = [(u, '') for u in urls]

    if isMatch:
        for sHosterUrl, sHosterName in aResult:
            if 'youtube' in sHosterUrl:
                continue
            sName = sHosterName.strip() if sHosterName.strip() else cParser.urlparse(sHosterUrl).split('.')[0]
            sName = sName.replace('https://', '').replace('http://', '').strip()
            if sName.lower() == 'watch':
                sName = 'GXPlayer'
            if cConfig().isBlockedHoster(sName)[0]:
                continue
            sQuality = '720'
            hoster = {'link': sHosterUrl, 'name': sName, 'displayedName': '%s [I][%sp][/I]' % (sName, sQuality), 'quality': sQuality}
            hosters.append(hoster)
    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def getHosterUrl(sUrl=False):
    return [{'streamUrl': sUrl, 'resolved': False}]


def showSearch():
    win = xbmcgui.Window(10000)
    sSearchText = win.getProperty('xstream.megakino.lastSearchText')
    if not sSearchText:
        sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
        if not sSearchText:
            return
        win.setProperty('xstream.megakino.lastSearchText', sSearchText)
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    showEntries(URL_MAIN, oGui, sSearchText)
