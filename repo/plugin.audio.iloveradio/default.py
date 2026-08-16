# -*- coding: utf-8 -*-

import sys
import time
import threading

import xbmc
import xbmcaddon

from urllib.parse import parse_qsl

from resources.lib.navigator import (
    show_main_menu,
    show_categories,
    show_category,
    show_channels,
    show_favorites,
    show_search,
    open_settings
)

from resources.lib.player import (
    play_stream
)

from resources.lib.favorites import (
    add_favorite,
    remove_favorite
)

from resources.lib.m3u import (
    export_m3u
)

import resources.lib.navigator as navigator


ADDON = xbmcaddon.Addon()

AUTO_REFRESH = ADDON.getSettingBool(
    "auto_refresh"
)

REFRESH_INTERVAL = int(
    ADDON.getSetting(
        "refresh_interval"
    ) or 120
)


def auto_refresh():

    monitor = xbmc.Monitor()

    while not monitor.abortRequested():

        time.sleep(
            REFRESH_INTERVAL
        )

        xbmc.executebuiltin(
            "Container.Refresh"
        )


HANDLE = int(sys.argv[1])

navigator.PLUGIN_URL = sys.argv[0]

# START AUTO REFRESH
if AUTO_REFRESH:

    refresh_thread = threading.Thread(
        target=auto_refresh
    )

    refresh_thread.daemon = True

    refresh_thread.start()

params = dict(
    parse_qsl(
        sys.argv[2][1:]
    )
)

action = params.get("action")


# PLAY STREAM
if action == "play":

    stream = params.get(
        "stream"
    )

    channel_id = params.get(
        "id",
        ""
    )

    name = params.get(
        "name",
        ""
    )

    cover = params.get(
        "cover",
        ""
    )

    play_stream(
        HANDLE,
        stream,
        channel_id,
        name,
        cover
    )


# EXPORT M3U
elif action == "export_m3u":

    export_m3u()


# SETTINGS
elif action == "settings":

    open_settings()


# SEARCH
elif action == "search":

    show_search(
        HANDLE
    )


# CATEGORIES MENU
elif action == "categories":

    show_categories(
        HANDLE
    )


# CATEGORY VIEW
elif action == "category":

    category = params.get(
        "category",
        ""
    )

    show_category(
        HANDLE,
        category
    )


# FAVORITES VIEW
elif action == "favorites":

    show_favorites(
        HANDLE
    )


# ADD FAVORITE
elif action == "favorite_add":

    channel_id = params.get(
        "id",
        ""
    )

    add_favorite(
        channel_id
    )

    xbmc.executebuiltin(
        "Container.Refresh"
    )


# REMOVE FAVORITE
elif action == "favorite_remove":

    channel_id = params.get(
        "id",
        ""
    )

    remove_favorite(
        channel_id
    )

    xbmc.executebuiltin(
        "Container.Refresh"
    )


# ALL CHANNELS
elif action == "channels":

    show_channels(
        HANDLE
    )


# MAIN MENU
else:

    show_main_menu(
        HANDLE
    )