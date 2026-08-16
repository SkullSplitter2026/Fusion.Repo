# Scraper Aufbau — Anleitung für xStream Site-Plugins


## 1. IMPORTS


Imports bitte alle oben im File für den Überblick!
xbmcgui wird fuer den Such-Cache benoetigt (Window Properties).
Siehe Sektion 5 fuer Details zum showSearch + Cache + Neue-Suche-Item Pattern.

import xbmcgui
from resources.lib.handler.parameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.logger import logger
from resources.lib.tools import cParser           # cUtil optional dazu wenn benoetigt
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui


## 2. GRUNDKONFIGURATION


Jedes Site-Plugin braucht diese Variablen am Anfang:

# Eindeutiger Bezeichner — muss dem Dateinamen ohne .py entsprechen
SITE_IDENTIFIER = 'filmpalast'

# Anzeigename im xStream Menü
SITE_NAME = 'Filmpalast'

# Icon-Dateiname (liegt in resources/art/sites/)
SITE_ICON = 'filmpalast.png'


### URLs


URL_MAIN = 'https://' + DOMAIN
URL_MOVIES = URL_MAIN + '/movies/'
URL_KINO = URL_MAIN + '/kino/'
URL_SERIES = URL_MAIN + '/serien/'
URL_SEARCH = URL_MAIN + '/?s=%s'


### Domain-Konfiguration


Die Domain wird aus den xStream Einstellungen gelesen.
So kann der User die Domain ändern falls sie sich ändert,
ohne dass das Site-Plugin angepasst werden muss.

DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'filmpalast.to')
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status')
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER)
URL_MAIN = 'https://' + DOMAIN


### Globale Suche


Die globale Suche durchsucht alle aktivierten Site-Plugins gleichzeitig.
Kann pro Site deaktiviert werden:

if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)


## 3. MEDIATYPE (Pflicht!)


MediaType MUSS bei jedem GuiElement gesetzt werden.

Warum ist das wichtig?
  - Trailer:    Die Trailer-Suche braucht den MediaType um zu wissen ob es
                ein Film ('movie') oder eine Serie ('tv') ist. Ohne MediaType
                funktioniert die Trailer-Suche nicht korrekt.
  - Kodi:       Kodi zeigt Filme und Serien unterschiedlich an (anderes Layout,
                andere Sortierung, andere Infos).
  - TMDB:       Die Metadaten-Abfrage (Poster, Beschreibung, Bewertung) braucht
                den MediaType um beim richtigen Endpunkt zu suchen.
  - Globale Suche: Die globale Suche unterscheidet zwischen Filmen und Serien
                und sortiert die Ergebnisse entsprechend.

Erlaubte Werte:
  'movie'     Film
  'tvshow'    Serie (Haupteintrag / Übersicht)
  'season'    Staffel
  'episode'   Einzelne Episode


### Wann welchen Wert setzen?


Situation 1: Gemischter Inhalt — Standard (Filme + Serien auf einer Seite)
    Viele Seiten wie Filmpalast oder TopStreamFilm haben Filme und Serien gemischt.
    Hier muss pro Eintrag erkannt werden ob es ein Film oder eine Serie ist.
    Standard-Richtung: prüfe ob Serie, sonst Film.

    oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')

Situation 2: Gemischter Inhalt — Umgekehrt (Standard ist Serie, prüfe ob Film)
    Manche Seiten (z.B. AniWorld) sind primär Serien-Seiten, haben aber auch
    einzelne Filme. Hier ist die Logik umgedreht: Standard ist Serie,
    nur wenn explizit ein Film erkannt wird, setze 'movie'.

    oGuiElement.setMediaType('movie' if isMovie else 'tvshow')

    AniWorld nutzt das z.B. in der Staffel-Ansicht — wenn die URL auf
    '/filme' endet, ist es ein Film, sonst eine Staffel:

    isMovie = sUrl.endswith('filme')
    oGuiElement.setMediaType('season' if not isMovie else 'movie')

    Und in der Episoden-Ansicht — wenn es eine Filmliste ist,
    zeige 'movie' statt 'episode':

    oGuiElement.setMediaType('episode' if not isMovieList else 'movie')

Situation 3: Nur Serien (z.B. SerienStream, AniWorld, BurningSeries)
    Wenn die Seite ausschließlich Serien hat, einfach fest setzen:

    oGuiElement.setMediaType('tvshow')

Situation 4: Nur Filme (z.B. Einschalten, InternetArchive)
    Wenn die Seite ausschließlich Filme hat:

    oGuiElement.setMediaType('movie')

Situation 5: Getrennte Funktionen (z.B. Streamcloud)
    Manche Seiten haben separate Funktionen für Filme und Serien.
    Dann wird der MediaType in jeder Funktion fest gesetzt:

    def showMovieEntries():    # Nur Filme
        oGuiElement.setMediaType('movie')

    def showSeriesEntries():   # Nur Serien
        oGuiElement.setMediaType('tvshow')

Situation 6: Staffel-Ansicht
    oGuiElement.setMediaType('season')
    oGuiElement.setSeason(sSeason)

Situation 7: Episoden-Ansicht
    oGuiElement.setMediaType('episode')


## 4. FILM/SERIE ERKENNUNG (TMDB)


Wenn eine Seite gemischten Inhalt hat, muss pro Eintrag erkannt werden
ob es ein Film oder eine Serie ist. Es gibt zwei Methoden:


### Methode 1: Erkennung über Laufzeit


Einfachste Methode: Wenn die Laufzeit unter einem bestimmten Wert liegt
(z.B. 70 Minuten), ist es wahrscheinlich eine Serie.

    isDuration, sDuration = cParser.parseSingleResult(sDummy, r'time">([\d]+)')
    if int(sDuration) <= 70:
        isTvshow = True
    else:
        isTvshow = False

Problem: Nicht immer zuverlässig. Manche Filme sind kurz, manche
Serienepisoden sind lang.


### Methode 2: Erkennung über TMDB (genauer)


TMDB wird gefragt ob der Titel ein bekannter Film ist.
Wenn ja → Film. Wenn nicht → wahrscheinlich Serie.

    from resources.lib.tmdb.api import cTMDB
    oMetaget = cTMDB()
    if oMetaget:
        if isYear:
            meta = oMetaget.search_movie_name(sName, year=sYear)
        else:
            meta = oMetaget.search_movie_name(sName)
        if meta and 'id' in meta:
            isTvshow = False    # TMDB hat den Film gefunden
        else:
            isTvshow = True     # Nicht als Film gefunden → Serie
    else:
        isTvshow = False        # TMDB nicht verfügbar → Fallback auf Film


### Methode 3: Kombination (empfohlen)


