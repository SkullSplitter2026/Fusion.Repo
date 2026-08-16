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

SITE_IDENTIFIER = 'streamcloud'
SITE_NAME = 'Streamcloud'
SITE_ICON = 'streamcloud.png'

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'streamcloud.study') # Domain Auswahl über die xStream Einstellungen möglich
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht

URL_MAIN = 'https://' + DOMAIN + '/'
URL_MAINPAGE = URL_MAIN + 'streamcloud/'
URL_MOVIES = URL_MAIN + 'filme-stream/'
URL_KINO = URL_MAIN + 'kinofilme/'
URL_FAVOURITE_MOVIE_PAGE = URL_MAIN + 'beliebte-filme/'
URL_SERIES = URL_MAIN + 'serien/'
URL_SEARCH = URL_MAIN + 'index.php?story=%s&do=search&subaction=search'


def load(): # Menu structure of the site plugin
    logger.info('Load %s' % SITE_NAME)
    xbmcgui.Window(10000).clearProperty('xstream.streamcloud.lastSearchText')
    params = ParameterHandler()
    params.setParam('sUrl', URL_KINO)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30501), SITE_IDENTIFIER, 'showEntries'), params)  # Latest Releases
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30500), SITE_IDENTIFIER, 'showLatest'))  # Neues / Updates-Sektion (Filme+Serien)
    params.setParam('sUrl', URL_SERIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511), SITE_IDENTIFIER, 'showSeries'), params)  # Series
    params.setParam('sUrl', URL_MAINPAGE)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showGenre'), params)    # Categories
    params.setParam('sUrl', URL_MAINPAGE)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30538), SITE_IDENTIFIER, 'showCountry'), params)  # Country
    params.setParam('sUrl', URL_MAINPAGE)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)   # Search
    cGui().setEndOfDirectory()


def showLatest():
    """Zeigt die 'Updates' Sektion von der Streamcloud-Homepage.
    Container hat 2 Spalten: Filme links, Serien rechts (jeweils 12 Items).
    Items im Format: <a href="URL"><div><i class="flag flag-de"></i> NAME (YEAR)</div></a>
    URL-Pattern ist identisch fuer Filme und Serien — Movie/Serie-Erkennung erfolgt
    via Block-Position (vor/nach 'Serien</a>' Header).
    """
    params = ParameterHandler()
    sHtmlContent = cRequestHandler(URL_MAINPAGE).request()
    if not sHtmlContent:
        cGui().showInfo()
        return

    # Updates-Sektion isolieren
    isMatch, sContainer = cParser.parseSingleResult(
        sHtmlContent,
        r'<h2[^>]*>Updates</h2>(.*?)(?=<h2|<div\s+class="section)'
    )
    if not isMatch:
        cGui().showInfo()
        return

    # Container in Filme- und Serien-Block aufteilen
    sFilmsBlock = ''
    sSeriesBlock = ''
    splitMatch = re.search(r'<a\s+href="/serien/"[^>]*>Serien</a>', sContainer)
    if splitMatch:
        sFilmsBlock = sContainer[:splitMatch.start()]
        sSeriesBlock = sContainer[splitMatch.end():]
    else:
        sFilmsBlock = sContainer

    # Gleicher Item-Pattern fuer beide Bloecke
    item_pat = r'<a href="([^"]+)"[^>]*>\s*<div[^>]*>\s*<i class="flag flag-[a-z]+"></i>\s*([^<]+)\s*</div>\s*</a>'

    aFilms = re.findall(item_pat, sFilmsBlock)
    aSeries = re.findall(item_pat, sSeriesBlock)
    aItems = [(url, title.strip(), False) for url, title in aFilms] + \
             [(url, title.strip(), True) for url, title in aSeries]

    if not aItems:
        cGui().showInfo()
        return

    total = len(aItems)
    isTvshow = False
    for sUrl, sTitle, isSerie in aItems:
        # Year aus Title extrahieren: "Name (2026)"
        sYear = ''
        isYear, aYear = cParser.parseSingleResult(sTitle, r'\((\d{4})\)')
        if isYear:
            sYear = aYear

        # Title cleanen: Year-Suffix raus
        sName = re.sub(r'\s*\(\d{4}\)\s*$', '', sTitle).strip()

        # Absolute URL ggf.
        if sUrl.startswith('/'):
            sUrl = URL_MAIN.rstrip('/') + sUrl

        oGuiElement = cGuiElement(
            sName,
            SITE_IDENTIFIER,
            'showSeasons' if isSerie else 'showHosters'
        )
        oGuiElement.setMediaType('tvshow' if isSerie else 'movie')
        if sYear:
            oGuiElement.setYear(sYear)
        params.setParam('entryUrl', sUrl)
        params.setParam('sName', sName)
        if sYear:
            params.setParam('sYear', sYear)
        cGui().addFolder(oGuiElement, params, isSerie, total)
        isTvshow = isSerie

    cGui().setView('movies')
    cGui().setEndOfDirectory()


