"""Auto Backup Service"""
from __future__ import absolute_import, division, unicode_literals

import time
import threading
import xbmc

from .globals import G
from .loggers import Logger
from .backup import Backup
from .backup_manager import BackupManager


class AutoBackupService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._thread = None
            cls._instance._running = False
        return cls._instance

    def start(self):
        """Start auto backup service"""
        if self._running:
            return

        if not G.auto_backup_enabled:
            Logger.info('Auto-Backup deaktiviert')
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        Logger.info('Auto-Backup Service gestartet')

    def stop(self):
        """Stop auto backup service"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        Logger.info('Auto-Backup Service gestoppt')

    def _run(self):
        """Main service loop"""
        last_backup_time = time.time()   # statt 0

        while self._running:
            try:
                interval_seconds = G.auto_backup_interval * 3600
                current_time = time.time()

                if current_time - last_backup_time >= interval_seconds:
                    Logger.info('Erstelle automatisches Backup...')
                    if Backup.create_backup():
                        BackupManager.cleanup_old_backups()
                    last_backup_time = current_time

                for _ in range(60):
                    if not self._running:
                        break
                    time.sleep(1)

            except Exception as e:
                Logger.error('Auto-Backup Fehler: {}'.format(str(e)))
                time.sleep(60)


class AutoBackupMonitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.service = AutoBackupService()

    def onSettingsChanged(self):
        Logger.info('Einstellungen geändert - Auto-Backup aktualisieren')
        if G.auto_backup_enabled:
            self.service.start()
        else:
            self.service.stop()


def run_auto_backup_service():
    """Entry point for auto backup service"""
    Logger.info('Auto-Backup Service initialisieren...')
    monitor = AutoBackupMonitor()

    if G.auto_backup_enabled:
        monitor.service.start()

    monitor.waitForAbort()
    monitor.service.stop()
    Logger.info('Auto-Backup Service beendet')