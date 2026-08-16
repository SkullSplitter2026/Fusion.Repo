""" 
    Put this script in the root folder of your repo and it will
    zip up all addon folders, create a new zip in your zips folder
    and then update the md5 and addons.xml file
"""

import os
import hashlib
import shutil
import sys
import zipfile
import time
from datetime import datetime

from xml.etree import ElementTree

os.system("cls" if os.name == "nt" else "clear")

class Colors:
    RESET = "\x1b[0m"
    BOLD = "\x1b[1m"
    BOLD_GREEN = "\x1b[1;32m"
    BG_BLACK = "\x1b[40m"

print(f"""{Colors.BOLD_GREEN}{Colors.BG_BLACK}
                          ____  __.     .__  .__           .__
                    _____|    |/ _|__ __|  | |  |   ______ |__| ____   ____
                   /  ___/      < |  |  \  | |  |  /  ___/ |  |/    \_/ __)
                   \___ \|    |  \|  |  /  |_|  |__\___ \  |  |   |  \  \___
                  /____  >____|__ \____/|____/____/____  > |__|___|  /\___  >
                       \/        \/                    \/          \/     \/
 {Colors.RESET}""")

SCRIPT_VERSION = 5
KODI_VERSIONS = ["omega", "repo"]
IGNORE = [
    ".git",
    ".github",
    ".gitignore",
    ".DS_Store",
    "thumbs.db",
    ".idea",
    "venv",
]
_COLOR_ESCAPE = "\x1b[{}m"
_COLORS = {
    "black": "30",
    "red": "31",
    "green": "4;32",
    "yellow": "3;33",
    "blue": "34",
    "magenta": "35",
    "cyan": "1;36",
    "grey": "37",
    "endc": "0",
}


def _setup_colors():
    """
    Return True if the running system's terminal supports color,
    and False otherwise.
    """

    def vt_codes_enabled_in_windows_registry():
        """
        Check the Windows registry to see if VT code handling has been enabled by default.
        """
        try:
            import winreg
        except:
            return False
        else:
            reg_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, "Console", access=winreg.KEY_ALL_ACCESS
            )
            try:
                reg_key_value, _ = winreg.QueryValueEx(reg_key, "VirtualTerminalLevel")
            except FileNotFoundError:
                try:
                    winreg.SetValueEx(
                        reg_key, "VirtualTerminalLevel", 0, winreg.KEY_DWORD, 1
                    )
                except:
                    return False
                else:
                    reg_key_value, _ = winreg.QueryValueEx(
                        reg_key, "VirtualTerminalLevel"
                    )
            else:
                return reg_key_value == 1

    def is_a_tty():
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    def legacy_support():
        console = 0
        color = 0
        if sys.platform in ["linux", "linux2", "darwin"]:
            pass
        elif sys.platform == "win32":
            color = os.system("color")

            from ctypes import windll

            k = windll.kernel32
            console = k.SetConsoleMode(k.GetStdHandle(-11), 7)

        return any([color == 1, console == 1])

    return any(
        [
            is_a_tty(),
            sys.platform != "win32",
            "ANSICON" in os.environ,
            "WT_SESSION" in os.environ,
            os.environ.get("TERM_PROGRAM") == "vscode",
            vt_codes_enabled_in_windows_registry(),
            legacy_support(),
        ]
    )


_SUPPORTS_COLOR = _setup_colors()


def color_text(text, color):
    """
    Return an ANSI-colored string, if supported.
    """

    return (
        '{}{}{}'.format(
            _COLOR_ESCAPE.format(_COLORS[color]),
            text,
            _COLOR_ESCAPE.format(_COLORS["endc"]),
        )
        if _SUPPORTS_COLOR
        else text
    )


def convert_bytes(num):
    """
    this function will convert bytes to MB.... GB... etc
    """
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0


