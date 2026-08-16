# -*- coding: utf-8 -*-

# Always pay attention to the translations in the menu!
# HTML LangzeitCache hinzugefügt
# showGenre:     48 Stunden
# showEntries:    6 Stunden
# showEpisodes:   4 Stunden

import re
import xbmcgui
from resources.lib.handler.parameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.logger import logger
from resources.lib.tools import cParser, cUtil
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
from json import loads
from datetime import datetime
from random import randint

# Globale Variable für die JSON-Daten
apiJson = None

# Domain Abfrage ###

SITE_NAME = 'API Seite'
SITE_ICON = 'api_sites.png'
SITE_IDENTIFIER = 'api_sites'

# API Seite: ein Backend, viele Mirror-Domains. Aktive Domain unten als
# Default setzen oder in den Einstellungen (plugin_api_sites.domain) ueberschreiben.
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'megakino.to')
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht
ORIGIN = 'https://' + DOMAIN + '/'
REFERER = ORIGIN + '/'

URL_API = 'https://' + DOMAIN
URL_MAIN = URL_API + '/data/browse/?lang=%s&type=%s&order_by=%s&page=%s'
URL_SEARCH = URL_API + '/data/browse/?lang=%s&order_by=%s&page=%s&limit=0'
URL_THUMBNAIL = 'https://image.tmdb.org/t/p/w300%s'
URL_WATCH = URL_API + '/data/watch/?_id=%s'


# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)


def load():
    logger.info('Load %s' % SITE_NAME)
    xbmcgui.Window(10000).clearProperty('xstream.api_sites.lastSearchText')
    params = ParameterHandler()
    sLanguage = cConfig().getSetting('prefLanguage')
    # Änderung des Sprachcodes nach voreigestellter Sprache
    if sLanguage == '0':  # prefLang Alle Sprachen
        sLang = 'all'
    elif sLanguage == '1':  # prefLang Deutsch
        sLang = '2'
    elif sLanguage == '2':  # prefLang Englisch
        sLang = '3'
    elif sLanguage == '3':  # prefLang Japanisch
        sLang = cGui().showLanguage()
        return
    else:
        sLang = 'all'
    params.setParam('sLanguage', sLang)


    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30502), SITE_IDENTIFIER, 'showMovieMenu'), params)  # Movies
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511), SITE_IDENTIFIER, 'showSeriesMenu'), params)  # Series
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)  # Search
    cGui().setEndOfDirectory()


def _cleanTitle(sTitle):
    sTitle = re.sub("[\xE4]", 'ae', sTitle)
    sTitle = re.sub("[\xFC]", 'ue', sTitle)
    sTitle = re.sub("[\xF6]", 'oe', sTitle)
    sTitle = re.sub("[\xC4]", 'Ae', sTitle)
    sTitle = re.sub("[\xDC]", 'Ue', sTitle)
    sTitle = re.sub("[\xD6]", 'Oe', sTitle)
    sTitle = re.sub("[\x00-\x1F\x80-\xFF]", '', sTitle)
    return sTitle


def _getQuality(sQuality):
    isMatch, aResult = cParser.parse(sQuality, '(HDCAM|HD|WEB|BLUERAY|BRRIP|DVD|TS|SD|CAM)', 1, True)
    if isMatch:
        return aResult[0]
    else:
        return sQuality


def _getLanguage(sRelease):
    # Sprache aus dem Release-Namen des Streams (z.B. "...German..."/"...GERMAN...")
    s = sRelease.lower()
    if 'german' in s or 'deutsch' in s:
        return 'DE'
    if 'english' in s or 'englisch' in s:
        return 'EN'
    return ''


