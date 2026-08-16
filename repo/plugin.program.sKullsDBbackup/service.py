"""sKulls DB Backup - Background service entry point"""
from __future__ import absolute_import, division, unicode_literals

from lib.auto_backup import run_auto_backup_service

if __name__ == '__main__':
    run_auto_backup_service()