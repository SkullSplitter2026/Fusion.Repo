# -*- coding: utf-8 -*-
# Python 3
"""Wrapper-Resolver fuer die meinecloud-Plattform.

Mehrere DLE-Family-Sites verstecken Hoster hinter dem meinecloud-Aggregator.
Diese Datei buendelt alle meinecloud-spezifische Resolver-Logik (Filme +
Serien) zentral. Gehoert in resources/lib/wrappers/ — beim Hinzufuegen
einer weiteren Wrapper-Plattform: eigenes File im gleichen Ordner anlegen.

Hinweis: Die Plattform heisst technisch meinecloud. Sites labeln sie
unterschiedlich ('Sirius', 'meinecloud', 'Server 1' etc.) — alles dasselbe.


═══════════════════════════════════════════════════════════════════════
  WRAPPER-NUTZER — welche Sites importieren aus diesem File
═══════════════════════════════════════════════════════════════════════

Eine zentrale Stelle fuer alle Sites die meinecloud-Funktionen importieren
— beim Hinzufuegen/Entfernen einer Site nur HIER aktualisieren.

  sites/kinoger.py        — Filme Pattern A | Serien MERGE
  sites/hdfilme.py        — Filme Pattern A | Serien MERGE
  sites/kkiste.py         — Filme Pattern C ((URL, Name)-Tupel mit
                            Hostname-Fallback) | Serien MERGE.
                            Movie-Pfad hat eigenen _isValidHoster-Filter
                            und nutzt expandHosterList/buildHosterFromUrl
                            dort NICHT — bewusst um den Filter zu
                            erhalten; der Serien-Pfad laeuft ueber
                            buildMergedHosters (Helper indirekt).
  sites/streamcloud.py    — Filme Pattern D | Serien MC-ONLY
  sites/fhdfilme.py       — Filme Pattern B | Serien FALLBACK
  sites/topstreamfilm.py  — Filme Pattern B | Serien FALLBACK

Pattern-Legende:
  Filme  — Pattern A/B/C/D = unterschiedliche Site-HTML-Strukturen die
           alle in resolveMeinecloud() / expandHosterList() muenden
  Serien — drei Architekturen:
    MERGE     showSeasons + showEpisodes -> showHosters(hosterBlock +
              meinecloud_url). mc wird IMMER geladen und ist das
              Rueckgrat, native Hoster kommen dazu (buildMergedHosters);
              Staffeln/Episoden = Union beider Quellen.
    MC-ONLY   showSeasons + showEpisodes -> showHosters(meinecloud_url).
              Serien-Hoster kommen NUR von mc — natives data-num ist
              fuer mc-Serien tot; Nicht-mc-Serien laufen weiter ueber
              den nativen data-num-Pfad.
    FALLBACK  showSeasons + showEpisodes + showEpisodeHosters. Auf jeder
              Ebene erst natives DLE-Pattern, NUR bei 0 Treffern mc
              (resolveMeinecloudSerial). Liefert nativ irgendwas, wird
              mc gar nicht gefragt — KEIN Merge.

═══════════════════════════════════════════════════════════════════════
  meinecloud (Filme — resolveMeinecloud)
═══════════════════════════════════════════════════════════════════════

Pages: meinecloud Wrapper-URLs (Form: /movie/<imdb>)
Liefert <li ... data-link="//host.com/e/ID"> Hoster-Liste.

Erkennung im Site-HTML:
    <li data-link="https://<meinecloud-host>/movie/<imdb>">LABEL</li>
    Label variiert je nach Site — URL-Pattern bleibt.

Trigger in Site:
    from resources.lib.wrappers.meinecloud import resolveMeinecloud, MEINECLOUD_TRIGGER
    if MEINECLOUD_TRIGGER in sUrl:
        for resolved in resolveMeinecloud(sUrl, referer=URL_MAIN):
            ...

Pattern A — Standard:
    Im Hoster-Loop nach data-link-Match einen Expand-Block einbauen,
    meinecloud-URLs durch resolveMeinecloud() expandieren, andere durchreichen.
    Beispiel: sites/kinoger.py showHosters().

Pattern B — 2-Stage iframe:
    Site fetcht erst iframe-content, dann data-link daraus. Expand-Block
    INNERHALB des iframe-Branchs nach dem inneren data-link-Match.
    Beispiel: sites/fhdfilme.py showHosters().

Pattern C — (URL, Name)-Tupel:
    Site nutzt re.findall mit Tupel-Capture. Resolved URLs haben keinen
    Site-Namen — Hostname als Fallback aus URL extrahieren.
    Beispiel: sites/kkiste.py showHosters().

Pattern D — Multi-Mode konvergent:
    Site hat mehrere Modi (Episode/Movie) die in einer gemeinsamen
    Hoster-Loop konvergieren. Expand-Block direkt nach `if isMatch:`,
    faengt alle Modi ab.
    Beispiel: sites/streamcloud.py showHosters().

Filter im Resolver:
    - Leere data-link (Toggle-Buttons "andere Server")
    - Self-Refs auf meinecloud selbst (interne /fullhd/-Links sind Fakes,
      keine echten Streams)

Adversarial-Cases (alle -> []):
    - Leerer Response, Timeout, 403
    - HTML ohne data-link
    - HTML nur mit Self-Refs / leeren Toggles


═══════════════════════════════════════════════════════════════════════
  meinecloud (Serien — resolveMeinecloudSerial)
═══════════════════════════════════════════════════════════════════════

Seit ~05/2026 haben mehrere Sites Serien (z.B. Stranger Things) auf ein
DLE-Template umgestellt das die Staffel/Episoden-Daten NICHT mehr im
Detail-HTML rendert, sondern via JavaScript-Fetch von der meinecloud-Plattform
nachlaedt. Manche alte Serien (z.B. Wednesday) haben die Daten weiterhin in
'su-accordion' + 'se-ac-N' im Detail-HTML.

API-Flow:
    1. Existence-Check:  GET /serials.php?task=check&id_imdb=ttXXXXX
       Response (JSON):  {"exists":true,"player_url":"...","episode_count":N}
                     oder {"exists":false}
    2. Falls exists=true: GET <player_url> liefert die meinecloud-Serial-Page mit
       allen Staffeln/Episoden komplett auf einer Seite.
    3. Episoden-Pattern im meinecloud-HTML:
           data-link="//host/url" data-label="S<N> E<M> — <Titel>"

Aktueller Stand: meinecloud liefert pro Episode nur EINEN Hoster (default
dropload). Der Browser-Player macht keinen zweiten Call fuer mehr Hoster
— Architektur-bedingt ist das was wir kriegen koennen.


═══════════════════════════════════════════════════════════════════════
  meinecloud (Serien-Merge — buildMergedHosters)
═══════════════════════════════════════════════════════════════════════

Fuer die MERGE-Sites: legt native Roh-data-links und die meinecloud-URL
einer Episode zu EINER deduplizierten Hoster-Liste zusammen (native
zuerst, interne Fake-Links raus). Leere Eingaben ok — kein Crash.
Details: Docstring von buildMergedHosters().
"""

