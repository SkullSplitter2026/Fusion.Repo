import json
import os
import struct
import time
import uuid
import hashlib
import hmac
import urllib .request
import binascii
import zlib
import webbrowser
from urllib .parse import urlparse ,parse_qs ,urlencode ,quote
import xbmcaddon
import xbmcvfs
import xbmc
import xbmcgui
_addon =xbmcaddon .Addon ()
_addon_path =xbmcvfs .translatePath (_addon .getAddonInfo ('path'))

try :
    from resources .lib .evil import gui as evil_gui
    from resources .lib .evil .gui import Item as EvilItem
    _EVIL_AVAILABLE =True
except Exception :
    _EVIL_AVAILABLE =False

ADDON =xbmcaddon .Addon ()
ADDON_ID =ADDON .getAddonInfo ('id')
PROFILE_PATH =xbmcvfs .translatePath (ADDON .getAddonInfo ('profile'))

TOKEN_FILE =os .path .join (PROFILE_PATH ,'tokens.json')
GUEST_TOKEN_FILE =os .path .join (PROFILE_PATH ,'guest_tokens.json')
DEVICE_FILE =os .path .join (PROFILE_PATH ,'device.json')

CODEFILE =os .path .join ('/storage/emulated/0/Download','code.txt')

AUTH_BASE ='https://auth.rtl.de/auth/realms/rtlplus/protocol/openid-connect'
CLIENT_ID ='bedrock-m6group_web'
REDIRECT_URI ='https://plus.rtl.de/silent-sso-iframe.html'
DEVICE_CLIENT_ID ='bedrock-androidtv'

FRONT_AUTH_URL ='https://front-auth.rtlde.bedrock.tech/v2/rtlde/platforms/m6group_web/token'

CLIENT_RELEASE ='6.41.2'
USER_AGENT =('Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
'(KHTML, like Gecko) SamsungBrowser/29.0 Chrome/136.0.0.0 Mobile Safari/537.36')

def _log (msg ):
    xbmc .log (f'[RTL+ Auth] {msg }',xbmc .LOGDEBUG )
def _img (fname ):
            return os .path .join (_addon_path ,'resources','media',fname )

