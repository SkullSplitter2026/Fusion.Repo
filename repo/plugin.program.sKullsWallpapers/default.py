# -*- coding: utf-8 -*-
"""sKulls Fusion Wallpapers - Router Entry Point."""
import sys
import urllib.parse as up

from resources.lib import common
from resources.lib import ui
from resources.lib import sources as sources_mod

# Make sources available in ui module
ui.sources_mod = sources_mod


def router(params):
    mode = params.get("mode", "root")
    if mode == "root":
        ui.show_root()
    elif mode == "search_prompt":
        ui.search_prompt(params)
    elif mode == "search":
        ui.list_search_results(params)
    elif mode == "category":
        ui.list_category(params)
    elif mode == "wallpaper":
        ui.wallpaper_menu(params)
    elif mode == "download_image":
        ui.download_image(params)
    elif mode == "my_wallpapers":
        from resources.lib import my_wallpapers
        my_wallpapers.show(params)
    elif mode == "open_context":
        from resources.lib import my_wallpapers
        my_wallpapers.open_context(params)
    elif mode == "view_file":
        from resources.lib import my_wallpapers
        my_wallpapers.view_file(params)
    elif mode == "delete_file":
        from resources.lib import my_wallpapers
        my_wallpapers.delete_file(params)
    elif mode == "move_to_genre":
        from resources.lib import my_wallpapers
        my_wallpapers.move_to_genre(params)
    elif mode == "import_image":
        from resources.lib import my_wallpapers
        my_wallpapers.import_image(params)
    elif mode == "import_folder":
        from resources.lib import my_wallpapers
        my_wallpapers.import_folder(params)
    elif mode == "warm_thumbs":
        ui.warm_thumbs(params)
    elif mode == "skulls_root":
        ui.skulls_root(params)
    elif mode == "skulls_category":
        ui.list_skulls_category(params)
    elif mode == "skulls_wallpaper_menu":
        ui.skulls_wallpaper_menu(params)
    elif mode == "clear_cache":
        ui.clear_cache(params)
    elif mode == "add_custom_source":
        sources_mod.add(params)
    elif mode == "manage_custom_sources":
        sources_mod.manage(params)
    elif mode == "delete_custom_source":
        sources_mod.delete(params)
    elif mode == "open_custom_url":
        url = params.get("url", "")
        if url:
            import xbmc
            xbmc.executebuiltin(f"RunPlugin({url})")
        import xbmcplugin
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
    elif mode == "open_settings":
        common.ADDON.openSettings()
        import xbmcplugin
        xbmcplugin.endOfDirectory(common.HANDLE, cacheToDisc=False)
    elif mode == "browse_custom_source":
        sources_mod.browse(params)
    elif mode == "custom_wallpaper":
        ui.custom_wallpaper(params)
    elif mode == "show_history":
        ui.show_history(params)
    elif mode == "clear_history":
        ui.clear_history(params)
    elif mode == "preview_image":
        ui.preview_image(params)
    elif mode == "random_wallpaper":
        ui.random_wallpaper(params)
    elif mode == "show_favorites":
        ui.show_favorites(params)
    elif mode == "add_favorite":
        ui.add_favorite(params)
    elif mode == "remove_favorite":
        ui.remove_favorite(params)
    elif mode == "show_set":
        ui.show_set(params)
    elif mode == "add_to_set":
        ui.add_to_set(params)
    elif mode == "remove_from_set":
        ui.remove_from_set(params)
    elif mode == "clear_set":
        ui.clear_set(params)
    elif mode == "download_set":
        ui.download_set(params)
    elif mode == "slideshow":
        ui.slideshow(params)
    elif mode == "manage_genres":
        ui.manage_genres(params)
    elif mode == "create_genre":
        ui.create_genre(params)
    elif mode == "rename_genre":
        ui.rename_genre(params)
    elif mode == "delete_genre":
        ui.delete_genre(params)
    elif mode == "browse_genre":
        ui.browse_genre(params)
    elif mode == "set_download_path":
        ui.set_download_path(params)
    elif mode == "browse_download_path":
        ui.browse_download_path(params)
    else:
        ui.show_root()


if __name__ == "__main__":
    qs = {}
    if len(sys.argv) > 2 and sys.argv[2]:
        qs = dict(up.parse_qsl(sys.argv[2][1:]))
    router(qs)