def _apiRequest(sUrl, cacheTime=None):
    # API-Request mit Referer/Origin. Schlaegt der erste Versuch fehl, ist das beim
    # movie4k-Backend meist ein transienter Origin-404, den Cloudflare bis zu 24h cacht.
    # Darum einmal mit Cache-Buster nachfassen: andere URL -> CF-Cache-Miss -> frischer
    # Origin-Treffer, der i.d.R. wieder Daten liefert. Rueckgabe: geparstes JSON oder None.
    oRequest = cRequestHandler(sUrl, ignoreErrors=True)
    if cacheTime is not None:
        oRequest.cacheTime = cacheTime
    elif cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # HTML Cache Zeit 6 Stunden
    oRequest.addHeaderEntry('Referer', REFERER)
    oRequest.addHeaderEntry('Origin', ORIGIN)
    try:
        return loads(oRequest.request())
    except:
        pass
    sBust = sUrl + ('&' if '?' in sUrl else '?') + '_=' + str(randint(100000000, 999999999))
    oRetry = cRequestHandler(sBust, ignoreErrors=True)
    oRetry.cacheTime = 0  # Buster-URL ist einmalig, nicht cachen
    oRetry.addHeaderEntry('Referer', REFERER)
    oRetry.addHeaderEntry('Origin', ORIGIN)
    try:
        return loads(oRetry.request())
    except:
        return None


def showMovieMenu():
    params = ParameterHandler()
    sLanguage = params.getValue('sLanguage')

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'new', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30541), SITE_IDENTIFIER, 'showEntries'), params)  # Neue Filme

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'Updates', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30533), SITE_IDENTIFIER, 'showEntries'), params)  # Aktualisiert

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'name', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30542), SITE_IDENTIFIER, 'showEntries'), params)  # Alle Filme

    cGui().setEndOfDirectory()


# Serienmenue
def showSeriesMenu():
    params = ParameterHandler()
    sLanguage = params.getValue('sLanguage')

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'neu', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30514), SITE_IDENTIFIER, 'showEntries'), params)  # Neue Serien

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'Updates', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30533), SITE_IDENTIFIER, 'showEntries'), params)  # Aktualisiert

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'name', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30518), SITE_IDENTIFIER, 'showEntries'), params)  # Alle Serien

    cGui().setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    isTvshow = False
    sThumbnail = ''
    sLanguage = params.getValue('sLanguage')
    if not entryUrl: entryUrl = params.getValue('sUrl')
    aJson = _apiRequest(entryUrl)
    if aJson is None:
        if not sGui: oGui.showInfo()
        return

    if 'movies' not in aJson or not isinstance(aJson.get('movies'), list) or len(aJson['movies']) == 0:
        if not sGui: oGui.showInfo()
        return

    total = 0
    # ignore movies which does not contain any streams
    for movie in aJson['movies']:
        if '_id' in movie:
            total += 1
    for movie in aJson['movies']:
        if not '_id' in movie:
            continue
        sTitle = str(movie['title'])
        if sSearchText and not cParser.search(sSearchText, sTitle):
            continue
        if 'Staffel' in sTitle or 'Season' in sTitle:
            isTvshow = True
        oGuiElement = cGuiElement(sTitle, SITE_IDENTIFIER, 'showEpisodes' if isTvshow else 'showHosters')
        if 'poster_path_season' in movie and movie['poster_path_season']:
            sThumbnail = URL_THUMBNAIL % str(movie['poster_path_season'])
        elif 'poster_path' in movie and movie['poster_path']:
            sThumbnail = URL_THUMBNAIL % str(movie['poster_path'])
        elif 'backdrop_path' in movie and movie['backdrop_path']:
            sThumbnail = URL_THUMBNAIL % str(movie['backdrop_path'])
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        if 'storyline' in movie:
            oGuiElement.setDescription(str(movie['storyline']))
        elif 'overview' in movie:
            oGuiElement.setDescription(str(movie['overview']))
        if 'year' in movie and len(str(movie['year'])) == 4:
            oGuiElement.setYear(movie['year'])
        if 'rating' in movie:
            oGuiElement.addItemValue('rating', movie['rating'])
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        if 'runtime' in movie:
            isMatch, sRuntime = cParser.parseSingleResult(movie['runtime'], r'\d+')
            if isMatch:
                oGuiElement.addItemValue('duration', sRuntime)
        params.setParam('entryUrl', URL_WATCH % str(movie['_id']))
        params.setParam('sName', sTitle)
        params.setParam('sThumbnail', sThumbnail)
        oGui.addFolder(oGuiElement, params, isTvshow, total)

    if not sGui and not sSearchText:
        curPage = aJson['pager']['currentPage']
        if curPage < aJson['pager']['totalPages']:
            sNextUrl = entryUrl.replace('page=' + str(curPage), 'page=' + str(curPage + 1))
            params.setParam('sUrl', sNextUrl)
            oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        oGui.setView('tvshows' if isTvshow else 'movies')
        oGui.setEndOfDirectory()



