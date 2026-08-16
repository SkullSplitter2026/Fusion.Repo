"""Utility functions for sKulls DB Backup"""
from __future__ import absolute_import, division, unicode_literals

import os
import time
import xbmcvfs
import xbmcgui

from .loggers import Logger


def get_timestamp():
    return time.strftime('%Y%m%d_%H%M%S')


def get_backup_display_name(backup_name):
    """Convert backup filename to display name"""
    name = backup_name.replace('.zip', '')
    try:
        dt = time.strptime(name, 'backup_%Y%m%d_%H%M%S')
        return time.strftime('%d.%m.%Y %H:%M:%S', dt)
    except ValueError:
        return name


def get_file_size_display(size_bytes):
    """Convert bytes to human readable format"""
    size = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return '{:.1f} {}'.format(size, unit)
        size /= 1024
    return '{:.1f} TB'.format(size)


def copy_file(source, destination):
    """Copy a file using xbmcvfs"""
    try:
        xbmcvfs.copy(source, destination)
        return True
    except Exception as e:
        Logger.error('Failed to copy {}: {}'.format(source, str(e)))
        return False


def delete_file(filepath):
    """Delete a file using xbmcvfs"""
    try:
        if xbmcvfs.exists(filepath):
            xbmcvfs.delete(filepath)
        return True
    except Exception as e:
        Logger.error('Failed to delete {}: {}'.format(filepath, str(e)))
        return False


def create_directory(path):
    """Create directory if it doesn't exist"""
    try:
        if not xbmcvfs.exists(path):
            xbmcvfs.mkdir(path)
        return True
    except Exception as e:
        Logger.error('Failed to create directory {}: {}'.format(path, str(e)))
        return False


def get_directory_size(path):
    """Get total size of a directory"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if xbmcvfs.exists(filepath):
                try:
                    stat = xbmcvfs.Stat(filepath)
                    total_size += stat.st_size()
                except Exception:
                    pass
    return total_size


def show_notification(message, level=xbmcgui.NOTIFICATION_INFO, time_ms=5000):
    """Show Kodi notification"""
    xbmcgui.Dialog().notification('sKulls DB Backup', message, level, time_ms)


def show_yesno_dialog(title, line1, line2=''):
    """Show Yes/No dialog"""
    return xbmcgui.Dialog().yesno(title, line1, line2)


def show_browse_dialog(title, type=0, shares='', mask='', use_thumbs=False, default=''):
    """Show browse dialog for folder/file selection"""
    return xbmcgui.Dialog().browse(type, title, shares, mask, use_thumbs, False, default)