def showGenre(entryUrl=False):
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl)
    sHtmlContent = oRequest.request()    
    pattern = '>Genres<.*?</div></div>'
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, 'href="([^"]+).*?>([^<]+)')
    if not isMatch:
        cGui().showInfo()
        return

    # Navigations-Einträge filtern (sind schon im Hauptmenü)
    nav_slugs = ['filme', 'filme1', 'kinofilme', 'serien', 'serienstream-deutsch',
                 'kinofilme-online', 'aktuelle-kinofilme-im-kino', 'demnachst',
                 'filme-online-sehen', 'filme-stream', 'neue-filme',
                 'erotik', 'erotikfilme']
    for sUrl, sName in aResult:
        if sUrl.startswith('/'):
            sUrl = URL_MAIN + sUrl
        slug = sUrl.rstrip('/').split('/')[-1].lower()
        if slug in nav_slugs:
            continue
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showCountry(entryUrl=False): #ToDo Sortierung A-Z bei Ländern
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl)
    sHtmlContent = oRequest.request()
    pattern = '">Land.*?</div></div>'
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, 'href="([^"]+).*?>([^<]+)')
    if not isMatch:
        cGui().showInfo()
        return

    for sUrl, sName in aResult:
        if sUrl.startswith('/'):
            sUrl = URL_MAIN + sUrl
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False, sSearchText=False, sSearchPageText = False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    # Laender/Genres mit Leerzeichen (z.B. "South Africa") kommen aus dem
    # Parameter-Durchlauf unkodiert zurueck -> direkt vor dem Request kodieren
    # (deckt auch die Naechste-Seite-URL ab). Pfadstruktur bleibt erhalten.
    entryUrl = cParser.urlEncode(entryUrl, safe="/:?=&%#")
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    sHtmlContent = oRequest.request()
    pattern = 'class="thumb".*?title="([^"]+).*?href="([^"]+).*?src="([^"]+).*?_year">([^<]+)'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    for sName, sUrl, sThumbnail, sYear in aResult:
        if sSearchText and not cParser.search(sSearchText, sName):
            continue
        if sThumbnail[0] == '/':
            sThumbnail = sThumbnail[1:]

        # Film/Serie via Detail-Seite erkennen (zuverlässigste Quelle bei streamcloud)
        # xStream's Request-Cache macht Wiederholungen instant
        isTvshow = False
        try:
            detailHtml = cRequestHandler(sUrl).request()
            # Serie erkannt wenn data-num="NxN" (natives DLE-Pattern) ODER meinecloud-
            # serials.php im HTML. Streamcloud hat seine Serien auf meinecloud umgestellt
            # (kein data-num mehr) — ohne den serials-Marker wuerden mc-Serien wie
            # "The Rookie" als Film erkannt und direkt in einen Stream springen statt
            # in die Serie.
            isSeriesMatch, _ = cParser.parseSingleResult(detailHtml, r'data-num="\d+x\d+"')
            if not isSeriesMatch:
                isSeriesMatch, _ = cParser.parseSingleResult(detailHtml, r'meinecloud[^/\'"]*/serials\.php')
            if isSeriesMatch:
                isTvshow = True
        except Exception:
            isTvshow = False

        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons' if isTvshow else 'showHosters')
        oGuiElement.setThumbnail(URL_MAIN + sThumbnail)
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        if sYear: oGuiElement.setYear(sYear)  # Aki: reaktiviert - heutige tmdb/api.py hat getrennte year-Parameter
        params.setParam('entryUrl', sUrl)
        params.setParam('sName', sName)
        params.setParam('sThumbnail', sThumbnail)
        params.setParam('sYear', sYear)
        oGui.addFolder(oGuiElement, params, isTvshow, total)
        
    if not sGui and not sSearchText and not sSearchPageText:
        isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, 'href="([^"]+)">Next')
        # Start Page Function
        isMatchSiteSearch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, 'class="wp-pagenavi(.*?)Next')
        if isMatchSiteSearch:
            isMatch, aResult = cParser.parse(sHtmlContainer, r'<span>([\d]+)</span>.*?nav_ext">.*?">([\d]+)</a>.*?href="([^"]+)')
            if isMatch:
                for sPageActive, sPageLast, sNextPage in aResult:
                    # sPageName = '[I]Seitensuche starten  >>> [/I] Seite ' + str(sPageActive) + ' von ' + str(sPageLast) + ' Seiten  [I]<<<[/I]'
                    sPageName = cConfig().getLocalizedString(30284) + str(sPageActive) + cConfig().getLocalizedString(
                        30285) + str(sPageLast) + cConfig().getLocalizedString(30286)
                    params.setParam('sNextPage', sNextPage)
                    params.setParam('sPageLast', sPageLast)
                    oGui.searchNextPage(sPageName, SITE_IDENTIFIER, 'showSearchPage', params)
            # End Page Function

        if isMatchNextPage:
            params.setParam('sUrl', sNextUrl)
            oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)

        oGui.setView('movies')
        oGui.setEndOfDirectory()


