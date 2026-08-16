# -*- coding: utf-8 -*-
# Python 3
# kkiste HTML Scraper (DataLife Engine based)

import re
import xbmcgui
from resources.lib.handler.parameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.logger import logger
from resources.lib.wrappers.meinecloud import resolveMeinecloud, resolveMeinecloudSerial, buildMergedHosters, MEINECLOUD_TRIGGER
from resources.lib.tools import cParser, cUtil
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui


SITE_IDENTIFIER = 'kkiste'
SITE_NAME = 'KKiste'
SITE_ICON = 'kkiste.png'

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'kkiste-io.click')
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status')
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER)

URL_MAIN = 'https://' + DOMAIN
URL_NEW = URL_MAIN + '/'
URL_MOVIES = URL_MAIN + '/kinofilme-online/'
URL_SERIES = URL_MAIN + '/serienstream-deutsch/'
URL_KINO = URL_MAIN + '/aktuelle-kinofilme-im-kino/'
URL_SEARCH = URL_MAIN + '/index.php?do=search'


def load():
    """Hauptmenue."""
    logger.info('Load %s' % SITE_NAME)
    xbmcgui.Window(10000).clearProperty('xstream.kkiste.lastSearchText')
    params = ParameterHandler()

    # 1. Aktuelle Filme im Kino
    params.setParam('sUrl', URL_KINO)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30501), SITE_IDENTIFIER, 'showEntries'), params)  # Aktuelle Releases

    # 2. Neues (Startseite)
    params.setParam('sUrl', URL_NEW)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30500), SITE_IDENTIFIER, 'showEntries'), params)  # New

    # 3. Filme
    params.setParam('sUrl', URL_MOVIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30502), SITE_IDENTIFIER, 'showEntries'), params)  # Movies

    # 4. Serien
    params.setParam('sUrl', URL_SERIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511), SITE_IDENTIFIER, 'showEntries'), params)  # Series

    # 5. Genre
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showGenreMenu'))  # Genre

    # 6. Jahr

    # 7. Suche
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'))  # Search

    cGui().setEndOfDirectory()


