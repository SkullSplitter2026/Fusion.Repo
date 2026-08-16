# -*- coding: utf-8 -*-

import sys
import os
import re
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import json
import xbmcvfs
import shutil
import time
from datetime import datetime, timedelta
import requests
from urllib.parse import parse_qsl, urlencode, quote_plus, unquote_plus
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


HOST_AND_PATH				= sys.argv[0]
ADDON_HANDLE				= int(sys.argv[1])
dialog									= xbmcgui.Dialog()
addon									= xbmcaddon.Addon()
addon_id							= addon.getAddonInfo('id')
addon_name						= addon.getAddonInfo('name')
addon_version					= addon.getAddonInfo('version')
addon_desc						= addon.getAddonInfo('description')
addon_folder						= xbmcvfs.translatePath(addon.getAddonInfo('path'))
addon_profile					= xbmcvfs.translatePath(addon.getAddonInfo('profile'))
defaultFanart						= os.path.join(addon_folder, 'resources', 'media', 'fanart.jpg')
icon										= os.path.join(addon_folder, 'resources', 'media', 'icon.png')
artpic									= os.path.join(addon_folder, 'resources', 'media', '')
PERS_TOKEN						= str(addon.getSetting('pers_apiKey'))
DEB_LEVEL							= (xbmc.LOGINFO if addon.getSetting('enable_debug') == 'true' else xbmc.LOGDEBUG)
KODI_BUILD						= int(xbmc.getInfoLabel('System.BuildVersion')[0:2])
CHANNEL_CODE				= 'UCfMo0xj-sbdzHuzxvKdu1hw'
CHANNEL_NAME				= '@DFB'
BASE_YOUT						= 'plugin://plugin.video.youtube/channel/{}/playlist/{}/'
WEB_AGENT						= 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0'
HEAD_WEB							= {'User-Agent': WEB_AGENT, 'Referer': 'https://www.youtube.com/', 'Cache-Control': 'no-cache', 'Accept': 'application/json, application/x-www-form-urlencoded, text/plain, */*', 'DNT': '1', 'Upgrade-Insecure-Requests': '1', 'Accept-Encoding': 'gzip', 'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8'}

xbmcplugin.setContent(ADDON_HANDLE, 'tvshows')

def translation(id):
	return addon.getLocalizedString(id)

def failing(content):
	log(content, xbmc.LOGERROR)

def debug_MS(content):
	log(content, DEB_LEVEL)

def log(msg, level=xbmc.LOGINFO):
	return xbmc.log(f"[{addon_id} v.{addon_version}]{str(msg)}", level)

def build_mass(body):
	return f"{HOST_AND_PATH}?{urlencode(body)}"

def trackContent(url, method='GET', queries='JSON', headers={}, redirects=True, verify=False, timeout=30):
	fixation, ANSWER = requests.Session(), None
	try:
		response = fixation.request(method, url, headers=HEAD_WEB, allow_redirects=redirects, verify=verify, timeout=timeout)
		ANSWER = response.json() if queries == 'JSON' else response.text if queries == 'TEXT' else response
		debug_MS(f"(common.trackContent) === CALLBACK === STATUS : {response.status_code} || URL : {response.url} || HEADER : {response.request.headers} ===")
	except requests.exceptions.RequestException as exc:
		failing(f"(common.trackContent) ERROR - EXEPTION - ERROR ##### URL : {url} === FAILURE : {exc} #####")
		dialog.notification(translation(30521).format('URL'), translation(30523).format(exc), icon, 12000)
		return sys.exit(0)
	return ANSWER

def get_seconds(info):
	try:
		info = re.sub('[a-zA-Z]', '', info)
		secs = sum(x * int(t) for x, t in zip([1, 60, 3600], reversed(info.split(':'))))
		return "{0:.0f}".format(secs)
	except: return None

