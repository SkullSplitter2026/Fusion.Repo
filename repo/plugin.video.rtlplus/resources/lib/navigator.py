import os
import urllib .parse
import hashlib
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

from .api import BedrockAPI

IMAGE_CDN ='https://images-fio.rtlde.bedrock.tech'

_IMAGE_KEY ='x9vGg4RNeNBqV2nBfhqLV6cN4n'

def _sign_image (path_and_query :str )->str :
    return hashlib .sha1 ((path_and_query +_IMAGE_KEY ).encode ()).hexdigest ()

CHANNEL_IMAGES ={
'rtl':'channel/rtl.png',
'vox':'channel/vox.png',
'rtlzwei':'channel/rtl2.png',
'rtl2':'channel/rtl2.png',
'nitro':'channel/nitro.png',
'ntv':'channel/ntv.png',
'rtlup':'channel/rtlup.png',
'rtlplus':'channel/rtlplus.png',
'voxup':'channel/voxup.png',
'super_rtl':'channel/superrtl.png',
'superrtl':'channel/superrtl.png',
'toggo_plus':'channel/toggoplus.png',
'toggoplus':'channel/toggoplus.png',
'now':'channel/tvnow.png',
'tvnow':'channel/tvnow.png',
'tvnowkids':'channel/tvnowkids.png',
'geo':'channel/geo.png',
'crime':'channel/crime.png',
'living':'channel/living.png',
'passion':'channel/passion.png',
'nowus':'channel/nowus.png',
'watchbox':'channel/watchbox.png',
}

def _log (msg ):
    xbmc .log (f'[RTL+ Nav] {msg }',xbmc .LOGDEBUG )

_PREMIUM_STATUS_CACHE = {}

def _get_premium_status ():
    import time as _time
    cached = _PREMIUM_STATUS_CACHE.get('result')
    cached_ts = _PREMIUM_STATUS_CACHE.get('ts', 0)
    if cached is not None and (_time.time() - cached_ts) < 21600:
        return cached
    try:
        from .auth import RTLAuth
        result = RTLAuth().get_subscription_tier()
    except Exception:
        result = 'Free'
    _PREMIUM_STATUS_CACHE['result'] = result
    _PREMIUM_STATUS_CACHE['ts'] = _time.time()
    return result

def _premium_title (title ):
    return f'[COLOR gold]{title} (Premium)[/COLOR]'

def _quality_label ():
    try :
        idx =int (xbmcaddon .Addon ().getSetting ('quality_max')or '0')
        return ('1080p','720p','576p','360p')[idx ]if 0 <=idx <=3 else ''
    except Exception :
        return ''

def _prefer_clip_for_quality ():
    """True wenn Qualitaetseinstellung clip_id (1080p-Bedrock) gegenueber rrn bevorzugen soll."""
    try :
        addon =xbmcaddon .Addon ()
        pref =int (addon .getSetting ('quality_preferred')or '0')
        max_q =int (addon .getSetting ('quality_max')or '0')
        return pref ==1 or max_q ==0
    except Exception :
        return False

def _clean_title (title ):
    import re as _re
    title = _re.sub(r'\s*(Main Root Service|Root Service|Main Service|Main Root)\b', '', title, flags=_re.IGNORECASE)
    return title.strip()

def _image_url (image_data ,width =320 ,height =180 ,preferred_ratio ='16:9'):
    if not image_data :
        return ''
    if isinstance (image_data ,str ):
        img_id =image_data
    elif isinstance (image_data ,dict ):
        ids_by_ratio =image_data .get ('idsByRatio',{})or {}
        img_id =(ids_by_ratio .get (preferred_ratio ,'')
        or ids_by_ratio .get ('16:9','')
        or ids_by_ratio .get ('2:3','')
        or next (iter (ids_by_ratio .values ()),'')
        or image_data .get ('id',''))
    else :
        return ''
    if not img_id :
        return ''

    params =(f'auto=avif&blur=0&fit=max'
    f'&height={height }&interlace=1&quality=100&width={width }')
    path_and_query =f'/v2/images/{img_id }/raw?{params }'
    sig =_sign_image (path_and_query )

    headers =urllib .parse .urlencode ({
    'Referer':'https://plus.rtl.de/',
    'User-Agent':'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/29.0 Chrome/136.0.0.0 Mobile Safari/537.36',
    })
    return f'{IMAGE_CDN }{path_and_query }&hash={sig }|{headers }'

