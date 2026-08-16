# -*- coding: utf-8 -*-
# Python 3
# Always pay attention to the translations in the menu!
# HTML LangzeitCache hinzugefügt
# showGenre:     48 Stunden
# showEpisodes:   4 Stunden

import re
import xbmcgui
from resources.lib.handler.parameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.logger import logger
from resources.lib.wrappers.meinecloud import resolveMeinecloud, resolveMeinecloudSerial, expandHosterList, buildHosterFromUrl, buildMergedHosters, MEINECLOUD_TRIGGER
from resources.lib.tools import cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui

SITE_IDENTIFIER = 'hdfilme'
SITE_NAME = 'HD Filme'
SITE_ICON = 'hdfilme.png'

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'hdfilme1.co') # Domain Auswahl über die xStream Einstellungen möglich
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht

URL_MAIN = 'https://' + DOMAIN + '/'
URL_NEW = URL_MAIN + 'kinofilme-online/'
URL_KINO = URL_MAIN + 'aktuelle-kinofilme-im-kino/'
URL_SERIES = URL_MAIN + 'serienstream-deutsch/'
URL_SEARCH = URL_MAIN + 'index.php?do=search&subaction=search&story=%s'
#

def load(): # Menu structure of the site plugin
    logger.info('Load %s' % SITE_NAME)
    xbmcgui.Window(10000).clearProperty('xstream.hdfilme.lastSearchText')
    params = ParameterHandler()
    params.setParam('sUrl', URL_KINO)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30501), SITE_IDENTIFIER, 'showEntries'), params)  # Aktuelle Releases
    params.setParam('sUrl', URL_NEW)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30500), SITE_IDENTIFIER, 'showEntries'), params)  # New
    params.setParam('sUrl', URL_SERIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511), SITE_IDENTIFIER, 'showEntries'), params)  # Series
    params.setParam('sUrl', URL_MAIN)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showGenre'), params)  # Genre
    params.setParam('sUrl', URL_MAIN)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30538), SITE_IDENTIFIER, 'showCountry'), params)  # Country
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)# Search
    cGui().setEndOfDirectory()