def showGenreMenu():
    """Genre-Untermenue — Live aus der Sidebar 'Genres' auf der Startseite parsen."""
    params = ParameterHandler()
    oRequest = cRequestHandler(URL_MAIN + '/')
    oRequest.addHeaderEntry('Referer', URL_MAIN + '/')
    sHtmlContent = oRequest.request()

    # Sidebar-Block: <div class="side-bt">Genres</div> ... <ul class="nav-list fx-row">...</ul>
    pattern = r'<div class="side-bt">Genres</div>.*?<ul class="nav-list[^"]*"[^>]*>(.*?)</ul>'
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>')
    if not isMatch:
        cGui().showInfo()
        return

    # Navigations-Einträge + Erotik filtern
    nav_slugs = ['kinofilme-online', 'serienstream-deutsch', 'aktuelle-kinofilme-im-kino',
                 'demnachst', 'erotik', 'erotikfilme']
    for sUrl, sName in aResult:
        if sUrl.startswith('/'):
            sUrl = URL_MAIN + sUrl
        slug = sUrl.rstrip('/').split('/')[-1].lower()
        if slug in nav_slugs:
            continue
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(cUtil.unescape(sName.strip()), SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False, sSearchText=False):
    """Zeigt Liste der articles.short Cards von einer Kategorie- oder Paginations-Seite."""
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()

    if not entryUrl:
        entryUrl = params.getValue('sUrl')

    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    oRequest.addHeaderEntry('Referer', URL_MAIN + '/')
    sHtmlContent = oRequest.request()

    # Parse articles.short - Haupt-Container fuer Listen-Eintraege
    # Pattern: <article class="short">...<h2><a href="URL">TITLE</a>...<img src="THUMB" alt="TITLE (YEAR)" />...Jahr:..YYYY..
    pattern_articles = r'<article[^>]*class="short"[^>]*>(.*?)</article>'
    isMatch, aArticles = cParser.parse(sHtmlContent, pattern_articles)
    if not isMatch:
        if not sGui:
            oGui.showInfo()
        return

    total = len(aArticles)
    isTvshow = False

    for sArticle in aArticles:
        # Titel + Detail-URL
        isMatchT, aTitle = cParser.parseSingleResult(sArticle, r'<h2>\s*<a\s+href="([^"]+)"[^>]*>([^<]+)</a>')
        if not isMatchT:
            continue
        # parseSingleResult liefert bei einem Tupel-Pattern den kompletten Match — nehme alternativ:
        m = re.search(r'<h2>\s*<a\s+href="([^"]+)"[^>]*>([^<]+)</a>', sArticle)
        if not m:
            continue
        sDetailUrl = m.group(1)
        sName = cUtil.unescape(m.group(2).strip())

        if sSearchText and not cParser.search(sSearchText, sName):
            continue

        # Thumbnail
        mThumb = re.search(r'<img\s+src="([^"]+)"[^>]*alt="([^"]*)"', sArticle)
        sThumbnail = ''
        sAltText = ''
        if mThumb:
            sThumbnail = mThumb.group(1)
            if sThumbnail.startswith('/'):
                sThumbnail = URL_MAIN + sThumbnail
            sAltText = mThumb.group(2)

        # Jahr aus Alt-Text ("Title (2026)") oder aus "<span>Jahr:</span> 2026"
        sYear = ''
        mYear = re.search(r'<span>Jahr:</span>\s*(\d{4})', sArticle)
        if mYear:
            sYear = mYear.group(1)
        elif sAltText:
            mYearAlt = re.search(r'\((\d{4})\)', sAltText)
            if mYearAlt:
                sYear = mYearAlt.group(1)

        # Description
        sDesc = ''
        mDesc = re.search(r'<div class="st-line st-desc">([^<]+)</div>', sArticle)
        if mDesc:
            sDesc = cUtil.unescape(mDesc.group(1).strip())

        # Genre (aus st-line Genre-Block)
        sGenre = ''
        mGenre = re.search(r'<span>Genre:</span>(.*?)</div>', sArticle, re.DOTALL)
        if mGenre:
            genre_text = mGenre.group(1)
            genre_names = re.findall(r'>([^<]+)</a>', genre_text)
            if genre_names:
                sGenre = ', '.join(n.strip() for n in genre_names)

        # TV-Show-Erkennung: "Staffel" im Titel ODER alt-Text
        isTvshow = 'taffel' in sName or (sAltText and 'taffel' in sAltText)

        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons' if isTvshow else 'showHosters')
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        if sYear:
            oGuiElement.setYear(sYear)
        if sDesc:
            oGuiElement.setDescription(sDesc)
        if sGenre:
            oGuiElement.addItemValue('genre', sGenre)

        params.setParam('entryUrl', sDetailUrl)
        params.setParam('sName', sName)
        params.setParam('sThumbnail', sThumbnail)
        params.setParam('sYear', sYear)
        params.setParam('sDesc', sDesc)
        oGui.addFolder(oGuiElement, params, isTvshow, total)

    # Pagination
    if not sGui and not sSearchText:
        # class="pnext"><a href="URL">
        mNext = re.search(r'class="pnext"><a\s+href="([^"]+)"', sHtmlContent)
        if mNext:
            sNextUrl = mNext.group(1)
            if sNextUrl.startswith('/'):
                sNextUrl = URL_MAIN + sNextUrl
            params.setParam('sUrl', sNextUrl)
            oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)

    if not sGui:
        oGui.setView('tvshows' if isTvshow else 'movies')
        oGui.setEndOfDirectory()