import json
import re

from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.logger import logger
from resources.lib.tools import cParser


# ═══════════════════════════════════════════════════════════════════════
#   meinecloud — gemeinsame Konstanten
# ═══════════════════════════════════════════════════════════════════════

# Trigger-Substring fuer URL-Match. Bewusst nur 'meinecloud' (ohne TLD)
# — robust gegen TLD-Wechsel innerhalb der Plattform-Familie.
MEINECLOUD_TRIGGER = 'meinecloud'


def _discoverMeinecloudBase(sHtml):
    """Aus Site-HTML die aktuelle meinecloud-Base extrahieren.

    DLE-Sites haben im Inline-JS:
        fetch('https://<host>/serials.php?task=check&id_imdb=' + imdb)
    Wenn die TLD wechselt (z.B. .click → .io), passt der Webmaster die
    JS-URL an. Pattern bleibt aber gleich — wir extrahieren die aktuelle
    Base direkt aus dem Site-HTML, kein Hardcoding noetig.

    Args:
        sHtml: Site-HTML (z.B. die Detail-Page einer Serie)

    Returns:
        'https://<host>' oder None wenn Pattern nicht gefunden.
        Bei None liefert resolveMeinecloudSerial() leere Liste mit Log-
        Eintrag — sauberer Fail statt Crash.
    """
    if not sHtml:
        return None
    m = re.search(r"['\"]https?://([^/'\"]*meinecloud[^/'\"]*)/serials\.php", sHtml)
    if m:
        return 'https://' + m.group(1)
    return None