def showEpisodes():
    aEpisodes = []
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue("sThumbnail")
    try:
        oRequest = cRequestHandler(sUrl)
        if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
            oRequest.cacheTime = 60 * 60 * 4  # HTML Cache Zeit 4 Stunden
        oRequest.addHeaderEntry('Referer', REFERER)
        oRequest.addHeaderEntry('Origin', ORIGIN)
        sJson = oRequest.request()
        aJson = loads(sJson)
    except:
        cGui().showInfo()
        return

    if 'streams' not in aJson or len(aJson['streams']) == 0:
        cGui().showInfo()
        return

    for stream in aJson['streams']:
        if 'e' in stream:
            aEpisodes.append(int(stream['e']))
    if aEpisodes:
        aEpisodesSorted = set(aEpisodes)
        total = len(aEpisodesSorted)
        for sEpisode in aEpisodesSorted:
            oGuiElement = cGuiElement('Episode ' + str(sEpisode), SITE_IDENTIFIER, 'showHosters')
            oGuiElement.setThumbnail(sThumbnail)
            if 's' in aJson:
                oGuiElement.setSeason(aJson['s'])
            oGuiElement.setTVShowTitle('Episode ' + str(sEpisode))
            oGuiElement.setEpisode(sEpisode)
            oGuiElement.setMediaType('episode')
            cGui().addFolder(oGuiElement, params, False, total)
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def showHosters():
    hosters = []
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    sEpisode = params.getValue('episode')
    try:
        oRequest = cRequestHandler(sUrl)
        if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
            oRequest.cacheTime = 60 * 60 * 8  # HTML Cache Zeit 8 Stunden
        oRequest.addHeaderEntry('Referer', REFERER)
        oRequest.addHeaderEntry('Origin', ORIGIN)
        sJson = oRequest.request()
        aJson = loads(sJson) if sJson else None
    except:
        return hosters
    if aJson:
        if 'streams' in aJson:
            i = 0
            for stream in aJson['streams']:
                if (('e' not in stream) or (str(sEpisode) == str(stream['e']))):
                    sHoster = str(i) + ':'
                    isMatch, aName = cParser.parse(stream['stream'], '//([^/]+)/')
                    if isMatch:
#                        sName = cParser.urlparse(sUrl) ### angezeigter hostername api
                        
                        sName = aName[0][:aName[0].rindex('.')]
                        if cConfig().isBlockedHoster(sName)[0]: continue  # Hoster aus settings.xml oder deaktivierten Resolver ausschließen
                        sHoster = sHoster + ' ' + sName
                    if 'release' in stream and str(stream['release']) != '':
                        sLang = _getLanguage(str(stream['release']))
                        if sLang:
                            sHoster = sHoster + ' [' + sLang + ']'
                        sHoster = sHoster + ' [I][' + _getQuality(stream['release']) + '][/I]'
                    hoster = {'link': stream['stream'], 'name': sHoster}
                    hosters.append(hoster)
                    i += 1
    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def getHosterUrl(sUrl=False):
    return [{'streamUrl': sUrl, 'resolved': False}]


