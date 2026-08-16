# -*- coding: utf-8 -*-

import time

import xbmc
import xbmcaddon

from resources.lib.api import (
    get_channels,
    get_category_segmentnames
)

from resources.lib.categories import (
    CATEGORIES
)

from resources.lib.cache import (
    clear_expired_cache,
    is_cache_valid
)


ADDON = xbmcaddon.Addon()

STREAM_TYPE = ADDON.getSetting(
    "stream_type"
)

if not STREAM_TYPE:

    STREAM_TYPE = "aac"


CACHE_REFRESH_INTERVAL = 300

CHANNEL_CACHE_TIME = 3600
CATEGORY_CACHE_TIME = 21600
SEQUENCE_CACHE_TIME = 10


def log(message):

    xbmc.log(
        "[I LOVE MUSIC SERVICE] {}".format(
            message
        ),
        xbmc.LOGINFO
    )


class ILOVEBackgroundService:

    def __init__(self):

        self.monitor = xbmc.Monitor()

        self.player = xbmc.Player()

    def refresh_channels(self):

        try:

            # SKIP DURING PLAYBACK
            if self.player.isPlaying():

                log(
                    "SKIP CHANNEL REFRESH DURING PLAYBACK"
                )

                return

            cache_name = (
                "channels_{}".format(
                    STREAM_TYPE
                )
            )

            # ONLY IF CACHE EXPIRED
            if is_cache_valid(
                cache_name,
                CHANNEL_CACHE_TIME
            ):

                log(
                    "CHANNEL CACHE STILL VALID"
                )

                return

            log(
                "REFRESH CHANNEL CACHE"
            )

            get_channels()

        except Exception as error:

            log(
                "CHANNEL REFRESH ERROR: {}".format(
                    str(error)
                )
            )

    def refresh_categories(self):

        try:

            # SKIP DURING PLAYBACK
            if self.player.isPlaying():

                log(
                    "SKIP CATEGORY REFRESH DURING PLAYBACK"
                )

                return

            for name, url in CATEGORIES.items():

                cache_name = (
                    "category_{}".format(
                        url.split("/")[-2]
                    )
                )

                # ONLY IF CACHE EXPIRED
                if is_cache_valid(
                    cache_name,
                    CATEGORY_CACHE_TIME
                ):

                    log(
                        "CATEGORY CACHE VALID: {}".format(
                            name
                        )
                    )

                    continue

                log(
                    "REFRESH CATEGORY: {}".format(
                        name
                    )
                )

                get_category_segmentnames(
                    url
                )

        except Exception as error:

            log(
                "CATEGORY REFRESH ERROR: {}".format(
                    str(error)
                )
            )

    def cleanup_cache(self):

        try:

            cache_map = {

                "channels_aac":
                    CHANNEL_CACHE_TIME,

                "channels_mp3":
                    CHANNEL_CACHE_TIME,

                "sequence":
                    SEQUENCE_CACHE_TIME
            }

            # CATEGORY CACHES
            for name, url in CATEGORIES.items():

                cache_name = (
                    "category_{}".format(
                        url.split("/")[-2]
                    )
                )

                cache_map[
                    cache_name
                ] = CATEGORY_CACHE_TIME

            clear_expired_cache(
                cache_map
            )

        except Exception as error:

            log(
                "CACHE CLEANUP ERROR: {}".format(
                    str(error)
                )
            )

    def run(self):

        log(
            "SERVICE STARTED"
        )

        while not self.monitor.abortRequested():

            try:

                self.refresh_channels()

                self.refresh_categories()

                self.cleanup_cache()

            except Exception as error:

                log(
                    "SERVICE ERROR: {}".format(
                        str(error)
                    )
                )

            self.monitor.waitForAbort(
                CACHE_REFRESH_INTERVAL
            )

        log(
            "SERVICE STOPPED"
        )


if __name__ == "__main__":

    service = ILOVEBackgroundService()

    service.run()