def showSeasons():
    """Staffel-Ebene. kkiste legt pro Staffel eine eigene Seite an (intern immer
    "serie-1_N", echte Staffel im Titel); meinecloud liefert die komplette Serie.
    Hat mc mehr Staffeln, nehmen wir mc als Rueckgrat (alle Staffeln sichtbar) und
    mergen die nativen Hoster in die passende Staffel (siehe showEpisodes)."""
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    sName = params.getValue('sName') if params.exist('sName') else ''
    sThumbnail = params.getValue('sThumbnail') if params.exist('sThumbnail') else ''
    if not entryUrl:
        cGui().showInfo()
        return
    oRequest = cRequestHandler(entryUrl)
    oRequest.addHeaderEntry('Referer', URL_MAIN + '/')
    sHtmlContent = oRequest.request()

    aNativeInternal = re.findall(r'<li\s+id="serie-(\d+)_\d+"', sHtmlContent)
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

    sYear = params.getValue('sYear') if params.exist('sYear') else ''
    sDesc = params.getValue('sDesc') if params.exist('sDesc') else ''
    for sStaffel in seasons:
        oGuiElement = cGuiElement(cConfig().getLocalizedString(30512) + ' %s' % sStaffel, SITE_IDENTIFIER, 'showEpisodes')
        oGuiElement.setMediaType('season')
        oGuiElement.setSeason(sStaffel)
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        params.setParam('entryUrl', entryUrl)
        params.setParam('sName', sName)
        params.setParam('staffel', sStaffel)
        if sYear:
            params.setParam('sYear', sYear)
        if sDesc:
            params.setParam('sDesc', sDesc)
        cGui().addFolder(oGuiElement, params, True)
    cGui().setView('seasons')
    cGui().setEndOfDirectory()