def _detect_windows_browsers ():
    import os ,subprocess
    candidates =[
        ('Google Chrome',  r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
        ('Google Chrome',  r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'),
        ('Mozilla Firefox',r'C:\Program Files\Mozilla Firefox\firefox.exe'),
        ('Mozilla Firefox',r'C:\Program Files (x86)\Mozilla Firefox\firefox.exe'),
        ('Microsoft Edge', r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ('Microsoft Edge', r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'),
        ('Vivaldi',        r'C:\Users\{}\AppData\Local\Vivaldi\Application\vivaldi.exe'.format(os.environ.get('USERNAME',''))),
        ('Opera',          r'C:\Users\{}\AppData\Local\Programs\Opera\opera.exe'.format(os.environ.get('USERNAME',''))),
        ('Brave',          r'C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe'),
        ('Brave',          r'C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe'),
        ('Waterfox',       r'C:\Program Files\Waterfox\waterfox.exe'),
        ('LibreWolf',      r'C:\Program Files\LibreWolf\librewolf.exe'),
    ]
    found =[]
    seen =set ()
    for name ,path in candidates :
        if name not in seen and os .path .isfile (path ):
            found .append ((name ,path ))
            seen .add (name )
    return found

def _detect_libreelec_browsers ():
    import os
    candidates =[
        '/storage/.kodi/addons/browser.chromium/bin/chromium',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/usr/bin/firefox',
    ]
    return [p for p in candidates if os .path .isfile (p )]

def _is_libreelec ():
    import os
    return os .path .isfile ('/etc/libreelec-release')

def _open_browser (url ):
    import sys ,subprocess ,os
    try :
        if sys .platform .startswith ('android')or xbmc .getCondVisibility ('System.Platform.Android'):
            xbmc .executebuiltin (f'StartAndroidActivity(,android.intent.action.VIEW,,{url })')
            return True
        elif sys .platform .startswith ('win'):
            browsers =_detect_windows_browsers ()
            if browsers :
                labels =[name for name ,_ in browsers ]+['Standard-Browser (System)']
                idx =xbmcgui .Dialog ().select ('Browser für RTL+ Login wählen',labels )
                if idx <0 :
                    return False
                if idx <len (browsers ):
                    subprocess .Popen ([browsers [idx ][1 ],url ])
                    return True
                else :
                    import webbrowser
                    return bool (webbrowser .open (url ))
            else :
                import webbrowser
                return bool (webbrowser .open (url ))
        elif _is_libreelec ():
            browsers =_detect_libreelec_browsers ()
            if not browsers :
                _log ('_open_browser [LibreELEC]: kein Browser gefunden')
                return False
            _env =os .environ .copy ()
            _env .setdefault ('DISPLAY',':0')
            _env .setdefault ('XAUTHORITY','/var/run/slim.auth')
            _browser =browsers [0 ]
            _flags =['--no-sandbox','--disable-dev-shm-usage']
            if 'chromium' in _browser :
                _flags +=['--new-window','--disable-extensions','--disable-background-networking']
            subprocess .Popen ([_browser ]+_flags +[url ],env =_env ,
                stdout =subprocess .DEVNULL ,stderr =subprocess .DEVNULL )
            _log (f'_open_browser [LibreELEC]: gestartet: {_browser }')
            return True
        else :
            import webbrowser
            return bool (webbrowser .open (url ))
    except Exception as _e :
        _log (f'_open_browser: Fehler: {_e }')
        return False

def _write_black_png (path ):
    def _chunk (tag ,data ):
        crc =zlib .crc32 (tag +data )&0xffffffff
        return struct .pack ('>I',len (data ))+tag +data +struct .pack ('>I',crc )
    sig =b'\x89PNG\r\n\x1a\n'
    ihdr =_chunk (b'IHDR',struct .pack ('>IIBBBBB',1 ,1 ,8 ,2 ,0 ,0 ,0 ))
    idat =_chunk (b'IDAT',zlib .compress (b'\x00\x00\x00\x00'))
    iend =_chunk (b'IEND',b'')
    with open (path ,'wb')as f :
        f .write (sig +ihdr +idat +iend )

class _QRLoginWindow (xbmcgui .WindowDialog ):
    def __init__ (self ,qr_path ,text ,bg_path =''):
        super ().__init__ ()
        self .cancelled =False
        if bg_path :
            _bg =xbmcgui .ControlImage (0 ,0 ,1920 ,1080 ,bg_path )
            self .addControl (_bg )
        _box =xbmcgui .ControlTextBox (80 ,30 ,780 ,380 )
        self .addControl (_box )
        _box .setText (text )
        _img =xbmcgui .ControlImage (820 ,30 ,300 ,300 ,qr_path )
        self .addControl (_img )

    def onControl (self ,control ):
        self .cancelled =True
        self .close ()

    def onAction (self ,action ):
        if action .getId ()in (xbmcgui .ACTION_PREVIOUS_MENU ,xbmcgui .ACTION_NAV_BACK ,
                              xbmcgui .ACTION_SELECT_ITEM ):
            self .cancelled =True
            self .close ()

class RTLAuth :
    def __init__ (self ):
        os .makedirs (PROFILE_PATH ,exist_ok =True )
        self ._tokens =self ._load_tokens ()
        self ._guest_tokens =self ._load_guest_tokens ()

    def _load_guest_tokens (self ):
        try :
            if os .path .exists (GUEST_TOKEN_FILE ):
                with open (GUEST_TOKEN_FILE ,'r')as f :
                    return json .load (f )
        except Exception as e :
            _log (f'Load guest tokens error: {e }')
        return {}

    def _save_guest_tokens (self ):
        try :
            with open (GUEST_TOKEN_FILE ,'w')as f :
                json .dump (self ._guest_tokens ,f )
        except Exception as e :
            _log (f'Save guest tokens error: {e }')

    def _load_tokens (self ):
        _GUEST_KEYS =('is_guest','guest_bedrock_token','guest_bedrock_expires')
        try :
            if os .path .exists (TOKEN_FILE ):
                with open (TOKEN_FILE ,'r')as f :
                    raw =json .load (f )
                if raw .get ('__locked__'):
                    try :
                        data =json .loads (_decrypt_tokens (raw ['data']))
                    except Exception as e :
                        _log (f'GERÄTEBINDUNG fehlgeschlagen: {e }')
                        xbmcgui .Dialog ().notification (
                        'RTL+','Token ungültig für dieses Gerät – bitte neu anmelden',
                        xbmcgui .NOTIFICATION_ERROR ,5000 )
                        os .remove (TOKEN_FILE )
                        return {}
                else :
                    data =raw
                migrated =any (k in data for k in _GUEST_KEYS )
                for k in _GUEST_KEYS :
                    data .pop (k ,None )
                if migrated :
                    _log ('_load_tokens: Gast-Keys aus tokens.json entfernt (Migration)')
                return data
        except Exception as e :
            _log (f'Load tokens error: {e }')
        return {}

    def _save_tokens (self ):
        _login_keys =('access_token','refresh_token','gigya_uid')
        if not any (self ._tokens .get (k )for k in _login_keys ):
            _log ('_save_tokens: kein Login-Token vorhanden – tokens.json wird nicht geschrieben')
            return
        try :
            payload =json .dumps (self ._tokens )
            wrapper ={'__locked__':True ,'data':_encrypt_tokens (payload )}
            with open (TOKEN_FILE ,'w')as f :
                json .dump (wrapper ,f )
        except Exception as e :
            _log (f'Save tokens error: {e }')

    def logout (self ):
        self ._tokens ={}
        if os .path .exists (TOKEN_FILE ):
            os .remove (TOKEN_FILE )

    def invalidate_tokens (self ):
        for key in ('bedrock_token','bedrock_expires'):
            self ._tokens .pop (key ,None )
        self ._save_tokens ()
        _log ('Bedrock-Token invalidiert - wird beim naechsten Request erneuert')

    def _load_device_id (self ):
        try :
            if os .path .exists (DEVICE_FILE ):
                with open (DEVICE_FILE ,'r')as f :
                    return json .load (f ).get ('device_id','')
        except Exception as e :
            _log (f'Load device_id error: {e }')
        return ''

    def _save_device_id (self ,device_id ):
        try :
            os .makedirs (PROFILE_PATH ,exist_ok =True )

            with open (DEVICE_FILE ,'w')as f :
                json .dump ({'device_id':device_id },f )
        except Exception as e :
            _log (f'Save device_id error: {e }')

    def get_device_id (self ):
        if 'device_id'in self ._tokens :
            did =self ._tokens .pop ('device_id')
            self ._save_device_id (did )
            if self ._tokens :
                self ._save_tokens ()
            _log ('get_device_id: device_id aus tokens.json nach device.json migriert')
            return did
        did =self ._load_device_id ()
        if not did :
            did ='_luid_'+str (uuid .uuid4 ())
            self ._save_device_id (did )
            _log (f'get_device_id: neue device_id erzeugt: {did }')
        return did

    def get_oidc_token (self ):
        import requests
        now =time .time ()

        if (self ._tokens .get ('access_token')and
        self ._tokens .get ('oidc_expires',0 )>now +300 ):
            return self ._tokens ['access_token']

        _has_real_user =(bool (ADDON .getSetting ('username'))
                        and bool (self ._tokens .get ('refresh_token','')))
        if self ._guest_tokens .get ('is_guest')and not _has_real_user :
            return None
        if not ADDON .getSetting ('username'):
            return None

        refresh_token =self ._tokens .get ('refresh_token','')
        if refresh_token :
            _log ('Attempting OIDC token refresh...')
            _refresh_client =self ._tokens .get ('login_client',CLIENT_ID )
            try :
                resp =requests .post (
                f'{AUTH_BASE }/token',
                data ={
                'client_id':_refresh_client ,
                'grant_type':'refresh_token',
                'refresh_token':refresh_token ,
                },
                headers ={'User-Agent':USER_AGENT },
                timeout =15
                )
                if resp .status_code ==200 :
                    data =resp .json ()
                    self ._tokens ['access_token']=data ['access_token']
                    self ._tokens ['refresh_token']=data .get ('refresh_token',refresh_token )
                    self ._tokens ['oidc_expires']=now +data .get ('expires_in',3600 )
                    self ._tokens ['oidc_refresh_expires']=now +data .get ('refresh_expires_in',86400 )
                    self ._tokens .pop ('bedrock_token',None )
                    self ._tokens .pop ('bedrock_expires',None )
                    self ._save_tokens ()
                    _log ('OIDC token refreshed successfully')
                    return self ._tokens ['access_token']
                else :
                    _log (f'Refresh token rejected (HTTP {resp .status_code }) - will re-login silently')

                    self ._tokens .pop ('refresh_token',None )
                    self ._tokens .pop ('oidc_refresh_expires',None )
                    self ._save_tokens ()
            except Exception as e :
                _log (f'Refresh error: {e }')

        _log ('No valid token - attempting silent re-login')
        token =self ._silent_relogin ()
        if token :
            return token

        return self ._login ()

    def _silent_relogin (self ):
        import requests
        username =ADDON .getSetting ('username')
        password =ADDON .getSetting ('password')
        if not username or not password :
            _log ('Silent re-login skipped: no saved credentials')
            return None

        _log (f'Silent re-login for {username }')
        try :
            code_verifier =uuid .uuid4 ().hex +uuid .uuid4 ().hex
            import base64 as _b64 ,hashlib as _hl
            code_challenge =_b64 .urlsafe_b64encode (
            _hl .sha256 (code_verifier .encode ()).digest ()
            ).rstrip (b'=').decode ()

            session =requests .Session ()
            session .headers ['User-Agent']=USER_AGENT

            r1 =session .get (
            f'{AUTH_BASE }/auth',
            params ={
            'response_type':'code',
            'client_id':CLIENT_ID ,
            'redirect_uri':REDIRECT_URI ,
            'code_challenge':code_challenge ,
            'code_challenge_method':'S256',
            'scope':'openid',
            },
            allow_redirects =True ,
            timeout =15
            )

            import re as _re
            action_match =_re .search (r'action="([^"]+)"',r1 .text )
            if not action_match :
                _log ('Silent re-login: login form not found')
                return None

            action_url =action_match .group (1 ).replace ('&','&')

            r2 =session .post (
            action_url ,
            data ={'username':username ,'password':password ,'credentialId':''},
            allow_redirects =False ,
            timeout =15
            )

            location =r2 .headers .get ('Location','')
            code_match =_re .search (r'code=([^&]+)',location )
            if not code_match :
                _log (f'Silent re-login: kein Auth-Code in Redirect ({location [:100 ]}) – WAF-Block, gebe None zurück')
                return None

            r3 =session .post (
            f'{AUTH_BASE }/token',
            data ={
            'client_id':CLIENT_ID ,
            'grant_type':'authorization_code',
            'code':code_match .group (1 ),
            'code_verifier':code_verifier ,
            'redirect_uri':REDIRECT_URI ,
            },
            timeout =15
            )
            r3 .raise_for_status ()
            data =r3 .json ()

            now =time .time ()
            self ._tokens ['access_token']=data ['access_token']
            self ._tokens ['refresh_token']=data .get ('refresh_token','')
            self ._tokens ['oidc_expires']=now +data .get ('expires_in',3600 )
            self ._tokens ['oidc_refresh_expires']=now +data .get ('refresh_expires_in',86400 )

            try :
                payload =data ['access_token'].split ('.')[1 ]
                payload +='='*(-len (payload )%4 )
                import base64 as _b64j ,json as _json
                jwt_data =_json .loads (_b64j .b64decode (payload ))
                parts =jwt_data .get ('sub','').split (':')
                self ._tokens ['gigya_uid']=parts [-1 ]if parts else ''
            except Exception as je :
                _log (f'Silent re-login JWT parse: {je }')
                self ._tokens ['gigya_uid']=''

            self ._tokens .pop ('bedrock_token',None )
            self ._tokens .pop ('bedrock_expires',None )
            self ._save_tokens ()
            _log ('Silent re-login successful')
            return self ._tokens ['access_token']

        except Exception as e :
            _log (f'Silent re-login error: {e }')
            return None

    def download_accounts (self ):
        passw =''
        username =''
        userpass =''
        jsonData ={"js":[{"name":"Hier Anmelden","pass":"","username":"","password":""}]}

        return jsonData

    def select_and_save_credentials (self ):

        jsonData =[{"name":"Hier anmelden","pass":"","username":"","password":"",'icon':_img ('icon.png')}]

        Name =[]
        Username =[]
        Password =[]
        Passw =[]
        Icon =[]

        for i in jsonData :
            name =i .get ('name','?')
            username =i .get ('username','')
            password =i .get ('password','')
            passw =i .get ('pass','')
            try :
                icon =i ['icon']
            except Exception :
                icon =''

            Username .append (username )
            Password .append (password )
            Passw .append (passw )
            if passw !='':
                name =name +' [Pin Safe]'
            Name .append (name )
            Icon .append (icon )

        names =Name
        userlist =Username
        passlist =Password
        pinlist =Passw

        if _EVIL_AVAILABLE :
            _options =[]
            for i ,name in enumerate (names ):
                _options .append (EvilItem (label =name ,art ={'thumb':Icon [i ]}if Icon [i ]else {}))
            index =evil_gui .select ('RTL+ Zugang wählen',options =_options ,useDetails =True )
        else :
            index =xbmcgui .Dialog ().select ('RTL+ Zugang wählen',names )
        if index <0 :
            return None ,None

        username =userlist [index ]
        password =passlist [index ]
        pin =pinlist [index ]

        if not username :
            kb =xbmc .Keyboard ('','RTL+ E-Mail')
            kb .doModal ()
            if not kb .isConfirmed ():
                return None ,None
            username =kb .getText ().strip ()

            kb2 =xbmc .Keyboard ('','RTL+ Passwort',True )
            kb2 .doModal ()
            if not kb2 .isConfirmed ():
                return None ,None
            password =kb2 .getText ().strip ()
            pin =''

        if pin :
            while True :
                kb_pin =xbmc .Keyboard ('','User PIN',True )
                kb_pin .doModal ()
                if not kb_pin .isConfirmed ():
                    return None ,None
                if kb_pin .getText ()==pin :
                    break
                xbmcgui .Dialog ().notification ('RTL+','Falscher PIN',xbmcgui .NOTIFICATION_ERROR ,2000 )

        ADDON .setSetting ('username',username )
        ADDON .setSetting ('password',password )
        _log (f'select_and_save_credentials: Konto "{names [index ]}" gewählt')
        return username ,password

    def _browser_login (self ):
        """
        Fallback-Login via System-Browser + Datei-basierter Code-Übergabe.
        Wird automatisch aktiviert wenn AWS WAF den direkten requests-Login blockiert.

        Ablauf:
          1. code.txt im Download-Ordner anlegen (mit Anleitung als Kommentar)
          2. Auth-URL mit whitelisted redirect_uri (silent-sso-iframe.html) im Browser öffnen
          3. User meldet sich an – Browser landet auf:
               https://plus.rtl.de/silent-sso-iframe.html?code=XXXX&session_state=...
          4. User kopiert diese URL in code.txt und speichert
          5. User bestätigt in Kodi → Datei wird ausgelesen, Code extrahiert
          6. Token-Exchange, code.txt wird gelöscht

        Hintergrund: localhost als redirect_uri ist bei RTL+ server-seitig nicht
        whitelisted (→ "Ungültiger Parameter: redirect_uri").
        """
        import requests
        import re as _re

        _log ('=== Browser-Login START ===')
        _log (f'  AUTH_BASE    : {AUTH_BASE }')
        _log (f'  CLIENT_ID    : {CLIENT_ID }')
        _log (f'  REDIRECT_URI : {REDIRECT_URI }')

        import base64 as _b64 ,hashlib as _hl
        code_verifier =uuid .uuid4 ().hex +uuid .uuid4 ().hex
        code_challenge =_b64 .urlsafe_b64encode (
            _hl .sha256 (code_verifier .encode ()).digest ()
        ).rstrip (b'=').decode ()
        _log (f'  code_verifier: {code_verifier }')
        _log (f'  code_challenge:{code_challenge }')

        _saved_username =ADDON .getSetting ('username')
        params ={
            'response_type':'code',
            'client_id':CLIENT_ID ,
            'redirect_uri':REDIRECT_URI ,
            'code_challenge':code_challenge ,
            'code_challenge_method':'S256',
            'scope':'openid email profile',
            'auth_flow_type':'login',
            'claim':'sub',
        }
        if _saved_username :
            params ['login_hint']=_saved_username
            _log (f'  login_hint   : {_saved_username }')
        auth_url =f'{AUTH_BASE }/auth?'+urlencode (params )
        _log (f'  auth_url     : {auth_url }')

        xbmcgui .Dialog ().ok (
            'RTL+ Login – Anleitung',
            ('[B]Methode 1 – Datei (empfohlen für Android):[/B]\n'
             '  Browser → Anmelden → leere Seite erscheint\n'
             '  → Adressleiste antippen → URL kopieren\n'
             '  → Downloads/code.txt mit Text-Editor öffnen\n'
             '     (z.B. QuickEdit, Total Commander, ...)\n'
             '  → Alles löschen → URL einfügen → Speichern\n'
             '  → Kodi erkennt den Code automatisch.\n\n'
             '[B]Methode 2 – Tastatur:[/B]\n'
             '  Browser → Anmelden → Code nach "code=" ablesen\n'
             '  → zurück zu Kodi → [Abbrechen] tippen\n'
             '  → Code eintippen.\n\n'
             '[B]Methode 3 – Nur Datei:[/B]\n'
             '  code.txt mit Text-Editor öffnen\n'
             '  → URL aus code.txt kopieren und in Browser auf anderen Gerät\n'
             '     öffnen. (URL im Browser ändert sich)'
             '  → Adressleiste antippen → Geänderte URL kopieren\n'
             '  → Inhalt von code.txt löschen → Geänderte URL einfügen → Speichern\n'
             '  → Kodi erkennt den Code automatisch.' )
        )

        method =xbmcgui .Dialog ().select (
            'RTL+ Login – Methode wählen',
            [
                'TV-Gerätecode  –  Keycloak Device-Login (empfohlen)',
                'Datei  –  URL in Downloads/code.txt einfügen',
                'Tastatur  –  Code manuell eintippen',
                'Nur Datei  –  Auth-URL aus /code.txt entnehmen geänderte URL wieder einfügen',
            ]
        )
        if method <0 :
            _log ('Browser-Login: Methodenwahl abgebrochen')
            return None
        if method ==0 :
            return self ._device_login ()
        method -=1

        _codepath =CODEFILE
        if method ==0 or method ==2:
            _PATH_OPTIONS =[
                '/storage/emulated/0/Download/code.txt',
                '/storage/emulated/0/Downloads/code.txt',
                '/sdcard/Download/code.txt',
                '/mnt/sdcard/Download/code.txt',
                '/mnt/media_rw/sdcard/Download/code.txt',
                '/tmp/code.txt',
                'Eigener Pfad eingeben ...',
            ]
            _path_idx =xbmcgui .Dialog ().select (
                'code.txt – Speicherort wählen',
                _PATH_OPTIONS
            )
            if _path_idx <0 :
                _log ('Browser-Login [Datei]: Pfadwahl abgebrochen')
                return None
            if _path_idx ==len (_PATH_OPTIONS )-1 :
                _kb_path =xbmc .Keyboard (
                    CODEFILE ,'Vollständigen Pfad für code.txt eingeben'
                )
                _kb_path .doModal ()
                if not _kb_path .isConfirmed ():
                    return None
                _codepath =_kb_path .getText ().strip ()or CODEFILE
            else :
                _codepath =_PATH_OPTIONS [_path_idx ]
            _log (f'Browser-Login [Datei]: Pfad = {_codepath }')

        if method ==0:
            _log ('Browser-Login: öffne Auth-URL...')
            _browser_opened =_open_browser (auth_url )
            if not _browser_opened :
                _log ('_open_browser: kein Browser verfügbar – URL nur in code.txt')
                xbmcgui .Dialog ().ok (
                    'RTL+ Login – kein Browser',
                    ('Kein Browser auf diesem Gerät gefunden.\n'
                     'Die Login-URL wird in code.txt gespeichert.\n'
                     'Öffne die Datei auf diesem Gerät oder kopiere\n'
                     'die URL auf Handy/PC und melde dich dort an.'))

        code =None

        if method ==0 or method ==2:
            self ._write_codefile (auth_url, _codepath )
            _log ('Browser-Login [Datei]: code.txt angelegt – starte Polling')

            _poll_dlg =xbmcgui .DialogProgress ()
            
            if method ==0:
                _poll_dlg .create (
                    'RTL+ Login – warte auf code.txt',
                    ('1. Im Browser bei RTL+ anmelden.\n'
                     '2. Adressleiste antippen → [B]URL kopieren[/B].\n'
                     f'3. {_codepath } mit Text-Editor öffnen.\n'
                 '4. Alles löschen → URL einfügen → Speichern.\n'
                 'Kodi erkennt den Code automatisch.')
            )
            elif method ==2:
                _poll_dlg .create (
                    'RTL+ Login – warte auf code.txt',
                    ('1. Im Browser auf anderen Gerät bei RTL+ anmelden.\n'
                     f'2. {_codepath } mit Text-Editor öffnen.\n'
                     '3. URl aus code.txt kopieren und in Browser öffnen.\n'
                     '4. Adressleiste antippen → [B]Geänderte URL kopieren[/B].\n'
                    '5. Alles in code.txt löschen → geänderte URL einfügen → Speichern.\n'
                    'Kodi erkennt den Code automatisch.')
            )

            _deadline =time .time ()+300
            while time .time ()<_deadline and not _poll_dlg .iscanceled ():
                _remaining =int (_deadline -time .time ())
                _elapsed =300 -_remaining
                _poll_dlg .update (
                    min (99 ,int (_elapsed /3 )),
                    f'Noch {_remaining }s | code.txt öffnen → URL einfügen → Speichern.'
                )
                if os .path .exists (_codepath ):
                    try :
                        with open (_codepath ,'r',encoding ='utf-8')as _f :
                            _raw =_f .read ()
                        _content ='\n'.join (
                            l for l in _raw .splitlines ()
                            if not l .strip ().startswith ('#')
                        ).strip ()
                        if _content :
                            _log (f'[Datei] Inhalt: {_content [:200 ]}')
                            _err =_re .search (r'[?&]error=([^&\s]+)',_content )
                            if _err :
                                _poll_dlg .close ()
                                xbmcgui .Dialog ().notification (
                                    'RTL+',f'Login-Fehler: {_err .group (1 )}',
                                    xbmcgui .NOTIFICATION_ERROR ,5000 )
                                _log (f'[Datei] Auth-Fehler: {_err .group (1 )}')
                                return None
                            _cm =_re .search (r'[?&]code=([^&\s]+)',_content )
                            if _cm :
                                code =_cm .group (1 )
                                _log (f'[Datei] ✓ Auth-Code: {code [:20 ]}...')
                                break
                            if _re .match (
                                r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}'
                                r'-[0-9a-f]{4}-[0-9a-f]{12}$',
                                _content ,_re .IGNORECASE
                            ):
                                code =_content
                                _log (f'[Datei] ✓ UUID direkt: {code [:20 ]}...')
                                break
                    except Exception as _e :
                        _log (f'[Datei] Lesefehler: {_e }')
                xbmc .sleep (1000 )
            _poll_dlg .close ()

            try :
                if os .path .exists (_codepath ):
                    os .remove (_codepath )
                    _log ('[Datei] code.txt gelöscht')
            except Exception as _e :
                _log (f'[Datei] Löschen fehlgeschlagen: {_e }')

            if not code :
                xbmcgui .Dialog ().notification (
                    'RTL+','Kein Code in code.txt gefunden – Login abgebrochen.',
                    xbmcgui .NOTIFICATION_ERROR ,5000 )
                return None

        else :
            import sys as _sys
            if _sys .platform .startswith ('win'):
                _log ('Browser-Login [Tastatur]: öffne Auth-URL (Windows)...')
                _opened =_open_browser (auth_url )
                if not _opened :
                    _log ('Browser-Login [Tastatur]: _open_browser fehlgeschlagen')
            _log ('Browser-Login [Tastatur]: DialogProgress – warte auf Rückkehr')
            _park_dlg =xbmcgui .DialogProgress ()
            _park_dlg .create (
                'RTL+ Login – im Browser anmelden',
                ('1. Im Browser bei RTL+ anmelden.\n'
                 '2. Leere Seite erscheint → Adressleiste antippen.\n'
                 '3. Code nach [B]code=[/B] ablesen (UUID-Format).\n'
                 '4. Zurück zu Kodi → hier [B]Abbrechen[/B] tippen.\n'
                 '   Danach öffnet sich das Eingabefeld.')
            )
            while not _park_dlg .iscanceled ():
                xbmc .sleep (500 )
            _park_dlg .close ()
            _log ('Browser-Login [Tastatur]: Kodi im Vordergrund – zeige Keyboard')

            for _attempt in range (1 ,4 ):
                _kb =xbmc .Keyboard (
                    '',f'Code eingeben (nach code=) – Versuch {_attempt }/3'
                )
                _kb .doModal ()
                if not _kb .isConfirmed ():
                    _log (f'[Tastatur {_attempt }] Abgebrochen')
                    return None
                _raw =_kb .getText ().strip ()
                _log (f'[Tastatur {_attempt }] Eingabe: {_raw [:80 ]}')
                if not _raw :
                    if _attempt <3 :
                        xbmcgui .Dialog ().notification (
                            'RTL+','Kein Code eingegeben – nochmal versuchen',
                            xbmcgui .NOTIFICATION_WARNING ,3000 )
                    continue
                _url_cand =(_raw if 'code='in _raw
                            else f'{REDIRECT_URI }?code={_raw }')
                _err =_re .search (r'[?&]error=([^&\s]+)',_url_cand )
                if _err :
                    xbmcgui .Dialog ().notification (
                        'RTL+',f'Login-Fehler: {_err .group (1 )}',
                        xbmcgui .NOTIFICATION_ERROR ,5000 )
                    _log (f'[Tastatur] Auth-Fehler: {_err .group (1 )}')
                    return None
                _cm =_re .search (r'[?&]code=([^&\s]+)',_url_cand )
                if _cm :
                    code =_cm .group (1 )
                    _log (f'[Tastatur] ✓ Auth-Code: {code [:20 ]}...')
                    break
                _log (f'[Tastatur] Kein code=-Parameter: {_url_cand [:200 ]}')
                if _attempt <3 :
                    xbmcgui .Dialog ().notification (
                        'RTL+','Ungültige Eingabe – bitte nochmal',
                        xbmcgui .NOTIFICATION_WARNING ,3000 )

            if not code :
                return None

        _log ('=== Token-Exchange START ===')
        _log (f'  URL          : {AUTH_BASE }/token')
        _log (f'  client_id    : {CLIENT_ID }')
        _log (f'  redirect_uri : {REDIRECT_URI }')
        _log (f'  code         : {code }')
        _log (f'  code_verifier: {code_verifier }')
        try :
            token_url =f'{AUTH_BASE }/token'
            token_data ={
                'client_id':CLIENT_ID ,
                'grant_type':'authorization_code',
                'code':code ,
                'code_verifier':code_verifier ,
                'redirect_uri':REDIRECT_URI ,
            }
            token_headers ={
                'User-Agent':USER_AGENT ,
                'Origin':'https://plus.rtl.de',
                'Referer':'https://plus.rtl.de/',
                'Accept':'*/*',
                'Accept-Language':'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
                'Sec-Fetch-Site':'same-site',
                'Sec-Fetch-Mode':'cors',
                'Sec-Fetch-Dest':'empty',
            }
            _log (f'  POST Headers : {token_headers }')
            r =requests .post (token_url ,data =token_data ,headers =token_headers ,timeout =15 )
            _log (f'  HTTP Status  : {r .status_code } {r .reason }')
            _log (f'  Resp Headers : {dict (r .headers )}')
            _log (f'  Resp Body    : {r .text [:500 ]}')
            r .raise_for_status ()
            data =r .json ()
            _log (f'  access_token : {data .get ("access_token","(fehlt)")[:30 ]}...')
            _log (f'  token_type   : {data .get ("token_type")}')
            _log (f'  expires_in   : {data .get ("expires_in")}')
            _log ('=== Token-Exchange ERFOLGREICH ===')
        except requests .exceptions .HTTPError as e :
            _log (f'[Token-Exchange] HTTPError {r .status_code}: {r .text [:500 ]}')
            xbmcgui .Dialog ().ok ('RTL+ Token-Exchange Fehler',
                f'HTTP {r .status_code }\n{r .text [:300 ]}')
            return None
        except Exception as e :
            _log (f'[Token-Exchange] {type (e ).__name__}: {e }')
            xbmcgui .Dialog ().notification ('RTL+',f'Token-Exchange: {e }',
                xbmcgui .NOTIFICATION_ERROR ,5000 )
            return None

        now =time .time ()
        self ._tokens ['access_token']=data ['access_token']
        self ._tokens ['refresh_token']=data .get ('refresh_token','')
        self ._tokens ['oidc_expires']=now +data .get ('expires_in',3600 )
        self ._tokens ['oidc_refresh_expires']=now +data .get ('refresh_expires_in',86400 )

        try :
            import base64
            payload =data ['access_token'].split ('.')[1 ]
            payload +='='*(-len (payload )%4 )
            jwt_data =json .loads (base64 .b64decode (payload ))
            parts =jwt_data .get ('sub','').split (':')
            self ._tokens ['gigya_uid']=parts [-1 ]if parts else ''
        except Exception as je :
            _log (f'Browser-Login JWT parse: {je }')
            self ._tokens ['gigya_uid']=''

        self ._tokens .pop ('bedrock_token',None )
        self ._tokens .pop ('bedrock_expires',None )
        self ._tokens .pop ('_subscription_tier',None )
        self ._tokens .pop ('_premium_status_ts',None )

        if self ._guest_tokens .get ('is_guest'):
            self ._guest_tokens ['is_guest']=False
            self ._save_guest_tokens ()

        self ._tokens ['login_client']=CLIENT_ID
        self ._save_tokens ()
        _log (f'Browser-Login OK, gigya_uid={self ._tokens .get ("gigya_uid")}')
        self .get_bedrock_token ()
        return self ._tokens ['access_token']

    def _write_codefile (self , auth_url =None,path =None ):
        """Legt code.txt mit Anleitung am gewählten Pfad an (Methode 1 oder 3).
        Bestehender Inhalt wird überschrieben damit eine vorherige Session
        nicht versehentlich wiederverwendet wird.
        """
        if path is None :
            path =CODEFILE
        
        if auth_url is None :
            _instructions =(
            '# RTL+ Login – Anleitung (Methode: Datei)\n'
            '#\n'
            '# 1. Melde dich im Browser bei RTL+ an.\n'
            '# 2. Nach dem Login erscheint eine leere Seite.\n'
            '#    Die Adressleiste enthält eine URL wie:\n'
            '#    https://plus.rtl.de/silent-sso-iframe.html?code=XXXX&...\n'
            '# 3. Tippe auf die Adressleiste und kopiere die KOMPLETTE URL.\n'
            '# 4. Lösche ALLES in dieser Datei (auch diese Kommentare).\n'
            '# 5. Füge nur die URL ein und speichere die Datei.\n'
            '# 6. Kodi erkennt den Code automatisch – fertig!\n'
            '#\n'
            '# Datei-Pfad:\n'
            f'# {path }\n'
        )
        else:
            _instructions =(
            '# RTL+ Login – Anleitung (Methode: Nur Datei)\n'
            '#\n'
            '# 1. Melde dich auf anderem Gerät im Browser bei RTL+ an.\n'
            f'# 2. Rufe dann diese URL in dem Browser auf:\n{auth_url }\n'
            '# 3. Tippe auf die Adressleiste und kopiere die geänderte KOMPLETTE URL.\n'
            '# 4. Lösche ALLES in dieser Datei (auch diese Kommentare).\n'
            '# 5. Füge nur die URL ein und speichere die Datei.\n'
            '# 6. Kodi erkennt den Code automatisch – fertig!\n'
            '#\n'
            '# Datei-Pfad:\n'
            f'# {path }\n'
        )
        try :
            _dir =os .path .dirname (path )
            if _dir :
                os .makedirs (_dir ,exist_ok =True )
            with open (path ,'w',encoding ='utf-8')as _f :
                _f .write (_instructions )
            _log (f'_write_codefile: angelegt unter {path }')
        except Exception as _e :
            _log (f'_write_codefile: Fehler: {_e }')

    def _login (self ):
        import requests

        username =ADDON .getSetting ('username')
        password =ADDON .getSetting ('password')

        if not username or not password :
            idx =xbmcgui .Dialog ().select (
                'RTL+ Anmeldung',
                ['Zugangsdaten eingeben','TV-Gerätecode (empfohlen)','Browser-Login (Fallback)']
            )
            if idx <0 :
                return None
            if idx ==1 :
                return self ._device_login ()
            if idx ==2 :
                return self ._browser_login ()
            username ,password =self .select_and_save_credentials ()
            if not username or not password :
                return None

        _log (f'Logging in as {username }...')

        code_verifier =uuid .uuid4 ().hex +uuid .uuid4 ().hex
        import base64 ,hashlib
        code_challenge =base64 .urlsafe_b64encode (
        hashlib .sha256 (code_verifier .encode ()).digest ()
        ).rstrip (b'=').decode ()

        session =requests .Session ()
        session .headers ['User-Agent']=USER_AGENT

        try :
            r1 =session .get (
            f'{AUTH_BASE }/auth',
            params ={
            'response_type':'code',
            'client_id':CLIENT_ID ,
            'redirect_uri':REDIRECT_URI ,
            'code_challenge':code_challenge ,
            'code_challenge_method':'S256',
            'scope':'openid',
            },
            allow_redirects =True ,
            timeout =15
            )
        except Exception as e :
            _log (f'Auth page error: {e }')
            return None

        import re
        action_match =re .search (r'action="([^"]+)"',r1 .text )
        if not action_match :
            _log ('Could not find login form action')
            return None

        action_url =action_match .group (1 ).replace ('&','&')

        try :
            r2 =session .post (
            action_url ,
            data ={
            'username':username ,
            'password':password ,
            'credentialId':'',
            },
            allow_redirects =False ,
            timeout =15
            )
        except Exception as e :
            _log (f'Login POST error: {e }')
            return None

        location =r2 .headers .get ('Location','')
        code_match =re .search (r'code=([^&]+)',location )
        if not code_match :
            _log (f'No code in redirect: {location [:200 ]}')
            _log ('WAF-Block erkannt - versuche Silent Re-Login als zweiten Versuch')
            _silent_token =self ._silent_relogin ()
            if _silent_token :
                _log ('WAF-Fallback: Silent Re-Login erfolgreich – kein Browser nötig')
                return _silent_token
            _log ('Silent Re-Login auch fehlgeschlagen – starte Browser-Login als Fallback')
            xbmcgui .Dialog ().notification (
                'RTL+',
                'Sicherheitscheck erkannt – Browser öffnet sich...',
                xbmcgui .NOTIFICATION_INFO ,4000 )
            return self ._browser_login ()

        code =code_match .group (1 )

        try :
            r3 =session .post (
            f'{AUTH_BASE }/token',
            data ={
            'client_id':CLIENT_ID ,
            'grant_type':'authorization_code',
            'code':code ,
            'code_verifier':code_verifier ,
            'redirect_uri':REDIRECT_URI ,
            },
            timeout =15
            )
            r3 .raise_for_status ()
            data =r3 .json ()
        except Exception as e :
            _log (f'Token exchange error: {e }')
            return None

        now =time .time ()
        self ._tokens ['access_token']=data ['access_token']
        self ._tokens ['refresh_token']=data .get ('refresh_token','')
        self ._tokens ['oidc_expires']=now +data .get ('expires_in',3600 )
        self ._tokens ['oidc_refresh_expires']=now +data .get ('refresh_expires_in',86400 )

        try :
            import base64
            payload =data ['access_token'].split ('.')[1 ]
            payload +='='*(-len (payload )%4 )
            jwt_data =json .loads (base64 .b64decode (payload ))
            self ._tokens ['gigya_uid']=jwt_data .get ('sub','').split (':')[-1 ]

            parts =jwt_data .get ('sub','').split (':')
            if len (parts )>=3 :
                self ._tokens ['gigya_uid']=parts [-1 ]
            else :
                self ._tokens ['gigya_uid']=parts [-1 ]if parts else ''
        except Exception as e :
            _log (f'JWT parse error: {e }')
            self ._tokens ['gigya_uid']=''

        self ._tokens .pop ('bedrock_token',None )
        self ._tokens .pop ('bedrock_expires',None )
        self ._tokens .pop ('_subscription_tier',None )
        self ._tokens .pop ('_premium_status_ts',None )

        if self ._guest_tokens .get ('is_guest'):
            self ._guest_tokens ['is_guest']=False
            self ._save_guest_tokens ()
            _log ('Login: is_guest-Flag in guest_tokens geloescht')

        self ._tokens ['login_client']=CLIENT_ID
        self ._save_tokens ()
        _log (f'Login OK, gigya_uid={self ._tokens .get ("gigya_uid")}')
        self .get_bedrock_token ()
        _log (f'Login OK, profile_id={self ._tokens .get ("profile_id","FEHLT")}')
        return self ._tokens ['access_token']
    def _device_login (self ):
        import requests
        _log ('=== Device-Login START ===')

        device_auth_url =f'{AUTH_BASE }/auth/device'
        token_url =f'{AUTH_BASE }/token'

        try :
            resp =requests .post (
                device_auth_url ,
                data ={'client_id':DEVICE_CLIENT_ID ,'scope':'openid'},
                headers ={'User-Agent':USER_AGENT },
                timeout =15
            )
            resp .raise_for_status ()
            data =resp .json ()
        except Exception as e :
            _log (f'Device-Login: Anfrage fehlgeschlagen: {e }')
            xbmcgui .Dialog ().notification ('RTL+',f'Device-Login fehlgeschlagen: {e }',
                xbmcgui .NOTIFICATION_ERROR ,5000 )
            return None

        device_code =data .get ('device_code','')
        user_code =data .get ('user_code','')
        verification_uri =data .get ('verification_uri','https://auth.rtl.de/auth/realms/rtlplus/device')
        verification_uri_complete =data .get (
            'verification_uri_complete',
            f'{verification_uri }?user_code={user_code }'
        )
        expires_in =int (data .get ('expires_in',600 ))
        interval =max (int (data .get ('interval',5 )),5 )

        _log (f'Device-Login: user_code={user_code }, expires_in={expires_in }s, interval={interval }s')

        if not device_code or not user_code :
            _log ('Device-Login: kein device_code/user_code in Antwort')
            xbmcgui .Dialog ().notification ('RTL+','Device-Login: ungültige Serverantwort',
                xbmcgui .NOTIFICATION_ERROR ,5000 )
            return None

        code_display =user_code .upper ()

        qr_path =os .path .join (PROFILE_PATH ,'device_qr.png')
        bg_path =os .path .join (PROFILE_PATH ,'black.png')
        qr_ok =False
        try :
            _write_black_png (bg_path )
        except Exception :
            bg_path =''
        try :
            _qr_resp =requests .post (
                'https://api.qrserver.com/v1/create-qr-code/',
                data ={'size':'800x800','ecc':'L','data':verification_uri_complete },
                timeout =10
            )
            _qr_resp .raise_for_status ()
            with open (qr_path ,'wb')as _f :
                _f .write (_qr_resp .content )
            qr_ok =True
            _log (f'Device-Login: QR-Code gespeichert')
        except Exception as _e :
            _log (f'Device-Login: QR-Code Fehler: {_e }')

        instructions =(
            f'[B]Code:[/B] [COLOR gold]{code_display }[/COLOR]\n\n'
            f'Auf Handy/PC aufrufen:\n[B]{verification_uri }[/B]\n\n'
            f'QR-Code scannen: Code ist bereits vorausgefüllt.\n'
            f'Kodi erkennt die Anmeldung automatisch.'
        )

        deadline =time .time ()+expires_in
        access_token_data =None
        _last_poll =0
        _slow_interval =interval

        if qr_ok :
            try :
                qr_win =_QRLoginWindow (qr_path ,instructions ,bg_path )
                qr_win .show ()
            except Exception as _e :
                _log (f'Device-Login: QR-Fenster Fehler: {_e }')
                qr_ok =False

        if not qr_ok :
            poll_dlg =xbmcgui .DialogProgress ()
            poll_dlg .create (
                'RTL+ Device-Login',
                f'Auf Handy/PC: [B]{verification_uri }[/B]\n'
                f'Code: [COLOR gold][B]{code_display }[/B][/COLOR]\n\n'
                'Kodi wartet auf Bestätigung...'
            )

        while time .time ()<deadline :
            if qr_ok :
                if qr_win .cancelled :
                    break
            else :
                if poll_dlg .iscanceled ():
                    break
                _remaining =int (deadline -time .time ())
                _elapsed =expires_in -_remaining
                poll_dlg .update (
                    min (99 ,int (_elapsed *100 /expires_in )),
                    f'{verification_uri }   Code: [B]{code_display }[/B]\nNoch {_remaining }s'
                )

            _now =time .time ()
            if _now -_last_poll <_slow_interval :
                xbmc .sleep (500 )
                continue
            _last_poll =_now

            try :
                _r =requests .post (
                    token_url ,
                    data ={
                        'client_id':DEVICE_CLIENT_ID ,
                        'grant_type':'urn:ietf:params:oauth:grant-type:device_code',
                        'device_code':device_code ,
                    },
                    headers ={'User-Agent':USER_AGENT },
                    timeout =15
                )
            except Exception as _e :
                _log (f'Device-Login Poll-Fehler: {_e }')
                xbmc .sleep (2000 )
                continue

            if _r .status_code ==200 :
                access_token_data =_r .json ()
                _log ('Device-Login: Anmeldung bestätigt!')
                break

            try :
                _err_data =_r .json ()
            except Exception :
                _err_data ={}

            _err =_err_data .get ('error','')
            if _err =='authorization_pending':
                pass
            elif _err =='slow_down':
                _slow_interval =min (_slow_interval +5 ,30 )
                _log (f'Device-Login: slow_down – neues Intervall {_slow_interval }s')
            elif _err =='expired_token':
                _log ('Device-Login: Code abgelaufen')
                break
            elif _err =='access_denied':
                _log ('Device-Login: User hat abgelehnt')
                break
            else :
                _log (f'Device-Login: unbekannter Fehler {_err }: {_r .text [:200 ]}')
                break

        if qr_ok :
            try :
                qr_win .close ()
                del qr_win
            except Exception :
                pass
            try :
                if os .path .exists (qr_path ):
                    os .remove (qr_path )
            except Exception :
                pass
        else :
            poll_dlg .close ()

        if not access_token_data :
            xbmcgui .Dialog ().notification ('RTL+','Device-Login: nicht bestätigt',
                xbmcgui .NOTIFICATION_ERROR ,4000 )
            return None

        now =time .time ()
        self ._tokens ['access_token']=access_token_data ['access_token']
        self ._tokens ['refresh_token']=access_token_data .get ('refresh_token','')
        self ._tokens ['oidc_expires']=now +access_token_data .get ('expires_in',3600 )
        self ._tokens ['oidc_refresh_expires']=now +access_token_data .get ('refresh_expires_in',86400 )

        try :
            import base64
            _payload =access_token_data ['access_token'].split ('.')[1 ]
            _payload +='='*(-len (_payload )%4 )
            _jwt =json .loads (base64 .b64decode (_payload ))
            _parts =_jwt .get ('sub','').split (':')
            self ._tokens ['gigya_uid']=_parts [-1 ]if _parts else ''
        except Exception as _e :
            _log (f'Device-Login JWT parse: {_e }')
            self ._tokens ['gigya_uid']=''

        self ._tokens .pop ('bedrock_token',None )
        self ._tokens .pop ('bedrock_expires',None )
        self ._tokens .pop ('_subscription_tier',None )
        self ._tokens .pop ('_premium_status_ts',None )
        self ._tokens ['login_client']=DEVICE_CLIENT_ID

        if self ._guest_tokens .get ('is_guest'):
            self ._guest_tokens ['is_guest']=False
            self ._save_guest_tokens ()

        self ._save_tokens ()
        _log (f'Device-Login OK, gigya_uid={self ._tokens .get ("gigya_uid")}')
        self .get_bedrock_token ()
        _log (f'Device-Login OK, profile_id={self ._tokens .get ("profile_id","FEHLT")}')
        return self ._tokens ['access_token']

    def get_bedrock_token (self ):
        import requests
        now =time .time ()

        if (self ._tokens .get ('bedrock_token')and
        self ._tokens .get ('bedrock_expires',0 )>now +300 ):
            return self ._tokens ['bedrock_token']

        access_token =self .get_oidc_token ()
        if not access_token :
            return None

        gigya_uid =self .get_gigya_uid ()
        device_id =self .get_device_id ()
        profile_id =self ._tokens .get ('profile_id','')

        ts =int (now )
        auth_token =hmac .new (
        gigya_uid .encode ()if gigya_uid else b'',
        str (ts ).encode (),
        hashlib .sha1
        ).hexdigest ()if gigya_uid else ''

        headers ={
        'Authorization':f'Bearer {access_token }',
        'x-auth-device-name':'Android - Samsung Internet',
        'x-auth-gigya-uid':gigya_uid ,
        'x-auth-token-timestamp':str (ts ),
        'x-auth-token':auth_token ,
        'x-auth-profile-id':profile_id ,
        'x-auth-device-id':device_id ,
        'x-auth-device-player-size-width':'1920',
        'x-auth-device-player-size-height':'1080',
        'x-client-release':CLIENT_RELEASE ,
        'x-customer-name':'rtlde',
        'request-timeout':'10000',
        'User-Agent':USER_AGENT ,
        'Origin':'https://plus.rtl.de',
        'Referer':'https://plus.rtl.de/',
        'Accept':'*/*',
        }

        _log ('Getting Bedrock token...')
        try :
            resp =requests .get (FRONT_AUTH_URL ,headers =headers ,timeout =15 )
            resp .raise_for_status ()
            data =resp .json ()
            bedrock_token =data .get ('token','')
            if not bedrock_token :
                _log (f'No bedrock token in response: {data }')
                return self ._guest_tokens .get ('guest_bedrock_token') or None

            self ._tokens ['bedrock_token']=bedrock_token
            self ._tokens ['bedrock_expires']=now +86000
            self ._save_tokens ()
            _log ('Bedrock token OK')
            if not self ._tokens .get ('profile_id'):
                try :
                    import base64 as _b64 ,json as _json
                    payload =bedrock_token .split ('.')[1 ]
                    payload +='='*(4 -len (payload )%4 )
                    jwt_data =_json .loads (_b64 .b64decode (payload ))
                    _log (f'Bedrock JWT keys: {list (jwt_data .keys ())}')
                    pid =jwt_data .get ('profileid','')or jwt_data .get ('profileId','')
                    if pid :
                        self ._tokens ['profile_id']=pid
                        _log (f'Bedrock token: profileId={pid }')
                        self ._save_tokens ()
                    else :
                        _log ('Bedrock JWT: kein profileid - versuche Users-API')
                        gigya =self .get_gigya_uid ()
                        if gigya :
                            _pid =self ._fetch_profile_id_from_api (access_token ,bedrock_token )
                            if _pid :
                                self ._tokens ['profile_id']=_pid
                                self ._tokens .pop ('bedrock_token',None )
                                self ._tokens .pop ('bedrock_expires',None )
                                self ._save_tokens ()
                                _log (f'Bedrock token: profileId via API={_pid }, hole neuen Bedrock')
                                return self .get_bedrock_token ()
                except Exception as _ex :
                    _log (f'Bedrock JWT decode Fehler: {_ex }')
            return bedrock_token

        except Exception as e :
            _log (f'Bedrock token error: {e } - using guest_bedrock_token fallback')
            return self ._guest_tokens .get ('guest_bedrock_token') or None

    def _fetch_profile_id_from_api (self ,access_token ,bedrock_token ):
        import requests as _r
        gigya =self .get_gigya_uid ()
        if not gigya :
            return ''
        try :
            resp =_r .get (
                f'https://users.rtlde.bedrock.tech/v2/platforms/m6group_web/users/{gigya }/profiles',
                headers ={
                    'Authorization':f'Bearer {access_token }',
                    'x-bedrock-token':bedrock_token ,
                    'User-Agent':USER_AGENT ,
                    'Origin':'https://plus.rtl.de',
                    'Referer':'https://plus.rtl.de/',
                },
                timeout =10
            )
            profiles =resp .json ()
            if profiles and isinstance (profiles ,list ):
                pid =profiles [0 ].get ('uid','')
                _log (f'_fetch_profile_id_from_api: pid={pid }')
                return pid
        except Exception as e :
            _log (f'_fetch_profile_id_from_api error: {e }')
        return ''

    def get_gigya_uid (self ):
        uid =self ._tokens .get ('gigya_uid','')
        if uid :
            return uid
        import base64 ,json as _json
        at =self ._tokens .get ('access_token','')
        if at :
            try :
                parts =at .split ('.')
                payload =parts [1 ]+'=' *(-len (parts [1 ])%4 )
                sub =_json .loads (base64 .b64decode (payload )).get ('sub','')
                uid =sub .split (':')[-1 ]if sub else ''
                if uid :
                    self ._tokens ['gigya_uid']=uid
                    self ._save_tokens ()
                return uid
            except Exception :
                pass
        return ''

    def ensure_profile_id (self ):
        if self ._tokens .get ('profile_id'):
            return
        try :
            access_token =self .get_oidc_token ()
            self .get_profile_id (access_token =access_token )
            if self ._tokens .get ('profile_id'):
                self ._tokens .pop ('bedrock_token',None )
                self ._tokens .pop ('bedrock_expires',None )
                _log ('ensure_profile_id: bedrock invalidated for re-fetch with profile_id')
        except Exception as e :
            _log (f'ensure_profile_id error: {e }')

    def get_profile_id (self ,access_token =None ):
        if self ._tokens .get ('profile_id'):
            return self ._tokens ['profile_id']

        import base64 as _b64 ,json as _json ,requests
        bedrock_cached =self ._tokens .get ('bedrock_token','')
        if bedrock_cached :
            try :
                payload =bedrock_cached .split ('.')[1 ]
                payload +='='*(4 -len (payload )%4 )
                data =_json .loads (_b64 .b64decode (payload ))
                pid =data .get ('profileid','')or data .get ('profileId','')
                if pid :
                    self ._tokens ['profile_id']=pid
                    self ._save_tokens ()
                    _log (f'get_profile_id: aus bedrock-JWT: {pid }')
                    return pid
            except Exception as e :
                _log (f'get_profile_id JWT-Decode Fehler: {e }')

        gigya_uid =self .get_gigya_uid ()
        if not gigya_uid :
            return ''

        if not access_token :
            access_token =self .get_oidc_token ()

        try :
            bedrock =self .get_bedrock_token ()
            resp =requests .get (
            f'https://users.rtlde.bedrock.tech/v2/platforms/m6group_web/users/{gigya_uid }/profiles',
            headers ={
            'Authorization':f'Bearer {access_token }',
            'x-bedrock-token':bedrock or '',
            'User-Agent':USER_AGENT ,
            'Origin':'https://plus.rtl.de',
            'Referer':'https://plus.rtl.de/',
            },
            timeout =10
            )
            profiles =resp .json ()
            if profiles :
                self ._tokens ['profile_id']=profiles [0 ].get ('uid','')
                self ._save_tokens ()
                return self ._tokens ['profile_id']
        except Exception as e :
            _log (f'Profile error: {e }')
        return ''

    def _drm_headers (self ,auth_token ,bedrock_token ):
        return {
        'Authorization':f'Bearer {auth_token }',
        'x-bedrock-token':bedrock_token or '',
        'x-client-release':CLIENT_RELEASE ,
        'x-customer-name':'rtlde',
        'request-timeout':'10000',
        'User-Agent':USER_AGENT ,
        'Origin':'https://plus.rtl.de',
        'Referer':'https://plus.rtl.de/',
        'Accept':'*/*',
        }

    def _drm_url (self ,service_code ,user_id ,content_type ,content_id ):
        segment ='videos'if content_type =='video'else 'live'
        return (f'https://drm.rtlde.bedrock.tech/v1/customers/rtlde/platforms/m6group_web'
        f'/services/{service_code }/users/{user_id }/{segment }/{content_id }/upfront-token')

    def get_drm_token (self ,service_code ,content_type ,content_id ):
        import requests
        import time as _time

        if not hasattr (self ,'_drm_cache'):
            self ._drm_cache ={}
        cache_key =(service_code ,content_type ,content_id )
        cached =self ._drm_cache .get (cache_key )
        if cached :
            token ,expires =cached
            if _time .time ()<expires :
                _log (f'get_drm_token: Cache-Hit fuer {cache_key }')
                return token
            else :
                del self ._drm_cache [cache_key ]

        if content_type =='live':
            self .ensure_profile_id ()
        access_token =self .get_oidc_token ()
        bedrock_token =self .get_bedrock_token ()or self .get_guest_bedrock_token ()
        gigya_uid =self .get_gigya_uid ()
        _log (f'get_drm_token: gigya_uid={gigya_uid } bedrock={"OK" if bedrock_token else "LEER"}')

        if not gigya_uid :
            anon_oidc =self ._get_anonymous_oidc_token ()
            if not anon_oidc or not bedrock_token :
                _log ('get_drm_token: kein anonymer Token - DRM nicht moeglich')
                return None
            device_id =self .get_device_id ()
            anon_user_id =f'deviceid-{device_id }'
            url =self ._drm_url (service_code ,anon_user_id ,content_type ,content_id )
            try :
                resp =requests .get (url ,headers =self ._drm_headers (anon_oidc ,bedrock_token ),timeout =15 )
                _log (f'get_drm_token (Gast): HTTP {resp .status_code } user={anon_user_id }')
                resp .raise_for_status ()
                data =resp .json ()
                token =data .get ('token','')
                if token :
                    _log ('get_drm_token (Gast): Token OK')
                    self ._drm_cache [cache_key ]=(token ,_time .time ()+30 )
                    return token
                _log (f'get_drm_token (Gast): leere Antwort: {data }')
            except Exception as e :
                _log (f'get_drm_token (Gast) error: {e }')
            return None

        url =self ._drm_url (service_code ,gigya_uid ,content_type ,content_id )
        try :
            resp =requests .get (url ,headers =self ._drm_headers (access_token ,bedrock_token ),timeout =15 )
            resp .raise_for_status ()
            data =resp .json ()
            token =data .get ('token','')
            if token :
                self ._drm_cache [cache_key ]=(token ,_time .time ()+30 )
            return token
        except Exception as e :
            _log (f'DRM token error: {e }')
            return None

    def get_subscription_tier (self ):
        import requests
        import time as _time

        cached =self ._tokens .get ('_subscription_tier')
        cached_ts =self ._tokens .get ('_premium_status_ts',0 )
        if cached is not None and (_time .time ()-cached_ts )<21600 :
            return cached

        access_token =self .get_oidc_token ()
        gigya_uid =self .get_gigya_uid ()
        if not access_token or not gigya_uid :
            _log ('get_subscription_tier: kein OIDC/Gigya – abbruch')
            if cached is not None :
                return cached
            return 'Gast'

        bedrock_token =self .get_bedrock_token ()
        if not bedrock_token :
            _log ('get_subscription_tier: kein Bedrock-Token – abbruch')
            if cached is not None :
                return cached
            return 'Free'

        url =(f'https://stores.rtlde.bedrock.tech/premium/v4/customers/rtlde'
        f'/platforms/m6group_web/users/{gigya_uid }/subscriptions')
        headers ={
        'Authorization':f'Bearer {access_token }',
        'x-bedrock-token':bedrock_token ,
        'x-client-release':CLIENT_RELEASE ,
        'x-customer-name':'rtlde',
        'User-Agent':USER_AGENT ,
        'Origin':'https://plus.rtl.de',
        'Referer':'https://plus.rtl.de/',
        }
        try :
            resp =requests .get (url ,headers =headers ,timeout =10 )
            resp .raise_for_status ()
            if resp .status_code ==204 or not resp .content :
                _log ('get_subscription_tier: HTTP 204 – kein Body')
                return cached if cached is not None else 'Free'
            data =resp .json ()
            tier ='Gast'
            offer_code =''
            for sub in (data .get ('current',[])or []):
                offer_code =(sub .get ('offer',{})or {}).get ('code','')
                _log (f'get_subscription_tier: offer_code={offer_code !r}')
                if offer_code .startswith ('PM'):
                    tier ='Premium'
                    break
                if offer_code .startswith ('BA'):
                    tier ='Basic'
                    break
                if offer_code .startswith ('FR'):
                    tier ='Free'
                    break
                if offer_code :
                    tier ='Premium+'
                    break
            self ._tokens ['_subscription_tier']=tier
            self ._tokens ['_premium_status_ts']=_time .time ()
            self ._save_tokens ()
            _log (f'get_subscription_tier={tier } (offer={offer_code })')
            return tier
        except Exception as e :
            _log (f'get_subscription_tier error: {e }')
            if cached is not None :
                _log (f'get_subscription_tier: Fehler, nutze gecachten Wert: {cached }')
                return cached
            return 'Gast'

    def is_premium (self ):
        return self .get_subscription_tier () in ('Premium','Basic','Premium+')

    def guest_login (self ):
        import time as _t
        if bool (self ._tokens .get ('access_token','')):
            _log ('guest_login: echter User-Login aktiv – guest_login wird übersprungen')
            return
        existing =self ._guest_tokens .get ('guest_bedrock_token','')
        exp =self ._guest_tokens .get ('guest_bedrock_expires',0 )
        if existing and exp >_t .time ()+300 :
            _log ('guest_login: Gast-Token noch gültig')
            return
        self ._guest_tokens ={'is_guest':True }
        self ._save_guest_tokens ()
        _log ('guest_login: hole frischen Gast-Token...')
        self .get_guest_bedrock_token ()
        _log ('guest_login: abgeschlossen')

    _ANON_CLIENT_ID ='anonymous-user'
    _ANON_CLIENT_SECRET ='4bfeb73f-1c4a-4e9f-a7fa-96aa1ad3d94c'
    _ANON_OIDC_URL ='https://auth.rtl.de/auth/realms/rtlplus/protocol/openid-connect/token'

    def _get_anonymous_oidc_token (self ):
        import requests as _r
        cached =self ._guest_tokens .get ('anon_oidc_token','')
        exp =self ._guest_tokens .get ('anon_oidc_expires',0 )
        if cached and exp >time .time ()+300 :
            return cached
        try :
            resp =_r .post (
                self ._ANON_OIDC_URL ,
                data ={
                    'client_id':self ._ANON_CLIENT_ID ,
                    'client_secret':self ._ANON_CLIENT_SECRET ,
                    'grant_type':'client_credentials',
                },
                headers ={
                    'User-Agent':USER_AGENT ,
                    'Origin':'https://plus.rtl.de',
                    'Referer':'https://plus.rtl.de/',
                    'Accept':'*/*',
                    'Content-Type':'application/x-www-form-urlencoded',
                },
                timeout =15
            )
            resp .raise_for_status ()
            data =resp .json ()
            token =data .get ('access_token','')
            expires_in =data .get ('expires_in',86400 )
            if token :
                self ._guest_tokens ['anon_oidc_token']=token
                self ._guest_tokens ['anon_oidc_expires']=time .time ()+expires_in
                self ._save_guest_tokens ()
                _log ('Anonymer OIDC-Token OK')
            return token
        except Exception as e :
            _log (f'Anonymer OIDC-Token Fehler: {e }')
        return cached or ''

    def get_guest_bedrock_token (self ):
        import time as _t
        import requests as _requests
        now =_t .time ()
        cached =self ._guest_tokens .get ('guest_bedrock_token','')
        exp =self ._guest_tokens .get ('guest_bedrock_expires',0 )
        if cached and exp >now +300 :
            return cached
        _log ('get_guest_bedrock_token: hole frischen anonymen Bedrock-Token...')
        anon_oidc =self ._get_anonymous_oidc_token ()
        if not anon_oidc :
            _log ('get_guest_bedrock_token: kein anonymer OIDC-Token')
            return cached or None
        try :
            device_id =self .get_device_id ()
            ts =int (now )
            auth_token =hmac .new (b'',str (ts ).encode (),hashlib .sha1 ).hexdigest ()
            headers ={
                'Authorization':f'Bearer {anon_oidc }',
                'x-auth-device-name':'Android - Samsung Internet',
                'x-auth-gigya-uid':'',
                'x-auth-token-timestamp':str (ts ),
                'x-auth-token':auth_token ,
                'x-auth-profile-id':'',
                'x-auth-device-id':device_id ,
                'x-auth-device-player-size-width':'384',
                'x-auth-device-player-size-height':'682',
                'x-client-release':CLIENT_RELEASE ,
                'x-customer-name':'rtlde',
                'request-timeout':'10000',
                'User-Agent':USER_AGENT ,
                'Origin':'https://plus.rtl.de',
                'Referer':'https://plus.rtl.de/',
                'Accept':'*/*',
            }
            resp =_requests .get (FRONT_AUTH_URL ,headers =headers ,timeout =15 )
            resp .raise_for_status ()
            data =resp .json ()
            bedrock =data .get ('token','')
            if bedrock :
                self ._guest_tokens ['guest_bedrock_token']=bedrock
                self ._guest_tokens ['guest_bedrock_expires']=now +86000
                self ._save_guest_tokens ()
                _log ('get_guest_bedrock_token: anonymer Bedrock-Token OK')
                return bedrock
            _log (f'get_guest_bedrock_token: leere Antwort: {data }')
        except Exception as e :
            _log (f'get_guest_bedrock_token Fehler: {e }')
        return cached or None

def _get_device_key ():
    import base64

    try :
        import xbmcdrm
        wv =xbmcdrm .CryptoSession (
        'edef8ba9-79d6-4ace-a3c8-27dcd51d21ed',
        'AES/CBC/NoPadding'
        )
        wv_id =wv .GetPropertyByteArray ('deviceUniqueId')
        if wv_id :
            wv_str =base64 .b64encode (bytes (wv_id )).decode ()

            return hashlib .sha256 (('wv:'+wv_str ).encode ('utf-8')).digest ()
    except Exception as e :
        _log (f'Device key: Fehlgeschlagen: {e }')

    try :
        import subprocess
        out =subprocess .check_output (
        ['settings','get','secure','android_id'],timeout =2
        ).decode ().strip ()
        if out and out !='null':
            _log ('Device key: Android ID OK')
            return hashlib .sha256 (('aid:'+out ).encode ('utf-8')).digest ()
    except Exception :
        pass

    try :
        import subprocess
        out =subprocess .check_output (
        ['getprop','ro.serialno'],timeout =2
        ).decode ().strip ()
        if out and out not in ('','unknown'):
            _log ('Device key: Serial OK')
            return hashlib .sha256 (('sn:'+out ).encode ('utf-8')).digest ()
    except Exception :
        pass

    try :
        import socket
        host =socket .gethostname ()
        _log ('Device key: Hostname Fallback')
        return hashlib .sha256 (('host:'+host ).encode ('utf-8')).digest ()
    except Exception :
        pass

    _log ('Device key: KEIN Identifier gefunden – statischer Notfall-Key')
    return hashlib .sha256 (b'rtlplus-static-fallback').digest ()

def _encrypt_tokens (data :str )->str :
    import os as _os
    key =_get_device_key ()
    raw =data .encode ('utf-8')

    pad =16 -len (raw )%16
    raw +=bytes ([pad ]*pad )
    iv =_os .urandom (16 )
    try :
        from cryptography .hazmat .primitives .ciphers import Cipher ,algorithms ,modes
        from cryptography .hazmat .backends import default_backend
        c =Cipher (algorithms .AES (key ),modes .CBC (iv ),backend =default_backend ())
        enc =c .encryptor ()
        ct =enc .update (raw )+enc .finalize ()
    except ImportError :

        ct =b''
        prev =iv
        for i in range (0 ,len (raw ),16 ):
            blk =bytes (a ^b for a ,b in zip (raw [i :i +16 ],prev ))
            ks =hashlib .sha256 (key +prev ).digest ()[:16 ]
            blk =bytes (a ^b for a ,b in zip (blk ,ks ))
            ct +=blk
            prev =blk
    import base64
    return base64 .b64encode (iv +ct ).decode ()

def _decrypt_tokens (data :str )->str :
    import base64
    key =_get_device_key ()
    raw =base64 .b64decode (data )
    iv ,ct =raw [:16 ],raw [16 :]
    try :
        from cryptography .hazmat .primitives .ciphers import Cipher ,algorithms ,modes
        from cryptography .hazmat .backends import default_backend
        c =Cipher (algorithms .AES (key ),modes .CBC (iv ),backend =default_backend ())
        dec =c .decryptor ()
        pt =dec .update (ct )+dec .finalize ()
    except ImportError :
        pt =b''
        prev =iv
        for i in range (0 ,len (ct ),16 ):
            blk =ct [i :i +16 ]
            ks =hashlib .sha256 (key +prev ).digest ()[:16 ]
            dec_blk =bytes (a ^b for a ,b in zip (blk ,ks ))
            pt +=bytes (a ^b for a ,b in zip (dec_blk ,prev ))
            prev =blk
    pad =pt [-1 ]
    if pad <1 or pad >16 :
        raise ValueError ('Ungültiges Padding – falsches Gerät')
    return pt [:-pad ].decode ('utf-8')