def showGenre(entryUrl=False):
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl)
    sHtmlContent = oRequest.request()
    # Seiten-Update: Dropdown heißt jetzt "KATEGORIE", title="Genre"
    pattern = r'title="Genre">KATEGORIE.*?</ul>'
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, 'href="([^"]+)"[^>]*>([^<]+)</a>')
    if not isMatch:
        cGui().showInfo()
        return

    # Navigations-Einträge filtern (sind auch im Hauptmenü schon drin)
    nav_slugs = ['kinofilme-online', 'serienstream-deutsch', 'aktuelle-kinofilme-im-kino', 'demnachst',
                 'erotik', 'erotikfilme']
    for sUrl, sName in aResult:
        if sUrl.startswith('/'):
            sUrl = URL_MAIN + sUrl.lstrip('/')
        # Nav-Entries raus
        if any(nav in sUrl for nav in nav_slugs):
            continue
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName.strip(), SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showCountry(entryUrl=False):
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl)
    sHtmlContent = oRequest.request()
    # Seiten-Update: title="Land", Dropdown-Text "Filme nach Ländern", URLs sind /xfsearch/<name>/
    pattern = r'title="Land">Filme nach Ländern.*?</ul>'
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, 'href="(/xfsearch/[^"]+)"[^>]*>([^<]+)</a>')
    if not isMatch:
        cGui().showInfo()
        return

    for sUrl, sName in aResult:
        if sUrl.startswith('/'):
            sUrl = URL_MAIN + sUrl.lstrip('/')
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName.strip(), SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False, sSearchText=False, sSearchPageText = False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    isTvshow = False
    if not entryUrl: entryUrl = params.getValue('sUrl')
    # Laender mit Leerzeichen/Umlaut (z.B. "Vereinigte Staaten") kommen aus dem
    # Parameter-Durchlauf unkodiert zurueck -> direkt vor dem Request kodieren
    # (deckt auch die Naechste-Seite-URL ab). Pfadstruktur bleibt erhalten.
    entryUrl = cParser.urlEncode(entryUrl, safe="/:?=&%#")
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    sHtmlContent = oRequest.request()
    pattern = '<div class="box-product(.*?)<h3.*?href="([^"]+).*?">([^<]+).*?(.*?)</li>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    for sInfo, sUrl, sName, sDummy in aResult:
        if sSearchText and not cParser.search(sSearchText, sName):
            continue
        # Abfrage der voreingestellten Sprache
        sLanguage = cConfig().getSetting('prefLanguage')
        if (sLanguage == '1' and 'English*' in sName):   # Deutsch
            continue
        if (sLanguage == '2' and not 'English*' in sName):   # English
            continue
        elif sLanguage == '3':    # Japanisch
            cGui().showLanguage()
            continue
        isThumbnail, sThumbnail = cParser.parseSingleResult(sInfo, 'data-src="([^"]+)')  # Thumbnail
        isYear, sYear = cParser.parseSingleResult(sDummy, r'([\d]+)\s</p>')  # Release Jahr
        isQuality, sQuality = cParser.parseSingleResult(sDummy, 'quality-product">([^<]+)')  # Qualität
        isTvshow = True if 'taffel' in sName else False
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons' if isTvshow else 'showHosters')
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        if isThumbnail:
            sThumbnail = URL_MAIN + sThumbnail
            oGuiElement.setThumbnail(sThumbnail)
        if isYear:
            oGuiElement.setYear(sYear)
        if isQuality:
            oGuiElement.setQuality(sQuality)
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        params.setParam('entryUrl', sUrl)
        params.setParam('sName', sName)
        params.setParam('sThumbnail', sThumbnail)
        oGui.addFolder(oGuiElement, params, isTvshow, total)

    if not sGui and not sSearchText and not sSearchPageText:
        isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, 'href="([^"]+)">›</a></div>')
        # Start Page Function
        isMatchSiteSearch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, 'class="pagination(.*?)</div></div>')
        if isMatchSiteSearch:
            isMatch, aResult = cParser.parse(sHtmlContainer, r'<span>([\d]+)</span>.*?nav_ext">.*?">([\d]+)</a>.*?href="([^"]+)')
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
    """Staffel-Ebene. hdfilme legt pro Staffel eine eigene Seite an (intern immer
    "serie-1_N", echte Staffel im Titel); meinecloud liefert die komplette Serie.
    Hat mc mehr Staffeln, nehmen wir mc als Rueckgrat (alle Staffeln sichtbar) und
    mergen die nativen Hoster in die passende Staffel (siehe showEpisodes)."""
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    sName = params.getValue('sName') if params.exist('sName') else ''
    sThumbnail = params.getValue('sThumbnail') if params.exist('sThumbnail') else ''
    sHtmlContent = cRequestHandler(entryUrl).request()

    _, aNativeInternal = cParser.parse(sHtmlContent, r'<li id="serie-(\d+)_\d+">')
    nativeInternal = sorted(set(aNativeInternal), key=int) if aNativeInternal else []

    _, aImdb = cParser.parse(sHtmlContent, r'(tt\d{7,9})')
    sImdbId = aImdb[0] if aImdb else ''
    aMc = resolveMeinecloudSerial(sImdbId, referer=entryUrl, siteHtml=sHtmlContent) if sImdbId else []
    mcSeasons = sorted(set(ep['season'] for ep in aMc))

    if mcSeasons and len(mcSeasons) > len(nativeInternal):
        seasons = [str(s) for s in mcSeasons]
    elif nativeInternal:
        isTitleSeason, sTitleSeason = cParser.parseSingleResult(sName, r'[Ss]taffel\s*(\d+)')
        if len(nativeInternal) == 1 and isTitleSeason:
            seasons = [sTitleSeason]
        else:
            seasons = nativeInternal
    elif mcSeasons:
        seasons = [str(s) for s in mcSeasons]
    else:
        seasons = []

    if not seasons:
        cGui().showInfo()
        return

    if len(seasons) == 1:
        showEpisodes(staffel=seasons[0], htmlContent=sHtmlContent)
        return

    for sStaffel in seasons:
        oGuiElement = cGuiElement(cConfig().getLocalizedString(30512) + ' %s' % sStaffel, SITE_IDENTIFIER, 'showEpisodes')
        oGuiElement.setMediaType('season')
        oGuiElement.setSeason(sStaffel)
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        params.setParam('entryUrl', entryUrl)
        params.setParam('sName', sName)
        params.setParam('staffel', sStaffel)
        cGui().addFolder(oGuiElement, params, True)
    cGui().setView('seasons')
    cGui().setEndOfDirectory()