def showEpisodes(staffel=None, htmlContent=None):
    """Episoden einer Staffel — native Hoster + meinecloud gemergt."""
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    sShowName = params.getValue('sName') if params.exist('sName') else ''
    sThumbnail = params.getValue('sThumbnail') if params.exist('sThumbnail') else ''
    sYear = params.getValue('sYear') if params.exist('sYear') else ''
    sDesc = params.getValue('sDesc') if params.exist('sDesc') else ''
    sStaffel = staffel if staffel is not None else params.getValue('staffel')

    if not entryUrl:
        cGui().showInfo()
        return

    if htmlContent is not None:
        sHtmlContent = htmlContent
    else:
        oRequest = cRequestHandler(entryUrl)
        oRequest.addHeaderEntry('Referer', URL_MAIN + '/')
        sHtmlContent = oRequest.request()

    # --- Native Episoden-Map {episode:int -> (linktext, hosterBlock)} (serie-INTERN_N).
    # kinoger-Norm auch hier: intern immer eine Staffel, echte Nummer im Titel. ---
    nativeMap = {}
    aInternal = re.findall(r'<li\s+id="serie-(\d+)_\d+"', sHtmlContent)
    internalSeasons = sorted(set(aInternal), key=int) if aInternal else []
    isTitleSeason, sTitleSeason = cParser.parseSingleResult(sShowName, r'[Ss]taffel\s*(\d+)')
    sInternalForThis = None
    if len(internalSeasons) == 1:
        sRealOfPage = sTitleSeason if isTitleSeason else internalSeasons[0]
        if str(sRealOfPage) == str(sStaffel):
            sInternalForThis = internalSeasons[0]
    elif str(sStaffel) in internalSeasons:
        sInternalForThis = str(sStaffel)
    if sInternalForThis is not None:
        pattern = r'<li\s+id="serie-' + re.escape(sInternalForThis) + r'_(\d+)"[^>]*>(.*?)(?=<li\s+id="serie-\d+_\d+"|</ul>)'
        for m in re.finditer(pattern, sHtmlContent, re.DOTALL):
            iEp = int(m.group(1))
            sBlock = m.group(2)
            mTxt = re.search(r'<a href="#">([^<]+)</a>', sBlock)
            sTxt = mTxt.group(1).strip() if mTxt else ''
            nativeMap[iEp] = (sTxt, sBlock)

    # --- meinecloud Episoden dieser Staffel. ---
    _, aImdb = cParser.parse(sHtmlContent, r'(tt\d{7,9})')
    sImdbId = aImdb[0] if aImdb else ''
    aMc = resolveMeinecloudSerial(sImdbId, referer=entryUrl, siteHtml=sHtmlContent) if sImdbId else []
    mcMap = {ep['episode']: ep for ep in aMc if str(ep['season']) == str(sStaffel)}

    if not nativeMap and not mcMap:
        cGui().showInfo()
        return

    # Originaltitel (ohne " - Staffel N") fuer TVShowTitle
    originalTitle = re.sub(r'\s*-\s*Staffel\s+\d+.*$', '', sShowName or '')

    # --- Merge: Union aller Episoden (meinecloud + native). ---
    allEps = sorted(set(mcMap.keys()) | set(nativeMap.keys()))
    total = len(allEps)
    for iEp in allEps:
        mcEp = mcMap.get(iEp)
        sTxt, sBlock = nativeMap.get(iEp, ('', ''))
        # Label: meinecloud-Titel bevorzugt, sonst Site-Linktext 1:1, sonst "Folge N".
        if mcEp:
            sEpTitle = '%s %d — %s' % (cConfig().getLocalizedString(30513), iEp, mcEp['title'])
        elif sTxt:
            sEpTitle = sTxt
        else:
            sEpTitle = cConfig().getLocalizedString(30513) + ' ' + str(iEp)
        oGuiElement = cGuiElement(sEpTitle, SITE_IDENTIFIER, 'showHosters')
        oGuiElement.setMediaType('episode')
        oGuiElement.setSeason(str(sStaffel))
        oGuiElement.setEpisode(str(iEp))
        if originalTitle:
            oGuiElement.setTVShowTitle(originalTitle)
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        if sYear:
            oGuiElement.addItemValue('year', sYear)
        if sDesc:
            oGuiElement.setDescription(sDesc)
        params.setParam('entryUrl', entryUrl)
        params.setParam('hosterBlock', sBlock)
        params.setParam('meinecloud_url', mcEp['url'] if mcEp else '')
        cGui().addFolder(oGuiElement, params, False, total)

    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def _isValidHoster(url):
    """Pruefe ob ein Link ein echter Hoster ist (keine internen /vod/ URLs, kein YouTube-Preview).

    Wichtig: meinecloud liefert protokoll-relative URLs (//host/...).
    Die starten zwar mit '/' aber sind legitime externe Hoster — drum
    explizit '//' ausschliessen vom internen-URL-Filter.
    """
    if not url:
        return False
    # Interne Site-URLs (z.B. '/vod/vpn.html') filtern — aber nicht
    # protokoll-relative URLs (//host/...) die sind externe Hoster.
    if url.startswith('/') and not url.startswith('//'):
        return False
    if url.startswith('#'):
        return False
    if 'youtube.com/embed' in url:
        return False  # Trailer/Preview, keine Episode
    return True


