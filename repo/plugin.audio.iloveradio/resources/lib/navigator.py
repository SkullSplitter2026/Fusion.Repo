# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

from urllib.parse import urlencode

from .api import (
    get_channels,
    get_channels_by_category
)

from .categories import (
    CATEGORIES
)

from .favorites import (
    is_favorite,
    get_favorite_channels
)

from .search import (
    search_channels
)


ADDON = xbmcaddon.Addon()

FANART_ENABLED = ADDON.getSettingBool(
    "fanart"
)

SHOW_SETTINGS = ADDON.getSettingBool(
    "show_settings"
)

ADDON_ICON = ADDON.getAddonInfo(
    "icon"
)

ADDON_FANART = ADDON.getAddonInfo(
    "fanart"
)

DEFAULT_ICON = (
    "https://ilovemusic.de/"
    "fileadmin/templates/img/"
    "iloveradio_icon_sw_400x400.png"
)


# LOCALIZED STRINGS
SEARCH = ADDON.getLocalizedString(
    30000
)

FAVORITES = ADDON.getLocalizedString(
    30001
)

CATEGORIES_LABEL = ADDON.getLocalizedString(
    30002
)

ALL_CHANNELS = ADDON.getLocalizedString(
    30003
)

SETTINGS = ADDON.getLocalizedString(
    30004
)

ADD_TO_FAVORITES = ADDON.getLocalizedString(
    30010
)

REMOVE_FROM_FAVORITES = ADDON.getLocalizedString(
    30011
)


def clean_label(label):

    return (
        label
        .replace("I♥", "I LOVE ")
        .replace("I ♥", "I LOVE ")
    )


def set_folder_art(listitem):

    listitem.setArt({
        "thumb": ADDON_ICON,
        "icon": ADDON_ICON,
        "fanart": ADDON_FANART
    })


def show_main_menu(handle):

    # SEARCH
    search_url = build_url({
        "action": "search"
    })

    search_li = xbmcgui.ListItem(
        label="{}".format(
            SEARCH
        )
    )

    set_folder_art(
        search_li
    )

    xbmcplugin.addDirectoryItem(
        handle=handle,
        url=search_url,
        listitem=search_li,
        isFolder=True
    )

    # FAVORITES
    fav_url = build_url({
        "action": "favorites"
    })

    fav_li = xbmcgui.ListItem(
        label="{}".format(
            FAVORITES
        )
    )

    set_folder_art(
        fav_li
    )

    xbmcplugin.addDirectoryItem(
        handle=handle,
        url=fav_url,
        listitem=fav_li,
        isFolder=True
    )

    # CATEGORIES
    categories_url = build_url({
        "action": "categories"
    })

    categories_li = xbmcgui.ListItem(
        label="{}".format(
            CATEGORIES_LABEL
        )
    )

    set_folder_art(
        categories_li
    )

    xbmcplugin.addDirectoryItem(
        handle=handle,
        url=categories_url,
        listitem=categories_li,
        isFolder=True
    )

    # ALL CHANNELS
    channels_url = build_url({
        "action": "channels"
    })

    channels_li = xbmcgui.ListItem(
        label="{}".format(
            ALL_CHANNELS
        )
    )

    set_folder_art(
        channels_li
    )

    xbmcplugin.addDirectoryItem(
        handle=handle,
        url=channels_url,
        listitem=channels_li,
        isFolder=True
    )

    # SETTINGS
    if SHOW_SETTINGS:

        settings_li = xbmcgui.ListItem(
            label="{}".format(
                SETTINGS
            )
        )

        set_folder_art(
            settings_li
        )

        settings_url = build_url({
            "action": "settings"
        })

        xbmcplugin.addDirectoryItem(
            handle=handle,
            url=settings_url,
            listitem=settings_li,
            isFolder=False
        )

    xbmcplugin.endOfDirectory(handle)


def show_categories(handle):

    for category in CATEGORIES:

        url = build_url({
            "action": "category",
            "category": category
        })

        li = xbmcgui.ListItem(
            label=category
        )

        set_folder_art(
            li
        )

        li.setProperty(
            "IsPlayable",
            "false"
        )

        xbmcplugin.addDirectoryItem(
            handle=handle,
            url=url,
            listitem=li,
            isFolder=True
        )

    xbmcplugin.endOfDirectory(handle)


def open_settings():

    xbmc.executebuiltin(
        "Addon.OpenSettings(plugin.audio.iloveradio)"
    )


def show_search(handle):

    channels = search_channels()

    # SEARCH CANCELED
    if channels is None:

        xbmcplugin.endOfDirectory(
            handle,
            succeeded=False
        )

        return

    show_channel_items(
        handle,
        channels
    )


def show_favorites(handle):

    channels = get_favorite_channels()

    show_channel_items(
        handle,
        channels
    )


def show_channels(handle):

    channels = get_channels()

    show_channel_items(
        handle,
        channels
    )


def show_category(
    handle,
    category
):

    channels = get_channels_by_category(
        category
    )

    show_channel_items(
        handle,
        channels
    )


def show_channel_items(
    handle,
    channels
):

    # SORT CHANNELS
    channels = sorted(
        channels,
        key=lambda x: clean_label(
            x["name"]
        ).lower()
    )

    for item in channels:

        channel_id = item.get(
            "id",
            ""
        )

        label = clean_label(
            item["name"]
        )

        artist = item.get(
            "artist",
            ""
        )

        title = item.get(
            "title",
            ""
        )

        plot = "{} - {}".format(
            artist,
            title
        )

        url = build_url({
            "action": "play",
            "id": channel_id,
            "stream": item["stream"],
            "name": label,
            "cover": item.get("cover", "")
        })

        li = xbmcgui.ListItem(
            label=label
        )

        # SECOND LINE
        li.setLabel2(plot)

        cover = item.get(
            "cover",
            ""
        ).strip()

        if not cover.startswith("http"):
            cover = DEFAULT_ICON

        art = {
            "thumb": cover,
            "icon": cover
        }

        if FANART_ENABLED:

            art["fanart"] = cover

        li.setArt(
            art
        )

        # CLEAN MUSIC INFO
        li.setInfo("music", {
            "title": title,
            "artist": artist,
            "album": label,
            "genre": item["genre"],
            "tracknumber": 1
        })

        # EXTRA PROPERTIES FOR SKINS
        li.setProperty(
            "Artist",
            artist
        )

        li.setProperty(
            "Title",
            title
        )

        li.setProperty(
            "Album",
            label
        )

        li.setProperty(
            "Genre",
            item["genre"]
        )

        li.setProperty(
            "Plot",
            plot
        )

        li.setProperty(
            "IsPlayable",
            "true"
        )

        # CONTEXT MENU
        context_menu = []

        if is_favorite(channel_id):

            remove_url = build_url({
                "action": "favorite_remove",
                "id": channel_id
            })

            context_menu.append((
                REMOVE_FROM_FAVORITES,
                "RunPlugin({})".format(
                    remove_url
                )
            ))

        else:

            add_url = build_url({
                "action": "favorite_add",
                "id": channel_id
            })

            context_menu.append((
                ADD_TO_FAVORITES,
                "RunPlugin({})".format(
                    add_url
                )
            ))

        li.addContextMenuItems(
            context_menu
        )

        xbmcplugin.addDirectoryItem(
            handle=handle,
            url=url,
            listitem=li,
            isFolder=False
        )

    xbmcplugin.endOfDirectory(handle)


def build_url(query):

    return "{}?{}".format(
        PLUGIN_URL,
        urlencode(query)
    )


PLUGIN_URL = ""