def showSeries(entryUrl=False, sGui=False, sSearchText=False): # Neu eingebaut da auf der Webseite nicht erkennbar ist was Serien sind und was nicht
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    isTvshow = True
    if not entryUrl: entryUrl = params.getValue('sUrl')
    # Laender/Genres mit Leerzeichen (z.B. "South Africa") kommen aus dem
    # Parameter-Durchlauf unkodiert zurueck -> direkt vor dem Request kodieren
    # (deckt auch die Naechste-Seite-URL ab). Pfadstruktur bleibt erhalten.
    entryUrl = cParser.urlEncode(entryUrl, safe="/:?=&%#")
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    sHtmlContent = oRequest.request()
    pattern = 'class="thumb".*?title="([^"]+).*?href="([^"]+).*?src="([^"]+).*?_year">([^<]+)'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    for sName, sUrl, sThumbnail, sYear in aResult:
        if sSearchText and not cParser.search(sSearchText, sName):
            continue
        if sThumbnail[0] == '/':
            sThumbnail = sThumbnail[1:]
        sThumbAbs = URL_MAIN + sThumbnail
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setThumbnail(sThumbAbs)
        oGuiElement.setMediaType('tvshow')
        if sYear: oGuiElement.setYear(sYear)  # Aki: reaktiviert - heutige tmdb/api.py hat getrennte year-Parameter
        params.setParam('entryUrl', sUrl)
        params.setParam('sName', sName)
        params.setParam('sThumbnail', sThumbAbs)
        params.setParam('sYear', sYear)

        oGui.addFolder(oGuiElement, params, isTvshow, total)

    if not sGui and not sSearchText:
        isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, r'"nav_ext.*?>\d[1-9]+<.*?href="([^"]+).*?</div>')
        if isMatchNextPage:
            params.setParam('sUrl', sNextUrl)
            oGui.addNextPage(SITE_IDENTIFIER, 'showSeries', params)
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()


