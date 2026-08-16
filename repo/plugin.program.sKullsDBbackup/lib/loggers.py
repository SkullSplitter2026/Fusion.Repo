"""Logger wrapper for Kodi addon logging"""
from __future__ import absolute_import, division, unicode_literals

import xbmc

ADDON_ID = 'plugin.program.sKullsDBbackup'


class Logger:
    @staticmethod
    def log(message, level=xbmc.LOGINFO):
        xbmc.log('[sKullsDBBackup] {}'.format(message), level)

    @staticmethod
    def debug(message):
        Logger.log(message, xbmc.LOGDEBUG)

    @staticmethod
    def info(message):
        Logger.log(message, xbmc.LOGINFO)

    @staticmethod
    def warning(message):
        Logger.log(message, xbmc.LOGWARNING)

    @staticmethod
    def error(message):
        Logger.log(message, xbmc.LOGERROR)