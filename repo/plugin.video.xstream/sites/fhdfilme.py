# -*- coding: utf-8 -*-
# Python 3
# Always pay attention to the translations in the menu!
# HTML LangzeitCache hinzugefügt
# showValue:     48 Stunden
# showEntries:    6 Stunden
# showEpisodes:   4 Stunden


import xbmcgui
from resources.lib.handler.parameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.logger import logger
from resources.lib.wrappers.meinecloud import resolveMeinecloud, resolveMeinecloudSerial, expandHosterList, buildHosterFromUrl, MEINECLOUD_TRIGGER
from resources.lib.tools import cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui

SITE_IDENTIFIER = 'fhdfilme'
SITE_NAME = 'FHD Filme'
SITE_ICON = 'fhdfilme.png'

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'hdfilme.win') # Domain Auswahl über die xStream Einstellungen möglich
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht

URL_MAIN = 'https://' + DOMAIN

URL_NEW = URL_MAIN + '/filme1/'
URL_KINO = URL_MAIN + '/kinofilme/'
URL_SERIES = URL_MAIN + '/serien/'
URL_SEARCH = URL_MAIN + '/?story=%s&do=search&subaction=search'

#

def load(): # Menu structure of the site plugin
    logger.info('Load %s' % SITE_NAME)
    xbmcgui.Window(10000).clearProperty('xstream.fhdfilme.lastSearchText')
    xbmcgui.Window(10000).clearProperty('xstream.fhdfilme.lastYear')
    params = ParameterHandler()
    params.setParam('sUrl', URL_KINO)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30501), SITE_IDENTIFIER, 'showEntries'), params)  # Aktuelle Releases
    params.setParam('sUrl', URL_NEW)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30500), SITE_IDENTIFIER, 'showEntries'), params)  # New
    params.setParam('sUrl', URL_SERIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511), SITE_IDENTIFIER, 'showEntries'), params)  # Series
    params.setParam('Value', 'Genre')
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showValue'), params)    # Genre
    params.setParam('Value', 'Land')
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30538), SITE_IDENTIFIER, 'showValue'), params)  # Country
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)   # Search
    cGui().setEndOfDirectory()