class Generator:
    """
    Generates a new addons.xml file from each addons addon.xml file
    and a new addons.xml.md5 hash file. Must be run from the root of
    the checked-out repo.
    """

    def __init__(self, release):
        self.release_path = release
        self.zips_path = os.path.join(self.release_path, "zips")
        addons_xml_path = os.path.join(self.zips_path, "addons.xml")
        md5_path = os.path.join(self.zips_path, "addons.xml.md5")

        self.counters = {
            "video": 0,
            "audio": 0,
            "program": 0,
            "image": 0,
            "script": 0,
            "service": 0,
            "repository": 0,
            "skin": 0,
            "resource": 0,
            "metadata": 0,
            "pvr": 0,
            "other": 0,
        }

        self.total_size = 0
        self.errors = []
        self.start_time = time.time()
        self.total_addons = 0
        self.processed_addons = 0

        print(f"{Colors.BOLD_GREEN}Startzeit: {datetime.now().strftime('%H:%M:%S')}{Colors.RESET}\n")

        if not os.path.exists(self.zips_path):
            os.makedirs(self.zips_path)

        self._remove_binaries()

        if self._generate_addons_file(addons_xml_path):
            self._print_summary()
            self._print_time_stats()
            print()
            print(
                "Successfully updated {}".format(color_text(addons_xml_path, 'yellow'))
            )

            if self._generate_md5_file(addons_xml_path, md5_path):
                print("Successfully updated {}".format(color_text(md5_path, 'yellow')))
                print()

    def _remove_binaries(self):
        """
        Removes any and all compiled Python files before operations.
        """

        for parent, dirnames, filenames in os.walk(self.release_path):
            for fn in filenames:
                if fn.lower().endswith("pyo") or fn.lower().endswith("pyc"):
                    compiled = os.path.join(parent, fn)
                    try:
                        os.remove(compiled)
                        print(
                            "Removed compiled python file: {}".format(
                                color_text(compiled, 'green')
                            )
                        )
                    except:
                        print(
                            "Failed to remove compiled python file: {}".format(
                                color_text(compiled, 'red')
                            )
                        )
            for dir in dirnames:
                if "pycache" in dir.lower():
                    compiled = os.path.join(parent, dir)
                    try:
                        shutil.rmtree(compiled)
                        print(
                            "Removed __pycache__ cache folder: {}".format(
                                color_text(compiled, 'green')
                            )
                        )
                    except:
                        print(
                            "Failed to remove __pycache__ cache folder:  {}".format(
                                color_text(compiled, 'red')
                            )
                        )

    def _create_zip(self, folder, addon_id, version):
        """
        Creates a zip file in the zips directory for the given addon.
        """
        addon_folder = os.path.join(self.release_path, folder)
        zip_folder = os.path.join(self.zips_path, addon_id)
        if not os.path.exists(zip_folder):
            os.makedirs(zip_folder)

        final_zip = os.path.join(zip_folder, "{0}-{1}.zip".format(addon_id, version))
        
        needs_rebuild = True
        if os.path.exists(final_zip):
            addon_mtime = max(os.path.getmtime(os.path.join(root, f)) 
                            for root, _, files in os.walk(addon_folder) 
                            for f in files)
            zip_mtime = os.path.getmtime(final_zip)
            if addon_mtime <= zip_mtime:
                needs_rebuild = False
                self.total_size += os.path.getsize(final_zip)
        
        if needs_rebuild:
            zip = zipfile.ZipFile(final_zip, "w", compression=zipfile.ZIP_DEFLATED)
            root_len = len(os.path.dirname(os.path.abspath(addon_folder)))

            for root, dirs, files in os.walk(addon_folder):
                for i in IGNORE:
                    if i in dirs:
                        try:
                            dirs.remove(i)
                        except:
                            pass
                    for f in files:
                        if f.startswith(i):
                            try:
                                files.remove(f)
                            except:
                                pass

                archive_root = os.path.abspath(root)[root_len:]

                for f in files:
                    fullpath = os.path.join(root, f)
                    archive_name = os.path.join(archive_root, f)
                    zip.write(fullpath, archive_name, zipfile.ZIP_DEFLATED)

            zip.close()
        
        file_size = os.path.getsize(final_zip)
        self.total_size += file_size
        size = convert_bytes(file_size)
        
        self._increment_counter(addon_id)
        self.processed_addons += 1
        
        self._print_progress()
        
        print(
            "  Zip: {} ({}) - {}".format(
                color_text(addon_id, 'cyan'),
                color_text(version, 'green'),
                color_text(size, 'yellow'),
            )
        )

    def _increment_counter(self, addon_id):
        if addon_id.startswith("plugin.video"):
            self.counters["video"] += 1
        elif addon_id.startswith("plugin.audio"):
            self.counters["audio"] += 1
        elif addon_id.startswith("plugin.program"):
            self.counters["program"] += 1
        elif addon_id.startswith("plugin.image"):
            self.counters["image"] += 1
        elif addon_id.startswith("script"):
            self.counters["script"] += 1
        elif addon_id.startswith("service"):
            self.counters["service"] += 1
        elif addon_id.startswith("repository"):
            self.counters["repository"] += 1
        elif addon_id.startswith("skin"):
            self.counters["skin"] += 1
        elif addon_id.startswith("resource"):
            self.counters["resource"] += 1
        elif addon_id.startswith("metadata"):
            self.counters["metadata"] += 1
        elif addon_id.startswith("pvr"):
            self.counters["pvr"] += 1
        else:
            self.counters["other"] += 1

    def _print_progress(self):
        if self.total_addons > 0:
            percent = int((self.processed_addons / self.total_addons) * 50)
            bar = "█" * percent + "░" * (50 - percent)
            elapsed = time.time() - self.start_time
            print(f"\r[{bar}] {self.processed_addons}/{self.total_addons} ({elapsed:.1f}s)", end="", flush=True)

    def _print_summary(self):
        print(f"\n{Colors.BOLD_GREEN}{Colors.BG_BLACK}╔══════════════════════════════════════════════╗")
        print(f"║             Z I P   S U M M A R Y            ║")
        print(f"╠══════════════════════════════════════════════╣")
        
        items = [(cat, count) for cat, count in self.counters.items() if count > 0]
        half = (len(items) + 1) // 2
        
        row1 = items[:half]
        row2 = items[half:]
        
        for i in range(max(len(row1), len(row2))):
            left = row1[i] if i < len(row1) else ("", 0)
            right = row2[i] if i < len(row2) else ("", 0)
            left_str = f"{self._get_category_color(left[0])}{left[0].capitalize():12}{Colors.RESET} : {left[1]:3d}" if left[1] else " " * 18
            right_str = f"{self._get_category_color(right[0])}{right[0].capitalize():12}{Colors.RESET} : {right[1]:3d}" if right[1] else " " * 18
            print(f"║  {left_str}    {right_str}    ║")
        
        total = sum(count for _, count in items)
        total_size_str = convert_bytes(self.total_size)
        print(f"╠══════════════════════════════════════════════╣")
        print(f"║  {Colors.BOLD_GREEN}TOTAL{Colors.RESET}          : {total:3d}  |  Size: {total_size_str:>10}   ║")
        if self.errors:
            print(f"╠══════════════════════════════════════════════╣")
            print(f"║  {color_text('ERRORS:', 'red')} {len(self.errors):3d} addon(s) excluded          ║")
            for err in self.errors[:5]:
                print(f"║    - {color_text(err[:40], 'yellow'):40}    ║")
            if len(self.errors) > 5:
                print(f"║    ... and {len(self.errors) - 5} more                    ║")
        print(f"╚══════════════════════════════════════════════╝{Colors.RESET}")

    def _print_time_stats(self):
        elapsed = time.time() - self.start_time
        start_time_str = datetime.fromtimestamp(self.start_time).strftime('%H:%M:%S')
        end_time = datetime.now().strftime('%H:%M:%S')
        print(f"\n{Colors.BOLD_GREEN}Start: {start_time_str} | End: {end_time} | Duration: {elapsed:.2f}s{Colors.RESET}")

    def _get_category_color(self, cat):
        colors_map = {
            "video": "\x1b[1;31m",
            "audio": "\x1b[1;33m",
            "program": "\x1b[1;32m",
            "image": "\x1b[1;36m",
            "script": "\x1b[1;35m",
            "service": "\x1b[1;34m",
            "repository": "\x1b[1;37m",
            "skin": "\x1b[1;30m",
            "resource": "\x1b[1;35m",
            "metadata": "\x1b[1;33m",
            "pvr": "\x1b[1;31m",
            "other": "\x1b[1;37m",
        }
        return colors_map.get(cat, "")

    def _copy_meta_files(self, addon_id, addon_folder):
        """
        Copy the addon.xml and relevant art files into the relevant folders in the repository.
        """

        tree = ElementTree.parse(os.path.join(self.release_path, addon_id, "addon.xml"))
        root = tree.getroot()

        copyfiles = ["addon.xml"]
        for ext in root.findall("extension"):
            if ext.get("point") in ["xbmc.addon.metadata", "kodi.addon.metadata"]:
                assets = ext.find("assets")
                if assets is None:
                    continue
                for art in [a for a in assets if a.text]:
                    copyfiles.append(os.path.normpath(art.text))

        src_folder = os.path.join(self.release_path, addon_id)
        for file in copyfiles:
            addon_path = os.path.join(src_folder, file)
            if not os.path.exists(addon_path):
                continue

            zips_path = os.path.join(addon_folder, file)
            asset_path = os.path.split(zips_path)[0]
            if not os.path.exists(asset_path):
                os.makedirs(asset_path)

            shutil.copy(addon_path, zips_path)

    def _generate_addons_file(self, addons_xml_path):
        """
        Generates a zip for each found addon, and updates the addons.xml file accordingly.
        """
        if not os.path.exists(addons_xml_path):
            addons_root = ElementTree.Element('addons')
            addons_xml = ElementTree.ElementTree(addons_root)
        else:
            addons_xml = ElementTree.parse(addons_xml_path)
            addons_root = addons_xml.getroot()

        folders = [
            i
            for i in os.listdir(self.release_path)
            if os.path.isdir(os.path.join(self.release_path, i))
            and i != "zips"
            and not i.startswith(".")
            and os.path.exists(os.path.join(self.release_path, i, "addon.xml"))
        ]

        self.total_addons = len(folders)
        self.processed_addons = 0

        print(f"{Colors.BOLD_GREEN}Processing {self.total_addons} addons...{Colors.RESET}\n")

        addon_xpath = "addon[@id='{}']"
        changed = False
        for addon in folders:
            try:
                addon_xml_path = os.path.join(self.release_path, addon, "addon.xml")
                addon_xml = ElementTree.parse(addon_xml_path)
                addon_root = addon_xml.getroot()
                id = addon_root.get('id')
                version = addon_root.get('version')

                updated = False
                addon_entry = addons_root.find(addon_xpath.format(id))
                if addon_entry is not None and addon_entry.get('version') != version:
                    index = addons_root.findall('addon').index(addon_entry)
                    addons_root.remove(addon_entry)
                    addons_root.insert(index, addon_root)
                    updated = True
                    changed = True
                elif addon_entry is None:
                    addons_root.append(addon_root)
                    updated = True
                    changed = True

                if updated:
                    self._create_zip(addon, id, version)
                    self._copy_meta_files(addon, os.path.join(self.zips_path, id))
            except Exception as e:
                error_msg = f"{addon}: {str(e)}"
                self.errors.append(error_msg)
                print(
                    "Excluding {}: {}".format(
                        color_text(addon, 'yellow'), color_text(str(e), 'red')
                    )
                )

        if changed:
            addons_root[:] = sorted(addons_root, key=lambda addon: addon.get('id'))
            try:
                addons_xml.write(
                    addons_xml_path, encoding="utf-8", xml_declaration=True
                )

                return changed
            except Exception as e:
                print(
                    "An error occurred updating {}!\n{}".format(
                        color_text(addons_xml_path, 'yellow'), color_text(e, 'red')
                    )
                )

    def _generate_md5_file(self, addons_xml_path, md5_path):
        """
        Generates a new addons.xml.md5 file.
        """
        try:
            with open(addons_xml_path, "r", encoding="utf-8") as f:
                m = hashlib.md5(f.read().encode("utf-8")).hexdigest()
                self._save_file(m, file=md5_path)

            return True
        except Exception as e:
            print(
                "An error occurred updating {}!\n{}".format(
                    color_text(md5_path, 'yellow'), color_text(e, 'red')
                )
            )

    def _save_file(self, data, file):
        """
        Saves a file.
        """
        try:
            with open(file, "w") as f:
                f.write(data)
        except Exception as e:
            print(
                "An error occurred saving {}!\n{}".format(
                    color_text(file, 'yellow'), color_text(e, 'red')
                )
            )


if __name__ == "__main__":
    for release in [r for r in KODI_VERSIONS if os.path.exists(r)]:
        Generator(release)
