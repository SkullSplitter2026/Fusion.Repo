# -*- coding: utf-8 -*-

import time
import threading

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

from .api import (
    get_sequence_data
)


ADDON = xbmcaddon.Addon()

LIVE_METADATA = ADDON.getSettingBool(
    "live_metadata"
)

UPDATE_INTERVAL = int(
    ADDON.getSetting(
        "metadata_interval"
    ) or 15
)

FANART_ENABLED = ADDON.getSettingBool(
    "fanart"
)

NOTIFY_ENABLED = ADDON.getSettingBool(
    "notify"
)

NOTIFICATION_COOLDOWN = 30


# LOCALIZED STRINGS
NOW_PLAYING = ADDON.getLocalizedString(
    30030
)


def clean_label(label):

    return (
        label
        .replace("I♥", "I LOVE ")
        .replace("I ♥", "I LOVE ")
    )


class MetadataUpdater(threading.Thread):

    def __init__(
        self,
        player,
        stream_url,
        channel_id,
        channel_name
    ):

        threading.Thread.__init__(
            self
        )

        self.player = player

        self.stream_url = stream_url

        self.channel_id = channel_id

        self.channel_name = channel_name

        self.daemon = True

    def run(self):

        monitor = xbmc.Monitor()

        last_title = ""

        last_notification = 0

        while (
            not monitor.abortRequested()
            and self.player.isPlaying()
        ):

            try:

                sequence = get_sequence_data()

                current = sequence.get(
                    self.channel_id,
                    {}
                )

                artist = current.get(
                    "artist",
                    ""
                ).strip()

                title = current.get(
                    "title",
                    ""
                ).strip()

                cover = current.get(
                    "cover",
                    ""
                )

                # IGNORE EMPTY
                if not artist and not title:

                    monitor.waitForAbort(
                        UPDATE_INTERVAL
                    )

                    continue

                full_title = "{} - {}".format(
                    artist,
                    title
                ).strip(" -")

                # IGNORE INVALID
                if len(full_title) < 3:

                    monitor.waitForAbort(
                        UPDATE_INTERVAL
                    )

                    continue

                if full_title != last_title:

                    last_title = full_title

                    # CREATE UPDATED LISTITEM
                    li = xbmcgui.ListItem(
                        label=self.channel_name,
                        path=self.stream_url
                    )

                    li.setInfo("music", {
                        "title": title,
                        "artist": artist,
                        "album": self.channel_name
                    })

                    if cover:

                        art = {
                            "thumb": cover,
                            "icon": cover
                        }

                        if FANART_ENABLED:

                            art["fanart"] = cover

                        li.setArt(
                            art
                        )

                    li.setProperty(
                        "IsPlayable",
                        "true"
                    )

                    li.setMimeType(
                        "audio/aac"
                    )

                    li.setContentLookup(
                        False
                    )

                    # RE-APPLY TO PLAYER
                    self.player.play(
                        self.stream_url,
                        li
                    )

                    # SMART NOTIFICATION
                    now = int(
                        time.time()
                    )

                    if (
                        NOTIFY_ENABLED
                        and (
                            now - last_notification
                        ) > NOTIFICATION_COOLDOWN
                    ):

                        last_notification = now

                        xbmcgui.Dialog().notification(
                            "{}".format(
                                NOW_PLAYING
                            ),
                            full_title,
                            cover,
                            5000
                        )

                    xbmc.log(
                        "[I LOVE MUSIC] NOW PLAYING: {}".format(
                            full_title
                        ),
                        xbmc.LOGINFO
                    )

            except Exception as error:

                xbmc.log(
                    "[I LOVE MUSIC] METADATA ERROR: {}".format(
                        str(error)
                    ),
                    xbmc.LOGERROR
                )

            monitor.waitForAbort(
                UPDATE_INTERVAL
            )


def play_stream(
    handle,
    stream_url,
    channel_id="",
    name="",
    cover=""
):

    name = clean_label(name)

    li = xbmcgui.ListItem(
        label=name,
        path=stream_url
    )

    li.setInfo("music", {
        "title": name
    })

    if cover:

        art = {
            "thumb": cover,
            "icon": cover
        }

        if FANART_ENABLED:

            art["fanart"] = cover

        li.setArt(
            art
        )

    li.setProperty(
        "IsPlayable",
        "true"
    )

    li.setMimeType(
        "audio/aac"
    )

    li.setContentLookup(
        False
    )

    xbmcplugin.setResolvedUrl(
        handle,
        True,
        li
    )

    # START METADATA REFRESH
    if (
        LIVE_METADATA
        and channel_id
    ):

        updater = MetadataUpdater(
            xbmc.Player(),
            stream_url,
            channel_id,
            name
        )

        updater.start()