def resolveMeinecloud(sUrl, referer=''):
    """Loest meinecloud Wrapper zu Hoster-Liste auf.

    Args:
        sUrl: meinecloud Wrapper-URL (aktuelle Form siehe Sektion oben)
        referer: optional Referer-Header (URL der aufrufenden Site)

    Returns:
        list[str]: Hoster-URLs (kann leer sein, kein Crash bei Fehler).
                   URLs koennen protokoll-relativ sein (//host/...) — der
                   Caller muss Schema-Fix machen (https: prefixen).

    WICHTIG fuer Caller — Schema-Fix-Pflicht:
        Resolved URLs kommen oft im protokoll-relativen Format (//host/...).
        ResolveURL kann mit denen NICHT umgehen — Hoster wird still verworfen
        und taucht nicht in der Hoster-Liste auf (Bug-Pattern: 'mixdrop/dropload
        fehlen plötzlich aus der Liste').

        Caller-Code muss IMMER:
            _fixedUrl = ('https:' + url) if url.startswith('//') else url

        Und _fixedUrl muss ans System (link-Feld), NICHT die ungefixte URL.
        Beispiel korrekt: sites/kinoger.py Z258, sites/streamcloud.py Z445.
    """
    try:
        # caching=False: Hoster-Listen aendern sich haeufig (meinecloud rotiert Server,
        # tote Hoster werden ausgetauscht). Cache wuerde tote Hoster oder leere
        # Responses (Anti-Bot-Treffer) bis zu cacheTime Stunden weiter ausliefern
        # — siehe Bug 04.05.2026: 'mixdrop/dropload tauchen plötzlich nicht mehr auf'.
        oRequest = cRequestHandler(sUrl, caching=False)
        if referer:
            oRequest.addHeaderEntry('Referer', referer)
        sHtml = oRequest.request()
        if not sHtml:
            logger.info('wrappers.meinecloud: leere Response von %s' % sUrl)
            return []
        isMatch, aResult = cParser.parse(sHtml, r'data-link="([^"]+)"')
        if not isMatch or not aResult:
            logger.info('wrappers.meinecloud: keine data-link Treffer in %s' % sUrl)
            return []
        return [u for u in aResult if u and MEINECLOUD_TRIGGER not in u]
    except Exception as e:
        logger.error('wrappers.meinecloud: %s bei %s' % (e, sUrl))
    return []


def expandHosterList(aRawUrls, referer=''):
    """Hoster-Liste expandieren: meinecloud-URLs durch resolveMeinecloud() ersetzen,
    andere durchreichen. Mit Dedup ueber alle Treffer.

    Args:
        aRawUrls: Liste roher data-link URLs aus Site-HTML
        referer: optional Referer fuer den meinecloud-Request

    Returns:
        list[str]: deduplizierte Liste aller realen Hoster-URLs
                   (kann protokoll-relativ sein — Caller macht Schema-Fix
                   typischerweise via buildHosterFromUrl()).
    """
    seen = set()
    expanded = []
    for sUrl in aRawUrls or []:
        if not sUrl:
            continue
        if MEINECLOUD_TRIGGER in sUrl:
            for sResolvedUrl in resolveMeinecloud(sUrl, referer=referer):
                if sResolvedUrl and sResolvedUrl not in seen:
                    seen.add(sResolvedUrl)
                    expanded.append(sResolvedUrl)
        elif sUrl not in seen:
            seen.add(sUrl)
            expanded.append(sUrl)
    return expanded