def showSeasons():
    """Staffel-Ebene fuer Serien. Native DLE-Serien liefern die Staffeln ueber
    data-num="SxE", meinecloud-Serien ueber serials.php. Bei genau einer Staffel
    wird die Ordner-Ebene uebersprungen (direkt in die Episoden, HTML/mc werden
    durchgereicht — kein zweiter Request/Lookup)."""
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue('sThumbnail')
    sHtmlContent = cRequestHandler(entryUrl).request()

    # Native data-num Staffeln (erste Zahl vor dem 'x')
    isMatch, aNum = cParser.parse(sHtmlContent, r'data-num="(\d+)x\d+"')
    seasons = sorted(set(int(s) for s in aNum)) if isMatch else []

    # meinecloud-Serie: Staffeln aus serials.php
    aMc = []
    if not seasons:
        _, aImdb = cParser.parse(sHtmlContent, r'(tt\d{7,9})')
        sImdbId = aImdb[0] if aImdb else ''
        if sImdbId:
            aMc = resolveMeinecloudSerial(sImdbId, referer=entryUrl, siteHtml=sHtmlContent)
            seasons = sorted(set(ep['season'] for ep in aMc))

    if not seasons:
        cGui().showInfo()
        return

    # Nur eine Staffel: Ordner-Ebene sparen, direkt in die Episoden.
    if len(seasons) == 1:
        showEpisodes(staffel=seasons[0], htmlContent=sHtmlContent, mcEpisodes=aMc)
        return

    for iSeason in seasons:
        oGuiElement = cGuiElement(cConfig().getLocalizedString(30512) + ' %d' % iSeason, SITE_IDENTIFIER, 'showEpisodes')
        oGuiElement.setMediaType('season')
        oGuiElement.setSeason(iSeason)
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        params.setParam('entryUrl', entryUrl)
        params.setParam('staffel', str(iSeason))
        cGui().addFolder(oGuiElement, params, True)
    cGui().setView('seasons')
    cGui().setEndOfDirectory()


