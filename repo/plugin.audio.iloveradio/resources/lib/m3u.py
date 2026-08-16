# -*- coding: utf-8 -*-

import os
import json
import ssl

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

try:
    from urllib.request import Request, urlopen
except ImportError:
    from urllib2 import Request, urlopen

from .constants import (
    CHANNELS_URL
)


ADDON = xbmcaddon.Addon()

ADDON_ID = ADDON.getAddonInfo(
    "id"
)

DEFAULT_PATH = (
    "special://profile/addon_data/{}/".format(
        ADDON_ID
    )
)

DEFAULT_ICON = (
    "https://ilovemusic.de/"
    "fileadmin/templates/img/"
    "iloveradio_icon_sw_400x400.png"
)


# LOCALIZED STRINGS
EXPORT_SUCCESS = ADDON.getLocalizedString(
    30031
)

EXPORT_FAILED = ADDON.getLocalizedString(
    30032
)


def log(message):

    xbmc.log(
        "[I LOVE MUSIC M3U] {}".format(
            message
        ),
        xbmc.LOGINFO
    )


def clean_label(label):

    return (
        label
        .replace("I♥", "I LOVE ")
        .replace("I ♥", "I LOVE ")
        .replace("♥", "LOVE")
    )


def get_url(url):

    ssl_context = ssl._create_unverified_context()

    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response = urlopen(
        request,
        context=ssl_context,
        timeout=10
    )

    return response.read().decode(
        "utf-8",
        errors="ignore"
    )


def get_json(url):

    data = get_url(url)

    return json.loads(
        data.encode("utf-8").decode("utf-8-sig")
    )


def build_direct_stream(play_url):

    try:

        slug = (
            play_url
            .split("/")[-2]
        )

        # DEFAULT HOST
        host = "stream35"

        # SPECIAL HOSTS
        if any(x in slug for x in [
            "radio",
            "dance",
            "top100",
            "trashpop",
            "2dance"
        ]):

            host = "stream18"

        return (
            "https://ilm.{host}.radiohost.de/"
            "{slug}_mp3-192"
        ).format(
            host=host,
            slug=slug
        )

    except Exception:

        return play_url


def export_m3u():

    try:

        export_path = ADDON.getSetting(
            "m3u_path"
        )

        if not export_path:

            export_path = DEFAULT_PATH

        export_path = xbmcvfs.translatePath(
            export_path
        )

        # CREATE DIR
        if not xbmcvfs.exists(
            export_path
        ):

            xbmcvfs.mkdirs(
                export_path
            )

        file_path = os.path.join(
            export_path,
            "ilovemusic.m3u"
        )

        channels_data = get_json(
            CHANNELS_URL
        )

        lines = [
            "#EXTM3U"
        ]

        for channel_id, item in channels_data.items():

            try:

                name = clean_label(
                    item.get(
                        "name",
                        ""
                    )
                )

                streams = (
                    item["streams"]
                    ["streams"]
                )

                # FORCE MP3
                if "mp3" in streams:

                    play_url = (
                        streams["mp3"][0]
                    )

                # FALLBACK AAC
                elif "aac" in streams:

                    play_url = (
                        streams["aac"][0]
                    )

                else:

                    continue

                # BUILD DIRECT RADIOHOST URL
                stream = build_direct_stream(
                    play_url
                )

                lines.append(
                    '#EXTINF:-1 '
                    'tvg-id="" '
                    'tvg-name="{name}" '
                    'tvg-shift="" '
                    'radio="true" '
                    'tvg-logo="{logo}" '
                    'group-title="I LOVE MUSIC",{name}'.format(
                        name=name,
                        logo=DEFAULT_ICON
                    )
                )

                lines.append(
                    stream
                )

                log(
                    "EXPORT STREAM {} -> {}".format(
                        name,
                        stream
                    )
                )

            except Exception as error:

                log(
                    "CHANNEL EXPORT ERROR {} -> {}".format(
                        item.get("name"),
                        str(error)
                    )
                )

        with open(
            file_path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
                "\n".join(lines)
            )

        log(
            "M3U EXPORTED: {}".format(
                file_path
            )
        )

        xbmcgui.Dialog().notification(
            "I Love Music",
            EXPORT_SUCCESS,
            xbmcgui.NOTIFICATION_INFO,
            5000
        )

        return True

    except Exception as error:

        log(
            "EXPORT ERROR: {}".format(
                str(error)
            )
        )

        xbmcgui.Dialog().notification(
            "I Love Music",
            EXPORT_FAILED,
            xbmcgui.NOTIFICATION_ERROR,
            5000
        )

        return False