# -*- coding: utf-8 -*-
# Python 3

import ast
import time
import xbmcgui


class cCache(object):
    _win = None

    def __init__(self):
        # see https://kodi.wiki/view/Window_IDs
        self._win = xbmcgui.Window(10000)

    def __del__(self):
        del self._win

    def get(self, key, cache_time):
        cachedata = self._win.getProperty(key)

        if cachedata:
            cachedata = ast.literal_eval(cachedata)
            if time.time() - cachedata[0] < cache_time or cache_time < 0:
                return cachedata[1]
            else:
                self._win.clearProperty(key)

        return None
    
    def set(self, key, data):
        self._win.setProperty(key, repr((time.time(), data)))

    def clear(self):
        self._win.clearProperties()
