# -*- coding: utf-8 -*-
# Python 3
# Always pay attention to the translations in the menu!
# HTML LangzeitCache hinzugefügt
# showGenre:     48 Stunden
# showEntries:    6 Stunden
# showSeasons:    6 Stunden
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


SITE_IDENTIFIER = 'kinoger'
SITE_NAME = 'KinoGer'
SITE_ICON = 'kinoger.png'

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'kinoger.fun')  # Domain Auswahl über die xStream Einstellungen möglich
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status')  # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER)  # Ob Plugin aktiviert ist oder nicht

URL_MAIN = 'https://' + DOMAIN
URL_KINO = URL_MAIN + '/aktuelle-kinofilme-im-kino/'
URL_MOVIES = URL_MAIN + '/kinofilme-online/'
URL_SERIES = URL_MAIN + '/serienstream-deutsch/'


def load():  # Menu structure of the site plugin
    logger.info('Load %s' % SITE_NAME)
    xbmcgui.Window(10000).clearProperty('xstream.kinoger.lastSearchText')
    params = ParameterHandler()
    params.setParam('sUrl', URL_KINO)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30501), SITE_IDENTIFIER, 'showEntries'), params)  # Aktuelle Releases
    params.setParam('sUrl', URL_MOVIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30502), SITE_IDENTIFIER, 'showEntries'), params)  # Filme
    params.setParam('sUrl', URL_SERIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511), SITE_IDENTIFIER, 'showEntries'), params)  # Serien
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showGenre'))  # Genre
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'))  # Suche
    cGui().setEndOfDirectory()


def showGenre():
    params = ParameterHandler()
    oRequest = cRequestHandler(URL_MAIN)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 48  # 48 Stunden
    sHtmlContent = oRequest.request()
    # Genre-Items aus Sidebar/Footer-Menue, Format: <li class="links"><a href="ABSOLUTE_URL"><img.../> <b>Name</b></a></li>
    pattern = r'<li class="links"><a href="([^"]+)"><img[^>]*/>\s*<b>([^<]+)</b></a></li>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        cGui().showInfo()
        return

    # Top-Level Kategorien (Kinofilme, Serien, Aktuelle, Demnaechst) raus — zeigen wir schon im Hauptmenue
    # Erotikfilme raus — wie bei den anderen Sites in xStream
    skip = (URL_KINO, URL_MOVIES, URL_SERIES, URL_MAIN + '/demnachst/', URL_MAIN + '/erotikfilme/')
    for sUrl, sName in aResult:
        if sUrl in skip:
            continue
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl:
        entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    if sSearchText:
        oRequest.addParameters('do', 'search')
        oRequest.addParameters('subaction', 'search')
        oRequest.addParameters('story', sSearchText)
        oRequest.addParameters('titleonly', '3')
        oRequest.addParameters('submit', 'submit')
    sHtmlContent = oRequest.request()
    # Pattern: <div class="title"><div class="begin"><img.../> <a href="URL">Name (Year)</a></div></div>
    # ... gefolgt von <div class="content_text"><img src="THUMB" .../>BESCHREIBUNG<br><br
    pattern = r'<div class="title">\s*<div class="begin"><img[^>]*class="img"[^>]*/>\s*<a href="([^"]+)">([^<]+)</a>.*?<div class="content_text">.*?<img src="([^"]+)"[^>]*alt="[^"]*"[^>]*>(.+?)<br><br'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui:
            oGui.showInfo()
        return

    total = len(aResult)
    isTvshow = True if 'serienstream' in entryUrl else False  # Default basierend auf URL
    for sUrl, sName, sThumbnail, sDummy in aResult:
        if sSearchText and not cParser.search(sSearchText, sName):
            continue
        # Serien werden via "Staffel" im Titel oder /serienstream-deutsch/-URL erkannt
        isTvshow = True if 'staffel' in sName.lower() or 'serienstream' in entryUrl else False
        # Jahr aus Name extrahieren: "Der Super Mario Galaxy Film (2026)"
        sYear = ''
        isYear, aYear = cParser.parse(sName, r'(.*?)\s+\((\d{4})\)')
        if isYear and aYear:
            sName, sYear = aYear[0]
            sName = sName.strip()
        # Extra-Tags wie "*English*" oder "*Subbed*" rausziehen
        sName = re.sub(r'\s*\*[^*]+\*\s*', ' ', sName).strip()
        if sThumbnail.startswith('/'):
            sThumbnail = URL_MAIN + sThumbnail
        # Beschreibung aus dem Dummy-Block (alles vor dem Genre/Quality-Block)
        sDesc = sDummy
        # Erstes <div ...></div> (text-align right) raus
        sDesc = re.sub(r'<div[^>]*></div>', '', sDesc).strip()
        # Quality aus <b>(HD)</b>
        sQual = ''
        isQual, aQual = cParser.parseSingleResult(sDummy, r'<b>\(([^)]+)\)</b>')
        if isQual:
            sQual = aQual

        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons' if isTvshow else 'showHosters')
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        oGuiElement.setThumbnail(sThumbnail)
        if sYear:
            oGuiElement.setYear(sYear)
        if sDesc:
            oGuiElement.setDescription(sDesc[:500])  # Beschreibung trimmen
        if sQual:
            oGuiElement.setQuality(sQual)
        params.setParam('entryUrl', sUrl)
        params.setParam('searchTitle', sName)
        oGui.addFolder(oGuiElement, params, isTvshow, total)
    if not sGui:
        # Pagination: <a href="URL">vorwaerts + ...</a> am Ende des Navigation-Blocks
        # Findet auf Movie-Listings + Genre. Search hat keine Pagination auf kinoger.my
        if not sSearchText:
            isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, r'href="([^"]+)">vorw')
            if isMatchNextPage:
                params.setParam('sUrl', sNextUrl)
                oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        oGui.setView('tvshows' if isTvshow else 'movies')
        oGui.setEndOfDirectory()