def showHosters():
    """Hoster-Liste einer Film-Detailseite ODER einer Episode."""
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    sHosterBlock = params.getValue('hosterBlock') if params.exist('hosterBlock') else ''
    sMcUrl = params.getValue('meinecloud_url') if params.exist('meinecloud_url') else ''

    if not entryUrl:
        return []

    # Serie: showEpisodes hat hosterBlock (nativ) und/oder meinecloud_url gesetzt
    # -> native data-link Hoster + meinecloud-URL zusammenlegen ("mc plus deren"),
    # dedupliziert (siehe buildMergedHosters).
    if sHosterBlock or sMcUrl:
        aNativeRaw = re.findall(r'data-link="([^"]+)"', sHosterBlock) if sHosterBlock else []
        hosters = buildMergedHosters(aNativeRaw, sMcUrl, referer=URL_MAIN + '/')
        if hosters:
            hosters.append('getHosterUrl')
        return hosters

    # Movie-Pfad: Hoster direkt von der Film-Detailseite.
    oRequest = cRequestHandler(entryUrl)
    oRequest.addHeaderEntry('Referer', URL_MAIN + '/')
    sHtmlContent = oRequest.request()

    # HTML-Kommentare strippen — kkiste laesst auskommentierte alte Hoster-Eintraege
    # (z.B. <!-- <li data-link="..."> --> ) im HTML stehen. Unser Regex matched die
    # mit, was zu Duplikaten in der Hoster-Liste fuehrt (Bug 07.05.2026: meinecloud-
    # Eintrag wird 2x resolved → 2x dropload + 2x mixdrop in der Liste).
    sHtmlContent = re.sub(r'<!--.*?-->', '', sHtmlContent, flags=re.DOTALL)

    hosters = []

    # Film-Modus: Alle data-link aus <ul class="dropdown-menu video-servers">
    m = re.search(r'<ul[^>]*class="[^"]*dropdown-menu[^"]*video-servers[^"]*"[^>]*>(.*?)</ul>', sHtmlContent, re.DOTALL)
    if not m:
        return []
    block = m.group(1)
    # <li><span data-link="URL"><img src="..."/> NAME</span></li>
    entries = re.findall(r'data-link="([^"]+)"[^>]*>.*?(?:alt="[^"]*"[^/>]*/?>|/>\s*|>)\s*([^<]+)</(?:a|span)>', block, re.DOTALL)

    for sUrl, sName in entries:
        # Meinecloud-Wrapper expandieren: kkiste versteckt zusaetzliche Hoster
        # hinter meinecloud-URLs (siehe resources/lib/wrappers/meinecloud.py). Resolved URLs bekommen Name aus
        # Hostname (split-on-dot), original-Eintraege behalten ihren Site-Namen.
        if MEINECLOUD_TRIGGER in sUrl:
            for sResolvedUrl in resolveMeinecloud(sUrl, referer=URL_MAIN + '/'):
                if not sResolvedUrl or not _isValidHoster(sResolvedUrl):
                    continue
                # Schema-Fix: protokoll-relative URLs (//host/...) brauchen 'https:' prefix
                # damit ResolveURL sie aufloesen kann. meinecloud liefert oft im
                # protokoll-relativen Format zurueck.
                _fixedUrl = ('https:' + sResolvedUrl) if sResolvedUrl.startswith('//') else sResolvedUrl
                try:
                    from urllib.parse import urlparse
                    sResolvedName = (urlparse(_fixedUrl).hostname or '').split('.')[0]
                except Exception:
                    sResolvedName = ''
                if not sResolvedName:
                    sResolvedName = _fixedUrl
                if cConfig().isBlockedHoster(sResolvedName)[0]:
                    continue
                hosters.append({
                    'link': _fixedUrl,
                    'name': sResolvedName,
                    'displayedName': sResolvedName,
                })
            continue

        if not _isValidHoster(sUrl):
            continue
        sName = sName.strip()
        if not sName:
            # fallback: hostname aus URL
            try:
                from urllib.parse import urlparse
                sName = urlparse(sUrl).hostname or sUrl
            except Exception:
                sName = sUrl

        # Blocked-Hoster-Check
        if cConfig().isBlockedHoster(sName)[0]:
            continue

        hoster = {
            'link': sUrl,
            'name': sName,
            'displayedName': sName,
        }
        hosters.append(hoster)

    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def getHosterUrl(sUrl=False):
    return [{'streamUrl': sUrl, 'resolved': False}]


def showSearch():
    """Such-Keyboard anzeigen."""
    win = xbmcgui.Window(10000)
    sSearchText = win.getProperty('xstream.kkiste.lastSearchText')
    if not sSearchText:
        sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
        if not sSearchText:
            return
        win.setProperty('xstream.kkiste.lastSearchText', sSearchText)
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    """Suche via GET — DLE akzeptiert auch GET auf /index.php?do=search."""
    # URL-Pattern: /index.php?do=search&subaction=search&story=<query>
    sSearchUrl = URL_MAIN + '/index.php?do=search&subaction=search&story=' + cParser.quote(sSearchText)
    showEntries(sSearchUrl, oGui, sSearchText)
