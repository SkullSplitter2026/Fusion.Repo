# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import xbmcaddon

from .api import get_channels


ADDON = xbmcaddon.Addon()


# LOCALIZED STRINGS
SEARCH = ADDON.getLocalizedString(
    30020
)

NO_RESULTS = ADDON.getLocalizedString(
    30021
)


def log(message):

    xbmc.log(
        "[I LOVE MUSIC] {}".format(
            message
        ),
        xbmc.LOGINFO
    )


def search_channels():

    keyboard = xbmc.Keyboard(
        "",
        "I LOVE MUSIC {}".format(
            SEARCH
        )
    )

    keyboard.doModal()

    # SEARCH CANCELED
    if not keyboard.isConfirmed():

        return None

    query = keyboard.getText().strip()

    # EMPTY SEARCH
    if not query:

        return None

    query = query.lower()

    channels = get_channels()

    results = []

    for item in channels:

        name = item.get(
            "name",
            ""
        ).lower()

        genre = item.get(
            "genre",
            ""
        ).lower()

        artist = item.get(
            "artist",
            ""
        ).lower()

        title = item.get(
            "title",
            ""
        ).lower()

        search_text = " ".join([
            name,
            genre,
            artist,
            title
        ])

        if query in search_text:

            results.append(
                item
            )

    log(
        "SEARCH '{}' -> {} RESULTS".format(
            query,
            len(results)
        )
    )

    if not results:

        xbmcgui.Dialog().notification(
            "I LOVE MUSIC",
            NO_RESULTS,
            xbmcgui.NOTIFICATION_INFO,
            3000
        )

    return results