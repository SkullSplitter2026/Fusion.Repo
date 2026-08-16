import sys
import shutil
import urllib .parse
import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmcvfs

ADDON_HANDLE =int (sys .argv [1 ])
BASE_URL =sys .argv [0 ]
ADDON =xbmcaddon .Addon ()
ADDON_ID =ADDON .getAddonInfo ('id')
ADDON_PROFILE =xbmcvfs .translatePath (ADDON .getAddonInfo ('profile'))

def build_url (params ):
    return BASE_URL +'?'+urllib .parse .urlencode (params )

def get_params ():
    return dict (urllib .parse .parse_qsl (sys .argv [2 ][1 :]))

def router ():
    from resources .lib .api import BedrockAPI
    from resources .lib .navigator import Navigator
    from resources .lib .player import RTLPlayer

    params =get_params ()
    mode =params .get ('mode','')

    nav =Navigator (ADDON_HANDLE ,BASE_URL )

    if mode =='':
        nav .show_main_menu ()

    elif mode =='show_alias':
        alias =params .get ('alias','home')
        nav .show_alias (alias )

    elif mode =='show_folder':
        folder_id =params .get ('folder_id','')
        seo =params .get ('seo','')
        page =int (params .get ('page','1'))
        nav .show_folder (folder_id ,seo =seo ,page =page )

    elif mode =='show_folder_block':
        folder_id =params .get ('folder_id','')
        block_index =int (params .get ('block_index','0'))
        seo =params .get ('seo','')
        page =int (params .get ('page','1'))
        nav .show_folder_block (folder_id ,block_index ,seo =seo ,page =page )

    elif mode =='show_program':
        program_id =params .get ('program_id','')
        seo =params .get ('seo','')
        page =int (params .get ('page','1'))
        nav .show_program (program_id ,seo =seo ,page =page )

    elif mode =='show_season':
        program_id =params .get ('program_id','')
        block_index =int (params .get ('block_index','0'))
        season_title =urllib .parse .unquote_plus (params .get ('season_title',''))
        season_block_id =params .get ('season_block_id','')
        seo =params .get ('seo','')
        nav .show_season (program_id ,block_index ,season_title ,season_block_id ,seo )

    elif mode =='show_live':
        nav .show_live_channels ()

    elif mode =='show_epg':
        nav .show_epg ()

    elif mode =='show_az':
        nav .show_az ()

    elif mode =='show_jw_az':
        obj_type =params .get ('obj_type','SHOW')
        page =int (params .get ('page','1'))
        nav .show_jw_az (obj_type ,page )

    elif mode =='show_az_letter':
        letter =params .get ('letter','A')
        nav .show_az_letter (letter )

    elif mode =='search':
        query =params .get ('query','')
        nav .show_search (query )

    elif mode =='search_new':
        nav .show_search_new ()

    elif mode =='search_clear_history':
        nav .search_clear_history ()

    elif mode =='show_meine_inhalte':
        nav .show_meine_inhalte ()

    elif mode =='show_meine_block':
        block_key =params .get ('block_key','')
        label =urllib .parse .unquote_plus (params .get ('label',''))
        nav .show_meine_block (block_key ,label )

    elif mode =='add_bookmark':
        from resources .lib .evil import bookmarks
        path_val =params .get ('path','')
        label =urllib .parse .unquote_plus (params .get ('label',''))
        thumb =urllib .parse .unquote_plus (params .get ('thumb',''))
        fanart =urllib .parse .unquote_plus (params .get ('fanart',''))
        poster =urllib .parse .unquote_plus (params .get ('poster',''))
        series_title =urllib .parse .unquote_plus (params .get ('series_title',''))
        bookmarks .add (path =path_val ,label =label ,thumb =thumb ,folder =0 ,playable =1 ,fanart =fanart or None ,poster =poster or None ,series_title =series_title or None )
        xbmcgui .Dialog ().notification ('RTL+','Zu Weiterschauen hinzugefuegt',xbmcgui .NOTIFICATION_INFO ,2000 )

    elif mode =='remove_bookmark':
        from resources .lib .evil import bookmarks
        path_val =params .get ('path','')
        data_bk =bookmarks .get ()
        for i ,item in enumerate (data_bk ):
            if item ['path']==path_val :
                bookmarks .delete (i )
                break
        xbmc .executebuiltin ('Container.Refresh')

    elif mode =='show_service':
        service =params .get ('service','podcast')
        label =urllib .parse .unquote_plus (params .get ('label',service ))
        page =int (params .get ('page','1'))
        nav .show_service (service ,label ,page )

    elif mode =='play_program':
        program_id =params .get ('program_id','')
        seo =params .get ('seo','')
        title =urllib .parse .unquote_plus (params .get ('title','Film'))
        nav .play_program (program_id ,seo =seo ,title =title )

    elif mode =='play_vod':
        video_id =params .get ('video_id','')
        from resources .lib .evil import vod_meta as _vod_meta
        _cached =_vod_meta .load (video_id )
        title =urllib .parse .unquote_plus (params .get ('title',''))or _cached .get ('title','Video')
        video_seo =params .get ('video_seo','')or _cached .get ('video_seo','')
        program_seo =params .get ('program_seo','')or _cached .get ('program_seo','')
        program_id =params .get ('program_id','')or _cached .get ('program_id','')
        thumb =urllib .parse .unquote_plus (params .get ('thumb',''))or _cached .get ('thumb','')
        fanart =urllib .parse .unquote_plus (params .get ('fanart',''))or _cached .get ('fanart','')
        poster =urllib .parse .unquote_plus (params .get ('poster',''))or _cached .get ('poster','')
        series_title =urllib .parse .unquote_plus (params .get ('series_title',''))or _cached .get ('series_title','')
        RTLPlayer (ADDON_HANDLE ).play_vod (video_id ,title ,video_seo =video_seo ,program_seo =program_seo ,program_id =program_id ,thumb =thumb ,fanart =fanart ,poster =poster ,series_title =series_title )

    elif mode =='play_audio':
        audio_id =params .get ('audio_id','')
        title =urllib .parse .unquote_plus (params .get ('title','Audio'))
        RTLPlayer (ADDON_HANDLE ).play_audio (audio_id ,title )

    elif mode =='play_radio':
        radio_id =params .get ('radio_id','')
        title =urllib .parse .unquote_plus (params .get ('title','Radio'))
        RTLPlayer (ADDON_HANDLE ).play_radio (radio_id ,title )

    elif mode =='play_live':
        channel_id =params .get ('channel_id','')
        service_code =params .get ('service_code','rtlplus_root')
        content_id =params .get ('content_id','')
        title =urllib .parse .unquote_plus (params .get ('title','Live'))
        RTLPlayer (ADDON_HANDLE ).play_live (channel_id ,service_code ,content_id ,title )

    elif mode =='settings':
        ADDON .openSettings ()

    elif mode =='show_account_type':
        from resources .lib .auth import RTLAuth
        auth =RTLAuth ()
        tier =auth .get_subscription_tier ()
        if tier =='Premium':
            msg ='Account-Typ: [B]PREMIUM[/B] – HD-Streams aktiv'
        elif tier =='Basic':
            msg ='Account-Typ: [B]BASIC[/B] – HD-Streams aktiv, eingeschränkter Katalog'
        elif tier =='Premium+':
            msg ='Account-Typ: [B]PREMIUM+[/B] – erweitertes Paket aktiv'
        elif tier =='Free':
            msg ='Account-Typ: [B]FREE[/B] – Streams auf 576p begrenzt, Lauffähige Inhalte (Gold) markiert'
        else :
            msg ='Account-Typ: [B]Gast[/B] – Streams nicht alle verfügbar'
        xbmcgui .Dialog ().ok ('RTL+ Account-Typ',msg )

    elif mode =='refresh_account_type':
        from resources .lib .auth import RTLAuth
        from resources .lib .navigator import _PREMIUM_STATUS_CACHE
        auth =RTLAuth ()

        auth ._tokens .pop ('_premium_status',None )
        auth ._tokens .pop ('_premium_status_ts',None )
        auth ._tokens .pop ('_subscription_tier',None )
        auth ._save_tokens ()
        _PREMIUM_STATUS_CACHE .clear ()
        tier =auth .get_subscription_tier ()
        _PREMIUM_STATUS_CACHE .clear ()
        xbmcgui .Dialog ().notification ('RTL+',f'Account-Typ: {tier }',xbmcgui .NOTIFICATION_INFO ,3000 )

    elif mode =='show_guest_free':
        nav .show_guest_free ()

    elif mode =='login':
        from resources .lib .auth import RTLAuth
        auth =RTLAuth ()
        if auth ._tokens .get ('is_guest'):
            auth ._tokens ={}
            auth ._save_tokens ()
        if not ADDON .getSetting ('username') or not ADDON .getSetting ('password'):
            xbmcgui .Dialog ().ok ('RTL+ Anmeldung','Bitte E-Mail und Passwort in den Einstellungen eintragen,\ndann erneut auf [B]Anmelden[/B] tippen.')
            ADDON .openSettings ()
            xbmc .executebuiltin ('Container.Refresh')
        else :
            token =auth ._login ()
            if token :
                xbmcgui .Dialog ().notification ('RTL+','Anmeldung erfolgreich',xbmcgui .NOTIFICATION_INFO ,3000 )
                xbmc .sleep (500 )
                xbmc .executebuiltin ('Container.Update(%s,replace)' % BASE_URL )
            else :
                xbmcgui .Dialog ().notification ('RTL+','Anmeldung fehlgeschlagen',xbmcgui .NOTIFICATION_ERROR ,3000 )
                xbmc .executebuiltin ('Container.Refresh')

    elif mode =='logout':
        if not xbmcgui .Dialog ().yesno ('RTL+','Wirklich abmelden?'):
            return
        from resources .lib .auth import RTLAuth
        from resources .lib .navigator import _PREMIUM_STATUS_CACHE
        auth =RTLAuth ()
        auth .logout ()
        auth ._guest_tokens ={}
        auth ._save_guest_tokens ()
        _PREMIUM_STATUS_CACHE .clear ()
        xbmcgui .Dialog ().notification ('RTL+','Ausgeloggt',xbmcgui .NOTIFICATION_INFO ,3000 )
        xbmc .executebuiltin ('Container.Refresh')

    elif mode =='reset':
        if not xbmcgui .Dialog ().yesno ('RTL+','Addon wirklich zurücksetzen? Alle Daten werden gelöscht.'):
            return
        try :
            from resources .lib .navigator import _PREMIUM_STATUS_CACHE
            _PREMIUM_STATUS_CACHE .clear ()
        except Exception :
            pass
        try :
            ADDON .setSetting ('username','')
            ADDON .setSetting ('password','')
        except Exception as e :
            xbmc .log (f'[RTL+] Reset settings error: {e }',xbmc .LOGWARNING )
        try :
            shutil .rmtree (ADDON_PROFILE ,ignore_errors =True )
        except Exception as e :
            xbmc .log (f'[RTL+] Reset rmtree error: {e }',xbmc .LOGWARNING )
        xbmcgui .Dialog ().notification ('RTL+','Addon zurückgesetzt',xbmcgui .NOTIFICATION_INFO ,3000 )
        xbmc .executebuiltin ('Container.Refresh')

    elif mode =='widevine_update':
        import xbmc as _xbmc2
        is_android = _xbmc2.getCondVisibility('System.Platform.Android')
        if is_android:
            xbmcgui.Dialog().ok('RTL+',
                'Auf Android verwaltet das System Widevine automatisch.\n\n'
                'Ein manuelles Update ist nicht nötig und nicht möglich.\n\n'
                'Bei DRM-Problemen: Kodi-Cache leeren oder Kodi neu starten.')
        else:
            try:
                import xbmcaddon as _xbmcaddon
                helper = _xbmcaddon.Addon('script.module.inputstreamhelper')
                helper_path = helper.getAddonInfo('path')
                import sys as _sys
                if helper_path not in _sys.path:
                    _sys.path.insert(0, helper_path)
                import inputstreamhelper as _ish
                ish = _ish.Helper('mpd', drm='com.widevine.alpha')
                if ish.check_inputstream():
                    xbmcgui.Dialog().notification('RTL+', 'Widevine CDM wird aktualisiert …', xbmcgui.NOTIFICATION_INFO, 3000)
                    ish.install_widevine()
                else:
                    xbmcgui.Dialog().ok('RTL+',
                        'InputStream Adaptive nicht verfügbar.\n'
                        'Bitte installiere "InputStream Adaptive" und "InputStream Helper".')
            except Exception as _e:
                xbmc.log(f'[RTL+] widevine_update error: {_e}', xbmc.LOGWARNING)
                xbmcgui.Dialog().ok('RTL+',
                    'Widevine-Update fehlgeschlagen.\n\n'
                    'Bitte manuell über:\nEinstellungen → Add-ons → InputStream Helper → Widevine CDM installieren')

    elif mode =='inputstream_install':
        import xbmc as _xbmc3
        is_android = _xbmc3.getCondVisibility('System.Platform.Android')
        if is_android:
            confirm = xbmcgui.Dialog().yesno(
                'RTL+',
                'Auf Android ist InputStream Adaptive bereits im Kodi-Kern integriert.\n\n'
                'Eine manuelle Installation ist normalerweise nicht nötig.\n\n'
                'Trotzdem installieren?'
            )
            if confirm:
                try:
                    xbmc.executebuiltin('InstallAddon(inputstream.adaptive)')
                    xbmcgui.Dialog().notification('RTL+', 'InputStream Adaptive wird installiert …', xbmcgui.NOTIFICATION_INFO, 3000)
                except Exception as _e:
                    xbmc.log(f'[RTL+] inputstream_install android error: {_e}', xbmc.LOGWARNING)
                    xbmcgui.Dialog().ok('RTL+',
                        'Installation fehlgeschlagen.\n\n'
                        'Bitte manuell über:\nEinstellungen → Add-ons → Add-on-Browser → inputstream.adaptive')
        else:
            try:
                xbmc.executebuiltin('InstallAddon(inputstream.adaptive)')
                xbmcgui.Dialog().notification('RTL+', 'InputStream Adaptive wird installiert …', xbmcgui.NOTIFICATION_INFO, 3000)
            except Exception as _e:
                xbmc.log(f'[RTL+] inputstream_install error: {_e}', xbmc.LOGWARNING)
                xbmcgui.Dialog().ok('RTL+',
                    'Installation fehlgeschlagen.\n\n'
                    'Bitte manuell über:\nEinstellungen → Add-ons → Add-on-Browser → inputstream.adaptive')

    elif mode =='browse_export_path':
        try :
            import xbmcgui as _xbmcgui ,xbmcaddon as _xbmcaddon
            _addon =_xbmcaddon .Addon ()
            _current =_addon .getSetting ('m3u_export_path')or ''
            _selected =_xbmcgui .Dialog ().browse (3 ,'Exportordner wählen','files','' ,False ,False ,_current )
            if _selected and _selected !=_current :
                _addon .setSetting ('m3u_export_path',_selected )
        except Exception as _browse_err :
            import xbmcgui as _xbmcgui
            _xbmcgui .Dialog ().notification (
                'RTL+',
                'Dateibrowser nicht verfügbar – Pfad bitte manuell eingeben.' ,
                _xbmcgui .NOTIFICATION_WARNING ,4000 )
    elif mode =='export_m3u':
        nav .export_m3u ()

    elif mode =='toggle_bookmark':
        program_id =params .get ('program_id','')
        title =urllib .parse .unquote_plus (params .get ('title',''))
        subscribed =params .get ('subscribed','1')=='1'
        from resources .lib .api import BedrockAPI
        ok =BedrockAPI ().toggle_bookmark (program_id ,subscribed =subscribed )
        if ok :
            msg ='Gemerkt ✓' if subscribed else 'Nicht mehr gemerkt'
        else :
            msg ='Fehler beim Speichern'
        xbmcgui .Dialog ().notification ('RTL+',msg ,xbmcgui .NOTIFICATION_INFO ,2000 )

    else :
        nav .show_main_menu ()

if __name__ =='__main__':
    try :
        router ()
    except Exception as e :
        xbmc .log (f'[RTL+] FATAL: {e }',xbmc .LOGERROR )
        import traceback
        xbmc .log (traceback .format_exc (),xbmc .LOGERROR )
        xbmcgui .Dialog ().notification ('RTL+',f'Fehler: {e }',xbmcgui .NOTIFICATION_ERROR ,5000 )
        xbmcplugin .endOfDirectory (ADDON_HANDLE ,succeeded =False )