class Navigator :
    def __init__ (self ,handle ,base_url ):
        self .handle =handle
        self .base_url =base_url
        self .api =BedrockAPI ()

    def _img (self ,fname ):
        import os ,xbmcaddon ,xbmcvfs
        _addon =xbmcaddon .Addon ()
        _addon_path =xbmcvfs .translatePath (_addon .getAddonInfo ('path'))
        return os .path .join (_addon_path ,'resources','media',fname )

    def build_url (self ,params ):
        return self .base_url +'?'+urllib .parse .urlencode (params )

    def _vod_url (self ,video_id ,meta ):
        from .evil import vod_meta as _vod_meta
        _vod_meta .save (video_id ,meta )
        return self .build_url ({'mode':'play_vod','video_id':video_id })

    def _add_sort_methods (self ):
        _sm =xbmcplugin .addSortMethod
        _h =self .handle
        _sm (_h ,xbmcplugin .SORT_METHOD_NONE )
        _sm (_h ,xbmcplugin .SORT_METHOD_LABEL )
        _sm (_h ,xbmcplugin .SORT_METHOD_LABEL_IGNORE_THE )
        _sm (_h ,xbmcplugin .SORT_METHOD_VIDEO_TITLE )
        _sm (_h ,xbmcplugin .SORT_METHOD_VIDEO_YEAR )
        _sm (_h ,xbmcplugin .SORT_METHOD_VIDEO_RATING )
        _sm (_h ,xbmcplugin .SORT_METHOD_VIDEO_RUNTIME )
        _sm (_h ,xbmcplugin .SORT_METHOD_DURATION )
        _sm (_h ,xbmcplugin .SORT_METHOD_GENRE )
        _sm (_h ,xbmcplugin .SORT_METHOD_DATE )
        _sm (_h ,xbmcplugin .SORT_METHOD_DATEADDED )
        _sm (_h ,xbmcplugin .SORT_METHOD_LASTPLAYED )
        _sm (_h ,xbmcplugin .SORT_METHOD_PLAYCOUNT )
        _sm (_h ,xbmcplugin .SORT_METHOD_VIDEO_USER_RATING )
        _sm (_h ,xbmcplugin .SORT_METHOD_MPAA_RATING )
        _sm (_h ,xbmcplugin .SORT_METHOD_PRODUCTIONCODE )

    def _add_sort_methods_episode (self ):
        _sm =xbmcplugin .addSortMethod
        _h =self .handle
        _sm (_h ,xbmcplugin .SORT_METHOD_EPISODE )
        _sm (_h ,xbmcplugin .SORT_METHOD_NONE )
        _sm (_h ,xbmcplugin .SORT_METHOD_LABEL )
        _sm (_h ,xbmcplugin .SORT_METHOD_LABEL_IGNORE_THE )
        _sm (_h ,xbmcplugin .SORT_METHOD_VIDEO_TITLE )
        _sm (_h ,xbmcplugin .SORT_METHOD_VIDEO_YEAR )
        _sm (_h ,xbmcplugin .SORT_METHOD_VIDEO_RATING )
        _sm (_h ,xbmcplugin .SORT_METHOD_VIDEO_RUNTIME )
        _sm (_h ,xbmcplugin .SORT_METHOD_DURATION )
        _sm (_h ,xbmcplugin .SORT_METHOD_GENRE )
        _sm (_h ,xbmcplugin .SORT_METHOD_DATE )
        _sm (_h ,xbmcplugin .SORT_METHOD_DATEADDED )
        _sm (_h ,xbmcplugin .SORT_METHOD_LASTPLAYED )
        _sm (_h ,xbmcplugin .SORT_METHOD_PLAYCOUNT )
        _sm (_h ,xbmcplugin .SORT_METHOD_VIDEO_USER_RATING )
        _sm (_h ,xbmcplugin .SORT_METHOD_MPAA_RATING )
        _sm (_h ,xbmcplugin .SORT_METHOD_PRODUCTIONCODE )


    def show_main_menu (self ):
        import os
        import xbmcaddon
        import xbmcvfs
        _addon =xbmcaddon .Addon ()
        _addon_path =xbmcvfs .translatePath (_addon .getAddonInfo ('path'))
        _profile =xbmcvfs .translatePath (_addon .getAddonInfo ('profile'))
        _token_file =os .path .join (_profile ,'tokens.json')
        _logged_in =os .path .exists (_token_file )and _addon .getSetting ('username')!=''

        if _logged_in :

            reality_id ='1'
            kids_id ='148'
            anime_id ='165'
            try :
                nav_data =self .api .get_navigation ()
                if nav_data :
                    def _find_folder (obj ,keywords ):
                        if isinstance (obj ,dict ):
                            label =str (obj .get ('label','')or obj .get ('title','')or '').lower ()
                            vl =obj .get ('value_layout',{})or {}
                            if any (k in label for k in keywords )and vl .get ('type')=='folder':
                                return str (vl .get ('id',''))
                            for v in obj .values ():
                                r =_find_folder (v ,keywords )
                                if r :return r
                        elif isinstance (obj ,list ):
                            for v in obj :
                                r =_find_folder (v ,keywords )
                                if r :return r
                        return ''
                    reality_id =_find_folder (nav_data ,['reality','dating','show'])or reality_id
                    anime_id =_find_folder (nav_data ,['anime'])or anime_id
                    kids_id =_find_folder (nav_data ,['kids','kinder','toggo'])or kids_id
            except Exception :
                pass

            _account_type = _get_premium_status()
            _mein_label = f'Mein {_account_type} RTL+'

            items =[

            (_mein_label,{'mode':'show_meine_inhalte'},self._img ('favourites.png')),

            ('Startseite',{'mode':'show_alias','alias':'home'},self._img ('icon.png')),
            *([ ('Live-TV',{'mode':'show_live'},self._img ('icon.png')) ] if _account_type in ('Premium','Basic') else []),
            ('Filme',{'mode':'show_folder','folder_id':'4'},self._img ('icon.png')),
            ('Filme A-Z',{'mode':'show_jw_az','obj_type':'MOVIE','page':'1'},self._img ('icon.png')),
            ('Serien',{'mode':'show_folder','folder_id':'3'},self._img ('icon.png')),
            ('Serien A-Z',{'mode':'show_jw_az','obj_type':'SHOW','page':'1'},self._img ('icon.png')),
            ('Shows',{'mode':'show_folder','folder_id':'2','seo':'shows-rtl'},self._img ('icon.png')),
            ('Reality',{'mode':'show_folder','folder_id':reality_id },self._img ('icon.png')),
            ('Anime',{'mode':'show_folder','folder_id':anime_id },self._img ('icon.png')),
            ('Sport',{'mode':'show_folder','folder_id':'6'},self._img ('icon.png')),
            ('Kids',{'mode':'show_folder','folder_id':kids_id },self._img ('icon.png')),
            ('Neuheiten entdecken',{'mode':'show_folder','folder_id':'17','seo':'neu-auf-rtl-main-root-service-f_17'},self._img ('icon.png')),
            ('Adrenalin & Spannung',{'mode':'show_folder','folder_id':'150','seo':'action-main-root-service-f_150'},self._img ('icon.png')),

            ('Podcasts',{'mode':'show_service','service':'podcast',
            'label':urllib .parse .quote_plus ('Podcasts')},self._img ('icon.png')),
            ('Hörbücher',{'mode':'show_service','service':'hoerbuecher',
            'label':urllib .parse .quote_plus ('Hörbücher')},self._img ('icon.png')),
            ('Radio',{'mode':'show_service','service':'live-radios',
            'label':urllib .parse .quote_plus ('Radio')},self._img ('icon.png')),
            ]

            items.append(('[COLOR gold]Gast Inhalte[/COLOR]',{'mode':'show_guest_free'},self._img ('icon.png')))

            if _addon.getSetting('show_az_menu') == 'true':
                items.append(('A-Z',{'mode':'show_az'},self._img ('basesearch.png')if os .path .exists (self._img ('basesearch.png'))else self._img ('icon.png')))

            items.extend([
            ('Suche',{'mode':'search'},self._img ('basesearch.png')if os .path .exists (self._img ('basesearch.png'))else self._img ('icon.png')),

            ('Einstellungen',{'mode':'settings'},self._img ('settings.png')),
            ('Addon Reset',{'mode':'reset'},self._img ('remove.png')),
            ('Logout',{'mode':'logout'},self._img ('remove.png')),
            ])
        else :
            try :
                from resources .lib .auth import RTLAuth as _RTLAuth
                _RTLAuth ().guest_login ()
            except Exception :
                pass
            items =[
            ('Anmelden',{'mode':'login'},self._img ('icon.png')),
            ('[COLOR gold]Gast Inhalte[/COLOR]',{'mode':'show_guest_free'},self._img ('icon.png')),
            ('Addon Reset',{'mode':'reset'},self._img ('remove.png')),
            ]

        for label ,params ,thumb in items :
            li =xbmcgui .ListItem (label =label )
            li .setProperty ('IsPlayable','false')
            if os .path .exists (thumb ):
                li .setArt ({'thumb':thumb ,'icon':thumb })
            li .setInfo ('video',{'title':label })
            xbmcplugin .addDirectoryItem (
            handle =self .handle ,
            url =self .build_url (params ),
            listitem =li ,
            isFolder =params .get ('mode')not in ('settings','logout','login','reset')
            )
        xbmcplugin .addSortMethod (self .handle ,xbmcplugin .SORT_METHOD_NONE )
        xbmcplugin .endOfDirectory (self .handle )

    def show_guest_free (self ):
        import os ,hashlib
        import xbmcaddon ,xbmcvfs
        _addon =xbmcaddon .Addon ()
        _addon_path =xbmcvfs .translatePath (_addon .getAddonInfo ('path'))
        _profile =xbmcvfs .translatePath (_addon .getAddonInfo ('profile'))
        _token_file =os .path .join (_profile ,'tokens.json')
        _logged_in =(not self .api .auth ._guest_tokens .get ('is_guest',False )
                     and bool (self .api .auth ._tokens .get ('access_token','')))

        _log (f'show_guest_free: lade Gast-Inhalte (logged_in={_logged_in })')
        data =self .api .get_folder_guest ('193',nb_pages =5 )
        if not data and not _logged_in :
            try :
                from resources .lib .auth import RTLAuth as _RTLAuth
                _RTLAuth ().guest_login ()
            except Exception :
                pass
            data =self .api .get_folder_guest ('193',nb_pages =5 )
        if not data :
            xbmcgui .Dialog ().notification (
                'RTL+','Gast Inhalte nicht ladbar.',
                xbmcgui .NOTIFICATION_ERROR ,4000 )
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
            return

        _IMAGE_KEY ='x9vGg4RNeNBqV2nBfhqLV6cN4n'
        def _thumb (img ):
            if not img or not isinstance (img ,dict ):return ''
            ids =img .get ('idsByRatio',{})or {}
            img_id =(ids .get ('16:9','')or ids .get ('2:3','')
                     or next (iter (ids .values ()),''))
            if not img_id :return ''
            pq =f'/v2/images/{img_id }/raw?auto=webp&blur=0&fit=max&width=320&height=180&interlace=1&quality=65'
            sig =hashlib .sha1 ((pq +_IMAGE_KEY ).encode ()).hexdigest ()
            return f'https://images-fio.rtlde.bedrock.tech{pq }&hash={sig }'

        xbmcplugin .setContent (self .handle ,'videos')

        live_entries =[]
        other_entries =[]

        _log (f'show_guest_free DEBUG: {len (data .get ("blocks",[]))} Bloecke total')
        for _bi ,_block in enumerate (data .get ('blocks',[])):
            _bc =_block .get ('content',{})
            _items =_bc .get ('items',[])
            _log (f'  Block[{_bi }]: {len (_items )} items')
            for _ii ,_it in enumerate (_items [:3 ]):
                _ic =_it .get ('itemContent',{})
                _act =(_ic .get ('action')or {})
                _tgt =(_act .get ('target')or {})
                _vl =(_tgt .get ('value_layout')or {})
                _vp =(_tgt .get ('value_player')or {})
                _log (f'    item[{_ii }]: t_type={_tgt .get ("type","?")!r} vl_type={_vl .get ("type","?")!r} vl_id={str (_vl .get ("id",""))!r} vp_type={_vp .get ("type","")!r} title={str (_ic .get ("title",""))[:30]!r}')

        for block in data .get ('blocks',[]):
            bc =block .get ('content',{})
            bt =bc .get ('title',{})
            bt =(bt .get ('short','')or bt .get ('long',''))if isinstance (bt ,dict )else str (bt or '')
            for it in bc .get ('items',[]):
                ic =it .get ('itemContent',{})
                _title_raw =ic .get ('title','')or ''
                _extra_title =ic .get ('extraTitle','')or ''
                _action_tmp =(ic .get ('action')or {})
                _target_tmp =(_action_tmp .get ('target')or {})
                _vl_tmp =(_target_tmp .get ('value_layout')or {})
                _seo_tmp =str (_vl_tmp .get ('seo',''))
                _highlight =ic .get ('highlight','')or ''
                _seo_title =_seo_tmp .replace ('-',' ').title ()if _seo_tmp else ''
                if _title_raw and _extra_title :
                    title =f'{_title_raw } - {_extra_title }'
                elif _title_raw :
                    title =_title_raw
                elif _extra_title :
                    title =_extra_title
                elif _seo_title :
                    title =_seo_title
                elif _highlight :
                    title =_highlight .split ('•')[0 ].strip ()
                else :
                    title ='Unbekannt'
                action =(ic .get ('action')or {})
                target =(action .get ('target')or {})
                t_type =target .get ('type','')
                if t_type =='lock':
                    _inner =target .get ('value_lock',{})or {}
                    while _inner .get ('originalTarget',{}).get ('type','')=='lock':
                        _inner =_inner .get ('originalTarget',{}).get ('value_lock',{})or {}
                    _orig =_inner .get ('originalTarget',{})or {}
                    if _orig .get ('type','')in ('layout','player'):
                        target =_orig
                        t_type =_orig .get ('type','')
                vl =(target .get ('value_layout')or {})
                vl_type =vl .get ('type','')
                vl_id =str (vl .get ('id',''))
                vl_seo =str (vl .get ('seo',''))
                vp =(target .get ('value_player')or {})
                vp_id =str (vp .get ('id',''))
                vp_content_type =vp .get ('type','')
                thumb =_thumb (ic .get ('image'))

                if vl_type =='live'and vl_id :
                    channel_slug =vl_id .replace ('rtlde_','')
                    live_label =f'[COLOR gold][B]LIVE - {title }[/B][/COLOR]'
                    url =self .build_url ({
                        'mode':'play_live',
                        'channel_id':channel_slug ,
                        'title':urllib .parse .quote_plus (title ),
                    })
                    li =xbmcgui .ListItem (label =live_label )
                    li .setProperty ('IsPlayable','true')
                    local_img =self ._channel_image (channel_slug )
                    art_img =local_img or thumb
                    if art_img :
                        li .setArt ({'thumb':art_img ,'icon':art_img ,'clearlogo':art_img ,'fanart':art_img })
                    li .setInfo ('video',{'title':'\u0001'+live_label ,'plot':ic .get ('description','')or '','tvshowtitle':bt })
                    live_entries .append ((url ,li ,False ))
                    continue

                if t_type =='player'and vp_id :
                    if vp_content_type in ('live','livetv','channel','event','live_event','event_stream'):
                        live_label =f'[COLOR gold][B]LIVE - {title }[/B][/COLOR]'
                        url =self .build_url ({
                            'mode':'play_live',
                            'channel_id':vp_id ,
                            'title':urllib .parse .quote_plus (title ),
                        })
                        li =xbmcgui .ListItem (label =live_label )
                        li .setProperty ('IsPlayable','true')
                        local_img =self ._channel_image (vp_id )
                        art_img =local_img or thumb
                        if art_img :
                            li .setArt ({'thumb':art_img ,'icon':art_img ,'clearlogo':art_img ,'fanart':art_img })
                        li .setInfo ('video',{'title':'\u0001'+live_label ,'plot':ic .get ('description','')or '','tvshowtitle':bt })
                        live_entries .append ((url ,li ,False ))
                        continue
                    _vl_alt =target .get ('value_layout',{})or {}
                    _clip_alt =_vl_alt .get ('id','')if _vl_alt .get ('type','')=='video' else ''
                    _play_id =_clip_alt if (_clip_alt and _prefer_clip_for_quality ())else vp_id
                    if _clip_alt and _prefer_clip_for_quality ():
                        _log (f'show_guest_free player->clip: rrn={vp_id !r} -> clip={_clip_alt !r}')
                    url =self ._vod_url (_play_id ,{'title':title ,'thumb':thumb })
                    li =xbmcgui .ListItem (label =(title) + (f" [{_quality_label()}]" if _quality_label() else ""))
                    li .setProperty ('IsPlayable','true')
                    li .setArt ({'thumb':thumb ,'icon':thumb ,'fanart':thumb })
                    li .setInfo ('video',{'title':title ,'plot':ic .get ('description','')or '','tvshowtitle':bt })
                    other_entries .append ((url ,li ,False ))
                    continue

                if not vl_id :continue
                li =xbmcgui .ListItem (label =title )
                li .setArt ({'thumb':thumb ,'icon':thumb ,'fanart':thumb })
                li .setInfo ('video',{'title':title ,'plot':ic .get ('description','')or '','tvshowtitle':bt })
                if vl_type =='program':
                    url =self .build_url ({'mode':'show_program','program_id':vl_id ,'seo':vl_seo })
                    is_folder =True
                elif vl_type =='video':
                    url =self ._vod_url (vl_id ,{'title':title ,'video_seo':vl_seo })
                    li .setProperty ('IsPlayable','true')
                    is_folder =False
                else :
                    continue
                other_entries .append ((url ,li ,is_folder ))

        _show_live =os .path .exists (_token_file )
        _entries_to_show =(live_entries if _show_live else [])+other_entries
        if not _show_live and live_entries :
            _log (f'show_guest_free: {len (live_entries )} Live-Eintraege ausgeblendet (nicht eingeloggt)')

        _search_img =self._img ('basesearch.png')if os .path .exists (self._img ('basesearch.png'))else self._img ('icon.png')
        li_search =xbmcgui .ListItem (label ='[COLOR gold][B]» Suche...[/B][/COLOR]')
        li_search .setArt ({'thumb':_search_img ,'icon':_search_img })
        li_search .setInfo ('video',{'title':'Suche'})
        li_search .setProperty ('IsPlayable','false')
        xbmcplugin .addDirectoryItem (handle =self .handle ,url =self .build_url ({'mode':'search'}),listitem =li_search ,isFolder =True )

        found =0
        for url ,li ,is_folder in _entries_to_show :
            xbmcplugin .addDirectoryItem (handle =self .handle ,url =url ,listitem =li ,isFolder =is_folder )
            found +=1

        self ._add_sort_methods ()
        _log (f'show_guest_free: {found } Eintraege (davon {len (live_entries ) if _show_live else 0} LIVE)')
        if found ==0 :
            xbmcgui .Dialog ().notification (
                'RTL+','Keine Inhalte gefunden.',xbmcgui .NOTIFICATION_WARNING ,3000 )
        xbmcplugin .endOfDirectory (self .handle )

    _meine_cache ={}

    def show_meine_inhalte (self ):
        _log ('show_meine_inhalte')

        _bt =self .api .auth .get_bedrock_token ()
        if not _bt :
            _log ('show_meine_inhalte: kein Bedrock-Token – OIDC abgelaufen, Neu-Login nötig')
            xbmcgui .Dialog ().notification (
                'RTL+',
                'Sitzung abgelaufen – bitte erneut anmelden.',
                xbmcgui .NOTIFICATION_WARNING ,6000 )
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
            return

        from .evil import bookmarks as _bookmarks
        local_data =_bookmarks .get ()

        data =self .api .get_frontspace ('bookmarks',page =1 ,nb_pages =2 )
        if not data and not local_data :
            xbmcgui .Dialog ().notification (
            'RTL+','Mein RTL+: Anmeldung erforderlich oder Serverfehler.',
            xbmcgui .NOTIFICATION_ERROR ,5000
            )
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
            return

        Navigator ._meine_cache ['local']=local_data or []
        Navigator ._meine_cache ['api']=data or {}

        folder_count =0

        if local_data :
            url =self .build_url ({'mode':'show_meine_block','block_key':'weiterschauen','label':urllib .parse .quote_plus ('Weiterschauen')})
            li =xbmcgui .ListItem (label ='Weiterschauen')
            li .setProperty ('IsPlayable','false')
            li .setArt ({'thumb':os .path .join (xbmcvfs .translatePath (xbmcaddon .Addon ().getAddonInfo ('path')),'resources','media','favourites.png')})
            li .setInfo ('video',{'title':'Weiterschauen','plot':f'{len (local_data )} gespeicherte Inhalte'})
            xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )
            folder_count +=1

        if data :
            blocks =data .get ('blocks',[])
            def _is_real_block (b ):
                items =b .get ('content',{}).get ('items',[])
                return any (
                    ((it .get ('itemContent',{})or {}).get ('action',{})or {}).get ('target',{}).get ('value_layout',{}).get ('type','')!='frontspace'
                    for it in items )
            valid_blocks =[b for b in blocks if _is_real_block (b )]
            if not valid_blocks and blocks :
                _log ('show_meine_inhalte: Nur frontspace-Items → Neu anmelden')
                xbmcgui .Dialog ().notification ('RTL+','Bitte neu anmelden.',xbmcgui .NOTIFICATION_WARNING ,5000 )
            _log (f'show_meine_inhalte: {len (valid_blocks )} API-Blöcke mit Inhalten')
            for idx ,block in enumerate (valid_blocks ):
                content_b =block .get ('content',{})
                block_title_obj =content_b .get ('title')or {}
                if isinstance (block_title_obj ,dict ):
                    block_title =block_title_obj .get ('short','')or block_title_obj .get ('long','')or ''
                else :
                    block_title =str (block_title_obj )if block_title_obj else ''
                if not block_title :
                    block_title =f'Meine Inhalte {idx +1 }'
                if block_title .lower ()=='jetzt weiterschauen':
                    block_title ='Jetzt weiterschauen (Online Liste)'
                items =content_b .get ('items',[])
                block_key =f'api_{idx }'
                url =self .build_url ({'mode':'show_meine_block','block_key':block_key ,'label':urllib .parse .quote_plus (block_title )})
                li =xbmcgui .ListItem (label =block_title )
                li .setProperty ('IsPlayable','false')
                li .setArt ({'thumb':os .path .join (xbmcvfs .translatePath (xbmcaddon .Addon ().getAddonInfo ('path')),'resources','media','favourites.png')})
                li .setInfo ('video',{'title':block_title ,'plot':f'{len (items )} Inhalte'})
                xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )
                folder_count +=1

        if folder_count ==0 :
            xbmcgui .Dialog ().notification (
            'RTL+','Mein RTL+ ist leer – noch nichts gemerkt oder angesehen.',
            xbmcgui .NOTIFICATION_INFO ,4000
            )
            li =xbmcgui .ListItem (label ='[Keine Inhalte]')
            xbmcplugin .addDirectoryItem (self .handle ,'',li ,False )

        self ._add_sort_methods ()
        xbmcplugin .endOfDirectory (self .handle )

    def show_meine_block (self ,block_key ,label =''):
        _log (f'show_meine_block key={block_key }')

        if block_key =='weiterschauen':
            local_data =Navigator ._meine_cache .get ('local',[])
            if not local_data :
                from .evil import bookmarks as _bookmarks
                local_data =_bookmarks .get ()
            if not local_data :
                xbmcgui .Dialog ().notification ('RTL+','Keine gespeicherten Inhalte.',xbmcgui .NOTIFICATION_INFO ,3000 )
                self ._add_sort_methods ()
                xbmcplugin .endOfDirectory (self .handle )
                return
            for item in local_data :
                series_title =item .get ('series_title','')
                episode_label =item ['label']
                if series_title and series_title !=episode_label :
                    display_label =f'{series_title} - {episode_label}'
                else :
                    display_label =episode_label
                li =xbmcgui .ListItem (label =display_label )
                thumb =item .get ('thumb','')
                fanart =item .get ('fanart','')or thumb
                poster =item .get ('poster','')or thumb
                art ={'thumb':thumb ,'fanart':fanart }
                if poster :art ['poster']=poster
                li .setArt (art )
                li .setProperty ('IsPlayable','true'if item .get ('playable')else 'false')
                info ={'title':display_label }
                if series_title :info ['tvshowtitle']=series_title
                li .setInfo ('video',info )
                cmd =f'RunPlugin({self .base_url }?mode=remove_bookmark&path={urllib .parse .quote_plus (item ["path"])})'
                li .addContextMenuItems ([('Von Weiterschauen entfernen',cmd )])
                xbmcplugin .addDirectoryItem (self .handle ,item ['path'],li ,bool (item .get ('folder',0)))
            xbmcplugin .setContent (self .handle ,'videos')
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle )
            return

        try :
            idx =int (block_key .replace ('api_',''))
        except ValueError :
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
            return

        data =Navigator ._meine_cache .get ('api')
        if not data :
            data =self .api .get_frontspace ('bookmarks',page =1 ,nb_pages =2 )
            if not data :
                xbmcgui .Dialog ().notification ('RTL+','Fehler beim Laden.',xbmcgui .NOTIFICATION_ERROR ,4000 )
                self ._add_sort_methods ()
                xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
                return
            Navigator ._meine_cache ['api']=data

        blocks =data .get ('blocks',[])
        valid_blocks =[b for b in blocks if b .get ('content',{}).get ('items')]
        if idx >=len (valid_blocks ):
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
            return

        items =valid_blocks [idx ].get ('content',{}).get ('items',[])
        total =0
        for item in items :
            if self ._add_item_as_folder (item ):
                total +=1

        if total ==0 :
            li =xbmcgui .ListItem (label ='[Keine Inhalte]')
            xbmcplugin .addDirectoryItem (self .handle ,'',li ,False )

        xbmcplugin .setContent (self .handle ,'videos')
        self ._add_sort_methods ()
        xbmcplugin .endOfDirectory (self .handle )

    def _add_item_as_folder (self ,item ):
        try :
            ic =item .get ('itemContent',{})
            if not ic :
                return False
            action =ic .get ('action',{})or {}
            target =action .get ('target',{})or {}
            t_type =target .get ('type','')
            if t_type =='lock':
                target =(target .get ('value_lock',{})or {}).get ('originalTarget',{})or {}
                t_type =target .get ('type','')
            vl =target .get ('value_layout',{})or {}
            layout_type =vl .get ('type','')
            layout_id =vl .get ('id','')
            layout_seo =vl .get ('seo','')

            if not layout_id :
                return self ._add_item (item )

            title_raw =ic .get ('title','')or ''
            extra_title =ic .get ('extraTitle','')or ''
            highlight =ic .get ('highlight','')or ''
            seo_title =layout_seo .replace ('-',' ').title ()if layout_seo else ''
            if title_raw and extra_title :
                full_title =f'{title_raw } - {extra_title }'
            elif title_raw :
                full_title =title_raw
            elif extra_title :
                full_title =extra_title
            elif seo_title :
                full_title =seo_title
            elif highlight :
                full_title =highlight .split ('•')[0 ].strip ()
            else :
                return False

            thumb =_image_url (ic .get ('image',{}),width =320 ,height =180 ,preferred_ratio ='16:9')
            fanart =_image_url (ic .get ('secondaryImage',{}),width =640 ,height =360 ,preferred_ratio ='16:9')or thumb
            poster =_image_url (ic .get ('image',{}),width =213 ,height =320 ,preferred_ratio ='2:3')or thumb
            description =ic .get ('description','')or highlight

            if layout_type =='program':
                url =self .build_url ({'mode':'show_program','program_id':layout_id ,'seo':layout_seo })
                li =xbmcgui .ListItem (label =full_title )
                li .setProperty ('IsPlayable','false')
                art ={'thumb':thumb or poster ,'fanart':fanart }
                if poster :art ['poster']=poster
                li .setArt (art )
                li .setInfo ('video',{'title':full_title ,'plot':description ,'mediatype':'tvshow'})
                bookmark_url =self .build_url ({'mode':'toggle_bookmark','program_id':layout_id ,'title':urllib .parse .quote_plus (full_title ),'subscribed':'1'})
                unmark_url =self .build_url ({'mode':'toggle_bookmark','program_id':layout_id ,'title':urllib .parse .quote_plus (full_title ),'subscribed':'0'})
                li .addContextMenuItems ([('Merken',f'RunPlugin({bookmark_url })'),('Nicht mehr merken',f'RunPlugin({unmark_url })')])
                xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )
                return True

            elif layout_type =='video':
                parent =vl .get ('parent',{})or {}
                parent_id =str (parent .get ('id',''))
                parent_seo =parent .get ('seo','')
                if parent_id :
                    url =self .build_url ({'mode':'show_program','program_id':parent_id ,'seo':parent_seo })
                    li =xbmcgui .ListItem (label =title_raw or full_title )
                    li .setProperty ('IsPlayable','false')
                    art ={'thumb':thumb or poster ,'fanart':fanart }
                    if poster :art ['poster']=poster
                    li .setArt (art )
                    li .setInfo ('video',{'title':title_raw or full_title ,'plot':description ,'mediatype':'tvshow'})
                    xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )
                    return True
                return self ._add_item (item )

            elif layout_type =='frontspace':
                _log (f'_add_item_as_folder: frontspace-Item uebersprungen id={layout_id }')
                return False

            else :
                return self ._add_item (item )

        except Exception as e :
            _log (f'_add_item_as_folder error: {e }')
            return False

    def _render_layout_with_headers (self ,data ):
        blocks =data .get ('blocks',[])
        total =0

        for block in blocks :
            content =block .get ('content',{})
            block_title_obj =content .get ('title')or {}
            if isinstance (block_title_obj ,dict ):
                block_title =block_title_obj .get ('short','')or block_title_obj .get ('long','')or ''
            else :
                block_title =str (block_title_obj )if block_title_obj else ''

            items =content .get ('items',[])
            if not items :
                continue

            if block_title :
                sep =xbmcgui .ListItem (label =f'[COLOR gold]── {block_title } ──[/COLOR]')
                sep .setProperty ('IsPlayable','false')
                sep .setInfo ('video',{'title':block_title })
                xbmcplugin .addDirectoryItem (self .handle ,'',sep ,False )

            for item in items :
                if self ._add_item (item ):
                    total +=1

        if total ==0 :
            li =xbmcgui .ListItem (label ='[Keine Inhalte]')
            xbmcplugin .addDirectoryItem (self .handle ,'',li ,False )

        xbmcplugin .setContent (self .handle ,'videos')
        self ._add_sort_methods ()
        xbmcplugin .endOfDirectory (self .handle )

    def _add_context_menu (self ,li ,params ,title ,thumb ,fanart =None ,poster =None ,series_title =None ):
        url =self .build_url (params )
        enc_url =urllib .parse .quote_plus (url )
        enc_title =urllib .parse .quote_plus (title )
        enc_thumb =urllib .parse .quote_plus (thumb or '')
        cmd =f'RunPlugin({self .base_url }?mode=add_bookmark&path={enc_url }&label={enc_title }&thumb={enc_thumb }'
        if fanart :cmd +=f'&fanart={urllib .parse .quote_plus (fanart )}'
        if poster :cmd +=f'&poster={urllib .parse .quote_plus (poster )}'
        if series_title :cmd +=f'&series_title={urllib .parse .quote_plus (series_title )}'
        cmd +=')'
        li .addContextMenuItems ([('Zu Weiterschauen hinzufuegen',cmd )])

    def show_service (self ,service ,label ='',page =1 ):
        _log (f'show_service service={service } page={page }')
        data =self .api .get_service (service ,page =page ,nb_pages =2 )
        if not data :
            xbmcgui .Dialog ().notification ('RTL+','Fehler beim Laden',xbmcgui .NOTIFICATION_ERROR ,4000 )
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
            return

        self ._render_layout (data ,next_params ={
        'mode':'show_service',
        'service':service ,
        'label':urllib .parse .quote_plus (label or service ),
        })

    def show_alias (self ,alias ,page =1 ):
        _log (f'show_alias alias={alias } page={page }')
        data =self .api .get_alias (alias ,page =page )
        if not data :
            xbmcgui .Dialog ().notification ('RTL+','Fehler beim Laden',xbmcgui .NOTIFICATION_ERROR ,4000 )
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
            return

        if alias =='home':
            blocks =data .get ('blocks',[])
            highlights_block =None
            other_blocks =[]
            for block in blocks :
                ct =block .get ('content',{})
                title_obj =ct .get ('title')or {}
                btitle =(title_obj .get ('short','')or title_obj .get ('long','')
                if isinstance (title_obj ,dict )else str (title_obj ))
                if 'highlight'in btitle .lower ()or 'neu'in btitle .lower ():
                    if highlights_block is None :
                        highlights_block =block
                    else :
                        other_blocks .append (block )
                else :
                    other_blocks .append (block )
            if highlights_block :
                data =dict (data )
                data ['blocks']=[highlights_block ]+other_blocks

        self ._render_layout (data ,next_params ={'mode':'show_alias','alias':alias })

    def show_folder (self ,folder_id ,seo ='',page =1 ):
        _log (f'show_folder id={folder_id } page={page }')
        data =self .api .get_folder (folder_id ,seo =seo ,page =page )
        if not data :
            xbmcgui .Dialog ().notification ('RTL+','Fehler beim Laden',xbmcgui .NOTIFICATION_ERROR ,4000 )
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
            return

        blocks =data .get ('blocks',[])
        named_blocks =[]
        actionless_blocks =[]
        inline_blocks =[]
        for i ,block in enumerate (blocks ):
            content =block .get ('content',{})
            title_obj =content .get ('title')or {}
            if isinstance (title_obj ,dict ):
                btitle =title_obj .get ('short','')or title_obj .get ('long','')or ''
            else :
                btitle =str (title_obj )
            items =content .get ('items',[])
            if not items :
                continue
            has_action =any ((it .get ('itemContent',{})or {}).get ('action')for it in items )
            if not has_action :
                actionless_blocks .append ((i ,btitle ,items ))
            elif btitle and len (items )>1 :
                named_blocks .append ((i ,btitle ,items ))
            else :
                inline_blocks .append ((i ,btitle ,items ))

        if actionless_blocks or len (named_blocks )>=2 :
            _log (f'show_folder: {len (named_blocks )} named + {len (actionless_blocks )} actionless + {len (inline_blocks )} inline')
            for block_idx ,btitle ,items in inline_blocks :
                for item in items :
                    self ._add_item (item )
            for block_idx ,btitle ,items in actionless_blocks :
                for item in items :
                    ic =item .get ('itemContent',{})or {}
                    analytics =ic .get ('analytics',{})or {}
                    tealium =analytics .get ('tealiumImpression',{})or {}
                    folder_id_str =str (tealium .get ('item_id',''))
                    item_title =tealium .get ('item_title','')
                    img =ic .get ('image',{})or {}
                    caption =img .get ('caption','')
                    label =item_title or caption
                    if not label or not folder_id_str :
                        continue
                    thumb =_image_url (img ,width =320 ,height =180 ,preferred_ratio ='16:9')
                    url =self .build_url ({'mode':'show_folder','folder_id':folder_id_str })
                    li =xbmcgui .ListItem (label =label )
                    li .setProperty ('IsPlayable','false')
                    if thumb :
                        li .setArt ({'thumb':thumb ,'fanart':thumb })
                    li .setInfo ('video',{'title':label })
                    xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )
            for block_idx ,btitle ,items in named_blocks :
                cat_thumb =''
                for it in items [:3 ]:
                    ic =it .get ('itemContent',{})
                    cat_thumb =_image_url (ic .get ('image',{}),preferred_ratio ='16:9')
                    if cat_thumb :
                        break
                url =self .build_url ({
                'mode':'show_folder_block',
                'folder_id':folder_id ,
                'block_index':block_idx ,
                'seo':seo ,
                })
                clean_btitle =_clean_title (btitle )
                li =xbmcgui .ListItem (label =clean_btitle )
                li .setProperty ('IsPlayable','false')
                if cat_thumb :
                    li .setArt ({'thumb':cat_thumb ,'fanart':cat_thumb })
                li .setInfo ('video',{'title':clean_btitle ,'plot':clean_btitle })
                xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )
            xbmcplugin .setContent (self .handle ,'videos')
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle )
        else :
            self ._render_layout (data ,next_params ={'mode':'show_folder','folder_id':folder_id })

    def show_folder_block (self ,folder_id ,block_index ,seo ='',page =1 ):
        import math as _math
        _log (f'show_folder_block id={folder_id } block={block_index }')
        data =self .api .get_folder (folder_id ,seo =seo ,page =page )
        if not data :
            xbmcgui .Dialog ().notification ('RTL+','Fehler beim Laden',xbmcgui .NOTIFICATION_ERROR ,4000 )
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
            return

        blocks =data .get ('blocks',[])
        if block_index >=len (blocks ):
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle )
            return

        block =blocks [block_index ]
        block_id =block .get ('id','')
        content =block .get ('content',{})
        items =list (content .get ('items',[]))

        pagination =content .get ('pagination',{})or {}
        total_items =pagination .get ('totalItems',0 )
        ipp =pagination .get ('itemsPerPage',6 )or 6
        next_page =pagination .get ('nextPage')

        if block_id and next_page and total_items >len (items ):
            NB =3
            total_pages =_math .ceil (total_items /ipp )
            cur_page =next_page
            while cur_page <=total_pages :
                _log (f'show_folder_block: fetching block page {cur_page } of {total_pages }')
                page_data =self .api .get_block_page (folder_id ,block_id ,page =cur_page ,nb_pages =NB )
                if not page_data :
                    break
                page_items =page_data .get ('content',{}).get ('items',[])or []
                if not page_items :
                    break
                items .extend (page_items )
                _log (f'show_folder_block: got {len (page_items )} items, total now {len (items )}')
                cur_page +=NB

        total =0
        for item in items :
            if self ._add_item (item ):
                total +=1

        if total ==0 :
            li =xbmcgui .ListItem (label ='[Keine Inhalte]')
            xbmcplugin .addDirectoryItem (self .handle ,'',li ,False )

        xbmcplugin .setContent (self .handle ,'movies')
        self ._add_sort_methods ()
        xbmcplugin .endOfDirectory (self .handle )

    _SEASON_PATTERNS =('staffel','season','saison','serie ','teil ')
    _MOVIE_KEYWORDS =('film','spielfilm','kinofilm','movie','dokumentarfilm')
    _SERIES_KEYWORDS =('staffel','folge','season','episode','serie','show')

    def _is_movie_highlight (self ,highlight ,extra_details ='',details =''):
        hl =(highlight or '').lower ()
        ed =(extra_details or '').lower ()
        det =(details or '').lower ()
        combined =hl +' '+ed +' '+det
        has_movie_kw =any (k in combined for k in self ._MOVIE_KEYWORDS )
        has_series_kw =any (k in combined for k in self ._SERIES_KEYWORDS )
        import re as _re
        has_duration =bool (_re .search (r'\d+\s*min',combined ))
        return (has_movie_kw or has_duration )and not has_series_kw

    def play_program (self ,program_id ,seo ='',title ='Film'):
        data =self .api .get_program_layout (program_id ,seo =seo ,page =1 )
        if not data :
            xbmcgui .Dialog ().notification ('RTL+','Fehler beim Laden',xbmcgui .NOTIFICATION_ERROR ,4000 )
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
            return

        blocks =data .get ('blocks',[])
        all_clips =[]
        for block in blocks :
            bc =block .get ('content',{})
            btitle_obj =bc .get ('title')or {}
            btitle =(btitle_obj .get ('short','')or btitle_obj .get ('long','')
            if isinstance (btitle_obj ,dict )else str (btitle_obj ))
            if 'empfehlung'in btitle .lower ()or 'recommendation'in btitle .lower ():
                continue
            for item in bc .get ('items',[]):
                ic =item .get ('itemContent',{})
                action =ic .get ('action',{})or {}
                target =action .get ('target',{})or {}
                if target .get ('type')=='lock':
                    target =(target .get ('value_lock',{})or {}).get ('originalTarget',{})or {}
                vl =target .get ('value_layout',{})or {}
                if target .get ('type')=='layout'and vl .get ('type')=='video':
                    all_clips .append ((vl .get ('id',''),vl .get ('seo',''),ic ))

        unique_ids =list (dict .fromkeys (cid for cid ,_ ,_ in all_clips if cid ))
        if not unique_ids :

            self .show_program (program_id ,seo =seo )
            return

        clip_id =unique_ids [0 ]
        ic =next ((ic for cid ,_ ,ic in all_clips if cid ==clip_id ),all_clips [0 ][2 ])
        vl_seo =next ((s for cid ,s ,_ in all_clips if cid ==clip_id ),'')

        resolved_title =(ic .get ('title')or ic .get ('extraTitle')or title )
        thumb =_image_url (ic .get ('image',{}),width =320 ,height =180 ,preferred_ratio ='16:9')
        fanart =_image_url (ic .get ('secondaryImage',{}),width =640 ,height =360 ,preferred_ratio ='16:9')or thumb
        poster =_image_url (ic .get ('image',{}),width =213 ,height =320 ,preferred_ratio ='2:3')or thumb

        _vod_meta_dict ={
        'title':resolved_title ,
        'video_seo':vl_seo ,
        'program_id':program_id ,
        }
        if thumb :_vod_meta_dict ['thumb']=thumb
        if fanart :_vod_meta_dict ['fanart']=fanart
        if poster :_vod_meta_dict ['poster']=poster
        play_url =self ._vod_url (clip_id ,_vod_meta_dict )
        li =xbmcgui .ListItem (label =(resolved_title) + (f" [{_quality_label()}]" if _quality_label() else ""),path =play_url )
        li .setProperty ('IsPlayable','true')
        if thumb :
            li .setArt ({'thumb':thumb ,'poster':poster ,'fanart':fanart })
        li .setInfo ('video',{
        'title':resolved_title ,
        'plot':ic .get ('description','')or '',
        'mediatype':'movie',
        })
        xbmcplugin .setResolvedUrl (self .handle ,True ,li )

    def _is_season_block (self ,btitle ):
        bl =btitle .lower ().strip ()
        if any (bl .startswith (p )for p in self ._SEASON_PATTERNS ):
            return True
        if bl .startswith ('s')and len (bl )<=4 and bl [1 :].isdigit ():
            return True
        if 'spieltag'in bl :
            return True
        import re as _re
        if _re .match (r'^[a-zäöü\s]+ \d+$',bl ):
            return True
        return False

    def show_program (self ,program_id ,seo ='',page =1 ):
        _log (f'show_program id={program_id } page={page }')
        if str (program_id )=='bookmarks':
            _log ('show_program: bookmarks-ID → show_meine_inhalte')
            return self .show_meine_inhalte ()

        all_blocks =[]
        cur_page =1
        MAX_PAGES =30
        while cur_page <=MAX_PAGES :
            data =self .api .get_program_layout (program_id ,seo =seo ,page =cur_page ,nb_pages =3 )
            if not data :
                if cur_page ==1 :
                    xbmcgui .Dialog ().notification ('RTL+','Fehler beim Laden',xbmcgui .NOTIFICATION_ERROR ,4000 )
                    self ._add_sort_methods ()
                    xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
                    return
                break
            new_blocks =data .get ('blocks',[])
            if not new_blocks :
                break
            existing_ids ={b .get ('id','')for b in all_blocks }
            fresh =[b for b in new_blocks if b .get ('id','')not in existing_ids ]
            if not fresh and cur_page >1 :
                break
            all_blocks .extend (fresh )
            has_more =data .get ('pagination',{}).get ('hasMore',False )or data .get ('hasMore',False )
            total_pages =data .get ('pagination',{}).get ('totalPages',1 )or 1
            if not has_more and cur_page >=total_pages :
                break
            cur_page +=1

        blocks =all_blocks
        _log (f'show_program {program_id }: {len (blocks )} Blöcke über {cur_page } Seite(n) geladen')
        import re as _re

        direct_seasons =[]
        concurrent_seasons =[]

        for block in blocks :
            bc =block .get ('content',{})
            btitle_obj =bc .get ('title')or {}
            btitle =(btitle_obj .get ('short','')or btitle_obj .get ('long','')
            if isinstance (btitle_obj ,dict )else str (btitle_obj or ''))
            block_id =block .get ('id','')

            if btitle and block_id and self ._is_season_block (btitle ):
                btitle =_clean_title (btitle )
                block_items =bc .get ('items',[])or []
                direct_seasons .append ((btitle ,block_id ,block_items ))

            alt =block .get ('alternativeContent')
            if not alt or not isinstance (alt ,dict ):
                continue
            concurrent =alt .get ('concurrentBlocks')
            if not concurrent or not isinstance (concurrent ,list ):
                continue
            for cb in concurrent :
                if not cb or not isinstance (cb ,dict ):
                    continue
                cb_title =cb .get ('title','')
                cb_id =cb .get ('id','')
                if cb_title and cb_id :
                    cb_title =_clean_title (cb_title )
                    cb_items =cb .get ('content',{}).get ('items',[])or []
                    concurrent_seasons .append ((cb_title ,cb_id ,cb_items ))

        all_seasons =direct_seasons +concurrent_seasons

        if len (all_seasons )>=1 :
            _log (f'show_program {program_id }: {len (direct_seasons )} direkte + {len (concurrent_seasons )} concurrentBlocks-Staffeln')

            def _season_sort_key (entry ):
                m =_re .search (r'\d+',entry [0 ])
                return int (m .group ())if m else 0

            all_seasons .sort (key =_season_sort_key ,reverse =True )

            seen_ids =set ()
            for idx ,(s_title ,s_block_id ,s_items )in enumerate (all_seasons ):
                if s_block_id in seen_ids :
                    continue
                seen_ids .add (s_block_id )
                m =_re .search (r'\d+',s_title )
                s_num =int (m .group ())if m else (idx +1 )
                cat_thumb =''
                for it in s_items [:3 ]:
                    ic2 =it .get ('itemContent',{})
                    cat_thumb =_image_url (ic2 .get ('image',{}),preferred_ratio ='16:9')
                    if cat_thumb :
                        break
                url =self .build_url ({
                'mode':'show_season',
                'program_id':program_id ,
                'season_title':urllib .parse .quote_plus (s_title ),
                'block_index':idx ,
                'season_block_id':s_block_id ,
                'seo':seo ,
                })
                li =xbmcgui .ListItem (label =s_title )
                li .setProperty ('IsPlayable','false')
                if cat_thumb :
                    li .setArt ({'thumb':cat_thumb ,'fanart':cat_thumb })
                li .setInfo ('video',{'title':s_title ,'season':s_num ,'mediatype':'season'})
                xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )
            xbmcplugin .setContent (self .handle ,'tvshows')
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle )
            return

        content_blocks =[]
        for block in blocks :
            bc =block .get ('content',{})
            btitle_obj =bc .get ('title')or {}
            btitle =(btitle_obj .get ('short','')or btitle_obj .get ('long','')
            if isinstance (btitle_obj ,dict )else str (btitle_obj ))
            if 'empfehlung'in btitle .lower ()or 'recommendation'in btitle .lower ():
                continue
            items =bc .get ('items',[])
            if items :
                content_blocks .append ((btitle ,items ))

        all_clips =[]
        for btitle ,items in content_blocks :
            for item in items :
                ic =item .get ('itemContent',{})
                action =ic .get ('action',{})or {}
                target =action .get ('target',{})or {}
                if target .get ('type')=='lock':
                    target =(target .get ('value_lock',{})or {}).get ('originalTarget',{})or {}
                vl =target .get ('value_layout',{})or {}
                if target .get ('type')=='layout'and vl .get ('type')=='video':
                    all_clips .append ((vl .get ('id',''),ic ))

        unique_clip_ids =list (dict .fromkeys (cid for cid ,_ in all_clips if cid ))
        if len (all_clips )>=1 and len (unique_clip_ids )==1 :
            clip_id ,ic =all_clips [0 ]
            action =ic .get ('action',{})or {}
            vl =(action .get ('target',{})or {}).get ('value_layout',{})or {}
            seo =vl .get ('seo','')
            seo_title =seo .replace ('-',' ').title ()if seo else ''
            title =(ic .get ('title')or ic .get ('extraTitle')or seo_title or
            ic .get ('highlight','').split ('•')[-1 ].strip ()or clip_id )
            thumb =_image_url (ic .get ('image',{}),width =320 ,height =180 ,preferred_ratio ='16:9')
            fanart =_image_url (ic .get ('secondaryImage',{}),width =640 ,height =360 ,preferred_ratio ='16:9')or thumb
            poster =_image_url (ic .get ('image',{}),width =213 ,height =320 ,preferred_ratio ='2:3')or thumb
            _vod_p2_meta ={'title':title }
            if thumb :_vod_p2_meta ['thumb']=thumb
            if fanart :_vod_p2_meta ['fanart']=fanart
            if poster :_vod_p2_meta ['poster']=poster
            play_url =self ._vod_url (clip_id ,_vod_p2_meta )
            li =xbmcgui .ListItem (label =(title) + (f" [{_quality_label()}]" if _quality_label() else ""),path =play_url )
            li .setProperty ('IsPlayable','true')
            if thumb :
                li .setArt ({'thumb':thumb ,'poster':poster ,'fanart':fanart })
            li .setInfo ('video',{
            'title':title ,
            'plot':ic .get ('description','')or '',
            'mediatype':'movie',
            })
            xbmcplugin .addDirectoryItem (self .handle ,play_url ,li ,False )
            xbmcplugin .setContent (self .handle ,'movies')
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle )
            return

        season_blocks =[(bt ,it )for bt ,it in content_blocks if self ._is_season_block (bt )]

        if len (season_blocks )>=2 :
            _log (f'show_program {program_id }: {len (season_blocks )} Staffeln (Titel-Erkennung)')
            for block_idx ,(btitle ,items )in enumerate (season_blocks ):
                m =_re .search (r'\d+',btitle )
                s_num =int (m .group ())if m else (block_idx +1 )
                cat_thumb =''
                for it in items [:3 ]:
                    ic2 =it .get ('itemContent',{})
                    cat_thumb =_image_url (ic2 .get ('image',{}),preferred_ratio ='16:9')
                    if cat_thumb :
                        break
                url =self .build_url ({
                'mode':'show_season',
                'program_id':program_id ,
                'season_title':urllib .parse .quote_plus (btitle ),
                'block_index':block_idx ,
                })
                li =xbmcgui .ListItem (label =btitle )
                li .setProperty ('IsPlayable','false')
                if cat_thumb :
                    li .setArt ({'thumb':cat_thumb ,'fanart':cat_thumb })
                li .setInfo ('video',{'title':btitle ,'season':s_num ,'mediatype':'season'})
                xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )
            xbmcplugin .setContent (self .handle ,'tvshows')
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle )
            return

        total =0
        for btitle ,items in content_blocks :
            for item in items :
                if self ._add_item (item ):
                    total +=1

        if total ==0 :
            xbmcgui .Dialog ().notification ('RTL+','Keine Episoden vorhanden',xbmcgui .NOTIFICATION_INFO ,3000 )
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
            return

        xbmcplugin .setContent (self .handle ,'episodes')
        self ._add_sort_methods_episode ()
        xbmcplugin .endOfDirectory (self .handle )

    def _fetch_all_block_items (self ,program_id ,season_block_id ,seo =''):
        import math as _math
        NB =3
        all_items =[]

        first =self .api .get_program_block (program_id ,season_block_id ,page =1 ,nb_pages =NB ,seo =seo )
        if not first :
            return all_items

        def _extract (block_data ):
            c =block_data .get ('content',{})
            it =c .get ('items',[])or []
            if not it :
                for b in block_data .get ('blocks',[]):
                    bi =b .get ('content',{}).get ('items',[])or []
                    it .extend (bi )
            if not it :
                it =block_data .get ('items',[])or []
            fixed =[]
            for item in it :
                if 'itemContent' not in item and ('title' in item or 'action' in item or 'video' in item ):
                    fixed .append ({'itemContent':item })
                else :
                    fixed .append (item )
            return c ,fixed

        first_content ,first_items =_extract (first )
        all_items .extend (first_items )

        pagination =first_content .get ('pagination')or {}
        total_items =pagination .get ('totalItems',0 )
        ipp =pagination .get ('itemsPerPage',6 )or 6
        if not total_items :
            _log (f'_fetch_all_block_items: kein totalItems, nur erste {len (all_items )} items')
            return all_items

        total_pages =_math .ceil (total_items /ipp )
        _log (f'_fetch_all_block_items: totalItems={total_items } ipp={ipp } totalPages={total_pages }')

        page =1 +NB
        while page <=total_pages :
            block_data =self .api .get_program_block (program_id ,season_block_id ,page =page ,nb_pages =NB ,seo =seo )
            if not block_data :
                break
            _ ,page_items =_extract (block_data )
            all_items .extend (page_items )
            _log (f'_fetch_all_block_items page={page } got={len (page_items )} total={len (all_items )}')
            page +=NB

        return all_items

    def show_season (self ,program_id ,block_index ,season_title ='',season_block_id ='',seo =''):
        _log (f'show_season id={program_id } block={block_index } block_id={season_block_id }')
        items =[]

        if season_block_id and program_id :
            _log (f'show_season: fetching all pages via /program/{program_id }/block/{season_block_id }')
            items =self ._fetch_all_block_items (program_id ,season_block_id ,seo =seo )
            _log (f'show_season block API total: {len (items )} items')

        if not items :
            data =self .api .get_program_layout (program_id ,page =1 ,nb_pages =5 )
            if not data :
                xbmcgui .Dialog ().notification ('RTL+','Fehler beim Laden',xbmcgui .NOTIFICATION_ERROR ,4000 )
                self ._add_sort_methods ()
                xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
                return

            blocks =data .get ('blocks',[])
            season_blocks =[]
            for block in blocks :
                bc =block .get ('content',{})
                btitle_obj =bc .get ('title')or {}
                btitle =(btitle_obj .get ('short','')or btitle_obj .get ('long','')
                if isinstance (btitle_obj ,dict )else str (btitle_obj ))
                if 'empfehlung'in btitle .lower ()or 'recommendation'in btitle .lower ():
                    continue
                block_items =bc .get ('items',[])
                if block_items and self ._is_season_block (btitle ):
                    season_blocks .append ((btitle ,block_items ))
            if block_index <len (season_blocks ):
                _ ,items =season_blocks [block_index ]

        total =0
        for item in items :
            if self ._add_item (item ):
                total +=1

        if total ==0 :
            xbmcgui .Dialog ().notification ('RTL+','Keine Episoden vorhanden',xbmcgui .NOTIFICATION_INFO ,3000 )
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
            return

        xbmcplugin .setContent (self .handle ,'episodes')
        self ._add_sort_methods_episode ()
        xbmcplugin .endOfDirectory (self .handle )

    def _epg_current_program (self ,epgbox ):
        import time as _time
        from datetime import datetime as _dt
        import re as _re
        now_ts = _time.time ()
        current = None
        next_ep = None

        def _parse_ts (date_str ):
            try :
                s = _re.sub (r'([+-]\d{2}):(\d{2})$',lambda m :f'{m.group(1)}{m.group(2)}',date_str )
                return _dt.strptime (s ,'%Y-%m-%dT%H:%M:%S%z').timestamp ()
            except Exception :
                return None

        for ep in epgbox :
            pb = ep.get ('progressBar')
            if pb is not None :
                start_ts = _parse_ts (ep.get ('start',{}).get ('date',''))
                end_ts = _parse_ts (ep.get ('end',{}).get ('date',''))
                if start_ts is not None and end_ts is not None :
                    if start_ts <= now_ts <= end_ts :
                        current = ep
                        break

                else :

                    current = ep
                    break

        if current is None :
            for ep in epgbox :
                start_ts = _parse_ts (ep.get ('start',{}).get ('date',''))
                end_ts = _parse_ts (ep.get ('end',{}).get ('date',''))
                if start_ts is None or end_ts is None :
                    continue
                if start_ts <= now_ts <= end_ts :
                    current = ep
                    break

        for ep in epgbox:
            if current and ep is current:
                continue
            try:
                from datetime import datetime as _dt
                import re as _re
                start_str = ep.get ('start',{}).get ('date','')
                if not start_str:
                    continue
                start_str_utc = _re.sub (r'([+-]\d{2}):(\d{2})$',lambda m:f'{m.group(1)}{m.group(2)}',start_str)
                start_ts = _dt.strptime (start_str_utc,'%Y-%m-%dT%H:%M:%S%z').timestamp ()
                if start_ts > now_ts:
                    next_ep = ep
                    break
            except Exception:
                continue
        return current,next_ep

    def _add_fast_channels (self ):
        import os as _os ,xbmcaddon as _xad ,xbmcvfs as _xvfs
        _profile =_xvfs .translatePath (_xad .Addon ().getAddonInfo ('profile'))
        if not _os .path .exists (_os .path .join (_profile ,'tokens.json')):
            _log ('_add_fast_channels: nicht eingeloggt – FAST-Kanäle werden nicht angezeigt')
            return 0
        _log ('_add_fast_channels: lade FAST-Kanäle aus folder/193')

        def _fetch_data ():
            return self .api .get_folder_guest ('193')

        def _render (data ):
            count =0
            for block in data .get ('blocks',[]):
                for item in block .get ('content',{}).get ('items',[]):
                    ic =item .get ('itemContent',{})
                    action =(ic .get ('action')or {})
                    target =(action .get ('target')or {})
                    t_type =target .get ('type','')
                    if t_type !='layout':
                        continue
                    vl =(target .get ('value_layout')or {})
                    if vl .get ('type','')!='live':
                        continue
                    vl_id =str (vl .get ('id',''))
                    if not vl_id or not vl_id .startswith ('rtlde_fast'):
                        continue
                    channel_slug =vl_id .replace ('rtlde_','')
                    title =ic .get ('title','')or channel_slug .upper ()
                    live_label =f'[COLOR gold][B]LIVE - {title }[/B][/COLOR]'
                    url =self .build_url ({
                        'mode':'play_live',
                        'channel_id':channel_slug ,
                        'title':urllib .parse .quote_plus (title ),
                    })
                    li =xbmcgui .ListItem (label =live_label )
                    li .setProperty ('IsPlayable','true')
                    local_img =self ._channel_image (channel_slug )
                    thumb =''
                    img_data =ic .get ('image')
                    if img_data and isinstance (img_data ,dict ):
                        thumb =_image_url (img_data ,width =320 ,height =180 ,preferred_ratio ='16:9')
                    art_img =local_img or thumb
                    if art_img :
                        li .setArt ({'thumb':art_img ,'icon':art_img ,'clearlogo':art_img ,'fanart':art_img })
                    li .setInfo ('video',{'title':'\u0001'+live_label ,'plot':ic .get ('description','')or ''})
                    xbmcplugin .addDirectoryItem (self .handle ,url ,li ,False )
                    count +=1
            return count

        try :
            data =_fetch_data ()
            if not data :
                _log ('_add_fast_channels: kein Ergebnis – erneuere Tokens und versuche erneut')
                self .api .auth ._guest_tokens .pop ('guest_bedrock_token',None )
                self .api .auth ._guest_tokens .pop ('guest_bedrock_expires',None )
                self .api .auth ._save_guest_tokens ()
                self .api .auth .get_guest_bedrock_token ()
                data =_fetch_data ()
            if not data :
                _log ('_add_fast_channels: auch nach Token-Erneuerung kein Ergebnis')
                return 0
            count =_render (data )
            _log (f'_add_fast_channels: {count } FAST-Kanäle hinzugefuegt')
            return count
        except Exception as e :
            _log (f'_add_fast_channels error: {e }')
            return 0

    def show_live_channels (self ):
        _log ('show_live_channels')

        import time as _time
        data = self.api.get_epg_grid ()
        if not data:
            xbmcgui.Dialog ().notification ('RTL+','Fehler beim Laden der Senderliste',xbmcgui.NOTIFICATION_ERROR,4000)
            self ._add_sort_methods ()
            xbmcplugin.endOfDirectory (self.handle,succeeded=False)
            return

        items = data.get ('content',{}).get ('items',[])
        if not items:
            for b in data.get ('blocks',[]):
                items += b.get ('content',{}).get ('items',[])

        _log (f'show_live_channels: {len (items)} EPG items via get_epg_grid')

        count = 0
        for item in items:
            li = self._create_live_listitem_epg (item)
            if li:
                count += 1

        fast_count = self._add_fast_channels ()
        count += fast_count

        xbmcplugin.setContent (self.handle,'videos')
        if count == 0:
            _log ('show_live_channels: Keine Kanäle')
            li = xbmcgui.ListItem (label='[COLOR yellow]Bitte erneut öffnen (Anmeldung wird erneuert...)[/COLOR]')
            xbmcplugin.addDirectoryItem (self.handle,'',li,False)
            self ._add_sort_methods ()
            xbmcplugin.endOfDirectory (self.handle,succeeded=True)
        else:
            self ._add_sort_methods ()
            xbmcplugin.endOfDirectory (self.handle,succeeded=True)

    def show_epg (self ):
        _log ('show_epg')
        data = self.api.get_epg_grid ()
        if not data:
            xbmcgui.Dialog ().notification ('RTL+','Fehler beim Laden',xbmcgui.NOTIFICATION_ERROR,4000)
            self ._add_sort_methods ()
            xbmcplugin.endOfDirectory (self.handle,succeeded=False)
            return
        items = data.get ('content',{}).get ('items',[])
        if not items:
            for b in data.get ('blocks',[]):
                items += b.get ('content',{}).get ('items',[])

        added = 0
        for item in items:
            li = self._create_live_listitem_epg (item)
            if li:
                added += 1

        xbmcplugin.setContent (self.handle,'videos')
        self ._add_sort_methods ()
        xbmcplugin.endOfDirectory (self.handle)

    _MIDDLEWARE_BASE ='https://pc.middleware.rtlde.bedrock.tech/6play/v2/platforms/m6group_web/services/rtlplus_root'

    def _middleware_headers (self ):
        from .auth import USER_AGENT ,CLIENT_RELEASE
        return {
        'User-Agent':USER_AGENT ,
        'x-client-release':CLIENT_RELEASE ,
        'x-customer-name':'rtlde',
        'Referer':'https://plus.rtl.de/',
        'Origin':'https://plus.rtl.de',
        }

    def _middleware_image_url (self ,images ,role ='landscape',width =320 ,height =180 ):
        if not images :
            return ''
        role_prio =[role ,'landscape','vignette','banner','square']
        img_id =''
        for r in role_prio :
            for img in images :
                if img .get ('role')==r :
                    img_id =str (img .get ('external_key','')or img .get ('id',''))
                    if img_id :
                        break
            if img_id :
                break
        if not img_id :
            img_id =str (images [0 ].get ('external_key','')or images [0 ].get ('id',''))
        if not img_id :
            return ''
        params =f'auto=avif&blur=0&fit=max&height={height }&interlace=1&quality=100&width={width }'
        path_and_query =f'/v2/images/{img_id }/raw?{params }'
        sig =_sign_image (path_and_query )
        headers_enc =urllib .parse .urlencode ({
        'Referer':'https://plus.rtl.de/',
        'User-Agent':'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/29.0 Chrome/136.0.0.0 Mobile Safari/537.36',
        })
        return f'{IMAGE_CDN }{path_and_query }&hash={sig }|{headers_enc }'

    def _extract_video_id_from_item (self ,item ):
        """Returns (video_id, title, thumb, season, episode, description) or None."""
        import re as _re
        ic =item .get ('itemContent',{})
        if not ic :
            return None
        action =ic .get ('action',{})or {}
        target =action .get ('target',{})or {}
        t_type =target .get ('type','')
        if t_type =='lock':
            target =(target .get ('value_lock',{})or {}).get ('originalTarget',{})or {}
            t_type =target .get ('type','')
        if t_type !='layout':
            return None
        vl =target .get ('value_layout',{})or {}
        if vl .get ('type','')!='video':
            return None
        video_id =vl .get ('id','')
        if not video_id :
            return None

        title_raw =ic .get ('title','')or ''
        extra_title =ic .get ('extraTitle','')or ''
        highlight =ic .get ('highlight','')or ''
        description =ic .get ('description','')or ''
        season_num =0
        episode_num =0
        episode_name =''
        if highlight and '•' in highlight :
            for part in [p .strip ()for p in highlight .split ('•')]:
                pl =part .lower ()
                if pl .startswith ('staffel'):
                    m =_re .search (r'\d+',pl )
                    if m :
                        try :season_num =int (m .group ())
                        except :pass
                elif pl .startswith ('folge'):
                    m =_re .search (r'\d+',pl )
                    if m :
                        try :episode_num =int (m .group ())
                        except :pass
                elif not _re .search (r'\d{2}\.\d{2}\.\d{4}',part ):
                    if part .lower ()not in (title_raw .lower (),'film','serie','show','episode'):
                        episode_name =part .strip ()

        if season_num and episode_num :
            label =f'S{season_num:02d}E{episode_num:02d}'
            if episode_name :
                label +=f' - {episode_name}'
        elif episode_num :
            label =f'Folge {episode_num}'
            if episode_name :
                label +=f' - {episode_name}'
        elif extra_title :
            label =f'{title_raw} - {extra_title}' if title_raw else extra_title
        else :
            label =title_raw or episode_name or video_id

        thumb =_image_url (ic .get ('image',{}),width =320 ,height =180 ,preferred_ratio ='16:9')
        return {
            'video_id':video_id ,
            'label':label ,
            'thumb':thumb ,
            'season':season_num ,
            'episode':episode_num ,
            'description':description ,
            'seo':vl .get ('seo',''),
        }

    def _fetch_episodes_for_series (self ,program_id ,seo =''):
        """Fetches all episodes for a series program_id.
        Returns list of dicts: {video_id, label, thumb, season, episode, description, seo}"""
        import re as _re

        all_blocks =[]
        cur_page =1
        while cur_page <=30 :
            data =self .api .get_program_layout (program_id ,seo =seo ,page =cur_page ,nb_pages =3 )
            if not data :
                break
            new_blocks =data .get ('blocks',[])
            if not new_blocks :
                break
            existing_ids ={b .get ('id','')for b in all_blocks }
            fresh =[b for b in new_blocks if b .get ('id','')not in existing_ids ]
            if not fresh and cur_page >1 :
                break
            all_blocks .extend (fresh )
            has_more =(data .get ('pagination',{}).get ('hasMore',False )
                       or data .get ('hasMore',False ))
            total_pages =data .get ('pagination',{}).get ('totalPages',1 )or 1
            if not has_more and cur_page >=total_pages :
                break
            cur_page +=1

        direct_seasons =[]
        concurrent_seasons =[]

        for block in all_blocks :
            bc =block .get ('content',{})
            btitle_obj =bc .get ('title')or {}
            btitle =(btitle_obj .get ('short','')or btitle_obj .get ('long','')
                     if isinstance (btitle_obj ,dict )else str (btitle_obj or ''))
            block_id =block .get ('id','')
            if btitle and block_id and self ._is_season_block (btitle ):
                direct_seasons .append ((btitle ,block_id ,bc .get ('items',[])or []))
            alt =block .get ('alternativeContent')
            if alt and isinstance (alt ,dict ):
                for cb in (alt .get ('concurrentBlocks')or []):
                    if cb and isinstance (cb ,dict ):
                        cb_title =cb .get ('title','')
                        cb_id =cb .get ('id','')
                        if cb_title and cb_id :
                            concurrent_seasons .append (
                                (cb_title ,cb_id ,cb .get ('content',{}).get ('items',[])or []))

        all_seasons =direct_seasons +concurrent_seasons

        episodes =[]
        if all_seasons :
            seen_ids =set ()
            for s_title ,s_block_id ,_ in all_seasons :
                if s_block_id in seen_ids :
                    continue
                seen_ids .add (s_block_id )
                items =self ._fetch_all_block_items (program_id ,s_block_id ,seo =seo )
                for item in items :
                    ep =self ._extract_video_id_from_item (item )
                    if ep :
                        episodes .append (ep )
            return episodes

        content_blocks =[]
        for block in all_blocks :
            bc =block .get ('content',{})
            btitle_obj =bc .get ('title')or {}
            btitle =(btitle_obj .get ('short','')or btitle_obj .get ('long','')
                     if isinstance (btitle_obj ,dict )else str (btitle_obj or ''))
            if 'empfehlung' in btitle .lower ()or 'recommendation' in btitle .lower ():
                continue
            items =bc .get ('items',[])
            if items :
                content_blocks .append (items )

        for items in content_blocks :
            for item in items :
                ep =self ._extract_video_id_from_item (item )
                if ep :
                    episodes .append (ep )

        return episodes

    def _jw_get_device_id (self ):
        import json ,uuid ,base64 ,os
        import xbmcaddon ,xbmcvfs
        _profile =xbmcvfs .translatePath (xbmcaddon .Addon ().getAddonInfo ('profile'))
        _jw_id_file =os .path .join (_profile ,'jw_device_id.json')
        _jw_id =''
        try :
            if os .path .exists (_jw_id_file ):
                with open (_jw_id_file ,'r')as _f :
                    _jw_id =json .load (_f ).get ('id','')
        except Exception :
            pass
        if not _jw_id :
            raw =uuid .uuid4 ().bytes +uuid .uuid4 ().bytes [:8]
            _jw_id =base64 .b64encode (raw ).decode ().rstrip ('=').replace ('+','').replace ('/','')[:22]
            try :
                os .makedirs (_profile ,exist_ok =True )
                with open (_jw_id_file ,'w')as _f :
                    json .dump ({'id':_jw_id },_f )
            except Exception :
                pass
        return _jw_id

    def _jw_fetch_all_titles (self ,obj_type ='SHOW',progress_cb =None ):
        """Fetches all RTL+ titles of obj_type ('SHOW' or 'MOVIE') from JustWatch.
        Returns list of dicts: {title, program_id, seo, thumb, year, plot, obj_type}
        progress_cb(done, total, label) – optional callback for progress updates."""
        import requests ,re as _re ,uuid
        from concurrent .futures import ThreadPoolExecutor ,as_completed

        JW_GQL ='https://apis.justwatch.com/graphql'
        JW_IMG ='https://images.justwatch.com'
        PER_PAGE =40

        _jw_id =self ._jw_get_device_id ()
        _pv_id =str (uuid .uuid4 ())
        _page_label ='Serien'if obj_type =='SHOW'else 'Filme'

        QUERY ="""query GetPopularTitles($country: Country!, $first: Int! = 70, $format: ImageFormat, $language: Language!, $after: String, $popularTitlesFilter: TitleFilter, $popularTitlesSortBy: PopularTitlesSorting! = POPULAR, $profile: PosterProfile, $sortRandomSeed: Int! = 0, $watchNowFilter: WatchNowOfferFilter!, $offset: Int = 0) {
  popularTitles(country: $country, filter: $popularTitlesFilter, first: $first, sortBy: $popularTitlesSortBy, sortRandomSeed: $sortRandomSeed, offset: $offset, after: $after) {
    __typename
    edges { cursor node { ...PopularTitleGraphql __typename } __typename }
    pageInfo { startCursor endCursor hasPreviousPage hasNextPage __typename }
    totalCount
  }
}
fragment PopularTitleGraphql on MovieOrShow {
  __typename id objectId objectType
  content(country: $country, language: $language) {
    title fullPath originalReleaseYear shortDescription
    posterUrl(profile: $profile, format: $format)
    isReleased runtime __typename
  }
  freeOffersCount: offerCount(country: $country, platform: WEB, filter: {monetizationTypes: [FREE, ADS]})
  watchNowOffer(country: $country, platform: WEB, filter: $watchNowFilter) { ...WatchNowOffer __typename }
}
fragment WatchNowOffer on Offer {
  __typename id standardWebURL
  package { id packageId clearName technicalName __typename }
  presentationType monetizationType
}"""

        def _make_headers (page ):
            _page_path ='/de/Anbieter/rtl-plus/{}?sort_by=title&sort_asc=true&page={}'.format (_page_label ,page )
            return {
                'Content-Type':'application/json',
                'Accept':'*/*',
                'Origin':'https://www.justwatch.com',
                'Referer':'https://www.justwatch.com/',
                'app-version':'3.13.0-web-web',
                'device-id':_jw_id ,
                'sg':f'c=DE&l=de&pv={_pv_id}&d={_jw_id}&p=3.13.0-web-web&pa={_page_path}&e=',
                'User-Agent':'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/29.0 Chrome/136.0.0.0 Mobile Safari/537.36',
                'accept-language':'de-DE,de;q=0.9,en-US;q=0.7,en;q=0.6',
            }

        def _make_payload (offset ):
            return {
                'operationName':'GetPopularTitles',
                'variables':{
                    'first':PER_PAGE ,
                    'popularTitlesSortBy':'ALPHABETICAL',
                    'sortRandomSeed':0,
                    'offset':offset ,
                    'after':None ,
                    'popularTitlesFilter':{
                        'ageCertifications':[],'excludeGenres':[],'excludeProductionCountries':[],
                        'objectTypes':[obj_type ],'productionCountries':[],'subgenres':[],'genres':[],
                        'packages':['tvn'],'excludeIrrelevantTitles':False ,
                        'presentationTypes':[],'monetizationTypes':[],'searchQuery':'',
                    },
                    'watchNowFilter':{'packages':['tvn'],'monetizationTypes':[]},
                    'language':'de','country':'DE','format':'JPG','profile':'S332',
                },
                'query':QUERY ,
            }

        def _resolve_redirect (rtl_url ):
            try :
                sess =self .api ._get_session ()
                resp =sess .get (rtl_url ,allow_redirects =False ,timeout =10 )
                loc =resp .headers .get ('Location','')or resp .headers .get ('location','')
                if loc :
                    pm =_re .search (r'-p_(\d+)',loc )
                    sm =_re .match (r'^/?([^/?]+)-p_\d+',loc .split ('?')[0 ])
                    if pm :
                        return pm .group (1 ),sm .group (1 )if sm else ''
            except Exception as _e :
                _log (f'_jw_fetch_all_titles redirect error {rtl_url}: {_e}')
            return '',''

        all_titles =[]
        page =1
        total =None

        while True :
            offset =(page -1 )*PER_PAGE
            try :
                resp =requests .post (JW_GQL ,headers =_make_headers (page ),
                                      json =_make_payload (offset ),timeout =20 )
                resp .raise_for_status ()
                data =resp .json ()
            except Exception as e :
                _log (f'_jw_fetch_all_titles page {page} error: {e}')
                break

            pt =data .get ('data',{}).get ('popularTitles',{})
            edges =pt .get ('edges',[])
            if total is None :
                total =pt .get ('totalCount',0)

            _log (f'_jw_fetch_all_titles {obj_type} page={page} edges={len(edges)} total={total}')

            new_fmt_urls =[]
            for ed in edges :
                offer =(ed .get ('node',{})or {}).get ('watchNowOffer')or {}
                rtl_url =offer .get ('standardWebURL','')
                if not rtl_url or 'plus.rtl.de' not in rtl_url :
                    continue
                path =rtl_url .replace ('https://plus.rtl.de','')
                if not _re .search (r'-p_(\d+)',path ):
                    new_fmt_urls .append (rtl_url )

            redirect_cache ={}
            if new_fmt_urls :
                unique_urls =list (dict .fromkeys (new_fmt_urls ))
                with ThreadPoolExecutor (max_workers =5 )as pool :
                    fut_map ={pool .submit (_resolve_redirect ,u ):u for u in unique_urls }
                    for fut in as_completed (fut_map ):
                        u =fut_map [fut ]
                        pid ,res_seo =fut .result ()
                        if pid :
                            redirect_cache [u ]=(pid ,res_seo )

            for ed in edges :
                node =ed .get ('node',{})
                content =node .get ('content',{})
                offer =node .get ('watchNowOffer')or {}
                title =content .get ('title','')
                year =content .get ('originalReleaseYear','')
                plot =content .get ('shortDescription','')or ''
                poster_tpl =content .get ('posterUrl','')
                rtl_url =offer .get ('standardWebURL','')
                if not rtl_url or 'plus.rtl.de' not in rtl_url :
                    continue
                path =rtl_url .replace ('https://plus.rtl.de','')
                pid_m =_re .search (r'-p_(\d+)',path )
                seo_m =_re .match (r'^/([^/]+)-p_\d+',path )
                program_id =pid_m .group (1 )if pid_m else ''
                seo =seo_m .group (1 )if seo_m else ''
                if not program_id :
                    program_id ,seo =redirect_cache .get (rtl_url ,('',''))
                if not program_id :
                    continue
                thumb =''
                if poster_tpl :
                    thumb =JW_IMG +poster_tpl .replace ('{profile}','s332').replace ('{format}','jpg')
                all_titles .append ({
                    'title':title ,'program_id':program_id ,'seo':seo ,
                    'thumb':thumb ,'year':year ,'plot':plot ,'obj_type':obj_type ,
                })

            if progress_cb and total :
                done =min (page *PER_PAGE ,total )
                label =f'{_page_label}: {done}/{total}'
                progress_cb (done ,total ,label )

            if not pt .get ('pageInfo',{}).get ('hasNextPage'):
                break
            page +=1

        return all_titles

    def show_jw_az (self ,obj_type ='SHOW',page =1 ):
        import requests ,uuid ,os ,json ,time as _time
        import xbmcaddon ,xbmcvfs
        _log (f'show_jw_az type={obj_type } page={page }')

        JW_GQL ='https://apis.justwatch.com/graphql'
        _page_label ='Serien'if obj_type =='SHOW'else 'Filme'
        _page_path ='/de/Anbieter/rtl-plus/{}?sort_by=title&sort_asc=true&page={}'.format (_page_label ,page )

        _profile =xbmcvfs .translatePath (xbmcaddon .Addon ().getAddonInfo ('profile'))
        _jw_id_file =os .path .join (_profile ,'jw_device_id.json')
        _jw_id =''
        try :
            if os .path .exists (_jw_id_file ):
                with open (_jw_id_file ,'r')as _f :
                    _jw_id =json .load (_f ).get ('id','')
        except Exception :
            pass
        if not _jw_id :
            import base64 ,struct
            raw =uuid .uuid4 ().bytes +uuid .uuid4 ().bytes [:8]
            _jw_id =base64 .b64encode (raw ).decode ().rstrip ('=').replace ('+','').replace ('/','')[:22]
            try :
                os .makedirs (_profile ,exist_ok =True )
                with open (_jw_id_file ,'w')as _f :
                    json .dump ({'id':_jw_id },_f )
            except Exception :
                pass
        _pv_id =str (uuid .uuid4 ())

        JW_HEADERS ={
            'Content-Type':'application/json',
            'Accept':'*/*',
            'Origin':'https://www.justwatch.com',
            'Referer':'https://www.justwatch.com/',
            'app-version':'3.13.0-web-web',
            'device-id':_jw_id ,
            'sg':f'c=DE&l=de&pv={_pv_id }&d={_jw_id }&p=3.13.0-web-web&pa={_page_path }&e=',
            'User-Agent':'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/29.0 Chrome/136.0.0.0 Mobile Safari/537.36',
            'accept-language':'de-DE,de;q=0.9,en-US;q=0.7,en;q=0.6',
        }
        PER_PAGE =40
        offset =(page -1 )*PER_PAGE

        QUERY ="""query GetPopularTitles($country: Country!, $first: Int! = 70, $format: ImageFormat, $language: Language!, $after: String, $popularTitlesFilter: TitleFilter, $popularTitlesSortBy: PopularTitlesSorting! = POPULAR, $profile: PosterProfile, $sortRandomSeed: Int! = 0, $watchNowFilter: WatchNowOfferFilter!, $offset: Int = 0) {
  popularTitles(
    country: $country
    filter: $popularTitlesFilter
    first: $first
    sortBy: $popularTitlesSortBy
    sortRandomSeed: $sortRandomSeed
    offset: $offset
    after: $after
  ) {
    __typename
    edges {
      cursor
      node { ...PopularTitleGraphql __typename }
      __typename
    }
    pageInfo { startCursor endCursor hasPreviousPage hasNextPage __typename }
    totalCount
  }
}
fragment PopularTitleGraphql on MovieOrShow {
  __typename id objectId objectType
  content(country: $country, language: $language) {
    title fullPath originalReleaseYear shortDescription
    posterUrl(profile: $profile, format: $format)
    isReleased runtime __typename
  }
  freeOffersCount: offerCount(country: $country, platform: WEB, filter: {monetizationTypes: [FREE, ADS]})
  watchNowOffer(country: $country, platform: WEB, filter: $watchNowFilter) {
    ...WatchNowOffer
    __typename
  }
}
fragment WatchNowOffer on Offer {
  __typename id standardWebURL
  package { id packageId clearName technicalName __typename }
  presentationType monetizationType
}"""

        payload ={
            'operationName':'GetPopularTitles',
            'variables':{
                'first':PER_PAGE ,
                'popularTitlesSortBy':'ALPHABETICAL',
                'sortRandomSeed':0,
                'offset':offset ,
                'after':None ,
                'popularTitlesFilter':{
                    'ageCertifications':[],
                    'excludeGenres':[],
                    'excludeProductionCountries':[],
                    'objectTypes':[obj_type ],
                    'productionCountries':[],
                    'subgenres':[],
                    'genres':[],
                    'packages':['tvn'],
                    'excludeIrrelevantTitles':False ,
                    'presentationTypes':[],
                    'monetizationTypes':[],
                    'searchQuery':'',
                },
                'watchNowFilter':{'packages':['tvn'],'monetizationTypes':[]},
                'language':'de',
                'country':'DE',
                'format':'JPG',
                'profile':'S332',
            },
            'query':QUERY ,
        }

        try :
            resp =requests .post (JW_GQL ,headers =JW_HEADERS ,json =payload ,timeout =20 )
            resp .raise_for_status ()
            data =resp .json ()
        except Exception as e :
            _log (f'show_jw_az error: {e }')
            xbmcgui .Dialog ().notification ('RTL+',f'JustWatch Fehler: {e }',xbmcgui .NOTIFICATION_ERROR ,4000 )
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
            return

        pt =data .get ('data',{}).get ('popularTitles',{})
        edges =pt .get ('edges',[])
        total =pt .get ('totalCount',0)
        page_info =pt .get ('pageInfo',{})

        _log (f'show_jw_az: totalCount={total } edges={len (edges )} page={page }')

        import re as _re
        from concurrent .futures import ThreadPoolExecutor ,as_completed
        JW_IMG ='https://images.justwatch.com'

        def _resolve_redirect (rtl_url ):
            try :
                sess =self .api ._get_session ()
                resp =sess .get (rtl_url ,allow_redirects =False ,timeout =10 )
                loc =resp .headers .get ('Location','')or resp .headers .get ('location','')
                if loc :
                    pm =_re .search (r'-p_(\d+)',loc )
                    sm =_re .match (r'^/?([^/?]+)-p_\d+',loc .split ('?')[0 ])
                    if pm :
                        return pm .group (1 ),sm .group (1 )if sm else ''
            except Exception as _e :
                _log (f'show_jw_az redirect resolve error {rtl_url }: {_e }')
            return '',''

        new_fmt_urls =[]
        for ed in edges :
            offer =(ed .get ('node',{})or {}).get ('watchNowOffer')or {}
            rtl_url =offer .get ('standardWebURL','')
            if not rtl_url or 'plus.rtl.de' not in rtl_url :
                continue
            path =rtl_url .replace ('https://plus.rtl.de','')
            if not _re .search (r'-p_(\d+)',path ):
                new_fmt_urls .append (rtl_url )

        redirect_cache ={}
        if new_fmt_urls :
            unique_urls =list (dict .fromkeys (new_fmt_urls ))
            with ThreadPoolExecutor (max_workers =5 )as pool :
                fut_map ={pool .submit (_resolve_redirect ,u ):u for u in unique_urls }
                for fut in as_completed (fut_map ):
                    u =fut_map [fut ]
                    pid ,resolved_seo =fut .result ()
                    if pid :
                        redirect_cache [u ]=(pid ,resolved_seo )

        xbmcplugin .setContent (self .handle ,'tvshows'if obj_type =='SHOW'else 'movies')

        for ed in edges :
            node =ed .get ('node',{})
            content =node .get ('content',{})
            offer =node .get ('watchNowOffer')or {}

            title =content .get ('title','')
            year =content .get ('originalReleaseYear','')
            plot =content .get ('shortDescription','')or ''
            poster_tpl =content .get ('posterUrl','')
            rtl_url =offer .get ('standardWebURL','')

            if not rtl_url or 'plus.rtl.de' not in rtl_url :
                continue

            thumb =''
            if poster_tpl :
                thumb =JW_IMG +poster_tpl .replace ('{profile}','s332').replace ('{format}','jpg')

            path =rtl_url .replace ('https://plus.rtl.de','')
            pid_m =_re .search (r'-p_(\d+)',path )
            seo_m =_re .match (r'^/([^/]+)-p_\d+',path )
            program_id =pid_m .group (1 )if pid_m else ''
            seo =seo_m .group (1 )if seo_m else ''

            if not program_id :
                program_id ,seo =redirect_cache .get (rtl_url ,('',''))

            if not program_id :
                continue

            label =f'{title } ({year })'if year else title

            li =xbmcgui .ListItem (label =label )
            if thumb :
                li .setArt ({'thumb':thumb ,'poster':thumb ,'icon':thumb ,'fanart':thumb })
            li .setInfo ('video',{'title':label ,'plot':plot ,'year':int (year )if year else 0 ,
                'mediatype':'tvshow'if obj_type =='SHOW'else 'movie'})

            if obj_type =='MOVIE':
                li .setProperty ('IsPlayable','true')
                url =self .build_url ({
                    'mode':'play_program',
                    'program_id':program_id ,
                    'seo':seo ,
                    'title':label ,
                })
                xbmcplugin .addDirectoryItem (self .handle ,url ,li ,False )
            else :
                url =self .build_url ({
                    'mode':'show_program',
                    'program_id':program_id ,
                    'seo':seo ,
                })
                xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )

        if page_info .get ('hasNextPage'):
            next_page =page +1
            type_label ='Serien'if obj_type =='SHOW'else 'Filme'
            next_label =f'[COLOR gold]>> Seite {next_page } ({(next_page -1)*PER_PAGE +1}-{min (next_page *PER_PAGE ,total )} von {total })[/COLOR]'
            li =xbmcgui .ListItem (label =next_label )
            url =self .build_url ({'mode':'show_jw_az','obj_type':obj_type ,'page':str (next_page )})
            xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )

        self ._add_sort_methods ()
        xbmcplugin .endOfDirectory (self .handle ,succeeded =True )

    def show_az (self ):
        import os
        import requests
        import xbmcaddon
        import xbmcvfs
        _addon =xbmcaddon .Addon ()
        _addon_path =xbmcvfs .translatePath (_addon .getAddonInfo ('path'))

        def _alpha_img (letter ):
            fname =letter if letter !='#'else '0-9'
            path =os .path .join (_addon_path ,'resources','media','alphabet',f'{fname }.jpg')
            if os .path .exists (path ):
                return path
            return os .path .join (_addon_path ,'resources','media','icon.png')

        letter_counts ={}
        import json ,os ,time
        _addon2 =xbmcaddon .Addon ()
        _profile2 =xbmcvfs .translatePath (_addon2 .getAddonInfo ('profile'))
        _letters_cache =os .path .join (_profile2 ,'az_cache_letters.json')
        _cache_ok =False
        if os .path .exists (_letters_cache ):
            try :
                with open (_letters_cache ,'r',encoding ='utf-8')as _f :
                    _cd =json .load (_f )
                if time .time ()-_cd .get ('ts',0 )<86400 :
                    letter_counts =_cd .get ('counts',{})
                    _cache_ok =True
                    _log ('A-Z first-letters cache hit')
            except Exception as _e :
                _log (f'A-Z first-letters cache load error: {_e }')
        if not _cache_ok :
            try :
                resp =requests .get (
                f'{self ._MIDDLEWARE_BASE }/programs/first-letters',
                headers =self ._middleware_headers (),
                params ={'csa':6 },
                timeout =15 ,
                )
                resp .raise_for_status ()
                letter_counts =resp .json ()or {}
                try :
                    xbmcvfs .mkdirs (_profile2 )
                    with open (_letters_cache ,'w',encoding ='utf-8')as _f :
                        json .dump ({'ts':time .time (),'counts':letter_counts },_f )
                except Exception as _e :
                    _log (f'A-Z first-letters cache save error: {_e }')
            except Exception as e :
                _log (f'A-Z first-letters error: {e }')

        letters =['#']+list ('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        for letter in letters :
            label ='0-9 / #'if letter =='#'else letter
            count =letter_counts .get ('@',0 )if letter =='#'else letter_counts .get (letter .lower (),0 )
            if count :
                label =f'{label }  ({count })'
            url =self .build_url ({'mode':'show_az_letter','letter':letter })
            li =xbmcgui .ListItem (label =label )
            li .setProperty ('IsPlayable','false')
            img =_alpha_img (letter )
            li .setArt ({'thumb':img ,'icon':img })
            li .setInfo ('video',{'title':label })
            xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )

        xbmcplugin .setContent (self .handle ,'videos')
        self ._add_sort_methods ()
        xbmcplugin .endOfDirectory (self .handle )

    def _az_cache_path (self ,letter ):
        import xbmcaddon ,xbmcvfs ,os
        profile =xbmcvfs .translatePath (xbmcaddon .Addon ().getAddonInfo ('profile'))
        xbmcvfs .mkdirs (profile )
        safe ='0-9'if letter =='#'else letter .upper ()
        return os .path .join (profile ,f'az_cache_{safe }.json')

    def _az_cache_load (self ,letter ):
        import json ,os ,time
        path =self ._az_cache_path (letter )
        if not os .path .exists (path ):
            return None
        try :
            with open (path ,'r',encoding ='utf-8')as f :
                data =json .load (f )
            if time .time ()-data .get ('ts',0 )<86400 :
                _log (f'A-Z cache hit for {letter }')
                return data ['programs']
        except Exception as e :
            _log (f'A-Z cache load error: {e }')
        return None

    def _az_cache_save (self ,letter ,programs ):
        import json ,time
        path =self ._az_cache_path (letter )
        try :
            with open (path ,'w',encoding ='utf-8')as f :
                json .dump ({'ts':time .time (),'programs':programs },f )
            _log (f'A-Z cache saved for {letter } ({len (programs )} items)')
        except Exception as e :
            _log (f'A-Z cache save error: {e }')

    def show_az_letter (self ,letter ):
        _log (f'show_az_letter letter={letter }')
        import requests

        all_programs =self ._az_cache_load (letter )

        if all_programs is None :
            first_letter =''if letter =='#'else letter .lower ()
            all_programs =[]
            offset =0
            limit =100

            try :
                while True :
                    params ={'csa':6 ,'offset':offset ,'limit':limit ,'with':'rights'}
                    if first_letter :
                        params ['firstLetter']=first_letter
                    resp =requests .get (
                    f'{self ._MIDDLEWARE_BASE }/programs',
                    headers =self ._middleware_headers (),
                    params =params ,
                    timeout =20 ,
                    )
                    resp .raise_for_status ()
                    page =resp .json ()
                    if not isinstance (page ,list )or not page :
                        break
                    all_programs .extend (page )
                    if len (page )<limit :
                        break
                    offset +=limit
                    if offset >5000 :
                        break
                self ._az_cache_save (letter ,all_programs )
            except Exception as e :
                _log (f'A-Z middleware error: {e }')
                xbmcgui .Dialog ().notification ('RTL+',f'Fehler: {e }',xbmcgui .NOTIFICATION_ERROR ,4000 )
                self ._add_sort_methods ()
                xbmcplugin .endOfDirectory (self .handle ,succeeded =False )
                return

        if not all_programs :
            xbmcgui .Dialog ().notification ('RTL+','Keine Programme gefunden',xbmcgui .NOTIFICATION_INFO ,3000 )
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle )
            return

        filtered =[]
        for p in all_programs :
            title =str (p .get ('title')or '').strip ()
            if not title :
                continue
            first_char =title [0 ].upper ()
            if letter =='#':
                if first_char .isalpha ():
                    continue
            else :
                if first_char !=letter .upper ():
                    continue
            filtered .append (p )

        filtered .sort (key =lambda p :str (p .get ('title')or '').lower ())

        total =0
        seen_ids =set ()

        for p in filtered :
            program_id =str (p .get ('id',''))
            if not program_id or program_id in seen_ids :
                continue
            seen_ids .add (program_id )

            title =str (p .get ('title')or '').strip ()
            description =str (p .get ('description')or p .get ('summary')or '').strip ()
            images =p .get ('images')or []
            thumb =self ._middleware_image_url (images ,'landscape',320 ,180 )
            poster =self ._middleware_image_url (images ,'vignette',213 ,320 )
            fanart =self ._middleware_image_url (images ,'landscape',960 ,540 )

            program_seo =str (p .get ('seo','')or '').strip ()
            url =self .build_url ({'mode':'show_program','program_id':program_id ,'seo':program_seo })
            li =xbmcgui .ListItem (label =title )
            li .setProperty ('IsPlayable','false')
            art ={}
            if thumb :art ['thumb']=thumb
            if fanart :art ['fanart']=fanart
            if poster :art ['poster']=poster
            if art :li .setArt (art )
            li .setInfo ('video',{'title':title ,'plot':description ,'mediatype':'tvshow'})
            xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )
            total +=1

        if total ==0 :
            li =xbmcgui .ListItem (label =f'[Keine Inhalte unter {letter }]')
            xbmcplugin .addDirectoryItem (self .handle ,'',li ,False )

        xbmcplugin .setContent (self .handle ,'tvshows')
        self ._add_sort_methods ()
        xbmcplugin .endOfDirectory (self .handle )

    def show_search (self ,query =''):
        from .evil.constants import SEARCH_HISTORY_FILE
        from .evil.util import load_json ,save_json

        def _load_history ():
            try :
                return load_json (SEARCH_HISTORY_FILE )
            except Exception :
                return []

        def _save_history (q ):
            history =_load_history ()
            history =[h for h in history if h .lower ()!=q .lower ()]
            history .insert (0 ,q )
            save_json (SEARCH_HISTORY_FILE ,history [:20 ],pretty =True )

        def _do_search (q ,from_history =False ):
            _log (f'search query={q }')
            import requests
            from .api import LAYOUT_BASE ,RTL_WEB
            headers =self .api ._headers (x_location =f'{RTL_WEB }/suche?query={q }')
            try :
                resp =requests .get (
                    f'{LAYOUT_BASE }/frontspace/search/layout',
                    headers =headers ,
                    params ={'blockPage':1 ,'nbPages':2 ,'query':q },
                    timeout =20
                )
                resp .raise_for_status ()
                data =resp .json ()
            except Exception as e :
                _log (f'Search error: {e }')
                data =None
            if not data :
                xbmcgui .Dialog ().notification ('RTL+','Keine Ergebnisse',xbmcgui .NOTIFICATION_INFO ,3000 )
                self ._add_sort_methods ()
                xbmcplugin .endOfDirectory (self .handle )
                return
            if not from_history :
                _save_history (q )
            self ._render_layout (data ,next_params ={'mode':'search','query':q })

        if query :
            decoded_query =urllib .parse .unquote_plus (query )
            history =_load_history ()
            from_history =any (h .lower ()==decoded_query .lower ()for h in history )
            _do_search (decoded_query ,from_history =from_history )
            return

        history =_load_history ()

        new_url =self .build_url ({'mode':'search_new'})
        li_new =xbmcgui .ListItem (label ='[COLOR gold][B]» Neue Suche...[/B][/COLOR]')
        li_new .setArt ({'icon':self._img ('basesearch.png')})
        li_new .setInfo ('video',{'title':'Neue Suche'})
        xbmcplugin .addDirectoryItem (self .handle ,new_url ,li_new ,False )

        if history :
            sep =xbmcgui .ListItem (label ='[COLOR gray]── Suchverlauf ──[/COLOR]')
            sep .setProperty ('IsPlayable','false')
            xbmcplugin .addDirectoryItem (self .handle ,'',sep ,False )

            for h in history :
                url =self .build_url ({'mode':'search','query':h })
                li =xbmcgui .ListItem (label =h )
                li .setArt ({'icon':self._img ('basesearch.png')})
                li .setInfo ('video',{'title':h })
                li .setProperty ('IsPlayable','false')
                xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )

            clr_url =self .build_url ({'mode':'search_clear_history'})
            li_clr =xbmcgui .ListItem (label ='[COLOR red]Suchverlauf löschen[/COLOR]')
            li_clr .setInfo ('video',{'title':'Suchverlauf löschen'})
            xbmcplugin .addDirectoryItem (self .handle ,clr_url ,li_clr ,False )

        xbmcplugin .setContent (self .handle ,'files')
        self ._add_sort_methods ()
        xbmcplugin .endOfDirectory (self .handle )

    def show_search_new (self ):
        kb =xbmc .Keyboard ('','RTL+ Suche')
        kb .doModal ()
        if not kb .isConfirmed ()or not kb .getText ():
            self ._add_sort_methods ()
            xbmcplugin .endOfDirectory (self .handle )
            return
        query =kb .getText ()
        url =self .build_url ({'mode':'search','query':query })
        xbmc .executebuiltin (f'Container.Update({url })')

    def search_clear_history (self ):
        from .evil.constants import SEARCH_HISTORY_FILE
        from .evil.util import save_json
        save_json (SEARCH_HISTORY_FILE ,[],pretty =True )
        xbmcgui .Dialog ().notification ('RTL+','Suchverlauf gelöscht',xbmcgui .NOTIFICATION_INFO ,2000 )
        xbmc .executebuiltin ('Container.Refresh')

    def _render_layout (self ,data ,next_params =None ,skip_block_titles =None ):
        blocks =data .get ('blocks',[])
        skip_block_titles =[s .lower ()for s in (skip_block_titles or [])]

        all_items =[]
        for block in blocks :
            content =block .get ('content',{})
            block_title_obj =content .get ('title')or {}
            if isinstance (block_title_obj ,dict ):
                block_title =block_title_obj .get ('short','')or block_title_obj .get ('long','')or ''
            else :
                block_title =str (block_title_obj )
            if skip_block_titles and any (s in block_title .lower ()for s in skip_block_titles ):
                continue
            all_items .extend (content .get ('items',[]))

        def _is_live_item (item ):
            ic =item .get ('itemContent',{})or {}
            action =ic .get ('action',{})or {}
            target =action .get ('target',{})or {}
            t_type =target .get ('type','')
            if t_type =='lock':
                target =(target .get ('value_lock',{})or {}).get ('originalTarget',{})or {}
                t_type =target .get ('type','')
            if t_type =='layout':
                vl =target .get ('value_layout',{})or {}
                return vl .get ('type','')in ('live','channel')
            if t_type =='player':
                vp =target .get ('value_player',{})or {}
                return vp .get ('type','')in ('live','livetv','channel','event','live_event','event_stream')
            return False

        live_items =[i for i in all_items if _is_live_item (i )]
        other_items =[i for i in all_items if not _is_live_item (i )]
        ordered =live_items +other_items

        total =0
        for item in ordered :
            if self ._add_item (item ):
                total +=1

        if total ==0 :
            li =xbmcgui .ListItem (label ='[Keine Inhalte]')
            xbmcplugin .addDirectoryItem (self .handle ,'',li ,False )

        xbmcplugin .setContent (self .handle ,'videos')
        self ._add_sort_methods ()
        xbmcplugin .endOfDirectory (self .handle )

    def _add_item (self ,item ):
        try :
            item_type =item .get ('itemType','')
            ic =item .get ('itemContent',{}
            )
            if not ic :
                return False

            title =ic .get ('title','')or ''
            extra_title =ic .get ('extraTitle','')or ''
            highlight =ic .get ('highlight','')or ''
            extra_details =ic .get ('extraDetails','')or ''
            details =ic .get ('details','')or ''
            description =ic .get ('description','')or ''

            action_tmp =ic .get ('action',{})or {}
            vl_tmp =(action_tmp .get ('target',{})or {}).get ('value_layout',{})or {}
            seo_raw =vl_tmp .get ('seo','')
            seo_title =seo_raw .replace ('-',' ').title ()if seo_raw else ''

            if title and extra_title :
                full_title =f'{title } - {extra_title }'
            elif title :
                full_title =title
            elif extra_title :
                full_title =extra_title
            elif seo_title :
                full_title =seo_title
            elif highlight :
                parts =[p .strip ()for p in highlight .split ('•')]
                full_title =parts [0 ]if parts else highlight
            else :
                return False

            import re as _re
            episode_label =full_title
            season_num =0
            episode_num =0
            episode_name =''
            air_date =''

            if highlight and '•'in highlight :
                parts =[p .strip ()for p in highlight .split ('•')]

                for part in parts :
                    pl =part .lower ().strip ()
                    if pl .startswith ('staffel'):
                        m =_re .search (r'\d+',pl )
                        if m :
                            try :season_num =int (m .group ())
                            except :pass
                    elif pl .startswith ('folge'):
                        m =_re .search (r'\d+',pl )
                        if m :
                            try :episode_num =int (m .group ())
                            except :pass
                    elif _re .search (r'\d{2}\.\d{2}\.\d{4}',part ):
                        air_date =part .strip ()
                    elif _re .fullmatch (r'\d{4}-\d{2}',pl ):
                        pass
                    else :
                        if part .strip ().lower ()!=title .lower ():
                            episode_name =part .strip ()

                if episode_num and not season_num and (air_date or episode_name ):
                    parts_label =[f'Folge {episode_num }']
                    if air_date :
                        parts_label .append (air_date )
                    if episode_name :
                        parts_label .append (episode_name )
                    episode_label =' • '.join (parts_label )
                    full_title =episode_label

                elif season_num and episode_num :
                    if episode_name :
                        episode_label =f'S{season_num :02d}E{episode_num :02d} - {episode_name }'
                    else :
                        episode_label =f'S{season_num :02d}E{episode_num :02d}'
                    full_title =episode_label

                elif episode_num and not season_num :
                    episode_label =f'Folge {episode_num }'
                    if episode_name :
                        episode_label +=f' - {episode_name }'
                    full_title =episode_label

            if not description :
                parts =[]
                if highlight :parts .append (highlight )
                if extra_details :parts .append (extra_details )
                description =' | '.join (parts )

            genre =''
            year =0
            if highlight and '•'in highlight :
                hparts =[p .strip ()for p in highlight .split ('•')]
                genre_parts =[p for p in hparts if p .lower ()not in ('film','serie','show','episode')]
                genre =', '.join (genre_parts )if genre_parts else ''
            if extra_details :
                for part in extra_details .split ('•'):
                    part =part .strip ()
                    if part .isdigit ()and len (part )==4 :
                        try :year =int (part )
                        except :pass
            if not genre and details :
                genre =details

            thumb =_image_url (ic .get ('image',{}),width =320 ,height =180 ,preferred_ratio ='16:9')
            fanart =_image_url (ic .get ('secondaryImage',{}),width =640 ,height =360 ,preferred_ratio ='16:9')or thumb
            poster =_image_url (ic .get ('image',{}),width =213 ,height =320 ,preferred_ratio ='2:3')or thumb

            action =ic .get ('action',{})or {}
            target =action .get ('target',{})or {}
            t_type =target .get ('type','')

            is_premium_content =False
            if t_type =='lock':
                is_premium_content =True
                target =(target .get ('value_lock',{})or {}).get ('originalTarget',{})or {}
                t_type =target .get ('type','')

            if is_premium_content and _get_premium_status () not in ('Premium','Basic'):
                full_title =_premium_title (full_title )
                episode_label =_premium_title (episode_label )if episode_label else full_title

            if t_type =='layout':
                vl =target .get ('value_layout',{})or {}
                layout_type =vl .get ('type','')
                layout_id =vl .get ('id','')

                if not layout_id :
                    return False

                if layout_type =='video':
                    vl_seo =vl .get ('seo','')
                    parent =vl .get ('parent',{})or {}
                    parent_id =str (parent .get ('id',''))
                    parent_seo =parent .get ('seo','')
                    series_name =title if title and (season_num or episode_num )else ''
                    vod_params ={
                    'title':episode_label or full_title ,
                    'video_seo':vl_seo ,
                    'program_seo':parent_seo ,
                    'program_id':parent_id ,
                    }
                    if thumb :vod_params ['thumb']=thumb
                    if fanart :vod_params ['fanart']=fanart
                    if poster :vod_params ['poster']=poster
                    if series_name :vod_params ['series_title']=series_name
                    url =self ._vod_url (layout_id ,vod_params )
                    li =xbmcgui .ListItem (label =(episode_label or full_title) + (f" [{_quality_label()}]" if _quality_label() else ""))
                    li .setProperty ('IsPlayable','true')
                    if thumb :
                        li .setArt ({'thumb':thumb ,'poster':poster ,'fanart':fanart })
                    info ={
                    'title':episode_label or full_title ,
                    'plot':description ,
                    'genre':genre ,
                    }
                    if year :info ['year']=year
                    if season_num :info ['season']=season_num
                    if episode_num :info ['episode']=episode_num
                    if episode_name :info ['originaltitle']=episode_name
                    if series_name :info ['tvshowtitle']=series_name
                    li .setInfo ('video',info )
                    enc_url =urllib .parse .quote_plus (url )
                    enc_label =urllib .parse .quote_plus (episode_label or full_title )
                    enc_thumb =urllib .parse .quote_plus (thumb or '')
                    bm_cmd =f'RunPlugin({self .base_url }?mode=add_bookmark&path={enc_url }&label={enc_label }&thumb={enc_thumb }&playable=1'
                    if fanart :bm_cmd +=f'&fanart={urllib .parse .quote_plus (fanart )}'
                    if poster :bm_cmd +=f'&poster={urllib .parse .quote_plus (poster )}'
                    if series_name :bm_cmd +=f'&series_title={urllib .parse .quote_plus (series_name )}'
                    bm_cmd +=')'
                    li .addContextMenuItems ([('Zu Weiterschauen hinzufuegen',bm_cmd )])
                    xbmcplugin .addDirectoryItem (self .handle ,url ,li ,False )
                    return True

                elif layout_type =='audio':
                    url =self .build_url ({
                    'mode':'play_audio',
                    'audio_id':layout_id ,
                    'title':urllib .parse .quote_plus (full_title ),
                    })
                    li =xbmcgui .ListItem (label =full_title )
                    li .setProperty ('IsPlayable','true')
                    if thumb :
                        li .setArt ({'thumb':thumb ,'poster':poster ,'fanart':fanart })
                    li .setInfo ('music',{
                    'title':full_title ,
                    'comment':description ,
                    'genre':genre ,
                    })
                    xbmcplugin .addDirectoryItem (self .handle ,url ,li ,False )
                    return True

                elif layout_type =='radio':
                    url =self .build_url ({
                    'mode':'play_radio',
                    'radio_id':layout_id ,
                    'title':urllib .parse .quote_plus (full_title ),
                    })
                    li =xbmcgui .ListItem (label =full_title )
                    li .setProperty ('IsPlayable','true')
                    art_img =self ._channel_image (layout_id )or thumb
                    if art_img :
                        li .setArt ({'thumb':art_img ,'icon':art_img })
                    li .setInfo ('video',{'title':full_title ,'plot':description })
                    xbmcplugin .addDirectoryItem (self .handle ,url ,li ,False )
                    return True

                elif layout_type =='program':
                    is_movie =self ._is_movie_highlight (highlight ,extra_details ,details )
                    if is_movie :
                        play_url =self .build_url ({
                        'mode':'play_program',
                        'program_id':layout_id ,
                        'seo':vl .get ('seo',''),
                        'title':urllib .parse .quote_plus (full_title ),
                        })
                        li =xbmcgui .ListItem (label =full_title ,path =play_url )
                        li .setProperty ('IsPlayable','true')
                        art ={'thumb':thumb or poster ,'fanart':fanart }
                        if poster :art ['poster']=poster
                        li .setArt (art )
                        info ={
                        'title':full_title ,
                        'plot':description ,
                        'genre':genre ,
                        'mediatype':'movie',
                        }
                        if year :info ['year']=year
                        li .setInfo ('video',info )
                        bookmark_url =self .build_url ({'mode':'toggle_bookmark','program_id':layout_id ,'title':urllib .parse .quote_plus (full_title ),'subscribed':'1'})
                        unmark_url =self .build_url ({'mode':'toggle_bookmark','program_id':layout_id ,'title':urllib .parse .quote_plus (full_title ),'subscribed':'0'})
                        li .addContextMenuItems ([
                        ('Merken',f'RunPlugin({bookmark_url })'),
                        ('Nicht mehr merken',f'RunPlugin({unmark_url })'),
                        ])
                        xbmcplugin .addDirectoryItem (self .handle ,play_url ,li ,False )
                    else :
                        url =self .build_url ({
                        'mode':'show_program',
                        'program_id':layout_id ,
                        'seo':vl .get ('seo',''),
                        })
                        li =xbmcgui .ListItem (label =full_title )
                        li .setProperty ('IsPlayable','false')
                        art ={'thumb':thumb or poster ,'fanart':fanart }
                        if poster :art ['poster']=poster
                        li .setArt (art )
                        info ={
                        'title':full_title ,
                        'plot':description ,
                        'genre':genre ,
                        'mediatype':'tvshow',
                        }
                        if year :info ['year']=year
                        li .setInfo ('video',info )
                        bookmark_url =self .build_url ({'mode':'toggle_bookmark','program_id':layout_id ,'title':urllib .parse .quote_plus (full_title ),'subscribed':'1'})
                        unmark_url =self .build_url ({'mode':'toggle_bookmark','program_id':layout_id ,'title':urllib .parse .quote_plus (full_title ),'subscribed':'0'})
                        li .addContextMenuItems ([
                        ('Merken',f'RunPlugin({bookmark_url })'),
                        ('Nicht mehr merken',f'RunPlugin({unmark_url })'),
                        ])
                        xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )
                    return True

                elif layout_type in ('folder','serie','season'):
                    url =self .build_url ({
                    'mode':'show_folder',
                    'folder_id':layout_id ,
                    'seo':vl .get ('seo',''),
                    })
                    li =xbmcgui .ListItem (label =full_title )
                    li .setProperty ('IsPlayable','false')
                    if thumb :
                        li .setArt ({'thumb':thumb ,'fanart':fanart })
                    li .setInfo ('video',{'title':full_title ,'plot':description })
                    xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )
                    return True

                elif layout_type =='alias':
                    url =self .build_url ({'mode':'show_alias','alias':layout_id })
                    li =xbmcgui .ListItem (label =full_title )
                    li .setProperty ('IsPlayable','false')
                    if thumb :
                        li .setArt ({'thumb':thumb })
                    li .setInfo ('video',{'title':full_title })
                    xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )
                    return True

                elif layout_type in ('live','channel'):
                    live_label =f'[COLOR gold][B]LIVE - {full_title }[/B][/COLOR]'
                    url =self .build_url ({
                    'mode':'play_live',
                    'channel_id':layout_id ,
                    'title':urllib .parse .quote_plus (full_title ),
                    })
                    li =xbmcgui .ListItem (label =live_label )
                    li .setProperty ('IsPlayable','true')
                    local_img =self ._channel_image (layout_id )
                    art_img =local_img or thumb
                    if art_img :
                        li .setArt ({'thumb':art_img ,'icon':art_img ,'clearlogo':art_img })
                    li .setInfo ('video',{'title':'\u0001'+live_label })
                    xbmcplugin .addDirectoryItem (self .handle ,url ,li ,False )
                    return True

                elif layout_type =='frontspace':
                    _log (f'_add_item: frontspace-Item uebersprungen id={layout_id }')
                    return False

                else :
                    _log (f'Unknown layout_type={layout_type!r} id={layout_id }')
                    url =self .build_url ({'mode':'show_program','program_id':layout_id })
                    li =xbmcgui .ListItem (label =full_title )
                    li .setProperty ('IsPlayable','false')
                    if thumb :
                        li .setArt ({'thumb':thumb ,'fanart':fanart })
                    li .setInfo ('video',{'title':full_title ,'plot':description })
                    xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )
                    return True

            elif t_type =='app':
                va =target .get ('value_app',{})or {}
                ref =va .get ('reference','')

                if ref =='play':
                    video_obj =ic .get ('video',{})or {}
                    video_id =video_obj .get ('id','')or item .get ('ucid','')

                    if not video_id :
                        return False

                    url =self ._vod_url (video_id ,{'title':full_title ,'thumb':thumb ,'fanart':fanart ,'poster':poster })
                    li =xbmcgui .ListItem (label =(full_title) + (f" [{_quality_label()}]" if _quality_label() else ""))
                    li .setProperty ('IsPlayable','true')
                    if thumb :
                        li .setArt ({'thumb':thumb ,'poster':poster ,'fanart':fanart })
                    li .setInfo ('video',{
                    'title':full_title ,
                    'plot':description ,
                    'genre':extra_details ,
                    })
                    xbmcplugin .addDirectoryItem (self .handle ,url ,li ,False )
                    return True
                return False

            elif t_type =='player':
                vp =target .get ('value_player',{})or {}
                vid =vp .get ('id','')
                content_type =vp .get ('type','vod')

                if content_type in ('live','livetv','channel','event','live_event','event_stream'):
                    live_label =f'[COLOR gold][B]LIVE - {full_title }[/B][/COLOR]'
                    url =self .build_url ({
                    'mode':'play_live',
                    'channel_id':vid ,
                    'title':urllib .parse .quote_plus (full_title ),
                    })
                    li =xbmcgui .ListItem (label =live_label )
                    li .setProperty ('IsPlayable','true')
                    local_img =self ._channel_image (vid )
                    art_img =local_img or thumb
                    if art_img :
                        li .setArt ({'thumb':art_img ,'icon':art_img ,'clearlogo':art_img })
                    li .setInfo ('video',{'title':'\u0001'+live_label })
                    xbmcplugin .addDirectoryItem (self .handle ,url ,li ,False )
                else :
                    _vl_alt =target .get ('value_layout',{})or {}
                    _clip_alt =_vl_alt .get ('id','')if _vl_alt .get ('type','')=='video' else ''
                    if _clip_alt and _prefer_clip_for_quality ():
                        _log (f'player->clip Fallback: rrn={vid !r} -> clip={_clip_alt !r} (Qualitaet 1080p)')
                        vid =_clip_alt
                    url =self ._vod_url (vid ,{'title':full_title ,'thumb':thumb ,'fanart':fanart ,'poster':poster })
                    li =xbmcgui .ListItem (label =(full_title) + (f" [{_quality_label()}]" if _quality_label() else ""))
                    li .setProperty ('IsPlayable','true')
                    if thumb :
                        li .setArt ({'thumb':thumb ,'poster':poster ,'fanart':fanart })
                    li .setInfo ('video',{'title':full_title ,'plot':description })
                    xbmcplugin .addDirectoryItem (self .handle ,url ,li ,False )
                return True

            else :
                video_obj =ic .get ('video',{})or {}
                vid =video_obj .get ('id','')or ''
                if vid :
                    url =self ._vod_url (vid ,{'title':full_title ,'thumb':thumb ,'fanart':fanart ,'poster':poster })
                    li =xbmcgui .ListItem (label =(full_title) + (f" [{_quality_label()}]" if _quality_label() else ""))
                    li .setProperty ('IsPlayable','true')
                    if thumb :
                        li .setArt ({'thumb':thumb ,'poster':poster ,'fanart':fanart })
                    li .setInfo ('video',{'title':full_title ,'plot':description })
                    xbmcplugin .addDirectoryItem (self .handle ,url ,li ,False )
                    _log (f'_add_item fallback via ic.video.id={vid }')
                    return True
                _log (f'_add_item: unbekannter t_type={t_type !r} ic_keys={list (ic .keys ())}')
                return False

        except Exception as e :
            _log (f'_add_item error: {e }')
            import traceback
            _log (traceback .format_exc ())
            return False

    def _channel_image (self ,channel_slug ):
        import os
        import xbmcaddon
        import xbmcvfs
        _addon_path =xbmcvfs .translatePath (xbmcaddon .Addon ().getAddonInfo ('path'))
        raw =(channel_slug or '').lower ()
        slug =raw .replace ('rtlde_','')
        rel =CHANNEL_IMAGES .get (slug ,'')
        if rel :
            return os .path .join (_addon_path ,'resources','media',rel )
        return ''

    def export_m3u (self ):
        import os ,time as _time
        import xbmcaddon ,xbmcvfs ,xbmcgui

        _addon =xbmcaddon .Addon ()
        _profile =xbmcvfs .translatePath (_addon .getAddonInfo ('profile'))

        custom_path =(_addon .getSetting ('m3u_export_path')or '').strip ()
        if custom_path :
            export_path =xbmcvfs .translatePath (custom_path )
            if not export_path .endswith ('.m3u'):
                export_path =os .path .join (export_path ,'rtlplus.m3u')
        else :
            export_path =os .path .join (_profile ,'rtlplus.m3u')

        include_livetv =_addon .getSettingBool ('m3u_include_livetv')
        include_fast =_addon .getSettingBool ('m3u_include_fast')
        include_radio =_addon .getSettingBool ('m3u_include_radio')
        include_movies =_addon .getSettingBool ('m3u_include_movies')
        include_series =_addon .getSettingBool ('m3u_include_series')

        lines =['#EXTM3U\n']
        count =0


        prog =xbmcgui .DialogProgress ()
        prog .create ('RTL+ M3U-Export','Wird geladen...')


        if include_livetv :
            prog .update (0 ,'Lade Live-TV Kanäle...')
            try :
                data =self .api .get_epg_grid ()
                items =[]
                if data :
                    items =data .get ('content',{}).get ('items',[])
                    if not items :
                        for b in data .get ('blocks',[]):
                            items +=b .get ('content',{}).get ('items',[])

                for item in items :
                    try :
                        ic =item .get ('itemContent',{})
                        action =ic .get ('action',{})or {}
                        target =action .get ('target',{})or {}
                        t_type =target .get ('type','')

                        if t_type =='lock':
                            inner =target .get ('value_lock',{})or {}
                            while inner .get ('originalTarget',{}).get ('type','')=='lock':
                                inner =inner .get ('originalTarget',{}).get ('value_lock',{})or {}
                            orig =inner .get ('originalTarget',{})or {}
                            if orig .get ('type','')in ('layout','player'):
                                target =orig
                                t_type =orig .get ('type','')

                        channel_slug =''
                        if t_type =='layout':
                            raw_id =target .get ('value_layout',{}).get ('id','')
                            channel_slug =raw_id .replace ('rtlde_','')
                        elif t_type =='player':
                            raw_id =target .get ('value_player',{}).get ('id','')
                            channel_slug =raw_id .replace ('rtlde_','')

                        if not channel_slug :
                            continue

                        channel =ic .get ('channel',{})or {}
                        channel_title =(channel .get ('title','')or channel_slug .upper ()).strip ()
                        channel_img_data =channel .get ('image',{})or {}
                        logo =_image_url (channel_img_data ,width =200 ,height =200 ,preferred_ratio ='1:1')
                        if not logo :
                            logo =self ._channel_image (channel_slug )or ''

                        url =('plugin://plugin.video.rtlplus/?mode=play_live'
                              f'&channel_id={urllib .parse .quote_plus (channel_slug )}'
                              f'&title={urllib .parse .quote_plus (channel_title )}')

                        tvg_logo =logo .split ('|')[0 ]if '|'in logo else logo
                        lines .append (f'#EXTINF:-1 tvg-id="{channel_slug}" tvg-name="{channel_title}" tvg-logo="{tvg_logo}" group-title="Live TV",{channel_title}\n')
                        lines .append (f'{url}\n')
                        count +=1
                    except Exception :
                        pass
            except Exception as e :
                _log (f'export_m3u: EPG-Fehler {e }')

        if include_fast :
            prog .update (0 ,'Lade FAST-Kanäle...')
            try :
                data_fast =self .api .get_folder_guest ('193',nb_pages =10 )
                if not data_fast :
                    self .api .auth ._guest_tokens .pop ('guest_bedrock_token',None )
                    self .api .auth ._guest_tokens .pop ('guest_bedrock_expires',None )
                    self .api .auth ._save_guest_tokens ()
                    self .api .auth .get_guest_bedrock_token ()
                    data_fast =self .api .get_folder_guest ('193',nb_pages =10 )
                if data_fast :
                    for block in data_fast .get ('blocks',[]):
                        for item in block .get ('content',{}).get ('items',[]):
                            try :
                                ic =item .get ('itemContent',{})
                                action =(ic .get ('action')or {})
                                target =(action .get ('target')or {})
                                t_type =target .get ('type','')
                                if t_type =='lock':
                                    inner =(target .get ('value_lock',{})or {})
                                    while (inner .get ('originalTarget',{})or {}).get ('type','')=='lock':
                                        inner =(inner .get ('originalTarget',{})or {}).get ('value_lock',{})or {}
                                    orig =(inner .get ('originalTarget',{})or {})
                                    if orig .get ('type','')=='layout':
                                        target =orig
                                        t_type ='layout'
                                if t_type !='layout':
                                    continue
                                vl =(target .get ('value_layout')or {})
                                if vl .get ('type','')!='live':
                                    continue
                                vl_id =str (vl .get ('id',''))
                                if not vl_id or 'fast' not in vl_id .lower ():
                                    continue
                                channel_slug =vl_id .replace ('rtlde_','')
                                title =(ic .get ('title','')or channel_slug .upper ()).strip ()
                                thumb =''
                                img_data =ic .get ('image')
                                if img_data and isinstance (img_data ,dict ):
                                    thumb =_image_url (img_data ,width =320 ,height =180 ,preferred_ratio ='16:9')
                                tvg_logo =thumb .split ('|')[0 ]if '|'in thumb else thumb
                                url =('plugin://plugin.video.rtlplus/?mode=play_live'
                                      f'&channel_id={urllib .parse .quote_plus (channel_slug )}'
                                      f'&title={urllib .parse .quote_plus (title )}')
                                lines .append (f'#EXTINF:-1 tvg-id="{channel_slug}" tvg-name="{title}" tvg-logo="{tvg_logo}" group-title="FAST",{title}\n')
                                lines .append (f'{url}\n')
                                count +=1
                            except Exception :
                                pass
                _log (f'export_m3u: {count } FAST-Kanäle exportiert')
            except Exception as e :
                _log (f'export_m3u: FAST-Fehler {e }')


        if include_radio :
            prog .update (0 ,'Lade Radio-Sender...')
            try :
                radio_data =self .api .get_service_guest ('live-radios',nb_pages =5 )
                radio_items =[]
                if radio_data :
                    radio_items =radio_data .get ('content',{}).get ('items',[])
                    if not radio_items :
                        for b in radio_data .get ('blocks',[]):
                            radio_items +=b .get ('content',{}).get ('items',[])

                radio_count =0
                for item in radio_items :
                    try :
                        ic =item .get ('itemContent',{})
                        title =(ic .get ('title','')or ic .get ('label','')or '').strip ()
                        action =(ic .get ('action')or {})
                        target =(action .get ('target')or {})
                        t_type =target .get ('type','')
                        if t_type =='lock':
                            inner =(target .get ('value_lock',{})or {})
                            while (inner .get ('originalTarget',{})or {}).get ('type','')=='lock':
                                inner =(inner .get ('originalTarget',{})or {}).get ('value_lock',{})or {}
                            orig =(inner .get ('originalTarget',{})or {})
                            if orig .get ('type','')in ('layout','player'):
                                target =orig
                        vl =(target .get ('value_layout')or {})
                        radio_id =vl .get ('id','')
                        if not radio_id :
                            radio_id =ic .get ('video',{}).get ('id','')if ic .get ('video')else ''
                        if not radio_id or not title :
                            continue
                        thumb =_image_url (ic .get ('image',{})or {})
                        tvg_logo =thumb .split ('|')[0 ]if '|'in thumb else thumb
                        url =('plugin://plugin.video.rtlplus/?mode=play_radio'
                              f'&radio_id={urllib .parse .quote_plus (radio_id )}'
                              f'&title={urllib .parse .quote_plus (title )}')
                        lines .append (f'#EXTINF:-1 tvg-id="{radio_id}" tvg-name="{title}" tvg-logo="{tvg_logo}" radio="true" group-title="Radio",{title}\n')
                        lines .append (f'{url}\n')
                        count +=1
                        radio_count +=1
                    except Exception :
                        pass
                _log (f'export_m3u: {radio_count } Radio-Sender exportiert')
            except Exception as e :
                _log (f'export_m3u: Radio-Fehler {e }')


        if include_movies :
            try :
                if prog .iscanceled ():
                    prog .close ()
                    return
                prog .update (0 ,'Lade Filme von JustWatch...')
                def _movie_progress (done ,total ,label ):
                    if total :
                        pct =int (done /total *100 )
                        prog .update (pct ,f'Filme: {done}/{total}')
                movies =self ._jw_fetch_all_titles ('MOVIE',progress_cb =_movie_progress )
                for item in movies :
                    if prog .iscanceled ():
                        break
                    title =item ['title']
                    year =item .get ('year','')
                    program_id =item ['program_id']
                    seo =item .get ('seo','')
                    thumb =item .get ('thumb','')
                    label =f'{title} ({year})'if year else title
                    url =(f'plugin://plugin.video.rtlplus/?mode=play_program'
                          f'&program_id={urllib .parse .quote_plus (program_id )}'
                          f'&seo={urllib .parse .quote_plus (seo )}'
                          f'&title={urllib .parse .quote_plus (label )}')
                    lines .append (f'#EXTINF:-1 tvg-id="movie_{program_id}" tvg-name="{label}" tvg-logo="{thumb}" movie="true" group-title="Movie",{label}\n')
                    lines .append (f'{url}\n')
                    count +=1
                _log (f'export_m3u: {len(movies)} Filme')
            except Exception as e :
                _log (f'export_m3u: Filme-Fehler {e }')

        if include_series :
            try :
                if prog .iscanceled ():
                    prog .close ()
                    return
                prog .update (0 ,'Lade Serien-Liste von JustWatch...')
                def _series_progress (done ,total ,label ):
                    if total :
                        pct =int (done /total *100 )
                        prog .update (pct ,f'Serien: {done}/{total}')
                series_list =self ._jw_fetch_all_titles ('SHOW',progress_cb =_series_progress )
                _log (f'export_m3u: {len(series_list)} Serien gefunden – lade Episoden...')
                for s_idx ,series_item in enumerate (series_list ):
                    if prog .iscanceled ():
                        break
                    s_title =series_item ['title']
                    s_year =series_item .get ('year','')
                    s_program_id =series_item ['program_id']
                    s_seo =series_item .get ('seo','')
                    s_thumb =series_item .get ('thumb','')
                    s_label =f'{s_title} ({s_year})'if s_year else s_title
                    pct =int (s_idx /max (len (series_list ),1 )*100 )
                    prog .update (pct ,f'Episoden: {s_label} ({s_idx+1}/{len(series_list)})')
                    try :
                        episodes =self ._fetch_episodes_for_series (s_program_id ,seo =s_seo )
                    except Exception as ep_e :
                        _log (f'export_m3u: Episode-Fehler für {s_label}: {ep_e}')
                        episodes =[]
                    if not episodes :
                        fb_url =(f'plugin://plugin.video.rtlplus/?mode=show_program'
                                 f'&program_id={urllib .parse .quote_plus (s_program_id )}'
                                 f'&seo={urllib .parse .quote_plus (s_seo )}')
                        lines .append (f'#EXTINF:-1 tvg-id="show_{s_program_id}" tvg-name="{s_label}" tvg-logo="{s_thumb}" series="true" group-title="Series",{s_label}\n')
                        lines .append (f'{fb_url}\n')
                        count +=1
                        continue
                    for ep in episodes :
                        video_id =ep ['video_id']
                        ep_label =ep .get ('label','')or s_label
                        ep_thumb =ep .get ('thumb','')or s_thumb
                        full_label =f'{s_label} – {ep_label}'
                        self ._vod_url (video_id ,{'title':full_label ,'thumb':ep_thumb ,'video_seo':ep .get ('seo',''),'program_id':s_program_id ,'program_seo':s_seo })
                        ep_url =f'plugin://plugin.video.rtlplus/?mode=play_vod&video_id={urllib .parse .quote_plus (video_id )}'
                        lines .append (f'#EXTINF:-1 tvg-id="{video_id}" tvg-name="{full_label}" tvg-logo="{ep_thumb}" series="true" group-title="Series",{full_label}\n')
                        lines .append (f'{ep_url}\n')
                        count +=1
                _log (f'export_m3u: Serien-Episoden fertig, count={count}')
            except Exception as e :
                _log (f'export_m3u: Serien-Fehler {e }')

        prog .close ()

        if count ==0 :
            xbmcgui .Dialog ().notification ('RTL+ M3U-Export','Keine Einträge gefunden – bitte einloggen',xbmcgui .NOTIFICATION_WARNING ,5000 )
            return


        try :
            os .makedirs (os .path .dirname (export_path ),exist_ok =True )
        except Exception :
            pass

        try :
            f =xbmcvfs .File (export_path ,'w')
            f .write (''.join (lines ))
            f .close ()
            _log (f'export_m3u: {count } Einträge → {export_path }')
            xbmcgui .Dialog ().ok ('RTL+ M3U-Export',
                f'{count} Einträge exportiert.\n\n{export_path}')
        except Exception as e :
            _log (f'export_m3u: Schreibfehler {e }')
            xbmcgui .Dialog ().notification ('RTL+ M3U-Export',f'Fehler: {e }',xbmcgui .NOTIFICATION_ERROR ,6000 )

    def _create_live_listitem (self ,item ):
        try :
            ic =item .get ('itemContent',{})
            title =ic .get ('title','')or ic .get ('label','')
            thumb =_image_url (ic .get ('image',{}))

            action =ic .get ('action',{})or {}
            target =action .get ('target',{})or {}
            t_type =target .get ('type','')

            if t_type =='lock':
                inner =target .get ('value_lock',{})or {}

                while inner .get ('originalTarget',{}).get ('type','')=='lock':
                    inner =inner .get ('originalTarget',{}).get ('value_lock',{})or {}
                orig =inner .get ('originalTarget',{})or {}
                if orig .get ('type','')in ('layout','player'):
                    target =orig
                    t_type =orig .get ('type','')

            channel_slug =''
            content_id =''

            if t_type =='layout':
                vl =target .get ('value_layout',{})
                raw_id =vl .get ('id','')
                channel_slug =raw_id .replace ('rtlde_','')
            elif t_type =='player':
                vp =target .get ('value_player',{})
                raw_id =vp .get ('id','')
                channel_slug =raw_id .replace ('rtlde_','')
            else :
                video =ic .get ('video',{})
                if video :
                    content_id =video .get ('id','')
                    channel_slug =content_id .replace ('rtlde_','')

            if not channel_slug and not content_id :
                return None

            local_img =self ._channel_image (channel_slug or content_id )
            art_img =thumb or local_img

            li =xbmcgui .ListItem (label =title or channel_slug )
            li .setProperty ('IsPlayable','true')
            if art_img :
                li .setArt ({'thumb':art_img ,'icon':art_img ,'clearlogo':art_img })
            li .setInfo ('video',{'title':title ,'mediatype':'video'})

            url =self .build_url ({
            'mode':'play_live',
            'channel_id':channel_slug ,
            'content_id':content_id ,
            'title':urllib .parse .quote_plus (title or channel_slug ),
            })

            xbmcplugin .addDirectoryItem (self .handle ,url ,li ,False )
            return li

        except Exception as e :
            _log (f'_create_live_listitem error: {e }')
            return None

    def _create_live_listitem_epg (self ,item ):
        try:
            ic = item.get ('itemContent',{})

            action = ic.get ('action',{}) or {}
            target = action.get ('target',{}) or {}
            t_type = target.get ('type','')

            if t_type == 'lock':
                inner = target.get ('value_lock',{}) or {}
                while inner.get ('originalTarget',{}).get ('type','') == 'lock':
                    inner = inner.get ('originalTarget',{}).get ('value_lock',{}) or {}
                orig = inner.get ('originalTarget',{}) or {}
                if orig.get ('type','') in ('layout','player'):
                    target = orig
                    t_type = orig.get ('type','')

            channel_slug = ''
            if t_type == 'layout':
                raw_id = target.get ('value_layout',{}).get ('id','')
                channel_slug = raw_id.replace ('rtlde_','')
            elif t_type == 'player':
                raw_id = target.get ('value_player',{}).get ('id','')
                channel_slug = raw_id.replace ('rtlde_','')

            if not channel_slug:
                return None

            channel = ic.get ('channel',{}) or {}
            channel_title = channel.get ('title','') or channel_slug.upper ()
            channel_img_data = channel.get ('image',{}) or {}
            channel_logo = _image_url (channel_img_data,width=200,height=200,preferred_ratio='1:1')

            local_img = self._channel_image (channel_slug)
            channel_art = channel_logo or local_img

            epgbox = ic.get ('epgBox',[]) or []
            current,next_ep = self._epg_current_program (epgbox)

            if current:
                cur_title = current.get ('title','')
                cur_extra = current.get ('extraTitle','')
                cur_start = current.get ('start',{}).get ('title','')
                cur_end = current.get ('end',{}).get ('title','')
                cur_end_date = current.get ('end',{}).get ('date','')

                if cur_extra:
                    program_label = f'{cur_title} - {cur_extra}'
                else:
                    program_label = cur_title

                restzeit_str = ''
                try:
                    from datetime import datetime as _dt, timezone as _tz
                    import re as _re
                    end_str_utc = _re.sub (r'([+-]\d{2}):(\d{2})$',lambda m:f'{m.group(1)}{m.group(2)}',cur_end_date)
                    end_ts = _dt.strptime (end_str_utc,'%Y-%m-%dT%H:%M:%S%z').timestamp ()
                    import time as _time
                    remaining = int (end_ts - _time.time ())
                    if remaining > 0:
                        h,r = divmod (remaining,3600)
                        m,s = divmod (r,60)
                        if h:
                            restzeit_str = f'noch {h}h {m:02d}min'
                        else:
                            restzeit_str = f'noch {m}min'
                except Exception:
                    pass

                time_label = f'[{cur_start}-{cur_end}]' if cur_start and cur_end else ''

                nxt_title = ''
                nxt_extra = ''
                nxt_start = ''
                nxt_end = ''
                nxt_label = ''
                nxt_time_label = ''
                if next_ep:
                    nxt_title = next_ep.get ('title','')
                    nxt_extra = next_ep.get ('extraTitle','')
                    nxt_start = next_ep.get ('start',{}).get ('title','')
                    nxt_end = next_ep.get ('end',{}).get ('title','')
                    nxt_label = f'{nxt_title} - {nxt_extra}' if nxt_extra else nxt_title
                    nxt_time_label = f'[{nxt_start}-{nxt_end}]' if nxt_start and nxt_end else ''

                rest_suffix = f'  ({restzeit_str})' if restzeit_str else ''
                label = f'[B]{channel_title}[/B]  {time_label}  {program_label}{rest_suffix}'

                ep_img_id = current.get ('image',{})
                if ep_img_id:
                    thumb = _image_url (ep_img_id,width=320,height=180,preferred_ratio='16:9')
                else:
                    modal_id = (current.get ('action',{}) or {}).get ('target',{}).get ('value_modal',{}).get ('id','')
                    if modal_id:
                        thumb = self._get_epg_modal_thumb (modal_id)
                    else:
                        thumb = ''

                thumb = thumb or channel_art

                if nxt_label:
                    plot = f'Danach {nxt_time_label}: {nxt_label}'
                else:
                    plot = ''
            else:
                label = f'[B]{channel_title}[/B]'
                thumb = channel_art
                plot = channel_title

            url = self.build_url ({
                'mode':'play_live',
                'channel_id':channel_slug,
                'title':urllib.parse.quote_plus (channel_title),
            })

            li = xbmcgui.ListItem (label=label)
            li.setProperty ('IsPlayable','true')
            art = {}
            if channel_art:
                art['thumb'] = channel_art
                art['icon'] = channel_art
                art['clearlogo'] = channel_art
            if thumb and thumb != channel_art:
                art['fanart'] = thumb
            elif channel_art:
                art['fanart'] = channel_art
            if art:
                li.setArt (art)
            li.setInfo ('video',{
                'title':label,
                'plot':plot,
                'mediatype':'video',
            })

            xbmcplugin.addDirectoryItem (self.handle,url,li,False)
            return li

        except Exception as e:
            _log (f'_create_live_listitem_epg error: {e}')
            import traceback
            _log (traceback.format_exc ())
            return None

    def _get_epg_modal_thumb (self ,modal_id ):
        try:
            data = self.api.get_epg_modal (modal_id)
            if not data:
                return ''
            for block in data.get ('blocks',[]):
                for item in block.get ('content',{}).get ('items',[]):
                    ic = item.get ('itemContent',{})
                    img = ic.get ('image',{})
                    if img:
                        return _image_url (img,width=320,height=180,preferred_ratio='16:9')
            return ''
        except Exception as e:
            _log (f'_get_epg_modal_thumb error: {e}')
            return ''

    def _add_next_page (self ,folder_id ,block_id ,next_page ):
        li =xbmcgui .ListItem (label ='[COLOR yellow]>> Mehr laden >>[/COLOR]')
        url =self .build_url ({
        'mode':'show_folder',
        'folder_id':folder_id ,
        'page':next_page ,
        })
        xbmcplugin .addDirectoryItem (self .handle ,url ,li ,True )