Erst Laufzeit prüfen, dann bei Bedarf TMDB fragen:

    isDuration, sDuration = cParser.parseSingleResult(sDummy, r'time">([\d]+)')
    if int(sDuration) <= 70:
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


### Danach MediaType und Funktion setzen


    oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons' if isTvshow else 'showHosters')
    oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')

Erklärung:
  - Wenn Serie: Klick führt zu showSeasons() (Staffel-Auswahl)
  - Wenn Film:  Klick führt zu showHosters() (Hoster-Auswahl)


## 5. SUCH-CACHE (Site-interne Suche)


Der Such-Cache speichert den Suchbegriff als Kodi Window-Property.
Damit muss der User den Suchbegriff nicht erneut eingeben wenn er nach
der Wiedergabe eines Films/Trailers zurücknavigiert.

Globale Suche (xstream.py / globalSearch) nutzt das gleiche Cache-Pattern.


### Wie funktioniert es?


Der Cache nutzt Window(10000) — das ist Kodis globales Home-Window.
Properties die dort gesetzt werden bleiben bestehen bis Kodi beendet wird
oder bis sie explizit gelöscht werden.

Property-Name:  xstream.<SITE_IDENTIFIER>.lastSearchText
Beispiele:      xstream.filmpalast.lastSearchText
                xstream.topstreamfilm.lastSearchText
                xstream.hdfilme.lastSearchText


### Ablauf Schritt fuer Schritt


1. User oeffnet Site-Menue (load())
   → Such-Cache wird geleert (damit alte Suchbegriffe nicht haengen bleiben)

2. User klickt auf "Suche" (showSearch())
   → Kein Cache vorhanden → Tastatur oeffnet sich
   → User tippt Suchbegriff ein
   → Suchbegriff wird als Window Property gespeichert
   → Suche wird ausgefuehrt, Ergebnisse angezeigt

3. User waehlt einen Film/Serie aus → schaut Trailer oder Stream

4. User navigiert zurueck zur Suchliste (showSearch() wird erneut aufgerufen)
   → Cache vorhanden → Suchbegriff wird aus Property gelesen
   → KEINE Tastatur → Suche laeuft direkt mit dem gecachten Begriff
   → Ergebnisse erscheinen sofort

5. User navigiert weiter zurueck ins Site-Menue (load())
   → Cache wird geleert → naechste Suche startet frisch


### Implementierung


Muss an ZWEI Stellen eingebaut werden:

  1. In load()       — Cache leeren
  2. In showSearch() — Cache lesen oder Tastatur oeffnen

Wichtig: xbmcgui muss oben im File importiert sein!


### Stelle 1: In load() — Cache leeren


def load():
    logger.info('Load %s' % SITE_NAME)
    xbmcgui.Window(10000).clearProperty('xstream.<SITE_IDENTIFIER>.lastSearchText')
    params = ParameterHandler()
    # ... Menue-Eintraege ...
    cGui().setEndOfDirectory()


### Stelle 2: In showSearch() — Cache nutzen


def showSearch():
    win = xbmcgui.Window(10000)
    sSearchText = win.getProperty('xstream.<SITE_IDENTIFIER>.lastSearchText')
    if not sSearchText:
        sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
        if not sSearchText: return
        win.setProperty('xstream.<SITE_IDENTIFIER>.lastSearchText', sSearchText)
    _search(False, sSearchText)
    cGui().setEndOfDirectory()

Hinweis: setProperty() wird NUR aufgerufen wenn der User tatsaechlich neu
ueber die Tastatur eingegeben hat. Kommt der Suchbegriff aus dem Cache,
wird er direkt weiterverwendet ohne erneut gesetzt zu werden.


### Year-Suche analog


Sites mit showYearSearch (aniworld, fhdfilme, topstreamfilm)
nutzen das gleiche Pattern mit lastYear Property.


## 6. HTML-CACHE (Request-Cache)


Der requestHandler hat einen eingebauten HTML-Cache.
Damit werden Seiteninhalte nicht bei jedem Aufruf neu geladen.
Die Cache-Zeiten werden in Sekunden angegeben.

Empfohlene Cache-Zeiten:
  Menüseiten / Kategorien:  48 Stunden  (selten ändern sich Kategorien)
  Filmlisten / Einträge:     6 Stunden  (neue Filme kommen regelmäßig)
  Staffel-Listen:            6 Stunden  (Staffeln ändern sich selten)
  Episodenlisten:            4 Stunden  (Episoden ändern sich selten)
  Hoster-Links:              KEIN Cache (caching=False, immer frisch laden!)

Beispiel mit Cache:
    oRequest = cRequestHandler(sUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    sHtmlContent = oRequest.request()

Für Hoster-Links IMMER Cache deaktivieren (Links ändern sich ständig):
    sHtmlContent = cRequestHandler(sUrl, caching=False).request()


## 7. FUNKTIONS-TEMPLATES


Hier die Standard-Funktionen die jedes Site-Plugin braucht.
Die HTML-Patterns müssen an die jeweilige Seite angepasst werden,
aber die Struktur bleibt immer gleich.


### 7.1 load() — Hauptmenü


def load():
    logger.info('Load %s' % SITE_NAME)
    xbmcgui.Window(10000).clearProperty('xstream.<SITE_IDENTIFIER>.lastSearchText')
    params = ParameterHandler()
    params.setParam('sUrl', URL_KINO)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30501), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MOVIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30562), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_SERIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('Value', 'KATEGORIEN')
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showValue'), params)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30564), SITE_IDENTIFIER, 'showYearSearch'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)
    cGui().setEndOfDirectory()

Wichtig:
  - clearProperty() am Anfang → Such-Cache leeren beim Site-Menue-Aufruf
    (siehe Sektion 5)
  - Jeder Menüeintrag braucht einen cGuiElement mit:
    - Anzeigename (am besten getLocalizedString für Mehrsprachigkeit)
    - SITE_IDENTIFIER (damit xStream weiß welches Plugin)
    - Funktionsname der aufgerufen wird (z.B. 'showEntries')


### 7.2 showEntries() — Film-/Serienlisten