def showEpisodes(staffel=None, htmlContent=None, mcEpisodes=None):
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue('sThumbnail')
    # staffel/htmlContent/mcEpisodes werden von showSeasons durchgereicht
    # (Single-Staffel-Skip), sonst kommt die Staffel aus dem Parameter
    # (Klick auf einen Staffel-Ordner).
    if staffel is None and params.exist('staffel'):
        staffel = params.getValue('staffel')
    sStaffel = str(staffel) if staffel is not None else None
    if htmlContent is not None:
        sHtmlContent = htmlContent
    else:
        sHtmlContent = cRequestHandler(entryUrl).request()

    isMatch, aResult = cParser.parse(sHtmlContent, 'data-num="([^"]+)')

    # meinecloud-Episoden: durchgereicht (von showSeasons) oder — falls native
    # Pattern leer — neu laden (Stranger Things etc., Daten nur via serials.php).
    aMeinecloudEpisodes = list(mcEpisodes) if mcEpisodes else []
    if not isMatch and not aMeinecloudEpisodes:
        _, aImdb = cParser.parse(sHtmlContent, r'(tt\d{7,9})')
        sImdbId = aImdb[0] if aImdb else ''
        if sImdbId:
            aMeinecloudEpisodes = resolveMeinecloudSerial(sImdbId, referer=entryUrl, siteHtml=sHtmlContent)
    if aMeinecloudEpisodes and not isMatch:
        # Format wie Site-Pattern: "<staffel>x<episode>" — kompatibel zu showHosters
        aResult = ['%dx%d' % (ep['season'], ep['episode']) for ep in aMeinecloudEpisodes]

    if not aResult:
        cGui().showInfo()
        return

    # Auf die gewaehlte Staffel filtern (native + meinecloud synchron halten).
    if sStaffel is not None:
        if aMeinecloudEpisodes:
            filtered = [(ep, sNum) for ep, sNum in zip(aMeinecloudEpisodes, aResult) if str(ep['season']) == sStaffel]
            aMeinecloudEpisodes = [ep for ep, sNum in filtered]
            aResult = [sNum for ep, sNum in filtered]
        else:
            aResult = [sNum for sNum in aResult if sNum.split('x')[0] == sStaffel]
        if not aResult:
            cGui().showInfo()
            return

    # Falls kein Parent-Thumbnail uebergeben (z.B. aus showLatest): aus Detail-Page extrahieren
    if not sThumbnail:
        isMatchOg, sOgImage = cParser.parseSingleResult(sHtmlContent, r'<meta property="og:image" content="([^"]+)"')
        if isMatchOg and sOgImage:
            sThumbnail = sOgImage if sOgImage.startswith('http') else URL_MAIN.rstrip('/') + sOgImage

    total = len(aResult)
    for i, sName in enumerate(aResult):
        # meinecloud-Mode: Label mit Episodentitel anreichern
        if aMeinecloudEpisodes:
            ep = aMeinecloudEpisodes[i]
            sLabel = 'S%dE%d — %s' % (ep['season'], ep['episode'], ep['title'])
        else:
            sLabel = sName
        oGuiElement = cGuiElement(sLabel, SITE_IDENTIFIER, 'showHosters')
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        oGuiElement.setMediaType('episode')
        if aMeinecloudEpisodes:
            oGuiElement.setSeason(ep['season'])
            oGuiElement.setEpisode(ep['episode'])
        params.setParam('entryUrl', entryUrl)
        params.setParam('episode', sName)
        # meinecloud-Mode: Direct-URL mitgeben damit showHosters() ohne weiteren Lookup aufloest
        if aMeinecloudEpisodes:
            params.setParam('meinecloud_url', aMeinecloudEpisodes[i]['url'])
        cGui().addFolder(oGuiElement, params, False, total)
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def _resolvePlayerWrapper(wrapperUrl):
    """Löst einen streamcloud-internen /player/... Wrapper zu einer echten Hoster-URL auf."""
    try:
        oRequest = cRequestHandler(wrapperUrl)
        oRequest.addHeaderEntry('Referer', URL_MAIN)
        wrapperHtml = oRequest.request()
        # Innerhalb des Wrappers stehen iframes oder direkte Hoster-URLs
        # Pattern: iframe src=, oder data-link= mit http(s)
        isMatch, aResult = cParser.parse(wrapperHtml, r'<iframe[^>]+src="(https?://[^"]+)"')
        if isMatch and aResult:
            return aResult[0]
        isMatch, aResult = cParser.parse(wrapperHtml, r'data-link="(https?://[^"]+)"')
        if isMatch and aResult:
            return aResult[0]
    except Exception:
        pass
    return None


