# -*- coding: utf-8 -*-
# Python 3

import time
import xbmcgui
import re
import os
import hashlib
import json
import traceback
import ssl
import certifi
import socket
import zlib

from resources.lib.config import cConfig
from resources.lib.logger import logger
from resources.lib.cache import cCache
from resources.lib.tools import infoDialog
from xbmcvfs import translatePath

from urllib.parse import quote, urlencode, urlparse, quote_plus, urljoin
from urllib.error import HTTPError, URLError
from urllib.request import HTTPHandler, HTTPSHandler, Request, HTTPCookieProcessor, build_opener, urlopen, HTTPRedirectHandler
from http.cookiejar import LWPCookieJar, Cookie
from http.client import HTTPException
from random import choice
from contextlib import contextmanager

@contextmanager
def _doh_resolution(hostname, ip):
    """DNS-Bypass via getaddrinfo-Patch: loest 'hostname' temporaer auf 'ip' auf.
    Anders als ein direkter IP-Connect bleibt das SSL-Zertifikat gueltig, weil die
    Verbindung weiterhin den echten Hostnamen kennt (SNI + Cert-Hostname stimmen).
    Patch ist eng gekapselt und wird im finally IMMER zurueckgesetzt."""
    if not ip:
        yield
        return
    _orig_getaddrinfo = socket.getaddrinfo
    def _patched(host, *args, **kwargs):
        if host == hostname:
            return _orig_getaddrinfo(ip, *args, **kwargs)
        return _orig_getaddrinfo(host, *args, **kwargs)
    socket.getaddrinfo = _patched
    try:
        yield
    finally:
        socket.getaddrinfo = _orig_getaddrinfo


class RedirectFilter(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        if cConfig().getSetting('bypassDNSlock', 'false') != 'true':
            if 'notice.cuii' in newurl:
                xbmcgui.Dialog().ok(cConfig().getLocalizedString(30265), cConfig().getLocalizedString(30260) + '\n' + cConfig().getLocalizedString(30261))
                return None
        return HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, hdrs, newurl)


class _NoRedirect(HTTPRedirectHandler):
    # Folgt Redirects NICHT: redirect_request gibt None zurueck, wodurch urllib die
    # 3xx-Antwort als HTTPError durchreicht -> dort steht der Location-Header.
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        return None