def showEntries(entryUrl=False, sGui=False, sSearchText=False, sSearchPageText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    isTvshow = False
    if not entryUrl: entryUrl = params.getValue('sUrl')

    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    sHtmlContent = oRequest.request()

    # Pattern an die Seite anpassen!
    pattern = 'class="item">.*?href="([^"]+).*?src="([^"]+).*?title">([^<]+)(.*?)</div>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    for sUrl, sThumbnail, sName, sDummy in aResult:
        # Bei Suche: nur Treffer anzeigen die zum Suchbegriff passen
        if sSearchText and not cParser.search(sSearchText, sName):
            continue

        # Jahr und Qualität aus dem HTML extrahieren
        isYear, sYear = cParser.parseSingleResult(sDummy, r'year">([\d]+)')
        isQuality, sQuality = cParser.parseSingleResult(sDummy, 'quality">([^<]+)')
        isDesc, sDesc = cParser.parseSingleResult(sDummy, 'description"><p>([^<]+)')

        # Film/Serie Erkennung (siehe Abschnitt 4)
        # ... isTvshow = True/False ...

        # GuiElement erstellen
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons' if isTvshow else 'showHosters')
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')   # PFLICHT!
        oGuiElement.setThumbnail(sThumbnail)
        if isYear:
            oGuiElement.setYear(sYear)
        if isQuality:
            oGuiElement.setQuality(sQuality)
        if isDesc:
            oGuiElement.setDescription(sDesc)

        # Parameter für die nächste Funktion setzen
        params.setParam('entryUrl', sUrl)
        params.setParam('sThumbnail', sThumbnail)
        params.setParam('sDesc', sDesc)
        params.setParam('sName', sName)                    # fuer setTVShowTitle in showSeasons
        if isYear:
            params.setParam('sYear', sYear)                # Year an showSeasons weitergeben (Trailer-Match)
        oGui.addFolder(oGuiElement, params, isTvshow, total)

    # Pagination und View NUR wenn nicht aus globaler Suche
    if not sGui and not sSearchText and not sSearchPageText:
        isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, 'href="([^"]+)">Next')

        # Seitensprung-Funktion (optional, siehe 7.10)
        isMatchSiteSearch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, 'class="wp-pagenavi">(.*?)Next')
        if isMatchSiteSearch:
            isMatch, aResult = cParser.parse(sHtmlContainer, r'<span>([\d]+)</span>.*?nav_ext">.*?">([\d]+)</a>.*?href="([^"]+)')
            if isMatch:
                for sPageActive, sPageLast, sNextPage in aResult:
                    sPageName = cConfig().getLocalizedString(30284) + str(sPageActive) + cConfig().getLocalizedString(30285) + str(sPageLast) + cConfig().getLocalizedString(30286)
                    params.setParam('sNextPage', sNextPage)
                    params.setParam('sPageLast', sPageLast)
                    oGui.searchNextPage(sPageName, SITE_IDENTIFIER, 'showSearchPage', params)

        if isMatchNextPage:
            params.setParam('sUrl', sNextUrl)
            oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        oGui.setView('tvshows' if isTvshow else 'movies')
        oGui.setEndOfDirectory()

Parameter erklärt:
  entryUrl        — URL der Seite (oder False → aus ParameterHandler)
  sGui            — GUI-Objekt von der globalen Suche (oder False)
  sSearchText     — Suchbegriff zum Filtern (oder False)
  sSearchPageText — Seitennummer vom Seitensprung (oder False)

Wenn sGui gesetzt ist, kommt der Aufruf von der globalen Suche.
Dann KEIN setEndOfDirectory() und KEINE Pagination!


### 7.3 showSeasons() — Staffel-Auswahl


Wird aufgerufen wenn der User auf eine Serie klickt.
Zeigt alle verfügbaren Staffeln an.

def showSeasons():
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue('sThumbnail')
    isDesc = params.getValue('sDesc')
    sName = params.getValue('sName') or ''             # Show-Titel fuer setTVShowTitle (Season-Trailer)
    sYear = params.getValue('sYear') or ''             # Year fuer addItemValue (Trailer-Match)

    oRequest = cRequestHandler(sUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    sHtmlContent = oRequest.request()

    # Pattern für Staffeln — an die Seite anpassen!
    pattern = '<div class="season">(.*)</ul>'
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, r'"#season-(\d+)')
    if not isMatch:
        cGui().showInfo()
        return

    total = len(aResult)
    for sSeason in aResult:
        oGuiElement = cGuiElement(cConfig().getLocalizedString(30512) + ' ' + str(sSeason), SITE_IDENTIFIER, 'showEpisodes')
        oGuiElement.setSeason(sSeason)
        oGuiElement.setMediaType('season')         # PFLICHT!
        if sName:
            oGuiElement.setTVShowTitle(sName)      # PFLICHT fuer Season-Trailer-Support
        oGuiElement.setThumbnail(sThumbnail)
        if sYear:
            oGuiElement.addItemValue('year', sYear)
        if isDesc:
            oGuiElement.setDescription(isDesc)
        cGui().addFolder(oGuiElement, params, True, total)
    cGui().setView('seasons')
    cGui().setEndOfDirectory()

Wichtig:
  - setSeason() setzt die Staffelnummer
  - setMediaType('season') ist Pflicht
  - setTVShowTitle(sName) ist Pflicht fuer Season-Trailer-Support
    (sonst sucht Trailer mit "Staffel 1" statt mit Show-Name)
  - setView('seasons') für korrekte Kodi-Darstellung
  - params werden automatisch weitergereicht (entryUrl, sThumbnail etc.)


### 7.4 showEpisodes() — Episoden-Auswahl


Wird aufgerufen wenn der User auf eine Staffel klickt.
Zeigt alle Episoden dieser Staffel an.

def showEpisodes():
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue('sThumbnail')
    sSeason = params.getValue('season')
    isDesc = params.getValue('sDesc')

    oRequest = cRequestHandler(entryUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 4  # 4 Stunden
    sHtmlContent = oRequest.request()

    # Pattern: Episoden der gewählten Staffel finden
    pattern = 'id="season-%s(.*?)</ul>' % sSeason
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, r'data-title="Episode\s(\d+)')
    if not isMatch:
        cGui().showInfo()
        return

    total = len(aResult)
    for sEpisode in aResult:
        oGuiElement = cGuiElement(cConfig().getLocalizedString(30513) + ' ' + str(sEpisode), SITE_IDENTIFIER, 'showEpisodeHosters')
        oGuiElement.setThumbnail(sThumbnail)
        if isDesc:
            oGuiElement.setDescription(isDesc)
        oGuiElement.setMediaType('episode')        # PFLICHT!
        params.setParam('entryUrl', entryUrl)
        params.setParam('season', sSeason)
        params.setParam('episode', sEpisode)
        cGui().addFolder(oGuiElement, params, False, total)
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


### 7.5 showEpisodeHosters() — Hoster für eine Episode


def showEpisodeHosters():
    hosters = []
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    sSeason = params.getValue('season')
    sEpisode = params.getValue('episode')
    sHtmlContent = cRequestHandler(sUrl, caching=False).request()
    pattern = 'id="season-%s">(.*?)</ul>' % sSeason
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        pattern = '>%s</a>(.*?)</li>' % sEpisode
        isMatch, sHtmlLink = cParser.parseSingleResult(sHtmlContainer, pattern)
        if isMatch:
            isMatch, aResult = cParser.parse(sHtmlLink, 'data-link="([^"]+)')
            if isMatch:
                sQuality = '720'
                for sUrl in aResult:
                    if 'youtube' in sUrl: continue
                    elif sUrl.startswith('//'): sUrl = 'https:' + sUrl
                    sName = cParser.urlparse(sUrl).split('.')[0].strip()
                    if cConfig().isBlockedHoster(sName)[0]: continue
                    hoster = {'link': sUrl, 'name': sName, 'displayedName': '%s [I][%sp][/I]' % (sName, sQuality), 'quality': sQuality}
                    hosters.append(hoster)
    if hosters:
        hosters.append('getHosterUrl')
    return hosters