def buildHosterFromUrl(sUrl, sQuality='720', includeQualitySuffix=True):
    """Aus einer Hoster-URL ein Standard-Hoster-Dict bauen.

    Macht alle Standard-Schritte:
        - YouTube-Trailer skippen
        - Schema-Fix (//host/... -> https:)
        - Hostname-Extract als Name
        - Blocked-Hoster-Check (xStream Settings)
        - Quality-Suffix optional

    Args:
        sUrl: Hoster-URL (kann protokoll-relativ sein)
        sQuality: Quality-String fuer Anzeige + Hoster-Dict
        includeQualitySuffix: True -> 'Name [I][720p][/I]', False -> nur 'Name'

    Returns:
        dict mit 'link', 'name', 'displayedName', 'quality' — oder None
        wenn URL geskippt werden soll (YouTube/Blocked/leer/ungueltig).
    """
    if not sUrl:
        return None
    if 'youtube' in sUrl:
        return None
    if sUrl.startswith('//'):
        sUrl = 'https:' + sUrl
    try:
        sName = cParser.urlparse(sUrl).split('.')[0].strip()
    except Exception:
        sName = ''
    if not sName:
        return None
    try:
        from resources.lib.config import cConfig
        if cConfig().isBlockedHoster(sName)[0]:
            return None
    except Exception:
        pass
    if includeQualitySuffix:
        displayedName = '%s [I][%sp][/I]' % (sName, sQuality)
    else:
        displayedName = sName
    return {
        'link': sUrl,
        'name': sName,
        'displayedName': displayedName,
        'quality': sQuality,
    }


def buildMergedHosters(aNativeRawUrls, sMcUrl='', referer='', sQuality='720'):
    """Kombiniert native Hoster-URLs mit einer meinecloud-Direct-URL zu einer
    deduplizierten Hoster-Dict-Liste ("mc plus deren").

    Hintergrund: Bei Serien die BEIDE Quellen tragen (native DLE-Hoster + meinecloud)
    liefert der native Weg mehrere Hoster pro Episode, meinecloud nur einen. Diese
    Funktion legt beide zusammen — native zuerst (i.d.R. mehr/bessere Hoster), die
    meinecloud-URL als zusaetzlicher Eintrag, Duplikate (gleiche finale URL) raus.

    Args:
        aNativeRawUrls: Liste roher data-link URLs aus dem nativen Site-HTML
                        (koennen meinecloud-Wrapper-URLs sein -> werden expandiert,
                        koennen protokoll-relativ sein). Leer/None -> nur meinecloud.
        sMcUrl:         meinecloud-Direct-URL der Episode (1 Hoster). Leer -> nur native.
        referer:        Referer fuer den meinecloud-Expand-Request.
        sQuality:       Quality-String fuer die Hoster-Dicts.

    Returns:
        list[dict]: deduplizierte Hoster-Dicts (Schema wie buildHosterFromUrl).
                    Kann leer sein (kein Crash).
    """
    hosters = []
    seen = set()
    # Native zuerst — meinecloud-Wrapper expandieren, interne /vod/-Links filtern.
    for sUrl in expandHosterList(aNativeRawUrls or [], referer=referer):
        # Interne Site-URLs (z.B. /vod/vpn.html) raus — aber NICHT protokoll-relative
        # (//host/...) die sind externe Hoster.
        if sUrl.startswith('/') and not sUrl.startswith('//'):
            continue
        hoster = buildHosterFromUrl(sUrl, sQuality=sQuality, includeQualitySuffix=True)
        if hoster and hoster['link'] not in seen:
            seen.add(hoster['link'])
            hosters.append(hoster)
    # meinecloud-URL als zusaetzlicher Hoster
    if sMcUrl:
        hoster = buildHosterFromUrl(sMcUrl, sQuality=sQuality, includeQualitySuffix=True)
        if hoster and hoster['link'] not in seen:
            seen.add(hoster['link'])
            hosters.append(hoster)
    return hosters


