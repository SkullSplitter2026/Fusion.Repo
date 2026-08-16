# -*- coding: utf-8 -*-

import os
import json
import time

import xbmc
import xbmcvfs
import xbmcaddon


ADDON = xbmcaddon.Addon()

ADDON_ID = ADDON.getAddonInfo(
    "id"
)

PROFILE_PATH = xbmcvfs.translatePath(
    "special://profile/addon_data/{}/".format(
        ADDON_ID
    )
)

CACHE_DIR = os.path.join(
    PROFILE_PATH,
    "cache"
)


def log(message):

    xbmc.log(
        "[I LOVE MUSIC CACHE] {}".format(
            message
        ),
        xbmc.LOGINFO
    )


def ensure_cache_dir():

    # PROFILE DIR
    if not xbmcvfs.exists(
        PROFILE_PATH
    ):

        xbmcvfs.mkdirs(
            PROFILE_PATH
        )

    # CACHE DIR
    if not xbmcvfs.exists(
        CACHE_DIR
    ):

        xbmcvfs.mkdirs(
            CACHE_DIR
        )


def get_cache_file(name):

    ensure_cache_dir()

    return os.path.join(
        CACHE_DIR,
        "{}.json".format(name)
    )


def save_cache(
    name,
    data
):

    try:

        cache_file = get_cache_file(
            name
        )

        payload = {
            "timestamp": int(
                time.time()
            ),
            "data": data
        }

        with open(
            cache_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                payload,
                f,
                ensure_ascii=False,
                indent=2
            )

        log(
            "CACHE SAVED: {}".format(
                name
            )
        )

        return True

    except Exception as error:

        log(
            "SAVE ERROR {} -> {}".format(
                name,
                str(error)
            )
        )

        return False


def load_cache(name):

    try:

        cache_file = get_cache_file(
            name
        )

        if not os.path.exists(
            cache_file
        ):

            return None

        with open(
            cache_file,
            "r",
            encoding="utf-8"
        ) as f:

            payload = json.load(f)

        return payload

    except Exception as error:

        log(
            "LOAD ERROR {} -> {}".format(
                name,
                str(error)
            )
        )

        return None


def is_cache_valid(
    name,
    max_age
):

    try:

        payload = load_cache(
            name
        )

        if not payload:

            return False

        timestamp = payload.get(
            "timestamp",
            0
        )

        age = int(
            time.time()
        ) - timestamp

        valid = age < max_age

        log(
            "CACHE VALID {} -> {} ({}s)".format(
                name,
                valid,
                age
            )
        )

        return valid

    except Exception as error:

        log(
            "VALID ERROR {} -> {}".format(
                name,
                str(error)
            )
        )

        return False


def get_cache_data(name):

    payload = load_cache(
        name
    )

    if not payload:

        return None

    return payload.get(
        "data"
    )


def clear_cache(name):

    try:

        cache_file = get_cache_file(
            name
        )

        if os.path.exists(
            cache_file
        ):

            os.remove(
                cache_file
            )

            log(
                "CACHE REMOVED: {}".format(
                    name
                )
            )

        return True

    except Exception as error:

        log(
            "CLEAR ERROR {} -> {}".format(
                name,
                str(error)
            )
        )

        return False


def clear_expired_cache(max_age_map):

    try:

        ensure_cache_dir()

        files = os.listdir(
            CACHE_DIR
        )

        removed = 0

        for file_name in files:

            if not file_name.endswith(
                ".json"
            ):

                continue

            cache_name = file_name.replace(
                ".json",
                ""
            )

            max_age = max_age_map.get(
                cache_name
            )

            # UNKNOWN CACHE
            if max_age is None:

                continue

            if not is_cache_valid(
                cache_name,
                max_age
            ):

                clear_cache(
                    cache_name
                )

                removed += 1

        log(
            "CACHE CLEANUP: {} files".format(
                removed
            )
        )

        return True

    except Exception as error:

        log(
            "CACHE CLEANUP ERROR: {}".format(
                str(error)
            )
        )

        return False


def cache_exists(name):

    cache_file = get_cache_file(
        name
    )

    return os.path.exists(
        cache_file
    )


def get_cache_age(name):

    payload = load_cache(
        name
    )

    if not payload:

        return None

    timestamp = payload.get(
        "timestamp",
        0
    )

    return int(
        time.time()
    ) - timestamp