class cRequestHandler:
    # useful for e.g. tmdb request where multiple requests are made within a loop
    persistent_openers = {}

    @staticmethod
    def RandomUA():
        # Random User Agents aktualisiert 01.07.2026 (Chrome 150 Stable ab 30.06.2026)
        FF_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0'
        OPERA_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 OPR/133.0.0.0'
        EDGE_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0'
        CHROME_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36'
        SAFARI_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.5 Safari/605.1.15'

        _User_Agents = [FF_USER_AGENT, OPERA_USER_AGENT, EDGE_USER_AGENT, CHROME_USER_AGENT, SAFARI_USER_AGENT]
        return choice(_User_Agents)

    def __init__(self, sUrl, caching=True, ignoreErrors=False, method='GET', data=None, compression=True, jspost=False, ssl_verify=False):
        self._sUrl = self.__cleanupUrl(sUrl)
        self._sRealUrl = ''
        self._USER_AGENT = self.RandomUA()
        self._aParameters = {}
        self._headerEntries = {}
        self._profilePath = translatePath(cConfig().getAddonInfo('profile'))
        self._cachePath = ''
        self._cookiePath = ''
        self._Status = ''
        self._sResponseHeader = ''
        self._ssl_verify = ssl_verify
        self.ignoreDiscard(False)
        self.ignoreExpired(False)
        self.caching = caching
        self.method = method
        self.data = data
        self.ignoreErrors = ignoreErrors
        self.compression = compression
        self.jspost = jspost
        self.cacheTime = int(cConfig().getSetting('cacheTime', 1)) * 3600  # Stunden * 3600 = Sekunden
        self.requestTimeout = int(cConfig().getSetting('requestTimeout', 10))
        self.bypassDNSlock = (cConfig().getSetting('bypassDNSlock', 'false') == 'true')
        self.removeBreakLines(True)
        self.removeNewLines(True)
        self.__setDefaultHeader()
        self.__setCachePath()
        self.__setCookiePath()
        self.isMemoryCacheActive = (cConfig().getSetting('volatileHtmlCache', 'false') == 'true')
        if self.isMemoryCacheActive:
            self._memCache = cCache()
        
        socket.setdefaulttimeout(self.requestTimeout)

    def getStatus(self):
        return self._Status

    def removeNewLines(self, bRemoveNewLines):
        self.__bRemoveNewLines = bRemoveNewLines

    def removeBreakLines(self, bRemoveBreakLines):
        self.__bRemoveBreakLines = bRemoveBreakLines

    def addHeaderEntry(self, sHeaderKey, sHeaderValue):
        self._headerEntries[sHeaderKey] = sHeaderValue

    def getHeaderEntry(self, sHeaderKey):
        if sHeaderKey in self._headerEntries:
            return self._headerEntries[sHeaderKey]

    def addParameters(self, key, value, Quote=False):
        self._aParameters[key] = value if not Quote else quote(str(value))

    def getResponseHeader(self):
        return self._sResponseHeader

    def getRealUrl(self):
        return self._sRealUrl

    def getRequestUri(self):
        return self._sUrl + '?' + urlencode(self._aParameters)

    def __setDefaultHeader(self):
        self.addHeaderEntry('User-Agent', self._USER_AGENT)
        self.addHeaderEntry('Accept-Language', 'de,en-US;q=0.7,en;q=0.3')
        self.addHeaderEntry('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8')
        if self.compression:
            self.addHeaderEntry('Accept-Encoding', 'gzip, deflate')
        self.addHeaderEntry('Connection', 'keep-alive')
        self.addHeaderEntry('Keep-Alive', 'timeout=5')

    @staticmethod
    def __getDefaultHandler(ssl_verify):
        if ssl_verify:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
            return [HTTPSHandler(context=ssl_context)]
        else:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            return [HTTPSHandler(context=ssl_context)]

    @staticmethod
    def __cleanupUrl(url):
        #p = urlparse(url)
        #if p.query:
        #    query = quote_plus(p.query).replace('%3D', '=').replace('%26', '&')
        #    p = p._replace(query=p.query.replace(p.query, query))
        #else:
        #    path = quote_plus(p.path).replace('%2F', '/').replace('%26', '&').replace('%3D', '=')
        #    p = p._replace(path=p.path.replace(p.path, path))
        #return p.geturl()
        return url
    
    def request(self):
        if self.caching and self.cacheTime > 0  and self.method == 'GET' and self.data is None:
            if self.isMemoryCacheActive:
                sContent = self.__readVolatileCache(self.getRequestUri(), self.cacheTime)
            else:
                sContent = self.__readPersistentCache(self.getRequestUri())
            if sContent:
                self._Status = '200'
                return sContent
        else:
            logger.info('-> [requestHandler]: read html for %s' % self.getRequestUri())

        # DNS-Bypass global ueber Setting (kein per-Site-Flag mehr)
        if self.bypassDNSlock:
            ip_override = self.__doh_request(self._sUrl)
        else:
            ip_override = None
        _doh_host = urlparse(self._sUrl).hostname

        cookieJar = LWPCookieJar(filename=self._cookiePath)
        try:
            cookieJar.load(ignore_discard=self.__bIgnoreDiscard, ignore_expires=self.__bIgnoreExpired)
        except Exception as e:
            logger.debug(e)
        
        domain = urlparse(self._sUrl).netloc
        if domain in cRequestHandler.persistent_openers:
            opener = cRequestHandler.persistent_openers[domain]
        else:
            handlers = self.__getDefaultHandler(self._ssl_verify)        
            handlers += [HTTPHandler(), HTTPCookieProcessor(cookiejar=cookieJar), RedirectFilter()]
            opener = build_opener(*handlers)
            cRequestHandler.persistent_openers[domain] = opener

        # Prepare parameters for GET/POST
        if self.method == 'POST':
            if self.data is not None:
                if isinstance(self.data, dict):
                    # Default: form data
                    sParameters = urlencode(self.data).encode()
                elif isinstance(self.data, str):
                    sParameters = self.data.encode()
                else:
                    sParameters = self.data
            else:
                sParameters = None
        else:
            sParameters = json.dumps(self._aParameters).encode() if self.jspost else urlencode(self._aParameters, True).encode()
            if len(sParameters) == 0:
                sParameters = None
        
        oRequest = Request(self._sUrl, sParameters if sParameters and len(sParameters) > 0 else None)

        for key, value in self._headerEntries.items():
            oRequest.add_header(key, value)
        
        if self.method == 'POST' and 'Content-Type' not in self._headerEntries:
            oRequest.add_header('Content-Type', 'application/x-www-form-urlencoded')
        elif self.jspost:
            oRequest.add_header('Content-Type', 'application/json')
        
        cookieJar.add_cookie_header(oRequest)
        
        try:
            with _doh_resolution(_doh_host, ip_override):
                oResponse = opener.open(oRequest)
        except HTTPError as e:
            if e.code >= 400:
                self._Status = str(e.code)
                data = e.fp.read()
                if 'DDOS-GUARD' in str(data):
                    opener = build_opener(HTTPCookieProcessor(cookieJar))
                    opener.addheaders = [('User-agent', self._USER_AGENT), ('Referer', self._sUrl)]
                    response = opener.open('https://check.ddos-guard.net/check.js')
                    content = response.read().decode('utf-8', 'replace')
                    url2 = re.findall("Image.*?'([^']+)'; new", content)
                    url3 = urlparse(self._sUrl)
                    url3 = '%s://%s/%s' % (url3.scheme, url3.netloc, url2[0])
                    opener = build_opener(HTTPCookieProcessor(cookieJar))
                    opener.addheaders = [('User-agent', self._USER_AGENT), ('Referer', self._sUrl)]
                    opener.open(url3).read()
                    opener = build_opener(HTTPCookieProcessor(cookieJar))
                    opener.addheaders = [('User-agent', self._USER_AGENT), ('Referer', self._sUrl)]
                    oResponse = opener.open(self._sUrl, sParameters if len(sParameters) > 0 else None)
                    if not oResponse:
                        logger.error(' -> [requestHandler]: Failed DDOS-GUARD active: ' + self._sUrl)
                        return 'DDOS GUARD SCHUTZ'
                elif 'cloudflare' in str(e.headers):
                    if not self.ignoreErrors:
                        infoDialog(cConfig().getLocalizedString(30829), icon='WARNING', time=10000)
                    logger.error(' -> [requestHandler]: Failed Cloudflare active: ' + self._sUrl)
                    return 'CLOUDFLARE-SCHUTZ AKTIV' # Meldung geht als "e.doc" in die exception nach default.py
                else:
                    if not self.ignoreErrors:
                        xbmcgui.Dialog().ok('xStream', cConfig().getLocalizedString(30259) + ' {0} {1}'.format(self._sUrl, str(e)))
                    logger.error(' -> [requestHandler]: HTTPError ' + str(e) + ' Url: ' + self._sUrl)
                    return 'SEITE NICHT ERREICHBAR'
            else:
                if not self.ignoreErrors:
                    xbmcgui.Dialog().ok('xStream', cConfig().getLocalizedString(30259) + ' {0} {1}'.format(self._sUrl, str(e)))
                logger.error(' -> [requestHandler]: HTTPError ' + str(e) + ' Url: ' + self._sUrl)
                return 'SEITE NICHT ERREICHBAR'
        except URLError as e:
            if not self.ignoreErrors:
                xbmcgui.Dialog().ok('xStream', str(e.reason))
            logger.error(' -> [requestHandler]: URLError ' + str(e.reason) + ' Url: ' + self._sUrl)
            return 'URL FEHLER'
        except HTTPException as e:
            if not self.ignoreErrors:
                xbmcgui.Dialog().ok('xStream', str(e))
            logger.error(' -> [requestHandler]: HTTPException ' + str(e) + ' Url: ' + self._sUrl)
            return 'TIMEOUT'

        self._sResponseHeader = oResponse.info()
        
        content_encoding = self._sResponseHeader.get('Content-Encoding', '').lower()
        if content_encoding:
            raw_content = oResponse.read()
            if content_encoding == 'gzip':
                decompressed = zlib.decompress(raw_content, wbits=zlib.MAX_WBITS | 16)
            elif content_encoding == 'deflate':
                decompressed = zlib.decompress(raw_content, wbits=-zlib.MAX_WBITS)
            else:
                decompressed = raw_content
            sContent = decompressed.decode('utf-8', 'replace')
        else:
            sContent = oResponse.read().decode('utf-8', 'replace')

        if 'lazingfast' in sContent:
            bf = cBF().resolve(self._sUrl, sContent, cookieJar, self._USER_AGENT, sParameters)
            if bf:
                sContent = bf
            else:
                logger.error(' -> [requestHandler]: Failed Blazingfast active: ' + self._sUrl)

        try:
            cookieJar.save(ignore_discard=self.__bIgnoreDiscard, ignore_expires=self.__bIgnoreExpired)
        except Exception as e:
            logger.error(' -> [requestHandler]: Failed save cookie: %s' % e)

        self._sRealUrl = oResponse.geturl()
        self._Status = oResponse.getcode() if self._sUrl == self._sRealUrl else '301'

        if self.__bRemoveNewLines:
            sContent = sContent.replace('\n', '').replace('\r\t', '')
        if self.__bRemoveBreakLines:
            sContent = sContent.replace('&nbsp;', '')

        if self.caching and self.cacheTime > 0 and self.method == 'GET' and self.data is None:
            if self.isMemoryCacheActive:
                self.__writeVolatileCache(self.getRequestUri(), sContent)
            else:
                self.__writePersistentCache(self.getRequestUri(), sContent)

        return sContent

    def getRedirectUrl(self):
        # Loest EINEN Redirect-Hop auf und liefert NUR das Location-Ziel zurueck,
        # ohne die Zielseite selbst zu laden. Noetig fuer Hoster, deren Embed-Seite
        # hinter Cloudflare liegt (z.B. DoodStream): ein GET auf die Seite
        # loest den CF-Block aus. Das Redirect-Ziel liefert die Quell-Seite (URL_MAIN)
        # selbst aus, die Embed-Seite wird hier gar nicht kontaktiert; ResolveURL holt die
        # Seite spaeter mit eigener Logik. Nutzt bewusst dieselbe DoH/Cookie/UA-Basis
        # wie request(), aber KEINE persistent_openers (No-Follow darf den Cache nicht
        # verseuchen, sonst wuerden normale Requests derselben Domain nicht mehr folgen).
        if self.bypassDNSlock:
            ip_override = self.__doh_request(self._sUrl)
        else:
            ip_override = None
        _doh_host = urlparse(self._sUrl).hostname

        cookieJar = LWPCookieJar(filename=self._cookiePath)
        try:
            cookieJar.load(ignore_discard=self.__bIgnoreDiscard, ignore_expires=self.__bIgnoreExpired)
        except Exception as e:
            logger.debug(e)

        handlers = self.__getDefaultHandler(self._ssl_verify)
        handlers += [HTTPHandler(), HTTPCookieProcessor(cookiejar=cookieJar), _NoRedirect()]
        opener = build_opener(*handlers)

        oRequest = Request(self._sUrl)
        for key, value in self._headerEntries.items():
            oRequest.add_header(key, value)
        cookieJar.add_cookie_header(oRequest)

        sLocation = ''
        try:
            with _doh_resolution(_doh_host, ip_override):
                oResponse = opener.open(oRequest)
            sLocation = oResponse.geturl()  # kein Redirect gekommen (z.B. direkt 200) -> finale URL
        except HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                sLocation = e.headers.get('Location', '')
            else:
                logger.error(' -> [requestHandler]: getRedirectUrl HTTPError %s Url: %s' % (str(e), self._sUrl))
        except (URLError, HTTPException) as e:
            logger.error(' -> [requestHandler]: getRedirectUrl Fehler %s Url: %s' % (str(e), self._sUrl))

        if sLocation:
            sLocation = urljoin(self._sUrl, sLocation)  # relative Location -> absolut
        return sLocation

    def __setCookiePath(self):
        cookieFile = os.path.join(self._profilePath, 'cookies')
        if not os.path.exists(cookieFile):
            os.makedirs(cookieFile)
        if 'dummy' not in self._sUrl:
            cookieFile = os.path.join(cookieFile, urlparse(self._sUrl).netloc.replace('.', '_') + '.txt')
            if not os.path.exists(cookieFile):
                open(cookieFile, 'w').close()
            self._cookiePath = cookieFile

    def getCookie(self, sCookieName, sDomain=''):
        cookieJar = LWPCookieJar()
        try:
            cookieJar.load(self._cookiePath, self.__bIgnoreDiscard, self.__bIgnoreExpired)
        except Exception as e:
            logger.error(e)
        for entry in cookieJar:
            if entry.name == sCookieName:
                if sDomain == '':
                    return entry
                elif entry.domain == sDomain:
                    return entry
        return False

    def setCookie(self, oCookie):
        cookieJar = LWPCookieJar()
        try:
            cookieJar.load(self._cookiePath, self.__bIgnoreDiscard, self.__bIgnoreExpired)
            cookieJar.set_cookie(oCookie)
            cookieJar.save(self._cookiePath, self.__bIgnoreDiscard, self.__bIgnoreExpired)
        except Exception as e:
            logger.error(e)

    def ignoreDiscard(self, bIgnoreDiscard):
        self.__bIgnoreDiscard = bIgnoreDiscard

    def ignoreExpired(self, bIgnoreExpired):
        self.__bIgnoreExpired = bIgnoreExpired

    def __doh_request(self, url, doh_server="https://cloudflare-dns.com/dns-query"):
        # Parse the URL
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        # Bewusst NICHT gecacht: DDoS-Guard-Edges rotieren, eine im RAM-Cache
        # festgehaltene IP koennte innerhalb der TTL sterben -> immer frisch aufloesen.
        params = urlencode({"name": hostname, "type": "A"})
        doh_url = f"{doh_server}?{params}"
        req = Request(doh_url)
        req.add_header("Accept", "application/dns-json")

        try:
            response = urlopen(req, timeout=5)
            response_text = response.read().decode("utf-8", "replace")
            dns_response = json.loads(response_text)
            if "Answer" not in dns_response:
                raise Exception("Invalid DNS response")
            # Ersten echten A-Record (type 1) aus der Answer-Liste nehmen statt stur [0]:
            # bei CNAME-Ketten kann die IP erst weiter hinten stehen, [0] waere dann der CNAME.
            ip_address = next((a["data"] for a in dns_response["Answer"] if a.get("type") == 1), None)
            if not ip_address:
                raise Exception("No A record in DNS answer")
            return ip_address
        except Exception as e:
            logger.error(' -> [requestHandler]: DNS query failed: %s' % e)
            return None

    def __setCachePath(self):
        cache = os.path.join(self._profilePath, 'htmlcache')
        if not os.path.exists(cache):
            os.makedirs(cache)
        self._cachePath = cache

    def __readPersistentCache(self, url):
        h = hashlib.md5(url.encode('utf8')).hexdigest()
        cacheFile = os.path.join(self._cachePath, h)
        fileAge = self.getFileAge(cacheFile)
        if 0 < fileAge < self.cacheTime:
            try:
                with open(cacheFile, 'rb') as f:
                        content = f.read().decode('utf8')
            except Exception:
                logger.error(' -> [requestHandler]: Could not read Cache')
            if content:
                logger.info(' -> [requestHandler]: read html for %s from cache' % url)
                return content
        return None

    def __writePersistentCache(self, url, content):
        try:
            h = hashlib.md5(url.encode('utf8')).hexdigest()
            with open(os.path.join(self._cachePath, h), 'wb') as f:
                f.write(content.encode('utf8'))
        except Exception:
            logger.error(' -> [requestHandler]: Could not write Cache')

    def __writeVolatileCache(self, url, content):
        self._memCache.set(hashlib.md5(url.encode('utf8')).hexdigest(), content)

    def __readVolatileCache(self, url, cache_time):
        entry = self._memCache.get(hashlib.md5(url.encode('utf8')).hexdigest(), cache_time)
        if entry:
            logger.info('-> [requestHandler]: read html for %s from cache' % url)
        return entry

    @staticmethod
    def getFileAge(cacheFile):
        try:
            return time.time() - os.stat(cacheFile).st_mtime
        except Exception:
            return 0

    def clearCache(self, silent=False):
        # clear volatile cache
        if self.isMemoryCacheActive:
            self._memCache.clear()
        cRequestHandler.persistent_openers.clear()
        
        # clear persistent cache
        files = os.listdir(self._cachePath)
        for file in files:
            os.remove(os.path.join(self._cachePath, file))
        if not silent and files:
            infoDialog(cConfig().getLocalizedString(30405), icon='INFO')