def showValue():
    params = ParameterHandler()
    sValue = params.getValue('Value')
    oRequest = cRequestHandler(URL_MAIN)
    sHtmlContent = oRequest.request()
    pattern = '>{0}</(.*?)</a[^<]*</div>'.format(sValue)
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, 'href="([^"]+).*?>([^<]+)')
        if isMatch:
            # Bei Genre Navigations-Einträge filtern (sind auch im Hauptmenü)
            nav_slugs = ['filme1', 'kinofilme', 'serien', 'aktuelle-kinofilme-im-kino',
                         'kinofilme-online', 'serienstream-deutsch', 'demnachst',
                         'erotik', 'erotikfilme']
            for sUrl, sName in aResult:
                if sUrl.startswith('/'):
                    sUrl = URL_MAIN + sUrl
                if sValue == 'Genre':
                    # URL-Slug aus URL extrahieren (letzter Pfad-Abschnitt)
                    slug = sUrl.rstrip('/').split('/')[-1].lower()
                    if slug in nav_slugs:
                        continue
                params.setParam('sUrl', sUrl)
                cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    if not isMatch:
        cGui().showInfo()
        return
    cGui().setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False, sSearchText=False, sSearchPageText = False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    isTvshow = False
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    sHtmlContent = oRequest.request()
    pattern = 'class="item relative mt-3">.*?href="([^"]+).*?title="([^"]+).*?data-src="([^"]+)(.*?)</div></div>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    for sUrl, sName, sThumbnail, sDummy in aResult:
        if sSearchText and not cParser.search(sSearchText, sName):
            continue
        isYear, sYear = cParser.parseSingleResult(sDummy, r'mt-1">[^<]*<span>([\d]+)</span>')  # Release Jahr
        isDuration, sDuration = cParser.parseSingleResult(sDummy, r'<span>([\d]+)\smin</span>')  # Laufzeit
        if int(sDuration) <= int('70'): # Wenn Laufzeit kleiner oder gleich 70min, dann ist es eine Serie.
            isTvshow = True
        else:
            from resources.lib.tmdb.api import cTMDB
            oMetaget = cTMDB()
            if not oMetaget:
                isTvshow = False
            else:
                if isYear:
                    meta = oMetaget.search_movie_name(sName, year=sYear)
                else:
                    meta = oMetaget.search_movie_name(sName)
                if meta and 'id' in meta:
                    isTvshow = False
                else:
                    isTvshow = True
        if 'South Park: The End Of Obesity' in sName:
            isTvshow = False
        isQuality, sQuality = cParser.parseSingleResult(sDummy, '">([^<]+)</span>')  # Qualität
        sThumbnail = URL_MAIN + sThumbnail
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons' if isTvshow else 'showHosters')
        if isYear:
            oGuiElement.setYear(sYear)
        if isDuration:
            oGuiElement.addItemValue('duration', sDuration)
        if isQuality:
            oGuiElement.setQuality(sQuality)
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        oGuiElement.setThumbnail(sThumbnail)
        params.setParam('entryUrl', sUrl)
        params.setParam('sThumbnail', sThumbnail)
        params.setParam('sName', sName)
        if isYear: params.setParam('sYear', sYear)  # Aki: Year an showSeasons weitergeben
        oGui.addFolder(oGuiElement, params, isTvshow, total)
    if not sGui and not sSearchText and not sSearchPageText:
        isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, 'nav_ext">.*?next">.*?href="([^"]+)')
        # Start Page Function
        isMatchSiteSearch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, 'class="pages">(.*?)<svg')
        if isMatchSiteSearch:
            isMatch, aResult = cParser.parse(sHtmlContainer, r'<span>([\d]+)</span>.*?">([\d]+)</a></div>.*?ref="([^"]+)')
            if isMatch:
                for sPageActive, sPageLast, sNextPage in aResult:
                    #sPageName = '[I]Seitensuche starten  >>> [/I] Seite ' + str(sPageActive) + ' von ' + str(sPageLast) + ' Seiten  [I]<<<[/I]'
                    sPageName = cConfig().getLocalizedString(30284) + str(sPageActive) + cConfig().getLocalizedString(30285) + str(sPageLast) + cConfig().getLocalizedString(30286)
                    params.setParam('sNextPage', sNextPage)
                    params.setParam('sPageLast', sPageLast)
                    oGui.searchNextPage(sPageName, SITE_IDENTIFIER, 'showSearchPage', params)
            # End Page Function
        if isMatchNextPage:
            params.setParam('sUrl', sNextUrl)
            oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        oGui.setView('tvshows' if isTvshow else 'movies')
        oGui.setEndOfDirectory()


def showSeasons():
    params = ParameterHandler()
    # Parameter laden
    sUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue('sThumbnail')
    sTmdbID = params.getValue('tmdbID') or ''
    sName = params.getValue('sName') or ''
    sYear = params.getValue('sYear') or ''  # Aki: Year aus Listen-Ebene uebernehmen
    oRequest = cRequestHandler(sUrl)
    sHtmlContent = oRequest.request()
    pattern = 'class="su-accordion collapse show"(.*?)<br>'
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    aResult = []
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, r'#se-ac-(\d+)')

    # meinecloud-Fallback: alte DLE-Pattern leer (z.B. Stranger Things hat Daten nur via
    # meinecloud serials.php Endpoint). Bei 0 Treffern IMDB-ID extrahieren und
    # meinecloud-Resolver fragen. Episoden gruppieren nach Staffel-Nummern.
    if not aResult:
        _, aImdb = cParser.parse(sHtmlContent, r'(tt\d{7,9})')
        sImdbId = aImdb[0] if aImdb else ''
        if sImdbId:
            episodes = resolveMeinecloudSerial(sImdbId, referer=sUrl, siteHtml=sHtmlContent)
            if episodes:
                # Eindeutige Staffel-Nummern in sortierter Reihenfolge
                aResult = sorted({str(ep['season']) for ep in episodes}, key=int)

    if aResult:
        total = len(aResult)
        for sSeason in aResult:
            oGuiElement = cGuiElement(cConfig().getLocalizedString(30512) + ' ' + str(sSeason), SITE_IDENTIFIER, 'showEpisodes')
            oGuiElement.setSeason(sSeason)
            oGuiElement.setMediaType('season')
            if sName:
                oGuiElement.setTVShowTitle(sName)
            if sTmdbID:
                oGuiElement.addItemValue('tmdb_id', sTmdbID)
            if sYear:
                oGuiElement.addItemValue('year', sYear)  # Aki: Year auf Staffel setzen
            oGuiElement.setThumbnail(sThumbnail)
            cGui().addFolder(oGuiElement, params, True, total)
    else:
        cGui().showInfo()
        return
    cGui().setView('seasons')
    cGui().setEndOfDirectory()