def showSeasons():
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    sName = params.getValue('searchTitle')
    sThumb = params.getValue('thumbnail') if params.exist('thumbnail') else ''
    oRequest = cRequestHandler(sUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    sHtmlContent = oRequest.request()

    # Native interne Staffeln (kinoger-Norm: eine Serienseite = intern immer "1",
    # die echte Staffelnummer steht nur im Titel).
    _, aNativeInternal = cParser.parse(sHtmlContent, r'<li id="serie-(\d+)_\d+">')
    nativeInternal = sorted(set(aNativeInternal), key=int) if aNativeInternal else []

    # meinecloud-Staffeln IMMER mitpruefen (nicht nur als Fallback): kinoger legt pro
    # Staffel eine eigene Seite an, meinecloud liefert die KOMPLETTE Serie. Hat mc mehr
    # Staffeln als die native Seite, nehmen wir mc als Rueckgrat (alle Staffeln sichtbar)
    # und mergen die nativen Hoster in die passende Staffel (siehe showEpisodes).
    _, aImdb = cParser.parse(sHtmlContent, r'(tt\d{7,9})')
    sImdbId = aImdb[0] if aImdb else ''
    aMc = resolveMeinecloudSerial(sImdbId, referer=sUrl, siteHtml=sHtmlContent) if sImdbId else []
    mcSeasons = sorted(set(ep['season'] for ep in aMc))

    if mcSeasons and len(mcSeasons) > len(nativeInternal):
        seasons = [str(s) for s in mcSeasons]
    elif nativeInternal:
        # nur native: die echte Staffel steht im Titel (intern "1" -> Titel-Staffel)
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

    # Nur eine Staffel: Ordner-Ebene sparen, direkt in die Episoden springen
    # (bereits geladenes HTML weiterreichen).
    if len(seasons) == 1:
        showEpisodes(staffel=seasons[0], htmlContent=sHtmlContent)
        return

    for sStaffel in seasons:
        oGuiElement = cGuiElement(cConfig().getLocalizedString(30512) + ' %s' % sStaffel, SITE_IDENTIFIER, 'showEpisodes')
        oGuiElement.setMediaType('season')
        oGuiElement.setSeason(sStaffel)
        if sThumb:
            oGuiElement.setThumbnail(sThumb)
        params.setParam('entryUrl', sUrl)
        params.setParam('staffel', sStaffel)
        params.setParam('searchTitle', sName)
        cGui().addFolder(oGuiElement, params, True)
    cGui().setView('seasons')
    cGui().setEndOfDirectory()


def showEpisodes(staffel=None, htmlContent=None):
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    sName = params.getValue('searchTitle')
    # staffel/htmlContent werden von showSeasons durchgereicht (Single-Staffel-Skip),
    # sonst kommen sie wie gehabt aus den Parametern bzw. per Request.
    sStaffel = staffel if staffel is not None else params.getValue('staffel')
    sThumb = params.getValue('thumbnail') if params.exist('thumbnail') else ''
    if htmlContent is not None:
        sHtmlContent = htmlContent
    else:
        oRequest = cRequestHandler(sUrl)
        if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
            oRequest.cacheTime = 60 * 60 * 4  # 4 Stunden
        sHtmlContent = oRequest.request()
    # --- Native Episoden dieser Seite als Map {episode:int -> (linktext, hosterBlock)}.
    # kinoger-Norm: intern immer eine Staffel ("serie-1_N"), echte Nummer im Titel.
    # Der Linktext ("Episoden N") wird 1:1 als Label uebernommen (Site-Original), wenn
    # meinecloud keinen Episodentitel liefert. ---
    nativeMap = {}
    _, aInternal = cParser.parse(sHtmlContent, r'<li id="serie-(\d+)_\d+">')
    internalSeasons = sorted(set(aInternal), key=int) if aInternal else []
    isTitleSeason, sTitleSeason = cParser.parseSingleResult(sName, r'[Ss]taffel\s*(\d+)')
    sInternalForThis = None
    if len(internalSeasons) == 1:
        # echte Staffel dieser Seite = Titel-Staffel (Fallback: interne Nummer)
        sRealOfPage = sTitleSeason if isTitleSeason else internalSeasons[0]
        if str(sRealOfPage) == str(sStaffel):
            sInternalForThis = internalSeasons[0]
    elif str(sStaffel) in internalSeasons:
        # kinoger fuehrt doch mehrere interne Staffeln -> direkt matchen
        sInternalForThis = str(sStaffel)
    if sInternalForThis is not None:
        pattern = r'<li id="serie-' + re.escape(sInternalForThis) + r'_(\d+)"><a href="#">([^<]+)</a>\s*<ul[^>]*>(.*?)</ul>\s*</li>'
        isNat, aNat = cParser.parse(sHtmlContent, pattern)
        if isNat:
            for sEp, sTxt, sBlock in aNat:
                nativeMap[int(sEp)] = (sTxt.strip(), sBlock)

    # --- meinecloud Episoden dieser Staffel als Map {episode:int -> ep-dict}. ---
    _, aImdb = cParser.parse(sHtmlContent, r'(tt\d{7,9})')
    sImdbId = aImdb[0] if aImdb else ''
    aMc = resolveMeinecloudSerial(sImdbId, referer=sUrl, siteHtml=sHtmlContent) if sImdbId else []
    mcMap = {ep['episode']: ep for ep in aMc if str(ep['season']) == str(sStaffel)}

    if not nativeMap and not mcMap:
        cGui().showInfo()
        return

    # --- Merge: Union aller Episoden-Nummern (meinecloud + native). Pro Episode
    # bekommt showHosters BEIDE Quellen mit (nativer hosterBlock + meinecloud-URL)
    # und legt sie via buildMergedHosters zusammen ("mc plus deren"). ---
    allEps = sorted(set(mcMap.keys()) | set(nativeMap.keys()))
    total = len(allEps)
    for iEp in allEps:
        mcEp = mcMap.get(iEp)
        sTxt, sBlock = nativeMap.get(iEp, ('', ''))
        # Label: meinecloud-Titel bevorzugt (informativer), sonst Site-Linktext 1:1,
        # sonst synthetisch.
        if mcEp:
            sEpTitle = '%s - S%sE%s — %s' % (sName, str(sStaffel).zfill(2), str(iEp).zfill(2), mcEp['title'])
        elif sTxt:
            sEpTitle = sTxt
        else:
            sEpTitle = '%s - S%sE%s' % (sName, str(sStaffel).zfill(2), str(iEp).zfill(2))
        oGuiElement = cGuiElement(sEpTitle, SITE_IDENTIFIER, 'showHosters')
        oGuiElement.setMediaType('episode')
        oGuiElement.setSeason(str(sStaffel))
        oGuiElement.setEpisode(str(iEp))
        if sThumb:
            oGuiElement.setThumbnail(sThumb)
        params.setParam('hosterBlock', sBlock)
        params.setParam('meinecloud_url', mcEp['url'] if mcEp else '')
        params.setParam('searchTitle', sName)
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
        # Merge-Pfad: native data-link Hoster aus dem Block + meinecloud-URL
        # zusammenlegen ("mc plus deren"), dedupliziert (siehe buildMergedHosters).
        aNativeRaw = []
        if sHosterBlock:
            isMatch, aNativeRaw = cParser.parse(sHosterBlock, r'data-link="([^"]+)"')
            if not isMatch:
                aNativeRaw = []
        hosters = buildMergedHosters(aNativeRaw, sMcUrl, referer=URL_MAIN + '/')
        if hosters:
            hosters.append('getHosterUrl')
        return hosters

    # Movie-Pfad: Hoster direkt von der Movie-Page.
    sUrl = params.getValue('entryUrl')
    sHtmlContent = cRequestHandler(sUrl, caching=False).request()
    isMatch, aResult = cParser.parse(sHtmlContent, r'data-link="([^"]+)"')
    if isMatch:
        sQuality = '720'
        aResult = expandHosterList(aResult, referer=URL_MAIN + '/')
        for sHosterUrl in aResult:
            # kinoger-spezifischer Filter: interner 4K-Server-Link
            if sHosterUrl.startswith('/vod/'):
                continue
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
    sSearchText = win.getProperty('xstream.kinoger.lastSearchText')
    if not sSearchText:
        sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
        if not sSearchText:
            return
        win.setProperty('xstream.kinoger.lastSearchText', sSearchText)
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    showEntries(URL_MAIN + '/', oGui, sSearchText)