class cBF:
    def resolve(self, url, html, cookie_jar, user_agent, sParameters):
        page = urlparse(url).scheme + '://' + urlparse(url).netloc
        j = re.compile('<script[^>]src="([^"]+)').findall(html)
        if j:
            opener = build_opener(HTTPCookieProcessor(cookie_jar))
            opener.addheaders = [('User-agent', user_agent), ('Referer', url)]
            opener.open(page + j[0])
        a = re.compile(r'xhr\.open\("GET","([^,]+)",').findall(html)
        if a:
            import random
            aespage = page + a[0].replace('" + ww +"', str(random.randint(700, 1500)))
            opener = build_opener(HTTPCookieProcessor(cookie_jar))
            opener.addheaders = [('User-agent', user_agent), ('Referer', url)]
            html = opener.open(aespage).read().decode('utf-8', 'replace')
            cval = self.aes_decode(html)
            cdata = re.compile('cookie="([^="]+).*?domain[^>]=([^;]+)').findall(html)
            if cval and cdata:
                c = Cookie(version=0, name=cdata[0][0], value=cval, port=None, port_specified=False, domain=cdata[0][1], domain_specified=True, domain_initial_dot=False, path="/", path_specified=True, secure=False, expires=time.time() + 21600, discard=False, comment=None, comment_url=None, rest={})
                cookie_jar.set_cookie(c)
                opener = build_opener(HTTPCookieProcessor(cookie_jar))
                opener.addheaders = [('User-agent', user_agent), ('Referer', url)]
                return opener.open(url, sParameters if len(sParameters) > 0 else None).read().decode('utf-8', 'replace')

    @staticmethod
    def aes_decode(html):
        try:
            import pyaes
            keys = re.compile(r'toNumbers\("([^"]+)"').findall(html)
            if keys:
                from binascii import hexlify, unhexlify
                msg = unhexlify(keys[2])
                key = unhexlify(keys[0])
                iv = unhexlify(keys[1])
                decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(key, iv))
                plain_text = decrypter.feed(msg)
                plain_text += decrypter.feed()
                return hexlify(plain_text).decode()
        except Exception as e:
            logger.error(e)
