# -*- coding: utf-8 -*-

from .common import *
from .external.scrapetube import *


def main_menu(EXTRA=None):
	debug_MS("(navigator.main_menu) ------------------------------------------------ START = main_menu -----------------------------------------------")
	if PERS_TOKEN == 'AIzaSy.................................':
		return dialog.ok(addon_id, translation(30350))
	elif PERS_TOKEN[:6] != 'AIzaSy':
		return dialog.ok(addon_id, translation(30501))
	if EXTRA is None:
		add_views({'mode': 'list_videos', 'extra': 'YOUT_STREAMS'}, create_entries({'Title': translation(30621), 'Plot': 'Live-Events und Aktuelles: Deutscher Fußball-Bund (DFB)'}))
		add_views({'link': BASE_YOUT.format(CHANNEL_CODE, f'UU{CHANNEL_CODE[2:]}'), 'extra': 'YT_FOLDER'}, create_entries({'Title': translation(30622), 'Plot': 'Neue Uploads: Deutscher Fußball-Bund (DFB)'}))
		target = f"https://youtube.googleapis.com/youtube/v3/playlists?part=snippet,contentDetails&channelId={CHANNEL_CODE}&maxResults=50&key={PERS_TOKEN}"
		page_number, next_page = 1, None
		while page_number > 0:
			content = trackContent(target if page_number == 1 else next_page)
			for item in content.get('items', []):
				if item.get('kind', '') == 'youtube#playlist':
					debug_MS(f"(navigator.main_menu[1.1]) xxxxx ENTRY-01 : {item} xxxxx")
					debug_MS("---------------------------------------------")
					title, yout_video = cleaning(item['snippet']['title']), item.get('id', None)
					plot = (cleaning(item['snippet'].get('description', '')) or 'Offizieller YouTube Kanal des Deutschen Fußball-Bundes (DFB)')
					photo = (item['snippet']['thumbnails'].get('maxres', {}).get('url', '') or item['snippet']['thumbnails'].get('standard', {}).get('url', '') or item['snippet']['thumbnails'].get('high', {}).get('url', ''))
					numbers = item['contentDetails']['itemCount'] if str(item.get('contentDetails', {}).get('itemCount')).isdecimal() else None
					if isinstance(numbers, int) and int(numbers) == 0: continue
					name = translation(30623).format(title) if numbers is None else translation(30624).format(title, numbers)
					FETCH_UNO = create_entries({'Title': name, 'Plot': f'Playlist: {plot}', 'Image': photo})
					add_views({'link': BASE_YOUT.format(CHANNEL_CODE, yout_video), 'extra': 'YT_FOLDER'}, FETCH_UNO)
			if content.get('nextPageToken', None):
				next_page, page_number = f"{target}&pageToken={content['nextPageToken']}", page_number.__add__(1)
				debug_MS(f"(navigator.main_menu[1.2]) PAGES ### NOW GET NEXTPAGE : {next_page} ###")
			else: break
	else:
		content = get_channel(CHANNEL_CODE, limit=50, sleep=1, content_type='streams') # mit 'get_channel' hier die Streams eines Channels abrufen
		for item in content:
			plot, (travel_view, duration), (live_stream, soon_stream) = "", (None for _ in range(2)), (False for _ in range(2))
			yout_video = item.get('contentId', None)
			separate = [elem.strip() for elem in cleaning(item['title']['runs'][0]['text'], True).split('|')]
			debug_MS(f"(navigator.main_menu[2.1]) XXXXXX ENTRY-02 : {item} XXXXXX")
			debug_MS(f"(navigator.main_menu[2.2]) ### TITLE-SPLIT : {separate} ###")
			debug_MS("---------------------------------------------")
			travel_date = (item.get('publishedTimeText', {}).get('simpleText', None) or item.get('viewCountText', {}).get('simpleText', None))
			travel_past = item.get('publishedTimeText', {}).get('simpleText')
			if item.get('viewCountText', {}).get('simpleText'):
				travel_view = cleaning(item['viewCountText']['simpleText'], True).replace(' Aufrufe', '').replace('Views ', '').replace(' warten', '').replace('Waiting ', '')
			travel_time = item.get('lengthText', {}).get('simpleText')
			if travel_time and travel_time[:4].upper() == 'LIVE':
				live_stream = True
				plot += translation(30625)
			elif travel_date and re.search(r'\d{2}.\d{2}.\d{2}, \d{2}:\d{2}', travel_date): # Geplant für: 01.06.26, 20:00
				cipher = re.search(r'\d{2}.\d{2}.\d{2}, \d{2}:\d{2}', travel_date) # 01.06.26, 20:00
				available = datetime(*(time.strptime(cipher.group(), '%d.%m.%y, %H:%M')[0:6]))+timedelta(hours=9) # Irgend etwas stimmt mit der Zeit nicht - liegt 9 Stunden zurück !!!
				event_start = available.strftime('%a{0} %d{0}%m{0}%Y {1} %H{2}%M').format( '.', '•', ':')
				for tt in (('Mon', translation(32101)), ('Tue', translation(32102)), ('Wed', translation(32103)), ('Thu', translation(32104)), ('Fri', translation(32105)), ('Sat', translation(32106)), ('Sun', translation(32107))):
					event_start = event_start.replace(*tt)
				soon_stream = True
				if travel_view and not re.search(r'\d{2}.\d{2}.\d{2}, \d{2}:\d{2}', travel_view):
					plot += translation(30626).format(event_start, travel_view)
				else: plot += translation(30627).format(event_start)
			elif travel_past and any(vsx in travel_past.lower() for vsx in ['streamt', 'streamed']): # vor 3 Tagen gestreamt
				duration = get_seconds(travel_time)
				travel_past = cleaning(travel_past, True).replace(' gestreamt', '').replace('Streamed ', '').replace('vor ', 'Vor ')
				if travel_view and not re.search(r'\d{2}.\d{2}.\d{2}, \d{2}:\d{2}', travel_view):
					plot += translation(30628).format(travel_past, travel_view)
				else: plot += translation(30629).format(travel_past)
			if len(separate) > 1:
				title = f"{separate[0]}: {separate[1]}" if len(separate) > 1 and separate[0] == 'RE-LIVE' else f"{separate[0]} - {separate[2]}" if len(separate) > 2 and \
					separate[1] == 'RE-LIVE' else f"{separate[0].replace('RE-LIVE', 'RE-LIVE:')} - {separate[1]}" if len(separate) > 2 else separate[0].replace('RE-LIVE', 'RE-LIVE:')
				plot += f"[B]{title} | {separate[-2]} | {separate[-1]}[/B]" if len(separate) == 4 and separate[-2] not in title else f"[B]{title} | {separate[-1]}[/B]" if \
					(len(separate) == 4 and separate[-2] in title) or (len(separate) == 2 and separate[0] != 'RE-LIVE') or len(separate) == 3 else f"[B]{title}[/B]"
			else:
				title, plot = separate[0], f"{plot}[B]{separate[0]}[/B]"
			if live_stream is True:
				name = translation(30630).format(title[4:] if title[:4] == 'LIVE' else title)
			else: name = title[4:] if title[:4] == 'LIVE' else title
			photo = f"https://i.ytimg.com/vi/{yout_video}/sddefault.jpg"
			FETCH_UNO = {'Title': name, 'Plot': plot, 'Duration': duration, 'Mediatype': 'episode', 'Image': photo, 'Reference': 'Single'}
			add_views({'mode': 'play_video', 'link': yout_video}, create_entries(FETCH_UNO), False)
	xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=True, cacheToDisc=False)

