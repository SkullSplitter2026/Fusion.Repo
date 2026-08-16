# -*- coding: utf-8 -*-

import xbmcgui
import xbmcplugin

from urllib.parse import urlencode

from .categories import CATEGORIES


PLUGIN_URL = ""


def show_main_menu(handle):

    for category in CATEGORIES:

        url = build_url({
            "action": "category",
            "category": category
        })

        li = xbmcgui.ListItem(
            label=category
        )

        xbmcplugin.addDirectoryItem(
            handle=handle,
            url=url,
            listitem=li,
            isFolder=True
        )

    xbmcplugin.endOfDirectory(handle)


def build_url(query):

    return "{}?{}".format(
        PLUGIN_URL,
        urlencode(query)
    )