def cleaning(text, CUSTOMISE=False):
	if text is not None: # Remove Emojis and other unwanted Symbols in JSON-Text on YOUTUBE
		if CUSTOMISE is True:
			for ex in (('<strong>', 'fatstart'), ('</strong>', 'fatend'), ('<em>', 'slanstart'), ('</em>', 'slanend'), ('<br>', 'breakone'), ('\\n', '\n'), ('\n', 'breakone'), ('</p><p>', 'breakdouble'), (' | ', 'pipepipe'),
						(',', 'comcom'), (';', 'semisemi'), (':', 'doubledot'), ('.', 'nomdot'), ('!', 'markmark'), ('?', 'questquest'), ('=', 'equalequal'), ('&', 'andand'), ("'", 'quotone'), ('"', 'quotdouble'), ('-', 'dashdash'), ('–', 'dashdash'),
						('~', 'swunswun'), ('*', 'starstar'), ('+', 'crosscross'), ('(', 'brackstart'), (')', 'brackend'), ('//', 'verticvertic'), ('/', 'slashslash'), ('#', 'atrhomb'), ('@', 'atmonkey'), ('§', 'parapara'), ('$', 'dolldoll'), ('%', 'perper')):
						text = text.replace(*ex)
			text = re.sub(r'(\<.*?\>|[^\w])', ' ', text) # FIRST: Remove text between arrow-signs (Links etc.) // SECOND: Remove anything that's not alphanumeric or underscore
		for n in (('fatstart', '[B]'), ('fatend', '[/B]'), ('slanstart', '[I]'), ('slanend', '[/I]'), ('breakone   ', '[CR]'), ('breakone  ', '[CR]'), ('breakone', '[CR]'), ('breakdouble', '[CR][CR]'), ('pipepipe', ' | '),
					('comcom', ','), ('semisemi', ';'), ('doubledot', ':'), ('nomdot', '.'), ('markmark', '!'), ('questquest', '?'), ('equalequal', '='), ('andand', '&'), ('quotone', "'"), ('quotdouble', '"'), ('dashdash', '-'),
					('swunswun', '~'), ('starstar', '*'), ('crosscross', '+'), ('brackstart', '('), ('brackend', ')'), ('verticvertic', '|'), ('slashslash', '/'), ('atrhomb', '#'), ('atmonkey', '@'), ('parapara', '§'), ('dolldoll', '$'), ('perper', '%'),
					('&lt;', '<'), ('&gt;', '>'), ('&amp;', '&'), ('&apos;', "'"), ("&#x27;", "'"), ('&#34;', '"'), ('&#39;', '\''), ('&#039;', '\''), ('\\u0026', '&'), ('&quot;', '"'), ('&szlig;', 'ß'), ('&mdash;', '-'), ('&ndash;', '-'), ('&nbsp;', ' '),
					('&#x00c4', 'Ä'), ('&#x00e4', 'ä'), ('&#x00d6', 'Ö'), ('&#x00f6', 'ö'), ('&#x00dc', 'Ü'), ('&#x00fc', 'ü'), ('&#x00df', 'ß'), ('&#xD;', ''), ('\xc2\xb7', '-'), ('\xa0', ' '),
					('&Auml;', 'Ä'), ('&Euml;', 'Ë'), ('&Iuml;', 'Ï'), ('&Ouml;', 'Ö'), ('&Uuml;', 'Ü'), ('&auml;', 'ä'), ('&euml;', 'ë'), ('&iuml;', 'ï'), ('&ouml;', 'ö'), ('&uuml;', 'ü'), ('&yuml;', 'ÿ'),
					('&agrave;', 'à'), ('&aacute;', 'á'), ('&acirc;', 'â'), ('&egrave;', 'è'), ('&eacute;', 'é'), ('&ecirc;', 'ê'), ('&igrave;', 'ì'), ('&iacute;', 'í'), ('&icirc;', 'î'),
					('&ograve;', 'ò'), ('&oacute;', 'ó'), ('&ocirc;', 'ô'), ('&ugrave;', 'ù'), ('&uacute;', 'ú'), ('&ucirc;', 'û'), ('\\"', '"'), ('\t', ''), ('   ', ''), ('  ', ' ')):
					text = text.replace(*n)
		if CUSTOMISE is True:
			if 'Abonnier' in text or 'Subscribe' in text or 'Stream with' in text or 'http' in text:
				text = re.sub(r'(?:(?:\[CR]?-? ?)*Abonnier[\s\S]+|(?:\[CR]?-? ?)*Subscribe now [\s\S]+|(?:\[CR]?(?:#dfb)?-? ?)*Stream with[\s\S]+|https?:(?:\S+\[CR]|\S+))', '', text)
			text = text.replace('[CR][CR]...', '').replace('!.', '!')
		text = text.strip()
	return text

def create_entries(metadata, SIGNS=None):
	listitem = xbmcgui.ListItem(metadata['Title'])
	vinfo = listitem.getVideoInfoTag() if KODI_BUILD >= 20 else {}
	if KODI_BUILD >= 20: vinfo.setTitle(metadata['Title'])
	else: vinfo['Title'] = metadata['Title']
	description = metadata['Plot'] if metadata.get('Plot') not in ['', 'None', None] else ' '
	if KODI_BUILD >= 20: vinfo.setPlot(description)
	else: vinfo['Plot'] = description
	if str(metadata.get('Duration')).isdecimal():
		if KODI_BUILD >= 20: vinfo.setDuration(int(metadata['Duration']))
		else: vinfo['Duration'] = metadata['Duration']
	if KODI_BUILD >= 20: vinfo.setGenres(['Fußball'])
	else: vinfo['Genre'] = 'Fußball'
	if KODI_BUILD >= 20: vinfo.setStudios(['Dfb.de'])
	else: vinfo['Studio'] = 'Dfb.de'
	if metadata.get('Mediatype', ''):
		if KODI_BUILD >= 20: vinfo.setMediaType(metadata['Mediatype'])
		else: vinfo['Mediatype'] = metadata['Mediatype']
	picture = metadata.get('Image', icon)
	listitem.setArt({'icon': icon, 'thumb': picture, 'poster': picture, 'fanart': defaultFanart})
	if picture and not artpic in picture:
		listitem.setArt({'fanart': picture})
	if metadata.get('Reference') == 'Single':
		listitem.setProperty('IsPlayable', 'true')
	if KODI_BUILD < 20: listitem.setInfo('Video', vinfo)
	return listitem
