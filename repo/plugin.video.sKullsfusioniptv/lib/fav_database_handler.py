import sqlite3
import os
import xbmcvfs
from lib.loggers import Logger
from typing import Optional
import xbmcaddon


class FavDatabase:
    def __init__(self):
        # Pfad im Profil-Ordner des Addons
        db_dir = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.svod/')
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        self.db_path = os.path.join(db_dir, 'favorites.db')
        self._create_table()
        self._migrate_schema()

    def _create_table(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS favorites (
                    id TEXT,
                    portal_id INTEGER,
                    type TEXT,
                    name TEXT,
                    logo TEXT,
                    cmd TEXT,
                    description TEXT,
                    PRIMARY KEY (id, portal_id, type)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS portal_meta (
                    portal_id INTEGER PRIMARY KEY,
                    fingerprint TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS favorite_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    sort_order INTEGER DEFAULT 0
                )
            ''')

    def _migrate_schema(self):
        """Falls eine alte DB ohne 'description' existiert, Spalte nachziehen."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.execute("PRAGMA table_info(favorites)")
                cols = [row[1] for row in cur.fetchall()]  # row[1] = column name
                if 'description' not in cols:
                    conn.execute("ALTER TABLE favorites ADD COLUMN description TEXT")
                if 'category_id' not in cols:
                    conn.execute("ALTER TABLE favorites ADD COLUMN category_id INTEGER")
                if 'sort_order' not in cols:
                    conn.execute("ALTER TABLE favorites ADD COLUMN sort_order INTEGER DEFAULT 0")
        except Exception as e:
            Logger.error(f"DB migration failed: {str(e)}")

    def add_favorite(self, video_id, portal_id, _type, name, logo='', cmd='', description='', category_id=None, sort_order=0):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT OR REPLACE INTO favorites (id, portal_id, type, name, logo, cmd, description, category_id, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (str(video_id), int(portal_id), str(_type), str(name), str(logo or ''), str(cmd or ''),
                 str(description or ''), category_id, int(sort_order))
            )

    def remove_favorite(self, video_id, portal_id, _type):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'DELETE FROM favorites WHERE id = ? AND portal_id = ? AND type = ?',
                (str(video_id), int(portal_id), str(_type))
            )

    def remove_favorites_for_portal(self, portal_id: int):
        """Löscht alle lokalen Favoriten für ein Portal-Slot/portal_id."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM favorites WHERE portal_id = ?', (int(portal_id),))

    def _get_portal_fingerprint(self, portal_data: dict) -> str:
        """
        Erzeugt eine "Identität" des Portals aus JSON-Daten.
        Wenn sich diese ändert, ist es praktisch ein anderes Portal -> Favoriten sollten weg.
        """
        server = str(portal_data.get('server_address', '')).strip()
        mac = str(portal_data.get('mac_address', '')).strip()
        serial = str(portal_data.get('serial_number', '')).strip()
        # Wichtig: Fingerprint muss stabil sein, aber Änderungen zuverlässig erkennen.
        return f"server={server}|mac={mac}|serial={serial}"

    def _get_stored_fingerprint(self, portal_id: int) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute('SELECT fingerprint FROM portal_meta WHERE portal_id = ?', (int(portal_id),))
            row = cur.fetchone()
            return row[0] if row else None

    def _store_fingerprint(self, portal_id: int, fingerprint: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT OR REPLACE INTO portal_meta (portal_id, fingerprint) VALUES (?, ?)',
                (int(portal_id), str(fingerprint))
            )

    def _delete_meta(self, portal_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM portal_meta WHERE portal_id = ?', (int(portal_id),))

    def cleanup_orphaned_or_changed_portals(self, max_portals: int = 10):
        """
        Cleanup-Strategie (nutzt JSON-Konfiguration):
        - Portal nicht in JSON -> Favoriten dieses portal_id löschen
        - Portal im Slot ausgetauscht (Fingerprint geändert) -> Favoriten löschen
        """
        try:
            from .globals import G
            portals = G.get_available_portals()
            portal_ids_in_json = {int(p.get('id', 0)) for p in portals}

            # Alle möglichen Portal-IDs durchgehen
            all_portal_ids = set(range(1, int(max_portals) + 1))

            for portal_id in all_portal_ids:
                if portal_id not in portal_ids_in_json:
                    # Portal nicht in JSON -> Favoriten + Meta entfernen
                    self.remove_favorites_for_portal(portal_id)
                    self._delete_meta(portal_id)
                    continue

                # Portal-Daten aus JSON holen für Fingerprint
                portal_data = None
                for p in portals:
                    if int(p.get('id', 0)) == portal_id:
                        portal_data = p
                        break

                if not portal_data:
                    self.remove_favorites_for_portal(portal_id)
                    self._delete_meta(portal_id)
                    continue

                fp = self._get_portal_fingerprint(portal_data)
                old_fp = self._get_stored_fingerprint(portal_id)

                if old_fp is None:
                    # Erstinitialisierung: nur merken
                    self._store_fingerprint(portal_id, fp)
                elif old_fp != fp:
                    # Portal im gleichen Slot wurde ausgetauscht -> Favoriten weg
                    Logger.info(f"Portal {portal_id} changed -> removing local favorites for this portal slot.")
                    self.remove_favorites_for_portal(portal_id)
                    self._store_fingerprint(portal_id, fp)
        except Exception as e:
            Logger.error(f"Favorites cleanup failed: {str(e)}")

    def list_favorites(self, _type, category_id=None):
        with sqlite3.connect(self.db_path) as conn:
            if category_id is None:
                # Alle Favoriten (alte Funktionalität)
                cur = conn.execute(
                    'SELECT id, portal_id, type, name, logo, cmd, description, category_id, sort_order FROM favorites WHERE type = ? ORDER BY sort_order, name COLLATE NOCASE',
                    (str(_type),)
                )
            else:
                # Nur Favoriten einer bestimmten Kategorie
                cur = conn.execute(
                    'SELECT id, portal_id, type, name, logo, cmd, description, category_id, sort_order FROM favorites WHERE type = ? AND category_id = ? ORDER BY sort_order, name COLLATE NOCASE',
                    (str(_type), int(category_id))
                )
            rows = cur.fetchall()

        return [
            {'id': r[0], 'portal_id': r[1], 'type': r[2], 'name': r[3], 'logo': r[4], 'cmd': r[5], 'description': r[6], 'category_id': r[7], 'sort_order': r[8]}
            for r in rows
        ]

    def list_favorites_uncategorized(self, _type):
        """Listet alle Favoriten ohne Kategorie auf."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                'SELECT id, portal_id, type, name, logo, cmd, description, category_id, sort_order FROM favorites WHERE type = ? AND category_id IS NULL ORDER BY sort_order, name COLLATE NOCASE',
                (str(_type),)
            )
            rows = cur.fetchall()
        return [
            {'id': r[0], 'portal_id': r[1], 'type': r[2], 'name': r[3], 'logo': r[4], 'cmd': r[5], 'description': r[6], 'category_id': r[7], 'sort_order': r[8]}
            for r in rows
        ]

    # ==================== Kategorie-Verwaltung ====================

    def add_category(self, name, _type):
        """Erstellt eine neue Kategorie."""
        with sqlite3.connect(self.db_path) as conn:
            # Maximale sort_order ermitteln
            cur = conn.execute('SELECT MAX(sort_order) FROM favorite_categories WHERE type = ?', (str(_type),))
            max_order = cur.fetchone()[0]
            new_order = (max_order or 0) + 1

            cur = conn.execute(
                'INSERT INTO favorite_categories (name, type, sort_order) VALUES (?, ?, ?)',
                (str(name), str(_type), new_order)
            )
            return cur.lastrowid

    def remove_category(self, category_id):
        """Löscht eine Kategorie und setzt alle zugehörigen Favoriten auf category_id=NULL."""
        with sqlite3.connect(self.db_path) as conn:
            # Favoriten dieser Kategorie auf NULL setzen
            conn.execute('UPDATE favorites SET category_id = NULL WHERE category_id = ?', (int(category_id),))
            # Kategorie löschen
            conn.execute('DELETE FROM favorite_categories WHERE id = ?', (int(category_id),))

    def rename_category(self, category_id, new_name):
        """Benennt eine Kategorie um."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'UPDATE favorite_categories SET name = ? WHERE id = ?',
                (str(new_name), int(category_id))
            )

    def move_category(self, category_id, new_sort_order):
        """Ändert die Sortierreihenfolge einer Kategorie."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'UPDATE favorite_categories SET sort_order = ? WHERE id = ?',
                (int(new_sort_order), int(category_id))
            )

    def list_categories(self, _type):
        """Listet alle Kategorien eines Typs auf."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                'SELECT id, name, type, sort_order FROM favorite_categories WHERE type = ? ORDER BY sort_order, name COLLATE NOCASE',
                (str(_type),)
            )
            rows = cur.fetchall()
        return [
            {'id': r[0], 'name': r[1], 'type': r[2], 'sort_order': r[3]}
            for r in rows
        ]

    def assign_favorite_to_category(self, video_id, portal_id, _type, category_id):
        """Weist einen Favoriten einer Kategorie zu."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'UPDATE favorites SET category_id = ? WHERE id = ? AND portal_id = ? AND type = ?',
                (int(category_id) if category_id is not None else None, str(video_id), int(portal_id), str(_type))
            )

    def move_favorite_in_category(self, video_id, portal_id, _type, new_sort_order):
        """Ändert die Sortierreihenfolge eines Favoriten innerhalb seiner Kategorie."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'UPDATE favorites SET sort_order = ? WHERE id = ? AND portal_id = ? AND type = ?',
                (int(new_sort_order), str(video_id), int(portal_id), str(_type))
            )

    def get_category_count(self, category_id):
        """Gibt die Anzahl der Favoriten in einer Kategorie zurück."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                'SELECT COUNT(*) FROM favorites WHERE category_id = ?',
                (int(category_id),)
            )
            return cur.fetchone()[0]