def showEpisodes(staffel=None, htmlContent=None):
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    sName = params.getValue('sName') if params.exist('sName') else ''
    sThumbnail = params.getValue('sThumbnail') if params.exist('sThumbnail') else ''
    sStaffel = staffel if staffel is not None else params.getValue('staffel')
    if htmlContent is not None:
        sHtmlContent = htmlContent
    else:
        sHtmlContent = cRequestHandler(entryUrl).request()

    # Native Episoden-Map {episode:int -> (linktext, hosterBlock)} (serie-INTERN_N).
    nativeMap = {}
    _, aInternal = cParser.parse(sHtmlContent, r'<li id="serie-(\d+)_\d+">')
    internalSeasons = sorted(set(aInternal), key=int) if aInternal else []
    isTitleSeason, sTitleSeason = cParser.parseSingleResult(sName, r'[Ss]taffel\s*(\d+)')
    sInternalForThis = None
    if len(internalSeasons) == 1:
        sRealOfPage = sTitleSeason if isTitleSeason else internalSeasons[0]
        if str(sRealOfPage) == str(sStaffel):
            sInternalForThis = internalSeasons[0]
    elif str(sStaffel) in internalSeasons:
        sInternalForThis = str(sStaffel)
    if sInternalForThis is not None:
        pattern = r'<li id="serie-' + re.escape(sInternalForThis) + r'_(\d+)"><a href="#">([^<]+)</a>\s*<ul[^>]*>(.*?)</ul>\s*</li>'
        isNat, aNat = cParser.parse(sHtmlContent, pattern)
        if isNat:
            for sEp, sTxt, sBlock in aNat:
                nativeMap[int(sEp)] = (sTxt.strip(), sBlock)

    # meinecloud Episoden dieser Staffel.
    _, aImdb = cParser.parse(sHtmlContent, r'(tt\d{7,9})')
    sImdbId = aImdb[0] if aImdb else ''
    aMc = resolveMeinecloudSerial(sImdbId, referer=entryUrl, siteHtml=sHtmlContent) if sImdbId else []
    mcMap = {ep['episode']: ep for ep in aMc if str(ep['season']) == str(sStaffel)}

    if not nativeMap and not mcMap:
        cGui().showInfo()
        return

    isDesc, sDesc = cParser.parseSingleResult(sHtmlContent, '"description"[^>]content="([^"]+)')
    allEps = sorted(set(mcMap.keys()) | set(nativeMap.keys()))
    total = len(allEps)
    for iEp in allEps:
        mcEp = mcMap.get(iEp)
        sTxt, sBlock = nativeMap.get(iEp, ('', ''))
        if mcEp:
            sLabel = 'S%sE%s — %s' % (str(sStaffel).zfill(2), str(iEp).zfill(2), mcEp['title'])
        elif sTxt:
            sLabel = sTxt
        else:
            sLabel = 'S%sE%s' % (str(sStaffel).zfill(2), str(iEp).zfill(2))
        oGuiElement = cGuiElement(sLabel, SITE_IDENTIFIER, 'showHosters')
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        if isDesc:
            oGuiElement.setDescription(sDesc)
        oGuiElement.setMediaType('episode')
        oGuiElement.setSeason(str(sStaffel))
        oGuiElement.setEpisode(str(iEp))
        params.setParam('entryUrl', entryUrl)
        params.setParam('hosterBlock', sBlock)
        params.setParam('meinecloud_url', mcEp['url'] if mcEp else '')
        cGui().addFolder(oGuiElement, params, False, total)
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def showHosters():
    hosters = []
    params = ParameterHandler()
    # Serie: showEpisodes hat hosterBlock (nativ) und/oder meinecloud_url gesetzt.
    # Movie: keiner der beiden -> Movie-Page laden.
    sHosterBlock = params.getValue('hosterBlock') if params.exist('hosterBlock') else ''
    sMcUrl = params.getValue('meinecloud_url') if params.exist('meinecloud_url') else ''

    if sHosterBlock or sMcUrl:
        # Merge-Pfad: native data-link Hoster + meinecloud-URL zusammenlegen.
        aNativeRaw = []
        if sHosterBlock:
            isMatch, aNativeRaw = cParser.parse(sHosterBlock, r'data-link="([^"]+)"')
            if not isMatch:
                aNativeRaw = []
        hosters = buildMergedHosters(aNativeRaw, sMcUrl, referer=URL_MAIN)
        if hosters:
            hosters.append('getHosterUrl')
        return hosters

    # Movie-Pfad: Hoster direkt von der Movie-Page.
    sHtmlContent = cRequestHandler(params.getValue('entryUrl'), caching=False).request()
    isMatch, aResult = cParser.parse(sHtmlContent, 'link="([^"]+)')
    if isMatch:
        sQuality = '720'
        aResult = expandHosterList(aResult, referer=URL_MAIN)
        for sUrl in aResult:
            hoster = buildHosterFromUrl(sUrl, sQuality=sQuality, includeQualitySuffix=True)
            if hoster:
                hosters.append(hoster)
    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def getHosterUrl(sUrl=False):
    return [{'streamUrl': sUrl, 'resolved': False}]


def showSearch():
    win = xbmcgui.Window(10000)
    sSearchText = win.getProperty('xstream.hdfilme.lastSearchText')
    if not sSearchText:
        sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
        if not sSearchText: return
        win.setProperty('xstream.hdfilme.lastSearchText', sSearchText)
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
