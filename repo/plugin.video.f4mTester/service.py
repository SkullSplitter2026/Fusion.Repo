import xbmc
import xbmcaddon
import threading

# Global reference to server for cleanup
_server_thread = None

def run_server():
    try:
        from app import server_run
        server_run()
    except Exception:
        pass

# Start server in daemon thread
_server_thread = threading.Thread(target=run_server, daemon=True)
_server_thread.start()

# Keep addon alive until Kodi requests shutdown
monitor = xbmc.Monitor()
while not monitor.abortRequested():
    if monitor.waitForAbort(1):
        break

print("Servidor Flask encerrado.")
