# -*- coding: utf-8 -*-

import os
import json

import xbmc
import xbmcvfs
import xbmcaddon

from .api import get_channels


ADDON = xbmcaddon.Addon()

PROFILE_PATH = xbmcvfs.translatePath(
    ADDON.getAddonInfo("profile")
)

FAVORITES_FILE = os.path.join(
    PROFILE_PATH,
    "favorites.json"
)


def log(message):

    xbmc.log(
        "[I LOVE MUSIC] {}".format(message),
        xbmc.LOGINFO
    )


def ensure_profile():

    if not xbmcvfs.exists(
        PROFILE_PATH
    ):

        xbmcvfs.mkdirs(
            PROFILE_PATH
        )


def get_favorites():

    ensure_profile()

    if not xbmcvfs.exists(
        FAVORITES_FILE
    ):

        return []

    try:

        file = xbmcvfs.File(
            FAVORITES_FILE
        )

        data = file.read()

        file.close()

        favorites = json.loads(
            data
        )

        return favorites

    except Exception as error:

        log(
            "GET FAVORITES ERROR: {}".format(
                str(error)
            )
        )

        return []


def save_favorites(favorites):

    ensure_profile()

    try:

        file = xbmcvfs.File(
            FAVORITES_FILE,
            "w"
        )

        file.write(
            json.dumps(
                favorites,
                indent=4
            )
        )

        file.close()

        return True

    except Exception as error:

        log(
            "SAVE FAVORITES ERROR: {}".format(
                str(error)
            )
        )

        return False


def add_favorite(channel_id):

    favorites = get_favorites()

    if channel_id not in favorites:

        favorites.append(
            channel_id
        )

        save_favorites(
            favorites
        )

        log(
            "FAVORITE ADDED: {}".format(
                channel_id
            )
        )


def remove_favorite(channel_id):

    favorites = get_favorites()

    if channel_id in favorites:

        favorites.remove(
            channel_id
        )

        save_favorites(
            favorites
        )

        log(
            "FAVORITE REMOVED: {}".format(
                channel_id
            )
        )


def is_favorite(channel_id):

    favorites = get_favorites()

    return channel_id in favorites


def get_favorite_channels():

    favorites = get_favorites()

    channels = get_channels()

    filtered = []

    for item in channels:

        if item.get("id") in favorites:

            filtered.append(item)

    return filtered