def showSearch():
    win = xbmcgui.Window(10000)
    sSearchText = win.getProperty('xstream.api_sites.lastSearchText')
    if not sSearchText:
        sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
        if not sSearchText:
            return
        win.setProperty('xstream.api_sites.lastSearchText', sSearchText)
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    SSsearch(oGui, sSearchText)

    
def SSsearch(sGui=False, sSearchText=False):
    global apiJson
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    sLanguage = cConfig().getSetting('prefLanguage')
    
    # Falls die Daten noch nicht geladen wurden oder neu geladen werden sollen
    if apiJson is None or 'movies' not in apiJson:
        loadMoviesData()
        
    if 'movies' not in apiJson or not isinstance(apiJson.get('movies'), list) or len(apiJson['movies']) == 0:
        oGui.showInfo()
        return

    sst = sSearchText.lower()

    if not sGui:
        dialog = xbmcgui.DialogProgress()
        dialog.create(cConfig().getLocalizedString(30122), cConfig().getLocalizedString(30123))

    total = len(apiJson['movies'])
    position = 0
    for movie in apiJson['movies']:
        position += 1
        if not '_id' in movie:
            continue
        if not sGui and position % 128 == 0:  # Update progress every 128 items
            if dialog.iscanceled(): break
            dialog.update(position, str(position) + cConfig().getLocalizedString(30128) + str(total))
        sTitle = movie['title']
        if 'Staffel' in sTitle or 'Season' in sTitle:
            isTvshow = True
            sSearch = sTitle.rsplit('-', 1)[0].replace(' ', '').lower()
        else:
            isTvshow = False
            sSearch = sTitle.lower()
        if not sst in sSearch and not cUtil.isSimilarByToken(sst, sSearch):
            continue
        #logger.info('-> [DEBUG]: %s' % str(movie))
        oGuiElement = cGuiElement(sTitle, SITE_IDENTIFIER, 'showEpisodes' if isTvshow else 'showHosters')
        sThumbnail = ''
        if 'poster_path_season' in movie and movie['poster_path_season']:
            sThumbnail = URL_THUMBNAIL % str(movie['poster_path_season'])
        elif 'poster_path' in movie and movie['poster_path']:
            sThumbnail = URL_THUMBNAIL % str(movie['poster_path'])
        elif 'backdrop_path' in movie and movie['backdrop_path']:
            sThumbnail = URL_THUMBNAIL % str(movie['backdrop_path'])
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        if 'storyline' in movie:
            oGuiElement.setDescription(str(movie['storyline']))
        elif 'overview' in movie:
            oGuiElement.setDescription(str(movie['overview']))
        if 'year' in movie and len(str(movie['year'])) == 4:
            oGuiElement.setYear(movie['year'])
        if 'rating' in movie:
            oGuiElement.addItemValue('rating', movie['rating'])
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        if 'runtime' in movie:
            isMatch, sRuntime = cParser.parseSingleResult(movie['runtime'], r'\d+')
            if isMatch:
                oGuiElement.addItemValue('duration', sRuntime)
        params.setParam('entryUrl', URL_WATCH % str(movie['_id']))
        params.setParam('sName', sTitle)
        params.setParam('sThumbnail', sThumbnail)
        oGui.addFolder(oGuiElement, params, isTvshow, total)
    if not sGui:
        dialog.close()

def loadMoviesData():
    global apiJson
    sLanguage = cConfig().getSetting('prefLanguage')
    if sLanguage == '0':  # prefLang Alle Sprachen
        sLang = 'all'
    elif sLanguage == '1':  # prefLang Deutsch
        sLang = '2'
    elif sLanguage == '2':  # prefLang Englisch
        sLang = '3'
    else:
        sLang = 'all'
    
    # Grosser limit=0-Request (ganzer Katalog) -> 48h Cache. Laeuft jetzt ueber
    # _apiRequest, damit die Suche denselben CF-/Origin-404-Cache-Buster-Retry
    # hat wie die Browse-Kategorien. Vorher direkter Request ohne Retry -> auf
    # CF-Domains blieb apiJson leer (= "keine Suchergebnisse").
    data = _apiRequest(URL_SEARCH % (sLang, 'new', '1'), cacheTime=60 * 60 * 48)
    if data:
        apiJson = data
        logger.info('API-Daten erfolgreich geladen')
    else:
        logger.error('Fehler beim Laden der API-Daten')
        apiJson = {'movies': []}
        

# Daten werden lazy beim ersten Zugriff geladen (siehe SSsearch)
# loadMoviesData() - entfernt: beschleunigt den Import/Start erheblich