def showEpisodes():
    params = ParameterHandler()
    # Parameter laden
    entryUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue('sThumbnail')
    sSeason = params.getValue('season')
    oRequest = cRequestHandler(entryUrl)
    sHtmlContent = oRequest.request()
    pattern = '#se-ac-%s(.*?)</div></div>' % sSeason
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    aResult = []
    aMeinecloudEpisodes = []  # Bei meinecloud-Fallback: Episoden-Dicts mit Titel
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, r'Episode\s(\d+)')

    # meinecloud-Fallback: alte DLE-Pattern leer. IMDB-ID extrahieren, meinecloud
    # fragen, Episoden der angefragten Staffel filtern.
    if not aResult:
        _, aImdb = cParser.parse(sHtmlContent, r'(tt\d{7,9})')
        sImdbId = aImdb[0] if aImdb else ''
        if sImdbId:
            allEps = resolveMeinecloudSerial(sImdbId, referer=entryUrl, siteHtml=sHtmlContent)
            try:
                iSeason = int(sSeason)
            except (TypeError, ValueError):
                iSeason = 0
            aMeinecloudEpisodes = [ep for ep in allEps if ep['season'] == iSeason]
            aMeinecloudEpisodes.sort(key=lambda ep: ep['episode'])
            aResult = [str(ep['episode']) for ep in aMeinecloudEpisodes]

    if aResult:
        total = len(aResult)
        for i, sEpisode in enumerate(aResult):
            # meinecloud-Mode: Episode-Titel aus den Dict-Daten verwenden, sonst nur Nummer
            if aMeinecloudEpisodes:
                ep = aMeinecloudEpisodes[i]
                sLabel = '%s %s — %s' % (cConfig().getLocalizedString(30513), str(sEpisode), ep['title'])
            else:
                sLabel = cConfig().getLocalizedString(30513) + ' ' + str(sEpisode)
            oGuiElement = cGuiElement(sLabel, SITE_IDENTIFIER, 'showEpisodeHosters')
            oGuiElement.setThumbnail(sThumbnail)
            oGuiElement.setMediaType('episode')
            params.setParam('entryUrl', entryUrl)
            params.setParam('season', sSeason)
            params.setParam('episode', sEpisode)
            cGui().addFolder(oGuiElement, params, False, total)
    else:
        cGui().showInfo()
        return
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def showEpisodeHosters():
    hosters = []
    params = ParameterHandler()
    # Parameter laden
    sUrl = params.getValue('entryUrl')
    sSeason = params.getValue('season')
    sEpisode = params.getValue('episode')
    sHtmlContent = cRequestHandler(sUrl, caching=False).request()
    pattern = '#se-ac-%s(.*?)</div></div>' % sSeason
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        pattern = r'x%s\sEpisode(.*?)<br' % sEpisode
        isMatch, sHtmlLink = cParser.parseSingleResult(sHtmlContainer, pattern)
        if isMatch:
            isMatch, aResult = cParser.parse(sHtmlLink, 'href="([^"]+)')
            if isMatch:
                sQuality = '720'
                for sUrl in aResult:
                    # Standard-Hoster-Dict via zentralem Helper (Schema-Fix, Hostname,
                    # YouTube-Skip, Blocked-Check, Quality-Suffix)
                    hoster = buildHosterFromUrl(sUrl, sQuality=sQuality, includeQualitySuffix=True)
                    if hoster:
                        hosters.append(hoster)

    # meinecloud-Fallback: keine Hoster aus DLE-HTML gefunden. IMDB-ID extrahieren,
    # meinecloud fragen, gewuenschte Episode rausfiltern. Aktuell liefert meinecloud
    # nur 1 Hoster pro Episode (default dropload) — Architektur-bedingt.
    if not hosters:
        _, aImdb = cParser.parse(sHtmlContent, r'(tt\d{7,9})')
        sImdbId = aImdb[0] if aImdb else ''
        if sImdbId:
            try:
                iSeason = int(sSeason)
                iEpisode = int(sEpisode)
            except (TypeError, ValueError):
                iSeason = iEpisode = 0
            allEps = resolveMeinecloudSerial(sImdbId, referer=sUrl, siteHtml=sHtmlContent)
            for ep in allEps:
                if ep['season'] != iSeason or ep['episode'] != iEpisode:
                    continue
                # Standard-Hoster-Dict via zentralem Helper
                hoster = buildHosterFromUrl(ep['url'], sQuality='720', includeQualitySuffix=True)
                if hoster:
                    hosters.append(hoster)

    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def showHosters():
    hosters = []
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    sHtmlContent = cRequestHandler(sUrl, caching=False).request()
    # meinecloud-iframe aus der Film-Seite holen. Pattern robust gegen
    # Attribut-Reihenfolge (src kann zuerst stehen); interner player.php
    # (protokoll-relativ) und YouTube-Trailer werden via MEINECLOUD_TRIGGER
    # uebersprungen.
    isMatch, aIframes = cParser.parse(sHtmlContent, r'<iframe[^>]+src="(https?://[^"]+)"')
    hUrl = next((u for u in aIframes if MEINECLOUD_TRIGGER in u), '') if isMatch else ''
    if hUrl:
        sHtmlContainer = cRequestHandler(hUrl).request()
        isMatch, aResult = cParser.parse(sHtmlContainer, 'data-link="([^"]+)')
        if isMatch:
            sQuality = '720'
            # Meinecloud-Wrapper expandieren via zentralem Helper (meinecloud.expandHosterList).
            aResult = expandHosterList(aResult, referer=URL_MAIN + '/')

            for sHosterUrl in aResult:
                # Standard-Hoster-Dict via zentralem Helper (Schema-Fix, Hostname,
                # YouTube-Skip, Blocked-Check, Quality-Suffix)
                hoster = buildHosterFromUrl(sHosterUrl, sQuality=sQuality, includeQualitySuffix=True)
                if hoster:
                    hosters.append(hoster)
    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def getHosterUrl(sUrl=False):
    return [{'streamUrl': sUrl, 'resolved': False}]


def showSearch():
    win = xbmcgui.Window(10000)
    sSearchText = win.getProperty('xstream.fhdfilme.lastSearchText')
    if not sSearchText:
        sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
        if not sSearchText: return
        win.setProperty('xstream.fhdfilme.lastSearchText', sSearchText)
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    showEntries(URL_SEARCH % cParser.quotePlus(sSearchText), oGui, sSearchText)


def showSearchPage(): # Suche für die Page Funktion
    params = ParameterHandler()
    sNextPage = params.getValue('sNextPage') # URL mit nächster Seite
    sPageLast = params.getValue('sPageLast') # Anzahl gefundener Seiten
    #sHeading = 'Bitte eine Zahl zwischen 1 und ' + str(sPageLast) + ' wählen.'
    sHeading = cConfig().getLocalizedString(30282) + str(sPageLast)
    sSearchPageText = cGui().showKeyBoard(sHeading=sHeading)
    if not sSearchPageText: return
    sNextSearchPage = sNextPage.split('page/')[0].strip() + 'page/' + sSearchPageText + '/'
    showEntries(sNextSearchPage)
    cGui().setEndOfDirectory()
