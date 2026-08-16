# -*- coding: utf-8 -*-

import json
import re
import ssl

import xbmc
import xbmcaddon

try:
    from urllib.request import Request, urlopen
except ImportError:
    from urllib2 import Request, urlopen

from .constants import (
    CHANNELS_URL,
    SEQUENCE_URL,
    BASE_URL
)

from .categories import (
    CATEGORIES
)

from .cache import (
    save_cache,
    get_cache_data,
    is_cache_valid
)


ADDON = xbmcaddon.Addon()

STREAM_TYPE = ADDON.getSetting(
    "stream_type"
)

if not STREAM_TYPE:

    STREAM_TYPE = "aac"


CHANNEL_CACHE_TIME = 3600
CATEGORY_CACHE_TIME = 21600
SEQUENCE_CACHE_TIME = 10


def log(message):

    xbmc.log(
        "[I LOVE MUSIC] {}".format(
            message
        ),
        xbmc.LOGINFO
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


def get_sequence_data():

    try:

        # LOAD SEQUENCE CACHE
        if is_cache_valid(
            "sequence",
            SEQUENCE_CACHE_TIME
        ):

            cached = get_cache_data(
                "sequence"
            )

            if cached:

                log(
                    "USING SEQUENCE CACHE"
                )

                return cached

        data = get_json(
            SEQUENCE_URL
        )

        sequence = {}

        for item in data:

            channel_id = item.get(
                "id"
            )

            current = item.get(
                "current",
                {}
            )

            cover = current.get(
                "cover",
                ""
            )

            if cover:

                cover = BASE_URL + cover

            sequence[channel_id] = {

                "artist": current.get(
                    "artist",
                    ""
                ),

                "title": current.get(
                    "title",
                    ""
                ),

                "cover": cover
            }

        # SAVE SEQUENCE CACHE
        save_cache(
            "sequence",
            sequence
        )

        return sequence

    except Exception as error:

        log(
            "SEQUENCE ERROR: {}".format(
                str(error)
            )
        )

        return {}


def get_channels():

    try:

        cache_name = (
            "channels_{}".format(
                STREAM_TYPE
            )
        )

        # LOAD CHANNEL CACHE
        if is_cache_valid(
            cache_name,
            CHANNEL_CACHE_TIME
        ):

            cached = get_cache_data(
                cache_name
            )

            if cached:

                log(
                    "USING CHANNEL CACHE"
                )

                return cached

        channels_data = get_json(
            CHANNELS_URL
        )

        sequence_data = get_sequence_data()

        channels = []

        for channel_id, item in channels_data.items():

            try:

                streams = (
                    item["streams"]
                    ["streams"]
                )

                # DEBUG STREAM TYPES
                log(
                    "STREAMS {} -> {}".format(
                        item.get("name"),
                        streams
                    )
                )

                # SELECT STREAM TYPE
                if STREAM_TYPE in streams:

                    stream_url = (
                        streams
                        [STREAM_TYPE][0]
                    )

                # FALLBACK AAC
                elif "aac" in streams:

                    stream_url = (
                        streams
                        ["aac"][0]
                    )

                # FALLBACK MP3
                elif "mp3" in streams:

                    stream_url = (
                        streams
                        ["mp3"][0]
                    )

                else:

                    raise Exception(
                        "No valid stream found"
                    )

            except Exception as error:

                log(
                    "STREAM ERROR {} -> {}".format(
                        item.get("name"),
                        str(error)
                    )
                )

                continue

            current = sequence_data.get(
                channel_id,
                {}
            )

            # ONLY ACTIVE CHANNELS
            if not current:

                continue

            channels.append({

                "id": channel_id,

                "name": item.get(
                    "name",
                    ""
                ),

                "genre": item.get(
                    "genre",
                    ""
                ),

                "segmentname": item.get(
                    "segmentname",
                    ""
                ),

                "stream": stream_url,

                "artist": current.get(
                    "artist",
                    ""
                ),

                "title": current.get(
                    "title",
                    ""
                ),

                "cover": current.get(
                    "cover",
                    ""
                )
            })

        # SAVE CHANNEL CACHE
        save_cache(
            cache_name,
            channels
        )

        return channels

    except Exception as error:

        log(
            "CHANNEL ERROR: {}".format(
                str(error)
            )
        )

        return []


def get_category_segmentnames(url):

    try:

        cache_name = (
            "category_{}".format(
                url.split("/")[-2]
            )
        )

        # LOAD CATEGORY CACHE
        if is_cache_valid(
            cache_name,
            CATEGORY_CACHE_TIME
        ):

            cached = get_cache_data(
                cache_name
            )

            if cached:

                log(
                    "USING CATEGORY CACHE {}".format(
                        cache_name
                    )
                )

                return cached

        html = get_url(url)

        matches = re.findall(
            r'href="/([a-zA-Z0-9\\-]+)"',
            html
        )

        # ONLY LAST PART OF PAGE
        matches = matches[-15:]

        segmentnames = []

        for match in matches:

            value = match.lower()

            # DEBUG
            log(
                "MATCH {} -> {}".format(
                    url,
                    value
                )
            )

            # NORMAL CHANNELS
            if value.startswith(
                "ilove"
            ):

                segmentnames.append(
                    value
                )

            # TOP100 CHANNELS
            elif "top100" in value:

                cleaned = (
                    value
                    .replace("-", "")
                )

                segmentnames.append(
                    cleaned
                )

        segmentnames = list(
            set(segmentnames)
        )

        log(
            "SEGMENTS {}: {}".format(
                url,
                segmentnames
            )
        )

        # SAVE CATEGORY CACHE
        save_cache(
            cache_name,
            segmentnames
        )

        return segmentnames

    except Exception as error:

        log(
            "CATEGORY ERROR: {}".format(
                str(error)
            )
        )

        return []


def get_channels_by_category(category):

    channels = get_channels()

    category_url = CATEGORIES.get(
        category,
        ""
    )

    if not category_url:

        return []

    segmentnames = get_category_segmentnames(
        category_url
    )

    filtered = []

    for item in channels:

        segmentname = item.get(
            "segmentname",
            ""
        ).lower()

        # REMOVE "-"
        segmentname = (
            segmentname
            .replace("-", "")
        )

        if segmentname in segmentnames:

            filtered.append(
                item
            )

            log(
                "[{}] {}".format(
                    category,
                    item.get("name")
                )
            )

    return filtered