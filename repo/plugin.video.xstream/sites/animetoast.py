# -*- coding: utf-8 -*-
# AnimeToast - Anime-Streaming (Ger Dub / Ger Sub)
#
# Seiten-Mechanik (server-gerendert, kein AJAX):
#   Serie  bleach-ger-dub/           -> Hoster-Tabs (PlayN/Dood/Voe/FMoon), je Tab
#                                       Block-Buttons "S1:E01-E20" ... als Staffeln.
#                                       ?link=N ist FLACH durchnummeriert: der Hoster
#                                       ergibt sich aus dem Bereich (Tab0 ab 0, Tab1 ab 10 ...).
#   Block  bleach-ger-dub/?link=20   -> verlinkt die Einzel-Folgen der gewaehlten
#                                       Staffel auf die Arc-Seite.
#   Arc    14877-2/?link=0           -> EINE Folge: #player-embed traegt die echte
#                                       Hoster-URL (z.B. voe.sx/...) -> ResolveURL.
#
# Navigation hier: Serie -> Staffel -> Hoster -> alle Folgen (des Hosters) -> Stream.

import re
import ast
import json
import xbmcgui

from resources.lib.handler.parameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.logger import logger
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui

try:
    from html import unescape as _unescape
except Exception:
    def _unescape(x):
        return x

SITE_IDENTIFIER = 'animetoast'
SITE_NAME = 'AnimeToast'
SITE_ICON = 'animetoast.png'

# Global-Search-Schalter
SITE_GLOBAL_SEARCH = True
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage (Default ohne www; den echten Host mit/ohne www traegt der
# domainCheck selbst ein, er folgt dem Redirect und speichert die Domain).
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'animetoast.cc')
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status')
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER)
# Domain ohne fuehrendes www -> Basis fuer host-flexibles Link-Matching + "intern?"-Checks
# (www/non-www und Domain-Wechsel automatisch, nur das Setting aendern).
_BASE = re.sub(r'^www\.', '', DOMAIN)
_BASE_RE = re.escape(_BASE)

URL_MAIN = 'https://' + DOMAIN + '/'
URL_INDEX_DUB = URL_MAIN + 'a-z-index-dub/'
URL_INDEX_SUB = URL_MAIN + 'a-z-index-sub/'
URL_LATEST = URL_MAIN + 'latest-uploads/'

# --- Patterns ---------------------------------------------------------------
# Listing mit Thumb (Suche / Hauptseite): Poster-Anchor + img -> (url, titel, thumb)
_RE_ENTRY = re.compile(
    r'<a\s+href="(https?://[^/"]*%s/[a-z0-9][a-z0-9-]+/)"\s+title="([^"]+)">\s*<img[^>]+src="([^"]+)"' % _BASE_RE)
# A-Z-Index: flaches <li><a href="SLUG/">Titel</a>
_RE_AZ = re.compile(
    r'<li>\s*<a\s+href="(https?://[^/"]*%s/[a-z0-9][a-z0-9-]+/)">\s*([^<]+?)\s*</a>' % _BASE_RE)