def play_video(PLID):
	debug_MS("(navigator.play_video) ------------------------------------------------ START = play_video -----------------------------------------------")
	TEST_URL, FINAL_URL = False, f"plugin://plugin.video.youtube/play/?video_id={PLID}"
	verify = trackContent(f"https://youtu.be/{PLID}", 'GET', 'TRACK', timeout=15)
	if verify and verify.status_code in [200, 201, 202]: TEST_URL = True
	if FINAL_URL and TEST_URL:
		log(f"(navigator.play_video) StreamURL : {FINAL_URL}")
		LSM = xbmcgui.ListItem(path=FINAL_URL, offscreen=True)
		xbmcplugin.setResolvedUrl(ADDON_HANDLE, True, LSM)
	else:
		failing(f"(navigator.play_video[2]) ##### Abspielen des Streams NICHT möglich #####\n ##### IDD : {PLID} || FINAL_URL : {FINAL_URL} #####\n ########## Das Youtube-Video wurde nicht gefunden !!! ##########")
		xbmcplugin.setResolvedUrl(ADDON_HANDLE, False, xbmcgui.ListItem())
		xbmc.PlayList(1).clear()
		return dialog.notification(translation(30521).format('VIDEO'), translation(30524), icon, 10000)

def add_views(params, listitem, folder=True):
	uws = params.get('link') if params.get('extra') == 'YT_FOLDER' else build_mass(params)
	listitem.setPath(uws)
	return xbmcplugin.addDirectoryItem(ADDON_HANDLE, uws, listitem, folder)
