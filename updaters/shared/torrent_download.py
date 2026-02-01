import asyncio

try:
    from torrentp import TorrentDownloader
except ImportError:
    TorrentDownloader = None

def download_torrent(torrent_url: str, save_path: str, logging_callback=None) -> bool:
    """
    Download a file using a .torrent URL with torrentp.
    Returns True on success, False on failure.
    """
    if TorrentDownloader is None:
        if logging_callback:
            logging_callback("torrentp is not installed. Cannot download torrent files.")
        return False
    if logging_callback:
        logging_callback(f"Downloading torrent file: {torrent_url}")
    try:
        torrent = TorrentDownloader(torrent_url, save_path=save_path)
        asyncio.run(torrent.start_download())
        if logging_callback:
            logging_callback(f"Torrent download completed in: {save_path}")
        return True
    except Exception as e:
        if logging_callback:
            logging_callback(f"Torrent download failed: {e}")
        return False