### 7.6 showHosters() — Hoster für einen Film


def showHosters():
    hosters = []
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    sHtmlContent = cRequestHandler(sUrl, caching=False).request()
    pattern = 'data-link="([^"]+)'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if isMatch:
        sQuality = '720'
        for sUrl in aResult:
            if 'youtube' in sUrl: continue
            elif sUrl.startswith('//'): sUrl = 'https:' + sUrl
            sName = cParser.urlparse(sUrl).split('.')[0].strip()
            if cConfig().isBlockedHoster(sName)[0]: continue
            hoster = {'link': sUrl, 'name': sName, 'displayedName': '%s [I][%sp][/I]' % (sName, sQuality), 'quality': sQuality}
            hosters.append(hoster)
    if hosters:
        hosters.append('getHosterUrl')
    return hosters


### 7.7 getHosterUrl() — Finale Stream-URL


def getHosterUrl(sUrl=False):
    return [{'streamUrl': sUrl, 'resolved': False}]

'resolved': False  = ResolveURL soll den Link noch auflösen
'resolved': True   = Link ist bereits der finale Stream


### 7.8 showSearch() + _search() — Suche


WICHTIG: Such-Cache nutzen wie in Sektion 5 beschrieben! Pattern unten zeigt
die volle Version mit Window-Property-Cache. Ohne Cache muss der User den
Suchbegriff nach jeder Trailer/Stream-Wiedergabe neu eingeben.

def showSearch():
    win = xbmcgui.Window(10000)
    sSearchText = win.getProperty('xstream.<SITE_IDENTIFIER>.lastSearchText')
    if not sSearchText:
        sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
        if not sSearchText: return
        win.setProperty('xstream.<SITE_IDENTIFIER>.lastSearchText', sSearchText)
    _search(False, sSearchText)
    cGui().setEndOfDirectory()

def _search(oGui, sSearchText):
    showEntries(URL_SEARCH % cParser.quotePlus(sSearchText), oGui, sSearchText)

Plus in load() Cache leeren beim Site-Menue-Aufruf — siehe Sektion 5 + 7.1.


### 7.9 showValue() — Kategorien / Genre


def showValue():
    params = ParameterHandler()
    oRequest = cRequestHandler(URL_MAIN)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 48  # 48 Stunden
    sHtmlContent = oRequest.request()
    pattern = '>{0}</a>(.*?)</ul>'.format(params.getValue('Value'))
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


### 7.10 showSearchPage() — Seitensprung


Erlaubt dem User direkt auf eine bestimmte Seitenzahl zu springen,
anstatt sich Seite für Seite durchzuklicken.
Wird in showEntries() über oGui.searchNextPage() eingebunden.

def showSearchPage():
    params = ParameterHandler()
    sNextPage = params.getValue('sNextPage')
    sPageLast = params.getValue('sPageLast')
    sHeading = cConfig().getLocalizedString(30282) + str(sPageLast)
    sSearchPageText = cGui().showKeyBoard(sHeading=sHeading)
    if not sSearchPageText: return
    sNextSearchPage = sNextPage.split('page/')[0].strip() + 'page/' + sSearchPageText + '/'
    showEntries(sNextSearchPage)
    cGui().setEndOfDirectory()


### 7.11 showYearSearch() — Jahressuche


Erlaubt dem User nach einem bestimmten Erscheinungsjahr zu filtern.
Öffnet die Tastatur und erstellt daraus eine Such-URL.

def showYearSearch():
    sYear = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30563))
    if not sYear: return
    searchUrl = URL_MAIN + '/xfsearch/' + sYear
    showEntries(searchUrl)
    cGui().setEndOfDirectory()


## 8. PARAMETER WEITERGEBEN


Parameter werden über den ParameterHandler von Funktion zu Funktion
weitergegeben. Wichtig: Alle Daten die die nächste Funktion braucht
müssen VOR dem addFolder() gesetzt werden.

Typische Parameter:

  params.setParam('sUrl', sUrl)              # URL für showEntries
  params.setParam('entryUrl', sUrl)          # Detail-URL für showSeasons/showHosters
  params.setParam('sThumbnail', sThumbnail)  # Thumbnail weitergeben
  params.setParam('sDesc', sDesc)            # Beschreibung weitergeben
  params.setParam('season', sSeason)         # Staffelnummer für showEpisodes
  params.setParam('episode', sEpisode)       # Episodennummer für showEpisodeHosters
  params.setParam('Value', 'KATEGORIEN')     # Genre-Auswahl für showValue
  params.setParam('TVShowTitle', sName)      # Serienname (für Serien-only Seiten)

In der nächsten Funktion dann auslesen:

  sUrl = params.getValue('entryUrl')
  sThumbnail = params.getValue('sThumbnail')
  sSeason = params.getValue('season')


### setTVShowTitle()


setTVShowTitle ist PFLICHT bei jeder Site mit setMediaType('season').
Ohne setTVShowTitle sucht der Season-Trailer mit dem ListItem-Title
(z.B. "Staffel 1") statt mit dem Show-Namen — der Trailer findet
nichts oder den falschen.

Gilt fuer:
  - Serien-only Seiten (AniWorld, SerienStream, BurningSeries)
  - Mix-Sites mit Serien (TopStreamFilm, FHDFilme, FilmPalast,
    Moflix-Stream, Kinoger)

    oGuiElement.setTVShowTitle(sName)
    params.setParam('TVShowTitle', sName)        # bei Serien-only Pattern
    # ODER
    params.setParam('sName', sName)              # bei Mix-Sites Pattern


### addItemValue('originaltitle') — Clean-Title fuer Movie-Trailer

Bei Sites die fuer Movie-Items einen verseuchten Display-Label brauchen
(z.B. Anime-Sites mit Episode-Prefix wie "1 - Film 1 - <Originaltitel>"),
kann zusaetzlich ein Clean-Titel via originaltitle gesetzt werden.

**Was macht das System (gui.py Z230+):**

Der Trailer-Context-Menu in gui.py liest bei setMediaType('movie') primaer
itemValues['originaltitle'] und faellt nur dann auf getTitle() (Display-Label)
zurueck wenn nichts gesetzt ist. Code-Stelle:

    if oGuiElement._mediaType == 'movie':
        _trailerTitle = itemValues.get('originaltitle', '') or oGuiElement.getTitle()

