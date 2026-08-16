import time
import xbmc

from .auth import RTLAuth ,USER_AGENT ,CLIENT_RELEASE

LAYOUT_BASE ='https://layout.rtlde.bedrock.tech/front/v1/rtlde/m6group_web/main/token-web-31'
RTL_WEB ='https://plus.rtl.de'

def _log (msg ):
    xbmc .log (f'[RTL+ API] {msg }',xbmc .LOGDEBUG )

class BedrockAPI :
    def __init__ (self ):
        self .auth =RTLAuth ()
        self ._session =None

    def _get_session (self ):

        import requests
        return requests .Session ()

    def _headers (self ,x_location =None ,prefer_guest =False ):
        access_token =self .auth .get_oidc_token ()
        if prefer_guest :
            bedrock_token =self .auth .get_guest_bedrock_token ()or self .auth .get_bedrock_token ()
            label ='_headers_guest'
        else :
            bedrock_token =self .auth .get_bedrock_token ()or self .auth .get_guest_bedrock_token ()
            label ='_headers'
        if bedrock_token :
            try :
                import base64 as _b64 ,json as _json
                _p =bedrock_token .split ('.')[1 ]+'=='
                _d =_json .loads (_b64 .b64decode (_p ))
                _log (f'{label }: bedrock profileid={_d .get ("profileid","LEER")!r} gigya={_d .get ("gigya","LEER")!r}')
            except Exception as _e :
                _log (f'{label }: bedrock decode Fehler {_e }')
        h ={
        'User-Agent':USER_AGENT ,
        'Accept':'*/*',
        'Origin':RTL_WEB ,
        'Referer':RTL_WEB +'/',
        'x-client-release':CLIENT_RELEASE ,
        'x-customer-name':'rtlde',
        'request-timeout':'10000',
        }
        if access_token :
            h ['Authorization']=f'Bearer {access_token }'
        if bedrock_token :
            h ['x-bedrock-token']=bedrock_token
        if x_location :
            h ['x-location']=x_location
        return h

    def _headers_guest (self ,x_location =None ):
        return self ._headers (x_location =x_location ,prefer_guest =True )

    def _get (self ,path ,params =None ,x_location =None ,_retry =True ,prefer_guest =False ):
        import requests
        url =LAYOUT_BASE +path
        label ='GET (guest-bedrock)'if prefer_guest else 'GET'
        _log (f'{label } {url } xloc={x_location }')
        try :
            resp =self ._get_session ().get (
            url ,headers =self ._headers (x_location =x_location ,prefer_guest =prefer_guest ),params =params ,timeout =20
            )
            _log (f'HTTP {resp .status_code } for {path }')
            if resp .status_code in (401 ,403 )and _retry :
                _log (f'Token rejected (401/403) prefer_guest={prefer_guest } - erneuere Tokens und retry')
                self .auth .invalidate_tokens ()
                self .auth .get_oidc_token ()
                if prefer_guest :
                    self .auth ._guest_tokens .pop ('guest_bedrock_token',None )
                    self .auth ._guest_tokens .pop ('guest_bedrock_expires',None )
                    self .auth ._save_guest_tokens ()
                    self .auth .get_guest_bedrock_token ()
                else :
                    self .auth .get_bedrock_token ()
                import xbmc as _xbmc ;_xbmc .sleep (500 )
                return self ._get (path ,params =params ,x_location =x_location ,_retry =False ,prefer_guest =prefer_guest )
            if resp .status_code ==498 and _retry :
                _log (f'Token missing (498) prefer_guest={prefer_guest } - erneuere anonymen Bedrock')
                self .auth ._guest_tokens .pop ('guest_bedrock_token',None )
                self .auth ._guest_tokens .pop ('guest_bedrock_expires',None )
                self .auth ._save_guest_tokens ()
                self .auth .get_guest_bedrock_token ()
                import xbmc as _xbmc ;_xbmc .sleep (300 )
                return self ._get (path ,params =params ,x_location =x_location ,_retry =False ,prefer_guest =prefer_guest )
            if resp .status_code ==404 :
                _log (f'HTTP 404 – Inhalt nicht vorhanden: {path }')
                return {'_error':'not_found','_status':404 }
            if resp .status_code ==451 :
                _log (f'HTTP 451 – Geo-Sperre: {path }')
                return {'_error':'geo_blocked','_status':451 }
            resp .raise_for_status ()
            return resp .json ()
        except Exception as e :
            _log (f'Error ({type (e ).__name__ }): {e }')
            return None

    def _get_guest (self ,path ,params =None ,x_location =None ,_retry =True ):
        return self ._get (path ,params =params ,x_location =x_location ,_retry =_retry ,prefer_guest =True )

    def get_folder_guest (self ,folder_id ,page =1 ,nb_pages =3 ):
        xloc =f'{RTL_WEB }/rtlplus-root/kostenlose-inhalte-main-root-service-f_{folder_id }'
        _log (f'get_folder_guest folder_id={folder_id }')
        return self ._get_guest (f'/folder/{folder_id }/layout',{'blockPage':page ,'nbPages':nb_pages },x_location =xloc )

    def get_navigation (self ):
        return self ._get ('/navigation/desktop')

    def get_alias (self ,alias ,page =1 ,nb_pages =2 ):
        xloc =f'{RTL_WEB }/'if alias =='home'else f'{RTL_WEB }/{alias }'
        return self ._get (f'/alias/{alias }/layout',{'blockPage':page ,'nbPages':nb_pages },x_location =xloc )

    def get_folder (self ,folder_id ,seo ='',page =1 ,nb_pages =2 ):
        xloc =f'{RTL_WEB }/{seo }-f_{folder_id }'if seo else f'{RTL_WEB }/folder/{folder_id }'
        return self ._get (f'/folder/{folder_id }/layout',{'blockPage':page ,'nbPages':nb_pages },x_location =xloc )

    def get_frontspace (self ,name ,page =1 ,nb_pages =2 ):
        if name =='bookmarks':
            self .auth .ensure_profile_id ()
        xloc_map ={
        'bookmarks':f'{RTL_WEB }/meine-inhalte',
        'home':f'{RTL_WEB }/',
        }
        xloc =xloc_map .get (name ,f'{RTL_WEB }/{name }')
        return self ._get (f'/frontspace/{name }/layout',{'blockPage':page ,'nbPages':nb_pages },x_location =xloc )

    def get_service (self ,name ,page =1 ,nb_pages =2 ):
        return self ._get (f'/service/{name }/layout',{'blockPage':page ,'nbPages':nb_pages })

    def get_service_guest (self ,name ,page =1 ,nb_pages =2 ):
        return self ._get_guest (f'/service/{name }/layout',{'blockPage':page ,'nbPages':nb_pages })

    def get_program_layout (self ,program_id ,seo ='',page =1 ,nb_pages =2 ):
        xloc =f'{RTL_WEB }/{seo }-p_{program_id }'if seo else f'{RTL_WEB }/program/{program_id }'
        return self ._get (f'/program/{program_id }/layout',{'blockPage':page ,'nbPages':nb_pages },x_location =xloc )

    def get_video_layout (self ,video_id ,program_seo ='',program_id ='',video_seo ='',page =1 ,nb_pages =2 ):
        clip_num =video_id .replace ('clip_','')if video_id .startswith ('clip_')else video_id
        if program_seo and program_id and video_seo :
            xloc =f'{RTL_WEB }/{program_seo }-p_{program_id }/video/{video_seo }-c_{clip_num }'
        else :
            xloc =f'{RTL_WEB }/video/{video_id }'
        return self ._get (f'/video/{video_id }/layout',{'blockPage':page ,'nbPages':nb_pages },x_location =xloc )

    def get_audio_layout (self ,audio_id ,page =1 ,nb_pages =2 ):
        return self ._get (f'/audio/{audio_id }/layout',{'blockPage':page ,'nbPages':nb_pages })

    def get_radio_layout (self ,radio_id ,page =1 ,nb_pages =2 ):
        return self ._get (f'/radio/{radio_id }/layout',{'blockPage':page ,'nbPages':nb_pages })

    def get_live_layout (self ,channel_slug ,page =1 ,nb_pages =2 ):
        if channel_slug .startswith ('fast'):
            xloc =f'{RTL_WEB }/{channel_slug }/live'
        else :
            xloc =f'{RTL_WEB }/live/{channel_slug }'
        return self ._get (f'/live/{channel_slug }/layout',{'blockPage':page ,'nbPages':nb_pages },x_location =xloc )

    def get_epg_modal (self ,modal_id ):
        return self ._get (f'/epg_grid/{modal_id}/modal')

    def get_epg_grid (self ,day =None ,nb_pages =5 ):
        if not day :
            day =time .strftime ('%Y-%m-%d')
        return self ._get ('/epg_grid',{'day':day ,'nbPages':nb_pages })

    def get_block_page (self ,folder_id ,block_id ,page =2 ,nb_pages =3 ):
        return self ._get (f'/folder/{folder_id }/block/{block_id }',{'page':page ,'nbPages':nb_pages })

    def get_program_block (self ,program_id ,block_id ,page =1 ,nb_pages =3 ,seo =''):
        xloc =f'{RTL_WEB }/{seo }-p_{program_id }'if seo else f'{RTL_WEB }/program/{program_id }'
        return self ._get (f'/program/{program_id }/block/{block_id }',{'page':page ,'nbPages':nb_pages },x_location =xloc )

    def toggle_bookmark (self ,program_id ,subscribed =True ):
        import requests
        try :
            access_token =self .auth .get_oidc_token ()
            bedrock_token =self .auth .get_bedrock_token ()
            if not access_token :
                _log ('toggle_bookmark: kein Access-Token')
                return False
            url ='https://users.rtlde.bedrock.tech/v4/rtlde/m6group_web/bookmark'
            headers ={
            'Authorization':f'Bearer {access_token }',
            'User-Agent':USER_AGENT ,
            'x-client-release':CLIENT_RELEASE ,
            'x-customer-name':'rtlde',
            'Origin':RTL_WEB ,
            'Referer':RTL_WEB +'/',
            'Content-Type':'application/json',
            'request-timeout':'10000',
            }
            if bedrock_token :
                headers ['x-bedrock-token']=bedrock_token
            body ={'entityId':str (program_id ),'entityType':'program','subscribed':subscribed }
            resp =requests .put (url ,headers =headers ,json =body ,timeout =10 )
            _log (f'toggle_bookmark program={program_id } subscribed={subscribed } status={resp .status_code }')
            return resp .status_code in (200 ,201 ,204 )
        except Exception as e :
            _log (f'toggle_bookmark error: {e }')
            return False
    def get_video_assets (self ,video_id ,**kwargs ):
        data =self .get_video_layout (video_id ,**kwargs )
        if not data :
            return []
        if isinstance (data ,dict )and '_error'in data :
            return data
        return self ._extract_assets (data )

    def get_audio_assets (self ,audio_id ):
        data =self .get_audio_layout (audio_id )
        if not data :
            return []
        return self ._extract_audio_assets (data )

    def get_live_assets (self ,channel_slug ):
        data =self .get_live_layout (channel_slug )
        if not data :
            return []
        return self ._extract_assets (data )

    def get_radio_assets (self ,radio_id ):
        data =self .get_radio_layout (radio_id )
        if not data :
            data =self .get_live_layout (radio_id )
        if not data :
            return []
        assets =self ._extract_audio_assets (data )
        if not assets :
            assets =self ._extract_assets (data )
        return assets

    def _extract_title (self ,layout_data ):
        for block in layout_data .get ('blocks',[]):
            for item in block .get ('content',{}).get ('items',[]):
                ic =item .get ('itemContent',{})
                title_raw =ic .get ('title','')or ''
                extra_title =ic .get ('extraTitle','')or ''
                if extra_title :
                    return extra_title
                if title_raw :
                    return title_raw
        return ''

    def _extract_assets (self ,layout_data ):
        assets =[]
        for block in layout_data .get ('blocks',[]):
            for item in block .get ('content',{}).get ('items',[]):
                video =item .get ('itemContent',{}).get ('video',{})
                if video and 'assets'in video :
                    for a in video ['assets']:
                        fmt =a .get ('format','')
                        path =a .get ('path','')or a .get ('reference','')
                        if fmt in ('dashcenc','dash')and path :
                            assets .append ({
                            'path':path ,
                            'format':fmt ,
                            'quality':a .get ('quality','sd'),
                            'video_quality':a .get ('video_quality',''),
                            'drm_config':a .get ('drm',{}).get ('config',{}),
                            'drm_type':a .get ('drm',{}).get ('type','software'),
                            })
        return assets

    def _extract_audio_assets (self ,layout_data ):
        assets =[]
        for block in layout_data .get ('blocks',[]):
            for item in block .get ('content',{}).get ('items',[]):
                video =item .get ('itemContent',{}).get ('video',{})
                if video and 'assets'in video :
                    for a in video ['assets']:
                        fmt =a .get ('format','')
                        path =a .get ('path','')or a .get ('reference','')
                        if fmt in ('mp3','aac','hls','passthrough_mp3_mpeg','m3u8')and path :

                            assets .append ({
                            'path':path ,
                            'format':fmt ,
                            'quality':a .get ('quality','sd'),
                            'drm_config':{},
                            'drm_type':'none',
                            })
                        elif fmt not in ('dashcenc','dash','')and path :

                            assets .append ({
                            'path':path ,
                            'format':fmt ,
                            'quality':a .get ('quality','sd'),
                            'drm_config':a .get ('drm',{}).get ('config',{}),
                            'drm_type':a .get ('drm',{}).get ('type','none'),
                            })
        return assets