def showHosters():
    hosters = []
    sUrl = ParameterHandler().getValue('entryUrl')
    sMeinecloudUrl = ParameterHandler().getValue('meinecloud_url') if ParameterHandler().exist('meinecloud_url') else ''

    # meinecloud-Mode: URL kommt direkt aus showEpisodes (Stranger Things etc.),
    # kein DLE-HTML-Parsing noetig. Aktuell 1 Hoster pro Episode (meinecloud-Architektur).
    if sMeinecloudUrl:
        _fixedUrl = ('https:' + sMeinecloudUrl) if sMeinecloudUrl.startswith('//') else sMeinecloudUrl
        sName = cParser.urlparse(_fixedUrl).split('.')[0].strip()
        if not cConfig().isBlockedHoster(sName)[0]:
            hosters.append({'link': _fixedUrl, 'name': sName, 'displayedName': sName})
        if hosters:
            hosters.append('getHosterUrl')
        return hosters

    sHtmlContent = cRequestHandler(sUrl, caching=False).request()
    if ParameterHandler().exist('episode'): #kommt aus showSeries
        episode = ParameterHandler().getValue('episode')
        # Ganzen <li>-Block für diese Episode holen (primary + alle mirrors)
        # Struktur: <li><a data-num="NxN">...</a><div class="mirrors"><a data-m="..." data-link="...">...</a>...</div></li>
        blockPattern = r'<li>\s*<a [^>]*data-num="{0}".*?</li>'.format(episode)
        isMatch, sBlock = cParser.parseSingleResult(sHtmlContent, blockPattern)
        if not isMatch:
            cGui().showInfo()
            return
        # Echte HTML-Kommentare (<!-- ... -->) entfernen damit disablte Mirrors rausfliegen.
        # Aber NICHT <!--- ... ---> (drei Dashes) matchen — Streamcloud nutzt das Format
        # fuer "soft-disabled" Mirrors (z.B. Dropload). Falls Site-Owner sie reaktiviert,
        # sind sie automatisch verfuegbar ohne Code-Touch.
        sBlock = re.sub(r'<!--(?!-)(.*?)(?<!-)-->', '', sBlock, flags=re.DOTALL)
        # Alle data-link sammeln (externe + interne Player-Wrapper)
        isMatch, aResult = cParser.parse(sBlock, r'data-link="([^"]+)"')
        if not isMatch:
            cGui().showInfo()
            return
        # Interne /player/... URLs auflösen, externe direkt übernehmen
        resolvedLinks = []
        seen = set()
        for link in aResult:
            if link.startswith('/'):
                # Interner Player-Wrapper → zu echter Hoster-URL auflösen
                fullWrapperUrl = URL_MAIN + link.lstrip('/')
                realUrl = _resolvePlayerWrapper(fullWrapperUrl)
                if realUrl and realUrl not in seen:
                    seen.add(realUrl)
                    resolvedLinks.append(realUrl)
            elif link.startswith('http') and link not in seen:
                seen.add(link)
                resolvedLinks.append(link)
        aResult = resolvedLinks
        if not aResult:
            cGui().showInfo()
            return
        isMatch = True
    else:
        pattern = '<iframe.*?allowfull'
        isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
        if isMatch:
            isMatch, aResult = cParser.parse(sHtmlContainer, 'src="([^"]+)')
            try:
                sUrl = aResult[0]
            except:
                pass
        if not isMatch:
            cGui().showInfo()
            return
        sHtmlContent = cRequestHandler(sUrl).request()
        isMatch, aResult = cParser.parse(sHtmlContent, 'data-link="([^"]+)')
    if isMatch:
        sQuality = '720'
        # Meinecloud-Wrapper expandieren: streamcloud versteckt zusaetzliche Hoster
        # hinter meinecloud-URLs (siehe resources/lib/wrappers/meinecloud.py). Page liefert eigene data-link Liste.
        # Greift fuer beide Modi (Episode + Movie konvergieren hier).
        # Meinecloud-Wrapper expandieren via zentralem Helper (meinecloud.expandHosterList).
        aResult = expandHosterList(aResult, referer=URL_MAIN)

        for sUrl in aResult:
            if not sUrl or not sUrl.strip(): continue   # Leere data-link skippen (z.B. meinecloud "andere Server" Toggle)
            # Standard-Hoster-Dict via zentralem Helper (Schema-Fix, Hostname,
            # YouTube-Skip, Blocked-Check, Quality-Suffix)
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
    sSearchText = win.getProperty('xstream.streamcloud.lastSearchText')
    if not sSearchText:
        sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30287))
        if not sSearchText: return
        win.setProperty('xstream.streamcloud.lastSearchText', sSearchText)
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