Das ermoeglicht Sites, einen sauberen Movie-Titel an die Trailer-Pipeline
weiterzugeben ohne den Display-Label fuer den User zu aendern.

**Wie eine Site das nutzt:**

    oGuiElement.setMediaType('movie')
    oGuiElement.addItemValue('originaltitle', cleanTitle)

cleanTitle sollte der eigentliche Filmtitel sein ohne Episode-Prefixe,
Listing-Marker oder andere UI-Konventionen.

**Goldstandard-Beispiel:**

  sites/aniworld.py showEpisodes — Movie-Branch nutzt sNameEng aus dem
  HTML-Parser-Tuple als Clean-Title. Das HTML liefert pro Movie-Item
  einen separaten, sauberen englischen Titel (z.B. "Saga of Tanya the
  Evil: The Movie"). Phase-0-TMDB-Search findet damit zuverlaessig die
  TMDB-ID, Trailer-Pipeline laeuft.

**VORSICHT — wann NICHT setzen:**

Nur setzen wenn die Site einen wirklich spezifischen Movie-Titel im HTML
hat. Bei generischen Episode-Titeln (z.B. nur "The Movie", "Der Film")
wuerde Phase-0 mit dem Wildcard-Term auf TMDB einen Random-Match liefern
(z.B. ein zufaelliger anderer Film namens "The Movie").

Konkretes Beispiel was NICHT funktioniert:
  sites/serienstream.py Specials — HTML hat nur generische Episode-Titel
  ("The Movie [Movie]"). Patch wurde versucht und produzierte Random-
  Trailer (Mario-Galaxy-Movie statt Tanya). Bewusst zurueckgenommen:
  serienstream setzt deshalb KEIN originaltitle fuer Specials.
  Trailer-Menu erscheint trotzdem dank setMediaType('movie'), Phase-0
  findet meist nichts → "Kein Trailer gefunden" Notify ist akzeptiert.

**Ohne originaltitle:**

Phase-0-TMDB-Search nutzt getTitle() = Display-Label. Wenn der Label
Listing-Praefixe enthaelt ("1 - Film 1 - ..."), findet TMDB meist nichts
spezifisches → kein Trailer. Bei generischem Label kann es zu Random-
Matches kommen — drum lieber Label sauber halten oder originaltitle setzen.


## 8a. ANTI-BOT / TOKEN-FLOWS


Manche Sites liefern beim ersten GET nur einen JS-Stub der einen Token-
Endpoint hittet. Erst nach Token+Cookie kommt das echte HTML beim zweiten
GET zurueck. Typische Detektion: Response < 1KB + spezifischer Marker.

**Beispiel megakino (yg=token Flow):**

  def getHtmlContent(url):
      sessionUA = cRequestHandler.RandomUA()  # einmal pro Session-Flow!
      oRequest = cRequestHandler(url, bypass_dns=True)
      oRequest.cacheTime = 0
      oRequest.addHeaderEntry('User-Agent', sessionUA)
      oRequest.addHeaderEntry('Referer', URL_MAIN)
      sHtmlContent = oRequest.request()

      # Token-Stub erkannt -> Token holen + Original-URL retry
      if sHtmlContent and 'yg=token' in sHtmlContent and len(sHtmlContent) < 1000:
          oTokenRequest = cRequestHandler(URL_MAIN + 'index.php?yg=token', bypass_dns=True)
          oTokenRequest.cacheTime = 0
          oTokenRequest.addHeaderEntry('User-Agent', sessionUA)  # SELBER UA!
          oTokenRequest.addHeaderEntry('Referer', url)
          oTokenRequest.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
          oTokenRequest.request()

          # Original-URL nochmal abrufen mit Cookie
          oRequest2 = cRequestHandler(url, bypass_dns=True)
          oRequest2.cacheTime = 0
          oRequest2.addHeaderEntry('User-Agent', sessionUA)  # SELBER UA!
          oRequest2.addHeaderEntry('Referer', URL_MAIN)
          sHtmlContent = oRequest2.request()

      return sHtmlContent if sHtmlContent and len(sHtmlContent) > 1000 else None

**Wichtige Regeln:**

1. **UA-Stickiness:** Alle Requests im Token-Flow MUESSEN identischen UA
   nutzen. Cookies sind oft an UA gebunden, Anti-Bot-Systeme pruefen
   UA-Konsistenz zwischen Token+Folge-Requests. Drum einmal RandomUA()
   am Anfang aufrufen und an alle Requests weitergeben.

2. **cacheTime = 0:** Token-Flow-Requests duerfen NIE gecacht werden,
   sonst wird der einmalige Token-Stub als Permanent-Antwort gespeichert.

3. **Detektion-Marker:**
   - Response < 1KB Laenge = wahrscheinlich Stub, nicht echtes HTML
   - Marker im Body: 'yg=token' (megakino), 'cf-challenge' (Cloudflare),
     'jschl_vc' (Cloudflare JS-Challenge), 'turnstile' (Captcha)
   - HTTP 401 mit JSON-body = oft Auth-Token-Endpoint

4. **Referer-Header:** Token-Endpoint braucht oft den Original-URL als
   Referer (siehe megakino: Token-Request hat Referer=url, nicht URL_MAIN).
   Der zweite Original-GET hat dann wieder Referer=URL_MAIN.


## 9. PAGINATION (Nächste Seite)


Wenn eine Seite mehrere Ergebnisseiten hat:

    isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, 'href="([^"]+)">Next')
    if isMatchNextPage:
        params.setParam('sUrl', sNextUrl)
        oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)

Pagination nur anzeigen wenn NICHT aus der globalen Suche:

    if not sGui and not sSearchText:
        # Pagination hier
        oGui.setView('movies')
        oGui.setEndOfDirectory()


## 10. SPRACHFUNKTION


Sprachauswahl aus den xStream Einstellungen:

    sLanguage = cConfig().getSetting('prefLanguage')
    0 = Alle Sprachen
    1 = Deutsch
    2 = English
    3 = Japanisch

Beispiel im Menü:

    def load():
        params = ParameterHandler()
        sLanguage = cConfig().getSetting('prefLanguage')
        if sLanguage == '1':      # 1 = Deutsch
            sLanguage = '2'
        elif sLanguage == '2':    # 2 = Englisch
            sLanguage = '3'
        else:
            sLanguage = 'all'     # 0 = Alle Sprachen
        params.setParam('sLanguage', sLanguage)


## 11. QUALITÄTSFUNKTION


Qualitätsauswahl aus den xStream Einstellungen:

    sQuality = cConfig().getSetting('preferedQuality')
    params.setParam('sQuality', sQuality)


