"""Main addon logic - UI menus and routing"""
from __future__ import absolute_import, division, unicode_literals

import os
from urllib.parse import parse_qsl

import xbmcgui
import xbmcplugin
import xbmc

from .globals import G
from .backup import Backup
from .backup_manager import BackupManager
from .utils import show_notification

# Brand colors (matching the addon name style)
COLOR_PRIMARY = 'indianred'
COLOR_ACCENT = 'gold'


def _colorize(text, color, bold=False):
    """Wrap text in Kodi color/bold BBCode tags"""
    if bold:
        return '[COLOR {}][B]{}[/B][/COLOR]'.format(color, text)
    return '[COLOR {}]{}[/COLOR]'.format(color, text)


class SDBBackup:
    def __init__(self, argv):
        self.argv = argv
        self.handle = int(argv[1])
        self.fanart = os.path.join(
            G.addon_config.addon_path, 'resources', 'media', 'fanart.jpg'
        )

    def router(self, param_string):
        """Route to appropriate handler based on URL parameters"""
        params = dict(parse_qsl(param_string))

        action = params.get('action', None)

        if action is None or action == 'main_menu':
            self.__show_main_menu()
        elif action == 'create_backup':
            self.__create_backup()
        elif action == 'restore_backup':
            self.__restore_backup(params)
        elif action == 'delete_backup':
            self.__delete_backup(params)
        elif action == 'list_backups':
            self.__show_backup_list()
        elif action == 'auto_backup_status':
            self.__show_auto_backup_status()
        elif action == 'toggle_auto_backup':
            self.__toggle_auto_backup()
        elif action == 'set_backup_interval':
            self.__set_backup_interval()
        elif action == 'settings':
            self.__open_settings()
        else:
            self.__show_main_menu()

    def __make_list_item(self, label, icon, plot):
        """Create a styled ListItem with icon, fanart and description"""
        list_item = xbmcgui.ListItem(label=label)
        list_item.setArt({
            'icon': icon,
            'thumb': icon,
            'fanart': self.fanart
        })
        list_item.setInfo('video', {
            'title': label,
            'plot': plot
        })
        return list_item

    def __show_main_menu(self):
        """Display main menu"""
        items = [
            {
                'label': _colorize(G.get_localized_string(32001), COLOR_PRIMARY, bold=True),
                'icon': 'DefaultAddProgram.png',
                'plot': G.get_localized_string(32050),
                'action': 'create_backup',
                'folder': False,
            },
            {
                'label': _colorize(G.get_localized_string(32002), COLOR_ACCENT, bold=True),
                'icon': 'DefaultFolderOpens.png',
                'plot': G.get_localized_string(32051),
                'action': 'list_backups',
                'folder': True,
            },
            {
                'label': _colorize(G.get_localized_string(32003), COLOR_PRIMARY, bold=True),
                'icon': 'DefaultAddonService.png',
                'plot': G.get_localized_string(32052),
                'action': 'auto_backup_status',
                'folder': True,
            },
            {
                'label': _colorize(G.get_localized_string(32004), COLOR_ACCENT, bold=True),
                'icon': 'DefaultAddonProgram.png',
                'plot': G.get_localized_string(32053),
                'action': 'settings',
                'folder': False,
            },
        ]

        for item in items:
            list_item = self.__make_list_item(item['label'], item['icon'], item['plot'])

            url = G.get_plugin_url({'action': item['action']})
            xbmcplugin.addDirectoryItem(
                handle=self.handle,
                url=url,
                listitem=list_item,
                isFolder=item['folder']
            )

        xbmcplugin.setContent(self.handle, 'files')
        xbmcplugin.endOfDirectory(self.handle)

    def __create_backup(self):
        """Create a new backup"""
        Backup.create_backup()
        xbmcplugin.endOfDirectory(self.handle, succeeded=True, cacheToDisc=False)
        xbmc.executebuiltin('Container.Refresh')

    def __restore_backup(self, params):
        """Restore from backup"""
        filepath = params.get('file', '')
        if filepath:
            Backup.restore_backup(filepath)
        xbmcplugin.endOfDirectory(self.handle, succeeded=True, cacheToDisc=False)

    def __delete_backup(self, params):
        """Delete a backup"""
        filepath = params.get('file', '')
        if filepath:
            BackupManager.delete_backup(filepath)
        xbmcplugin.endOfDirectory(self.handle, succeeded=True, cacheToDisc=False)
        xbmc.executebuiltin('Container.Refresh')

    def __show_backup_list(self):
        """Show list of available backups"""
        BackupManager.show_backup_list(self.handle, self.fanart)

    def __show_auto_backup_status(self):
        """Show auto backup status and options"""
        enabled = G.auto_backup_enabled
        interval = G.auto_backup_interval

        status_text = G.get_localized_string(32006) if enabled else G.get_localized_string(32007)
        status_color = COLOR_ACCENT if enabled else COLOR_PRIMARY

        items = [
            {
                'label': _colorize(
                    G.get_localized_string(32005).format(status_text), status_color, bold=True
                ),
                'icon': 'DefaultAddonService.png',
                'plot': G.get_localized_string(32054),
                'action': 'toggle_auto_backup',
                'folder': False,
            },
            {
                'label': _colorize(
                    G.get_localized_string(32008).format(interval), COLOR_ACCENT, bold=True
                ),
                'icon': 'DefaultTimer.png',
                'plot': G.get_localized_string(32055),
                'action': 'set_backup_interval',
                'folder': False,
            },
            {
                'label': _colorize(G.get_localized_string(32009), COLOR_PRIMARY, bold=True),
                'icon': 'DefaultBack.png',
                'plot': G.get_localized_string(32056),
                'action': 'main_menu',
                'folder': True,
            },
        ]

        for item in items:
            list_item = self.__make_list_item(item['label'], item['icon'], item['plot'])

            url = G.get_plugin_url({'action': item['action']})
            xbmcplugin.addDirectoryItem(
                handle=self.handle,
                url=url,
                listitem=list_item,
                isFolder=item['folder']
            )

        xbmcplugin.setContent(self.handle, 'files')
        xbmcplugin.endOfDirectory(self.handle)

    def __toggle_auto_backup(self):
        """Toggle auto backup on/off"""
        current = G.auto_backup_enabled
        G.set_setting('auto_backup_enabled', 'false' if current else 'true')

        status_text = G.get_localized_string(32012) if current else G.get_localized_string(32011)
        show_notification(G.get_localized_string(32010).format(status_text))
        xbmcplugin.endOfDirectory(self.handle, succeeded=True, cacheToDisc=False)
        xbmc.executebuiltin('Container.Refresh')

    def __set_backup_interval(self):
        """Set backup interval"""
        hours_options = [1, 2, 4, 6, 8, 12, 24, 48, 72, 168]
        labels = []

        for hours in hours_options:
            if hours == 1:
                label = G.get_localized_string(32038).format(hours)
            else:
                label = G.get_localized_string(32037).format(hours)

            if hours == 168:
                label = '{} ({})'.format(label, G.get_localized_string(32039))

            labels.append(label)

        dialog = xbmcgui.Dialog()
        selected = dialog.select(G.get_localized_string(32013), labels)

        if selected >= 0:
            G.set_setting('auto_backup_interval', str(hours_options[selected]))
            show_notification(G.get_localized_string(32014).format(labels[selected]))

        xbmcplugin.endOfDirectory(self.handle, succeeded=True, cacheToDisc=False)
        xbmc.executebuiltin('Container.Refresh')

    def __open_settings(self):
        """Open addon settings"""
        xbmcplugin.endOfDirectory(self.handle, succeeded=True, cacheToDisc=False)
        xbmc.executebuiltin(
            'Addon.OpenSettings({})'.format(G.addon_config.addon_id)
        )


def run(argv):
    """Main entry point"""
    addon = SDBBackup(argv)
    param_string = argv[2][1:] if len(argv) > 2 else ''
    addon.router(param_string)