# wp-pagenavi naechste Seite
_RE_NEXT = re.compile(r'<a[^>]+class="[^"]*nextpostslink[^"]*"[^>]*href="([^"]+)"')
# Hoster-Tabs -> (tabIndex, name)
_RE_TAB = re.compile(r'<a\s+data-toggle="tab"\s+href="#multi_link_tab(\d+)">\s*([^<]+?)\s*</a>')
# multilink-btn Buttons -> (href, innererInhalt)
_RE_BTN = re.compile(r'<a\s+class="multilink-btn[^"]*"\s*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
# ?link=N aus href
_RE_LINKNUM = re.compile(r'[?&]link=(\d+)')
# Player-Embed: echte Hoster-URL (Voe als <a href>, PlayN/Dood/Mp4 als <iframe src>)
_RE_EMBED = re.compile(r'id="player-embed"[^>]*>\s*(?:<a\s+href|<iframe[^>]*?\ssrc)="([^"]+)"')
# Tab-Pane-Splitter
_RE_TABSPLIT = re.compile(r'id="multi_link_tab(\d+)"')

# Zweiter Seiten-Typ: simple-iframe-player (Episoden/URLs via admin-ajax.php)
_RE_IFRAME_PLAYER = re.compile(r'class="simple-iframe-player"\s+data-title="([^"]+)"')
_RE_NONCE = re.compile(r'iframe_loader\s*=\s*\{[^}]*?"nonce":"([^"]+)"')
_RE_SERVER_SEL = re.compile(r'<select[^>]*class="server-select"[^>]*>(.*?)</select>', re.DOTALL)
_RE_OPTION = re.compile(r'<option\s+value="(\d+)"[^>]*>\s*([^<]*?)\s*</option>')

# Slugs, die in der A-Z-Liste KEINE Serien sind (Menue/Navi)
_AZ_SKIP = ('a-z-index', 'wochenplan', 'season-', 'latest-upload', 'privacy',
            'agb', 'index-', 'category', 'genre', 'datenschutz', 'impressum')

# Hoster-Tabs, die hier ausgeblendet werden (normalisierte Namen). Aktuell leer:
# PlayN/waaw bleibt drin, auch wenn dessen Captcha ueber ResolveURL evtl. nicht
# durchgeht (bewusste Entscheidung). Liste fuer kuenftige Faelle behalten.
_SKIP_HOSTERS = ()


# --- Helfer -----------------------------------------------------------------
def _clean(s):
    # Tags raus, HTML-Entities aufloesen, Whitespace zusammenfassen.
    s = re.sub(r'<[^>]+>', '', s)
    s = _unescape(s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _hosterName(sUrl):
    # Anzeige-/Block-Check-Name aus der Domain (voe.sx -> "Voe"). Aufloesung
    # selbst macht ResolveURL anhand der URL, der Name ist nur kosmetisch.
    host = re.sub(r'^https?://', '', sUrl).split('/', 1)[0]
    part = host.split('.')[0] if host else 'Hoster'
    return part.title()


def _normHoster(s):
    # Hoster-Namen vergleichbar machen: "Voe"/"VOE"/"Voe.sx" -> "voe". Noetig, weil
    # die Tab-Reihenfolge auf Serie und Arc abweicht -> wird per Namen gematcht.
    s = (s or '').lower().strip()
    s = re.sub(r'\.(sx|com|net|to|sb|io|cc|me|stream|club|pro|live|fun|si|ws)$', '', s)
    return re.sub(r'[^a-z0-9]', '', s)


def _splitTabs(sHtml):
    # {tabIndex: chunkHtml} - Inhalt jeder Hoster-Tab-Pane. Split am Marker,
    # Chunk = alles bis zum naechsten Marker (multilink-btn gibt es nur hier).
    parts = _RE_TABSPLIT.split(sHtml)
    panes = {}
    for i in range(1, len(parts) - 1, 2):
        try:
            panes[int(parts[i])] = parts[i + 1]
        except ValueError:
            continue
    return panes


def _buttons(sChunk):
    # Liste (href, linkNum, label) aller multilink-btn im Chunk.
    out = []
    for href, inner in _RE_BTN.findall(sChunk):
        m = _RE_LINKNUM.search(href)
        if not m:
            continue
        out.append((href, int(m.group(1)), _clean(inner)))
    return out


def _slugOf(sUrl):
    # Erstes Pfad-Segment nach dem Host, domain-unabhaengig.
    m = re.search(r'https?://[^/]+/([^/?#]+)', sUrl or '')
    return m.group(1) if m else ''


def _cover(sHtml):
    # Serien-Poster aus dem og:image-Meta (WordPress/Yoast). Beide Attribut-
    # Reihenfolgen abdecken (property vor content und umgekehrt), sonst ''.
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', sHtml or '', re.I)
    if not m:
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', sHtml or '', re.I)
    return m.group(1) if m else ''


def _embedUrl(sHtml):
    # Hoster-URL aus #player-embed (a href oder iframe src), sonst ''.
    m = _RE_EMBED.search(sHtml)
    return m.group(1) if m else ''


def _epNum(sLabel):
    # Episodennummer aus einem Folgen-Label, z.B. "Ep. 12" -> 12 (erste Zahl).
    m = re.search(r'(\d+)', sLabel or '')
    return int(m.group(1)) if m else None


def _seasonRange(sLabel):
    # Episoden-Range aus einem S-Block-Label, z.B. "S2:E21-41" -> (21, 41). Format
    # auf der Seite uneinheitlich (E-Prefix mal da, mal nicht) -> erste/letzte Zahl
    # NACH dem "Sn:". Nicht erkennbar -> (None, None).
    m = re.search(r'S\d+:\D*(\d+)\D+(\d+)', sLabel or '')
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


# --- Menue ------------------------------------------------------------------
def load():  # Menuestruktur des Site-Plugins
    logger.info('Load %s' % SITE_NAME)
    xbmcgui.Window(10000).clearProperty('xstream.%s.lastSearchText' % SITE_IDENTIFIER)
    cGui().addFolder(cGuiElement('Neues', SITE_IDENTIFIER, 'showNews'))
    cGui().addFolder(cGuiElement('Seasons', SITE_IDENTIFIER, 'showSeasonArchive'))
    cGui().addFolder(cGuiElement('Index', SITE_IDENTIFIER, 'showIndexMenu'))
    cGui().addFolder(cGuiElement('Suche', SITE_IDENTIFIER, 'showSearch'))
    cGui().setEndOfDirectory()


def showIndexMenu():
    # 'Index' -> Untermenue Ger Dub / Ger Sub (beide oeffnen den A-Z-Index via showAZ).
    params = ParameterHandler()
    params.setParam('sUrl', URL_INDEX_DUB)
    cGui().addFolder(cGuiElement('Ger Dub', SITE_IDENTIFIER, 'showAZ'), params)
    params.setParam('sUrl', URL_INDEX_SUB)
    cGui().addFolder(cGuiElement('Ger Sub', SITE_IDENTIFIER, 'showAZ'), params)
    cGui().setEndOfDirectory()


def showNews():
    # Kategorie 'Neues': Kuerzlich hinzugefuegt (latest-uploads)
    # + Update/Upgrade (Startseite, heisst auf der Seite so). Beide nutzen das normale Grid.
    params = ParameterHandler()
    params.setParam('sUrl', URL_LATEST)
    cGui().addFolder(cGuiElement('Kürzlich hinzugefügt', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN)
    cGui().addFolder(cGuiElement('Update/Upgrade', SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


# --- Listen -----------------------------------------------------------------
def showEntries(entryUrl=False, sGui=False, sSearchText=False):
    # Grid-Listing mit Thumbnails (Suche, Hauptseite). Pagination via wp-pagenavi.
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl:
        entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6
    sHtmlContent = oRequest.request()
    aResult = _RE_ENTRY.findall(sHtmlContent)
    if not aResult:
        if not sGui:
            oGui.showInfo()
        return
    total = len(aResult)
    seen = set()
    for sUrl, sTitle, sThumb in aResult:
        if sUrl in seen:
            continue
        seen.add(sUrl)
        sTitle = _clean(sTitle)
        oGuiElement = cGuiElement(sTitle, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setMediaType('tvshow')
        oGuiElement.setThumbnail(sThumb)
        params.setParam('entryUrl', sUrl)
        params.setParam('sName', sTitle)
        oGui.addFolder(oGuiElement, params, True, total)
    if not sGui:
        m = _RE_NEXT.search(sHtmlContent)
        if m:
            params.setParam('sUrl', m.group(1))
            oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()


def showAZ(entryUrl=False, sGui=False, sSearchText=False):
    # Flache A-Z-Liste (<li><a>Titel</a>), Menue-/Navi-Links gefiltert.
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl:
        entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6
    sHtmlContent = oRequest.request()
    items = []
    seen = set()
    for sUrl, sTitle in _RE_AZ.findall(sHtmlContent):
        slug = _slugOf(sUrl)
        if any(b in slug for b in _AZ_SKIP) or sUrl in seen:
            continue
        seen.add(sUrl)
        items.append((sUrl, _clean(sTitle)))
    if not items:
        if not sGui:
            oGui.showInfo()
        return
    total = len(items)
    for sUrl, sTitle in items:
        oGuiElement = cGuiElement(sTitle, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setMediaType('tvshow')
        params.setParam('entryUrl', sUrl)
        params.setParam('sName', sTitle)
        oGui.addFolder(oGuiElement, params, True, total)
    if not sGui:
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()


# --- Season-Archiv (Jahr -> Season -> Grid) ---------------------------------
# Die Season-Navi steckt komplett im Mega-Menue der Startseite (server-gerendert);
# wir parsen sie live -> neue Seasons erscheinen von selbst, nichts hardgecodet.
# Jede Season ist eine eigene Archiv-Seite mit demselben Grid wie 'Update/Upgrade'.
_RE_SEASON = re.compile(r'%s/season-(winter|fruehling|sommer|herbst)-(\d{4})/' % _BASE_RE)
_SEASON_LABELS = (('winter', 'Winter'), ('fruehling', 'Frühling'),
                  ('sommer', 'Sommer'), ('herbst', 'Herbst'))


def _seasonMap():
    # {jahr(int): set(saison-slug)} aus der Startseiten-Navi.
    sHtmlContent = cRequestHandler(URL_MAIN).request()
    out = {}
    for saison, jahr in _RE_SEASON.findall(sHtmlContent):
        out.setdefault(int(jahr), set()).add(saison)
    return out


def showSeasonArchive():
    # Ebene 1: Jahre, neueste zuerst.
    oGui = cGui()
    seasons = _seasonMap()
    if not seasons:
        oGui.showInfo()
        oGui.setEndOfDirectory()
        return
    params = ParameterHandler()
    years = sorted(seasons.keys(), reverse=True)
    total = len(years)
    for jahr in years:
        oGuiElement = cGuiElement(str(jahr), SITE_IDENTIFIER, 'showSeasonArchiveYear')
        params.setParam('seasonYear', str(jahr))
        oGui.addFolder(oGuiElement, params, True, total)
    oGui.setView('seasons')
    oGui.setEndOfDirectory()


def showSeasonArchiveYear():
    # Ebene 2: vorhandene Seasons des Jahres (Winter -> Fruehling -> Sommer -> Herbst).
    # Jede Season -> showEntries auf der Season-Archiv-Seite (Grid wie 'Update/Upgrade').
    params = ParameterHandler()
    jahr = params.getValue('seasonYear')
    oGui = cGui()
    have = _seasonMap().get(int(jahr), set()) if jahr else set()
    rows = [(slug, label) for slug, label in _SEASON_LABELS if slug in have]
    if not rows:
        oGui.showInfo()
        oGui.setEndOfDirectory()
        return
    total = len(rows)
    for slug, label in rows:
        oGuiElement = cGuiElement('%s %s' % (label, jahr), SITE_IDENTIFIER, 'showEntries')
        oGuiElement.setMediaType('season')
        params.setParam('sUrl', '%sseason-%s-%s/' % (URL_MAIN, slug, jahr))
        oGui.addFolder(oGuiElement, params, True, total)
    oGui.setView('seasons')
    oGui.setEndOfDirectory()


# --- Serie -> Staffel -> Hoster -> Folgen -----------------------------------
def showSeasons():
    # Serien-Seite -> Block-Buttons (S1..Sn) eines Block-Hosters als Staffeln.
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    sName = params.getValue('sName')
    sHtmlContent = cRequestHandler(entryUrl).request()
    panes = _splitTabs(sHtmlContent)
    cover = _cover(sHtmlContent)
    params.setParam('sCover', cover)  # Serien-Poster nach unten durchreichen

    seasonBtns = []
    for idx in sorted(panes.keys()):
        blockBtns = [b for b in _buttons(panes[idx]) if re.match(r'S\d', b[2])]
        if len(blockBtns) >= 2:
            seasonBtns = blockBtns
            break

    # Kein Staffel-Raster gefunden.
    if not seasonBtns:
        # Zweiter Seiten-Typ: simple-iframe-player (AJAX) -> Server = Hoster.
        mPlayer = _RE_IFRAME_PLAYER.search(sHtmlContent)
        if mPlayer:
            showAjaxServers(entryUrl, sHtmlContent, mPlayer.group(1), sName)
            return
        # Dritter Typ (Lain): Tabs tragen die Episoden-Buttons direkt (kein Arc-Post,
        # ?link=N rendert den Embed server-seitig). -> Hoster = Tabs, je Hoster die
        # Folgen DES TABS.
        tabHosters = {}
        for i, n in _RE_TAB.findall(sHtmlContent):
            tabHosters[int(i)] = _clean(n)
        hosterRows = [(tabHosters.get(idx, 'Hoster %d' % idx), idx)
                      for idx in sorted(panes.keys())
                      if _buttons(panes[idx])
                      and _normHoster(tabHosters.get(idx, '')) not in _SKIP_HOSTERS]
        oGui = cGui()
        if hosterRows:
            total = len(hosterRows)
            for name, idx in hosterRows:
                oGuiElement = cGuiElement(name, SITE_IDENTIFIER, 'showEpisodes')
                oGuiElement.setMediaType('season')
                oGuiElement.setThumbnail(cover)
                params.setParam('entryUrl', entryUrl)
                params.setParam('sName', sName)
                params.setParam('hosterTab', str(idx))
                params.setParam('hosterName', name)
                oGui.addFolder(oGuiElement, params, True, total)
            oGui.setView('seasons')
            oGui.setEndOfDirectory()
            return
        oGui.showInfo()
        oGui.setEndOfDirectory()
        return

    oGui = cGui()
    total = len(seasonBtns)
    for pos, (href, linkNum, label) in enumerate(seasonBtns):
        oGuiElement = cGuiElement(label, SITE_IDENTIFIER, 'showSeasonHosters')
        oGuiElement.setMediaType('season')
        oGuiElement.setThumbnail(cover)
        params.setParam('entryUrl', entryUrl)
        params.setParam('sName', sName)
        params.setParam('seasonPos', str(pos))
        params.setParam('seasonLabel', label)
        oGui.addFolder(oGuiElement, params, True, total)
    oGui.setView('seasons')
    oGui.setEndOfDirectory()


def showSeasonHosters():
    # Fuer die gewaehlte Staffel je Hoster den passenden Block-Button anbieten.
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    sName = params.getValue('sName')
    seasonPos = params.getValue('seasonPos')
    seasonLabel = params.getValue('seasonLabel') or ''
    blockUrl = params.getValue('blockUrl')

    sUrl = entryUrl if entryUrl else blockUrl
    sHtmlContent = cRequestHandler(sUrl).request()
    panes = _splitTabs(sHtmlContent)
    cover = params.getValue('sCover') or _cover(sHtmlContent)
    hosterNames = {}
    for i, n in _RE_TAB.findall(sHtmlContent):
        hosterNames[int(i)] = _clean(n)

    lo, hi = _seasonRange(seasonLabel)  # Episoden-Range der Staffel, sonst (None, None)

    oGui = cGui()
    rows = []  # (label, blockUrl|False, hosterTab|False, epRange|False)
    for idx in sorted(panes.keys()):
        btns = _buttons(panes[idx])
        if not btns:
            continue
        name = hosterNames.get(idx, 'Hoster %d' % idx)
        if _normHoster(name) in _SKIP_HOSTERS:
            continue  # aktuell keine geskippt (siehe _SKIP_HOSTERS)
        blockBtns = [b for b in btns if re.match(r'S\d', b[2])]
        if blockBtns:
            # Block-Hoster: den seasonPos-ten S-Block-Button nehmen.
            try:
                href = blockBtns[int(seasonPos)][0]
            except (IndexError, ValueError):
                continue
            label = ('%s - %s' % (seasonLabel, name)) if seasonLabel else name
            rows.append((label, name, href, False, False))
        else:
            # Per-Episode-Hoster (z.B. FMoon): keine S-Bloecke, sondern Einzelfolgen.
            # Auf die Episoden-Range der Staffel eingrenzen wenn erkennbar, sonst alle.
            epNums = [n for n in (_epNum(b[2]) for b in btns) if n is not None]
            if lo is not None and epNums:
                inRange = [n for n in epNums if lo <= n <= hi]
                if not inRange:
                    continue  # Hoster hat in dieser Staffel keine Folgen
                label = '%s (Ep. %d-%d)' % (name, min(inRange), max(inRange))
                rows.append((label, name, False, str(idx), '%d-%d' % (lo, hi)))
            else:
                label = '%s (Ep. %d-%d)' % (name, min(epNums), max(epNums)) if epNums else name
                rows.append((label, name, False, str(idx), False))

    if not rows:
        oGui.showInfo()
        oGui.setEndOfDirectory()
        return

    total = len(rows)
    for label, name, href, hosterTab, epRange in rows:
        oGuiElement = cGuiElement(label, SITE_IDENTIFIER, 'showEpisodes')
        oGuiElement.setMediaType('season')
        oGuiElement.setThumbnail(cover)
        params.setParam('sName', sName)
        params.setParam('hosterName', name)
        params.setParam('entryUrl', sUrl)
        params.setParam('blockUrl', href if href else '')
        params.setParam('hosterTab', hosterTab if hosterTab else '')
        params.setParam('epRange', epRange if epRange else '')
        oGui.addFolder(oGuiElement, params, True, total)
    oGui.setView('seasons')
    oGui.setEndOfDirectory()


def showEpisodes():
    # Drei Faelle (Lain zuerst):
    # Lain : hosterTab gesetzt -> Folgen = Buttons des Tabs (Episoden inline auf der Serie).
    # A    : Block-Seite -> Embed = Arc-Post. Arc holen, Tab des Hosters per Namen, dessen Folgen.
    # B    : Embed direkt Hoster-URL -> eine einzelne Folge.
    # C    : Fallback - Folgen-Buttons auf der Block-Seite selbst (anderer Slug/Ep.).
    params = ParameterHandler()
    hosterTab = params.getValue('hosterTab')
    blockUrl = params.getValue('blockUrl')
    entryUrl = params.getValue('entryUrl')
    sName = params.getValue('sName')
    hosterName = params.getValue('hosterName') or ''
    cover = params.getValue('sCover') or ''
    oGui = cGui()

    # Lain-Stil: Folgen sind die Buttons des gewaehlten Tabs (?link=N rendert den Embed).
    if hosterTab is not False and hosterTab != '':
        epRange = params.getValue('epRange')
        sHtmlContent = cRequestHandler(entryUrl).request()
        panes = _splitTabs(sHtmlContent)
        try:
            epBtns = _buttons(panes[int(hosterTab)])
        except (KeyError, ValueError):
            epBtns = []
        # Range-Gateway (z.B. Code Geass Voe/Dood): manche Hoster-Tabs tragen nur
        # EINEN Range-Button ("Ep.1-25"), der per #player-embed auf einen Arc-Post
        # mit den echten Einzelfolgen zeigt. -> Gateway folgen, im Arc den Tab dieses
        # Hosters per Namen matchen, dessen Folgen uebernehmen. Findet sich kein
        # interner Arc/Hoster (echte 1-Stream-Range), bleibt der Button wie er ist.
        # Greift NICHT bei Plain-Per-Ep-Hostern (PlayN) - deren Labels sind Einzelfolgen.
        if len(epBtns) == 1 and re.search(r'\d+\s*-\s*\d+', epBtns[0][2]):
            arcUrl = _embedUrl(cRequestHandler(epBtns[0][0], caching=False).request())
            if arcUrl and _BASE in arcUrl and _slugOf(arcUrl) != _slugOf(entryUrl):
                arcHtml = cRequestHandler(arcUrl).request()
                arcPanes = _splitTabs(arcHtml)
                arcTabs = {}
                for i, n in _RE_TAB.findall(arcHtml):
                    arcTabs[int(i)] = _clean(n)
                tabIdx = None
                for idx, nm in arcTabs.items():
                    if _normHoster(nm) == _normHoster(hosterName):
                        tabIdx = idx
                        break
                arcBtns = _buttons(arcPanes[tabIdx]) if (tabIdx is not None and tabIdx in arcPanes) else []
                if arcBtns:
                    epBtns = arcBtns
        if epRange:
            # Per-Episode-Hoster aus dem Staffel-Flow -> auf die Staffel-Range eingrenzen.
            try:
                rlo, rhi = (int(x) for x in epRange.split('-'))
                epBtns = [b for b in epBtns
                          if _epNum(b[2]) is not None and rlo <= _epNum(b[2]) <= rhi]
            except (ValueError, TypeError):
                pass
        if not epBtns:
            oGui.showInfo()
            oGui.setEndOfDirectory()
            return
        total = len(epBtns)
        for pos, (href, linkNum, label) in enumerate(epBtns):
            epLabel = label if label else ('Folge %d' % (pos + 1))
            oGuiElement = cGuiElement(epLabel, SITE_IDENTIFIER, 'showHosters')
            oGuiElement.setMediaType('episode')
            oGuiElement.setThumbnail(cover)
            params.setParam('folgeUrl', href)
            params.setParam('sName', sName)
            oGui.addFolder(oGuiElement, params, False, total)
        oGui.setView('episodes')
        oGui.setEndOfDirectory()
        return

    sHtmlContent = cRequestHandler(blockUrl).request()
    embedUrl = _embedUrl(sHtmlContent)

    # Fall A: interner Arc-Link (anderer Post als die Block-Seite).
    if embedUrl and _BASE in embedUrl and _slugOf(embedUrl) != _slugOf(blockUrl):
        arcHtml = cRequestHandler(embedUrl).request()
        panes = _splitTabs(arcHtml)
        tabs = {}
        for i, n in _RE_TAB.findall(arcHtml):
            tabs[int(i)] = _clean(n)
        # Tab des gewaehlten Hosters per Namen (Reihenfolge Serie != Arc).
        tabIdx = None
        for idx, name in tabs.items():
            if _normHoster(name) == _normHoster(hosterName):
                tabIdx = idx
                break
        epBtns = _buttons(panes[tabIdx]) if (tabIdx is not None and tabIdx in panes) else _buttons(arcHtml)
        if epBtns:
            total = len(epBtns)
            for pos, (href, linkNum, label) in enumerate(epBtns):
                epLabel = label if label else ('Folge %d' % (pos + 1))
                oGuiElement = cGuiElement(epLabel, SITE_IDENTIFIER, 'showHosters')
                oGuiElement.setMediaType('episode')
                oGuiElement.setThumbnail(cover)
                params.setParam('folgeUrl', href)
                params.setParam('sName', sName)
                oGui.addFolder(oGuiElement, params, False, total)
            oGui.setView('episodes')
            oGui.setEndOfDirectory()
            return

    # Fall B: Embed ist direkt eine Hoster-URL -> eine einzelne Folge.
    if embedUrl and _BASE not in embedUrl:
        params.setParam('folgeUrl', blockUrl)
        showHosters()
        return

    # Fall C (Fallback): Folgen-Buttons auf der Block-Seite selbst.
    curSlug = _slugOf(blockUrl)
    epBtns = []
    for href, linkNum, label in _buttons(sHtmlContent):
        slug = _slugOf(href)
        if (slug and slug != curSlug) or re.match(r'(?i)ep\.?\s*\d', label):
            epBtns.append((href, linkNum, label))
    if epBtns:
        total = len(epBtns)
        for pos, (href, linkNum, label) in enumerate(epBtns):
            epLabel = label if label else ('Folge %d' % (pos + 1))
            oGuiElement = cGuiElement(epLabel, SITE_IDENTIFIER, 'showHosters')
            oGuiElement.setMediaType('episode')
            oGuiElement.setThumbnail(cover)
            params.setParam('folgeUrl', href)
            params.setParam('sName', sName)
            oGui.addFolder(oGuiElement, params, False, total)
        oGui.setView('episodes')
        oGui.setEndOfDirectory()
        return

    oGui.showInfo()
    oGui.setEndOfDirectory()


def showHosters():
    # Folgen-Seite holen, echte Hoster-URL aus #player-embed -> ResolveURL.
    params = ParameterHandler()
    folgeUrl = params.getValue('folgeUrl') or params.getValue('entryUrl') or params.getValue('sUrl')
    sHosterUrl = _embedUrl(cRequestHandler(folgeUrl, caching=False).request())
    # Interner Arc-/Block-Link -> einen Schritt folgen, dort den echten Embed lesen.
    if sHosterUrl and _BASE in sHosterUrl:
        sHosterUrl = _embedUrl(cRequestHandler(sHosterUrl, caching=False).request())
    hosters = []
    if sHosterUrl and _BASE not in sHosterUrl:
        sName = _hosterName(sHosterUrl)
        if not cConfig().isBlockedHoster(sName)[0]:
            hosters.append({'link': [sHosterUrl, sName], 'name': sName,
                            'displayedName': sName, 'quality': '720', 'languageCode': ''})
    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def getHosterUrl(hUrl=False):
    # Das Framework uebergibt den 'link'-Wert des Hosters = [url, name]
    # (ueber Parameter ggf. als String-Repr) -> echte Hoster-URL herausziehen.
    if isinstance(hUrl, str):
        try:
            hUrl = ast.literal_eval(hUrl)
        except (ValueError, SyntaxError):
            pass
    sUrl = hUrl[0] if isinstance(hUrl, (list, tuple)) else hUrl
    return [{'streamUrl': sUrl, 'resolved': False}]


# --- Zweiter Seiten-Typ: simple-iframe-player (AJAX) ------------------------
# Hier steht nichts im HTML; Episoden + Hoster-URL kommen per POST an
# admin-ajax.php (action=get_episode_data). "Server" = Hoster. Nonce wird
# jedes Mal frisch von der Serien-Seite gescrapt (laeuft ab, nie hardcoden).
def _ajaxEpisodeData(nonce, title, server, episode=None):
    oRequest = cRequestHandler(URL_MAIN + 'wp-admin/admin-ajax.php', caching=False)
    oRequest.addParameters('action', 'get_episode_data')
    oRequest.addParameters('title', title)
    oRequest.addParameters('server', server)
    if episode is not None:
        oRequest.addParameters('episode', str(episode))
    oRequest.addParameters('nonce', nonce)
    try:
        return json.loads(oRequest.request())
    except (ValueError, TypeError):
        return {}


def showAjaxServers(entryUrl, sHtmlContent, title, sName):
    # Server-Dropdown -> jeder Server ist ein Hoster -> showAjaxEpisodes.
    sel = _RE_SERVER_SEL.search(sHtmlContent)
    servers = _RE_OPTION.findall(sel.group(1)) if sel else []
    oGui = cGui()
    if not servers:
        oGui.showInfo()
        oGui.setEndOfDirectory()
        return
    params = ParameterHandler()
    cover = _cover(sHtmlContent)
    params.setParam('sCover', cover)  # Serien-Poster nach unten durchreichen
    total = len(servers)
    for value, label in servers:
        name = 'Server %s' % (label or value)
        oGuiElement = cGuiElement(name, SITE_IDENTIFIER, 'showAjaxEpisodes')
        oGuiElement.setMediaType('season')
        oGuiElement.setThumbnail(cover)
        params.setParam('entryUrl', entryUrl)
        params.setParam('ajaxTitle', title)
        params.setParam('server', value)
        params.setParam('sName', sName)
        oGui.addFolder(oGuiElement, params, True, total)
    oGui.setView('seasons')
    oGui.setEndOfDirectory()


def showAjaxEpisodes():
    # Episodenliste des gewaehlten Servers via AJAX. Nonce frisch scrapen.
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    title = params.getValue('ajaxTitle')
    server = params.getValue('server')
    sName = params.getValue('sName')
    cover = params.getValue('sCover') or ''
    sHtmlContent = cRequestHandler(entryUrl).request()
    oGui = cGui()
    mNonce = _RE_NONCE.search(sHtmlContent)
    if not mNonce:
        oGui.showInfo()
        oGui.setEndOfDirectory()
        return
    data = _ajaxEpisodeData(mNonce.group(1), title, server)
    episodes = data.get('data', {}).get('episodes', []) if data.get('success') else []
    if not episodes:
        oGui.showInfo()
        oGui.setEndOfDirectory()
        return
    total = len(episodes)
    for ep in episodes:
        epNum = str(ep.get('number', ''))
        epLabel = ep.get('title') or ('Folge %s' % epNum)
        oGuiElement = cGuiElement(epLabel, SITE_IDENTIFIER, 'showAjaxStream')
        oGuiElement.setMediaType('episode')
        oGuiElement.setThumbnail(cover)
        params.setParam('entryUrl', entryUrl)
        params.setParam('ajaxTitle', title)
        params.setParam('server', server)
        params.setParam('episode', epNum)
        params.setParam('sName', sName)
        oGui.addFolder(oGuiElement, params, False, total)
    oGui.setView('episodes')
    oGui.setEndOfDirectory()


def showAjaxStream():
    # Hoster-URL der gewaehlten Folge via AJAX -> ResolveURL. Nonce frisch scrapen.
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    title = params.getValue('ajaxTitle')
    server = params.getValue('server')
    episode = params.getValue('episode')
    sHtmlContent = cRequestHandler(entryUrl).request()
    hosters = []
    mNonce = _RE_NONCE.search(sHtmlContent)
    if mNonce:
        data = _ajaxEpisodeData(mNonce.group(1), title, server, episode)
        sHosterUrl = data.get('data', {}).get('url', '') if data.get('success') else ''
        if sHosterUrl:
            sName = _hosterName(sHosterUrl)
            if not cConfig().isBlockedHoster(sName)[0]:
                hosters.append({'link': [sHosterUrl, sName], 'name': sName,
                                'displayedName': sName, 'quality': '720', 'languageCode': ''})
    if hosters:
        hosters.append('getHosterUrl')
    return hosters


# --- Suche ------------------------------------------------------------------
def showSearch():
    win = xbmcgui.Window(10000)
    key = 'xstream.%s.lastSearchText' % SITE_IDENTIFIER
    sSearchText = win.getProperty(key)
    if not sSearchText:
        sSearchText = cGui().showKeyBoard(sHeading='AnimeToast Suche')
        if not sSearchText:
            return
        win.setProperty(key, sSearchText)
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    # WordPress-Suche: ?s=Begriff (Grid-Layout -> showEntries).
    try:
        from urllib.parse import quote_plus
    except ImportError:
        from urllib import quote_plus
    sUrl = URL_MAIN + '?s=' + quote_plus(sSearchText)
    showEntries(sUrl, oGui, sSearchText)