## 12. SEITEN NUR MIT SERIEN (Beispiel AniWorld)


Wenn eine Seite nur Serien hat, ist alles einfacher:
  - Kein Film/Serie Erkennung nötig
  - MediaType immer 'tvshow'
  - Klick geht immer auf showSeasons()
  - setTVShowTitle() für korrekten Serientitel in Episodenansicht

def showEntries(entryUrl=False, sGui=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl:
        entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6
    sHtmlContent = oRequest.request()

    pattern = '<a href="([^"]+).*?src="([^"]+).*?<h3>(.*?)<'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    for sUrl, sThumbnail, sName in aResult:
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setThumbnail(sThumbnail)
        oGuiElement.setMediaType('tvshow')          # Immer tvshow!
        oGuiElement.setTVShowTitle(sName)            # Serientitel setzen
        params.setParam('sUrl', URL_MAIN + sUrl)
        params.setParam('TVShowTitle', sName)
        oGui.addFolder(oGuiElement, params, True, total)
    if not sGui:
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()


## 13. KOMPLETTER ABLAUF (Übersicht)


Film-Seite:
  load() → showEntries() → showHosters() → getHosterUrl() → Wiedergabe

Serien-Seite:
  load() → showEntries() → showSeasons() → showEpisodes()
       → showEpisodeHosters() → getHosterUrl() → Wiedergabe

Suche:
  load() → showSearch() → _search() → showEntries(sSearchText)
       → showHosters/showSeasons → ...

Globale Suche:
  xstream.py searchGlobal() → _search(oGui, sSearchText)
       → showEntries(sGui=oGui) → Ergebnisse

Kategorien:
  load() → showValue() → showEntries() → ...

Seitensprung:
  showEntries() → searchNextPage → showSearchPage() → showEntries(page)

Jahressuche:
  load() → showYearSearch() → showEntries() → ...


## 14. WRAPPER-RESOLVER (resources/lib/wrappers/)


Manche Sites zeigen ihre Hoster nicht direkt an, sondern verlinken auf
externe Wrapper-Plattformen (Aggregatoren wie meinecloud), die dann erst
die echten Hoster ausspucken. Statt diese Wrapper-Logik in jedem Site-File
zu duplizieren liegt sie zentral im Ordner resources/lib/wrappers/ — pro Plattform ein File, eine
Sektion pro Wrapper-Plattform.

Hinweis: Die Plattform heisst technisch meinecloud. Sites labeln sie
unterschiedlich ('Sirius', 'meinecloud', 'Server 1' etc.) — alles dasselbe.


### Aktuell vorhanden


  meinecloud   genutzt von kinoger, hdfilme, fhdfilme, topstreamfilm,
               kkiste, streamcloud (DLE-Family-Sites).
               Serien-Architektur je Site unterschiedlich:
               kinoger/hdfilme/kkiste = MERGE (mc + native zusammen),
               streamcloud = mc-only, fhdfilme/topstreamfilm = mc nur
               als FALLBACK wenn das native Pattern leer ist.
               Detail-Karte: Top-Docstring wrappers/meinecloud.py.


### Wie sieht ein Wrapper-Link in der Site aus?


In der Hoster-Liste der Site steht ein <li> mit data-link auf den
Wrapper statt auf den echten Hoster:

  <li data-link="https://<wrapper-host>/movie/tt1234567">Sirius</li>

Der Label-Text ('Sirius', 'meinecloud', 'Server 1', ...) variiert —
zuverlaessig ist nur der URL-Pattern. Drum wird per Trigger-Substring
erkannt, nicht per Label.


### Anwendung im Site-File


Import + Trigger-Check in der Hoster-Loop:

    from resources.lib.wrappers.meinecloud import resolveMeinecloud, MEINECLOUD_TRIGGER

    # ... in showHosters() oder showEpisodeHosters():
    for sUrl, sName in aResult:
        if MEINECLOUD_TRIGGER in sUrl:
            for resolved in resolveMeinecloud(sUrl, referer=URL_MAIN):
                # resolved kann protokoll-relativ sein (//host/...)
                if resolved.startswith('//'):
                    resolved = 'https:' + resolved
                # ... als normaler Hoster-Eintrag adden ...
        else:
            # ... wie bisher: direkt als Hoster-Eintrag adden ...

Wichtig: resolveMeinecloud() liefert eine Liste (kann leer sein bei
Fehler/Timeout), kein Crash. Caller muss Schema-Fix machen falls
URLs protokoll-relativ zurueckkommen.

Cache ist im Wrapper bewusst deaktiviert (caching=False), weil Hoster-
Listen haeufig wechseln (meinecloud rotiert Server) und gecachte leere
Responses (Anti-Bot-Treffer) sonst stundenlang weiter ausgeliefert werden.


### Zentrale Helper: expandHosterList + buildHosterFromUrl + buildMergedHosters


Die Standard-Schritte beim meinecloud-Wrapping (Expansion + Hoster-Dict-
Bau) sind in zwei Helper zentralisiert. 5 der 6 Sites nutzen sie direkt
(kinoger, hdfilme, fhdfilme, topstreamfilm, streamcloud).
kkiste hat einen eigenen _isValidHoster()-Filter und nutzt die Helper
im eigenen Code nicht — bewusst um den Filter zu erhalten; ueber
buildMergedHosters (Serien-Pfad) laufen sie dort indirekt trotzdem.

  expandHosterList(aRawUrls, referer='')
      Aus einer Roh-Liste data-link-URLs eine deduplizierte Liste der
      realen Hoster-URLs bauen. meinecloud-URLs werden via
      resolveMeinecloud() expandiert, andere durchgereicht.

  buildHosterFromUrl(sUrl, sQuality='720', includeQualitySuffix=True)
      Aus einer einzelnen Hoster-URL ein Standard-Hoster-Dict bauen.
      Macht: YouTube-Skip, Schema-Fix (//host -> https:), Hostname-
      Extract, Blocked-Hoster-Check, Quality-Suffix.
      Returns: dict oder None (skip).

  buildMergedHosters(aNativeRawUrls, sMcUrl='', referer='', sQuality='720')
      Serien-Merge: native Roh-data-links + meinecloud-URL einer Episode
      zu EINER deduplizierten Hoster-Dict-Liste zusammenlegen (native
      zuerst). Nutzt intern expandHosterList + buildHosterFromUrl.
      Genutzt von kinoger, hdfilme, kkiste im Serien-showHosters.

Verwendung im Site-File:
    aResult = expandHosterList(aResult, referer=URL_MAIN)
    for u in aResult:
        h = buildHosterFromUrl(u, sQuality=sQuality)
        if h: hosters.append(h)

Vorteil: Schema-Fix passiert im Helper, kein Boilerplate pro Site. Bei
Aenderungen (z.B. Format der Hoster-Dicts) muss nur
wrappers/meinecloud.py angefasst werden.


### Serien-Resolver: resolveMeinecloudSerial


Seit ~05/2026 haben mehrere Sites Serien (z.B. Stranger Things) auf ein
DLE-Template umgestellt das die Staffel/Episoden-Daten NICHT mehr im
Detail-HTML rendert, sondern via JavaScript-Fetch von der meinecloud-Plattform
nachlaedt. Manche alte Serien (z.B. Wednesday) haben die Daten weiterhin
im DLE-HTML (su-accordion + se-ac-N).

Resolver-Flow:
  1. Auto-Discovery: aus Site-HTML die aktuelle meinecloud-Base extrahieren
     (Pattern: fetch('https://<host>/serials.php?...') im Inline-JS).
     Vollstaendig dynamisch — kein Hardcoding der Domain. Bei TLD-Wechsel
     (.click -> .io) findet Discovery die neue Domain automatisch.
  2. Existence-Check: GET /serials.php?task=check&id_imdb=ttXXXXX
     Response (JSON): {"exists":true,"player_url":"...","episode_count":N}
                  oder {"exists":false}
  3. Bei exists=true: GET <player_url> liefert meinecloud-Page mit allen
     Staffeln + Episoden auf einer Seite.
  4. Pattern: data-link="//host/url" data-label="S<N> E<M> — <Titel>"

Aufruf im Site-File — FALLBACK-Variante (fhdfilme/topstreamfilm; die
MERGE-Sites laden mc dagegen immer, s.u.):

    from resources.lib.wrappers.meinecloud import resolveMeinecloudSerial

    # In showSeasons / showEpisodes / showEpisodeHosters:
    if not aResult:                       # altes DLE-Pattern leer?
        _, aImdb = cParser.parse(sHtmlContent, r'(tt\d{7,9})')
        sImdbId = aImdb[0] if aImdb else ''
        if sImdbId:
            episodes = resolveMeinecloudSerial(sImdbId, referer=sUrl, siteHtml=sHtmlContent)
            # episodes = [{'season':int, 'episode':int, 'title':str,
            #              'url':str, 'label':str}, ...]

Wichtig: siteHtml MUSS mitgegeben werden — daraus wird die meinecloud-Base
extrahiert. Ohne siteHtml: Resolver returnt leere Liste mit Log-Eintrag
'kein meinecloud-Pattern im Site-HTML — wird uebersprungen'.

Aktuell genutzt von allen 6 meinecloud-Sites — aber unterschiedlich:
fhdfilme + topstreamfilm als FALLBACK (nur wenn das alte DLE-Pattern
leer ist), kinoger/hdfilme/kkiste laden mc IMMER (Serien-MERGE via
buildMergedHosters, mc = Rueckgrat + native dazu), streamcloud mc-only
fuer mc-Serien. Detail-Karte: Top-Docstring wrappers/meinecloud.py.

Aktuelle Architektur-Limitierung: meinecloud liefert pro Episode nur EINEN
Hoster (default dropload). Browser-Player macht keinen zweiten Call fuer
mehr Hoster — wir kriegen also was meinecloud hat.


### Schema-Fix-Pflicht (HAEUFIGE FEHLERQUELLE)


Der Schema-Fix ist die Stelle wo Bugs entstehen. Resolved URLs kommen
oft im protokoll-relativen Format (//host/...). ResolveURL kann mit
diesen URLs NICHT umgehen — der Hoster wird still verworfen und taucht
nicht in der Hoster-Liste auf.

Bug-Pattern: "mixdrop/dropload tauchen plötzlich nicht mehr in der
Hoster-Liste auf, andere Hoster sind aber da."

Caller-Code muss IMMER beide Schritte machen:

    1. URL fixen
       _fixedUrl = ('https:' + url) if url.startswith('//') else url

    2. _fixedUrl ans System uebergeben (link-Feld), NICHT die ungefixte URL.

Falsch (kkiste-Bug bis 04.05.2026):
    hosters.append({'link': sResolvedUrl, ...})       # ungefixt, klemmt

Richtig:
    hosters.append({'link': _fixedUrl, ...})          # gefixt, funktioniert

Korrekte Beispiele: sites/kinoger.py Z258, sites/streamcloud.py Z445.


### Pattern-Varianten


Die 6 nutzenden Sites haben leicht unterschiedliche Strukturen:

  Pattern A — Standard direkt im Hoster-Loop
              kinoger.py, hdfilme.py

  Pattern B — 2-Stage iframe (Site fetcht erst iframe-content,
              data-link liegt darin)
              fhdfilme.py, topstreamfilm.py

  Pattern C — (URL, Name)-Tupel mit Hostname-Fallback
              (resolved URLs haben keinen Site-Namen — Hostname aus
              der URL extrahieren als Anzeige)
              kkiste.py

  Pattern D — Multi-Mode konvergent (mehrere Modi treffen sich in
              einer gemeinsamen Hoster-Loop)
              streamcloud.py

Der Top-Docstring von wrappers/meinecloud.py beschreibt jedes Pattern mit
Beispiel-Site — bei einer neuen Site das passende Pattern abkupfern.


### Neuen Wrapper hinzufuegen


  1. Neues File in resources/lib/wrappers/ anlegen (z.B. neueplatform.py)
       - <NAME>_TRIGGER Konstante (Substring fuer URL-Match,
         bewusst ohne TLD wegen TLD-Wechsel-Robustheit)
       - resolve<Name>() Funktion (Signature analog resolveMeinecloud)
  2. Top-Docstring des neuen Files: WRAPPER-NUTZER Sektion (welche
     Sites importieren von hier)
  3. Site-Files importieren via 'from resources.lib.wrappers.<name>
     import ...' + Trigger-Check in der Hoster-Loop
  4. Diese Sektion hier ergaenzen


## 15. SETTINGS.XML — Eintrag für ein neues Site-Plugin


Jedes Site-Plugin braucht einen Eintrag in resources/settings.xml.
Dieser Block muss in die <category> für Site-Plugins eingefügt werden.

Ersetze "mysite" durch den SITE_IDENTIFIER deines Plugins.
Ersetze "30999" durch die Label-Nummer deines Plugins in strings.po.

Die Label-Nummern für die Standard-Texte:
  30050 = "Site-Plugin verwenden"
  30052 = "Für globale Suche verwenden"
  30277 = "Domain automatisch aktualisieren & globale Suche"
  30278 = "Aktuell verwendete Domain"
  30411 = "(Neustart erforderlich!)"


### Settings-Block zum Kopieren


			<group id="mysite" label="30999">
				<setting id="plugin_mysite" type="boolean" label="30050" help="30411">
					<level>0</level>
					<default>True</default>
					<control type="toggle"/>
				</setting>
				<setting id="global_search_mysite" type="boolean" label="30052">
					<level>0</level>
					<default>True</default>
					<dependencies>
						<dependency type="enable" operator="!is" setting="plugin_mysite">false</dependency>
					</dependencies>
					<control type="toggle"/>
				</setting>
				<setting id="plugin_mysite_checkDomain" type="boolean" label="30277">
					<level>3</level>
					<default>True</default>
					<dependencies>
						<dependency type="enable" operator="!is" setting="plugin_mysite">false</dependency>
						<dependency type="visible" operator="!is" setting="plugin_mysite">false</dependency>
					</dependencies>
					<control type="toggle"/>
				</setting>
				<setting id="plugin_mysite.domain" type="string" label="30278" help="">
					<level>3</level>
					<default/>
					<constraints>
						<allowempty>true</allowempty>
					</constraints>
					<dependencies>
						<dependency type="enable" operator="!is" setting="plugin_mysite">false</dependency>
						<dependency type="visible" operator="!is" setting="plugin_mysite">false</dependency>
					</dependencies>
					<control type="edit" format="string">
						<heading>30278</heading>
					</control>
				</setting>
				<setting id="plugin_mysite_status" type="string" label="Dummy" help="">
					<visible>false</visible>
					<default>true</default>
					<control type="toggle"/>
				</setting>
			</group>


### Was jede Setting-ID macht


  plugin_mysite            Plugin ein/ausschalten (Toggle im Menü)
  global_search_mysite     Plugin in die globale Suche einbinden (ja/nein)
  plugin_mysite_checkDomain  Domain beim Start automatisch prüfen
  plugin_mysite.domain     Vom User einstellbare Domain (leer = Standard aus dem Code)
  plugin_mysite_status     Internes Status-Feld (unsichtbar, für Domain-Check Ergebnis)


### strings.po Eintrag


Für jedes neue Site-Plugin muss auch ein Label in beiden Sprachdateien
angelegt werden (resources/language/resource.language.de_de/strings.po
und resources/language/resource.language.en_gb/strings.po):

  msgctxt "#30999"
  msgid "MeineSite"

Die Nummer (hier 30999) muss eindeutig sein und zum label="30999"
im settings.xml passen. Bestehende Nummern findest du in den
strings.po Dateien — nimm die nächste freie Nummer.




## 16. SPEZIELLE SITE-PATTERNS (Sonderfaelle)

Die Templates in Kapitel 7 decken den Standardfall ab (Serie -> Staffel ->
Episode -> Hoster). Zwei Sites weichen stark davon ab — hier dokumentiert,
damit das Wissen beim naechsten Anfassen nicht aus dem Code rekonstruiert
werden muss.


### 16.1 animetoast — Block-Buttons / Range-Gateway / Arc

animetoast hat KEINE saubere Staffel/Episoden-Struktur. Eine Serien-Seite
besteht aus Tab-Panes (ein Pane pro Hoster), und die Episoden-Buttons in
den Panes haben je nach Hoster unterschiedliche Granularitaet. Es gibt drei
Seiten-Typen, die showSeasons() in dieser Reihenfolge abklopft:

  1. Block-Hoster (Staffel-Raster): ein Pane enthaelt >=2 Buttons die auf
     "S\d" matchen (z.B. "S1", "S2"). Diese werden als Staffeln angeboten
     (-> showSeasonHosters -> pro Staffel je Hoster der passende Block-Button).

  2. simple-iframe-player (AJAX): kein Staffel-Raster, stattdessen ein
     einzelner Inline-iframe-Player. Server = Hoster (-> showAjaxServers).

  3. Lain-Typ: Tabs tragen die Episoden-Buttons direkt, ?link=N rendert den
     Embed server-seitig. -> Hoster = Tabs, je Hoster die Folgen DES Tabs.

Range-Gateway/Arc (der Knackpunkt): Bei manchen Serien (z.B. Code Geass)
zeigt ein Hoster-Tab nur EINEN Button mit einem Bereichs-Label wie
"Ep.1-25" statt einzelner Episoden. Dieser Button ist ein GATEWAY — sein
Embed ist nur ein Platzhalter-Bild, das auf einen SEPARATEN Arc-Post
(z.B. /17757-2) verlinkt, der die echten 25 Per-Episode-Buttons traegt.
showEpisodes() erkennt den Single-Range-Button (genau 1 Button + Label
matcht r'\d+\s*-\s*\d+'), folgt dem Gateway zum Arc-Post, baut die Arc-Tabs
und matcht den aktuellen Hoster per _normHoster() — dann werden die
Per-Episode-Buttons des Arc-Tabs eingesetzt. Graceful Fallback: extern /
kein Arc / kein Match -> der einzelne Button bleibt (spielt als ein Stream).

Hoster-Typen in den Tabs: Block / Lain / AJAX(Nonce). Cover kommt via
og:image (_cover) und wird als sCover durch alle Item-Ebenen gereicht
(A-Z-Index ist bewusst coverlos). Kein setSeason() -> Trailer laeuft als
normaler Titel-Trailer (kein Season-Pfad).


### 16.2 moviedream — AES-verschluesselte Hoster-Links

moviedream liefert die Hoster-URLs nicht im Klartext, sondern als
AES-verschluesselte CryptoJSAesJson-Bloecke im HTML (OpenSSL-KDF/MD5 +
AES-CBC). Film- UND Episode-Seiten nutzen identische Bloecke.

Aufbau im HTML:
  CryptoJSAesJson.decrypt('{"ct":"...","iv":"...","s":"..."}', '<PASSPHRASE>')
  - 1. Argument: JSON-Blob {ct: base64-ciphertext, iv: hex, s: hex-salt}
  - 2. Argument: die Passphrase (dynamisch! NIE hardcoden — pro Seite frisch
    via PATTERN_PASSPHRASE aus dem HTML ziehen)

Entschluesselung (Aequivalent zu CryptoJS):
  1. EVP_BytesToKey (MD5, 1 Iteration) leitet aus Passphrase+Salt den
     32-Byte-Key + 16-Byte-IV ab  (_evp_kdf).
  2. AES-CBC mit Key/IV entschluesseln, pyaes entfernt PKCS7-Padding selbst.
  3. Ergebnis ist JSON-gewrappt -> .strip() + json.loads -> echte URL.

Bibliothek: pyaes (kein PyCryptodome noetig). Passphrase pro Seite neu —
das ist der Anti-Bot-Schutz; ohne sie kein Decrypt. Bei TLD-/Layout-Wechsel
bleibt der Decrypt-Code gleich, nur die Patterns muessen ggf. nachgezogen
werden. setTVShowTitle() + setSeason() gesetzt -> moviedream ist der
Referenzfall fuer funktionierende Season-Trailer (siehe Kapitel 8).