def resolveMeinecloudSerial(sImdbId, referer='', siteHtml=None):
    """Loest meinecloud Serien-Wrapper zu Episoden-Liste auf.

    Args:
        sImdbId: IMDB-ID der Serie (Format 'tt1234567', mit oder ohne 'tt' prefix)
        referer: optional Referer-Header (URL der aufrufenden Site)
        siteHtml: Site-HTML aus dem die aktuelle meinecloud-Base extrahiert
                  wird (vollstaendig dynamisch, TLD-robust). MUSS gegeben sein —
                  ohne siteHtml returnt der Resolver leere Liste mit Log-Eintrag
                  (sauberer Fail statt Crash).

    Returns:
        list[dict]: Episoden mit Hoster-URLs. Jeder Eintrag:
            {
                'season':  int,  # Staffel-Nummer
                'episode': int,  # Episoden-Nummer
                'title':   str,  # Episoden-Titel ohne 'S<N> E<M> —' prefix
                'url':     str,  # Hoster-URL (kann protokoll-relativ sein!)
                'label':   str,  # Original 'S1 E1 — Titel' Label
            }
        Leere Liste bei Fehler/exists=false/Timeout/keine Discovery (kein Crash).

    WICHTIG fuer Caller — Schema-Fix-Pflicht:
        Wie bei resolveMeinecloud — URLs koennen protokoll-relativ sein.
        Caller muss ('https:' + url) if url.startswith('//') else url machen.
    """
    try:
        # IMDB-ID normalisieren (mit oder ohne 'tt' prefix)
        if not sImdbId:
            return []
        if sImdbId.startswith('tt'):
            sImdbId = sImdbId[2:]
        if not sImdbId.isdigit():
            logger.info('wrappers.meinecloud_serial: ungueltige IMDB-ID "%s"' % sImdbId)
            return []

        # Auto-Discovery: aus Site-HTML aktuelle Base extrahieren (TLD-robust).
        # Wenn das HTML kein meinecloud-Pattern enthaelt -> sauberer Fail mit
        # Log-Eintrag, kein Crash. meinecloud-Fallback in der Site greift dann einfach
        # nicht und legacy DLE-Pattern uebernimmt falls vorhanden.
        base = _discoverMeinecloudBase(siteHtml)
        if not base:
            logger.info('wrappers.meinecloud_serial: kein meinecloud-Pattern im Site-HTML — wird uebersprungen')
            return []

        # Step 1: Existence-Check via JSON-API
        sCheckUrl = '%s/serials.php?task=check&id_imdb=tt%s' % (base, sImdbId)
        oRequest = cRequestHandler(sCheckUrl, caching=False)
        if referer:
            oRequest.addHeaderEntry('Referer', referer)
        sJson = oRequest.request()
        if not sJson:
            logger.info('wrappers.meinecloud_serial: leere check-Response fuer tt%s' % sImdbId)
            return []
        try:
            data = json.loads(sJson)
        except (ValueError, TypeError) as e:
            logger.info('wrappers.meinecloud_serial: JSON-Parse-Fehler "%s" fuer tt%s' % (e, sImdbId))
            return []
        if not data.get('exists'):
            logger.info('wrappers.meinecloud_serial: keine Serien-Daten fuer tt%s' % sImdbId)
            return []
        sPlayerUrl = data.get('player_url', '')
        if not sPlayerUrl:
            logger.info('wrappers.meinecloud_serial: exists=true aber keine player_url fuer tt%s' % sImdbId)
            return []

        # Step 2: meinecloud-Player-Page laden (alle Staffeln/Episoden auf einer Seite)
        oRequest = cRequestHandler(sPlayerUrl, caching=False)
        if referer:
            oRequest.addHeaderEntry('Referer', referer)
        sHtml = oRequest.request()
        if not sHtml:
            logger.info('wrappers.meinecloud_serial: leere player-Response fuer tt%s' % sImdbId)
            return []

        # Step 3: Episoden parsen — data-link kommt vor data-label
        # Pattern: data-link="//host/url" ... data-label="S<N> E<M> — <Titel>"
        # em-dash (—) und en-dash (–) und normaler Bindestrich (-) als Separator zulassen
        pattern = r'data-link="([^"]+)"\s+data-label="(S(\d+)\s+E(\d+)\s*[—–-]\s*([^"]+))"'
        episodes = []
        for sUrl, sLabel, sSeason, sEpisode, sTitle in re.findall(pattern, sHtml):
            if not sUrl:
                continue
            episodes.append({
                'season':  int(sSeason),
                'episode': int(sEpisode),
                'title':   sTitle.strip(),
                'url':     sUrl,
                'label':   sLabel,
            })
        if not episodes:
            logger.info('wrappers.meinecloud_serial: keine Episoden-Treffer in player-page fuer tt%s' % sImdbId)
            return []
        logger.info('wrappers.meinecloud_serial: %d Episoden geladen fuer tt%s' % (len(episodes), sImdbId))
        return episodes
    except Exception as e:
        logger.error('wrappers.meinecloud_serial: %s bei tt%s' % (e, sImdbId))
    return []
