
import time
import requests
from pathlib import Path
import os
from tqdm import tqdm
import sys

from typing import Optional

def robust_download(url: str, local_file, method: str = "GET", retries: int = 4, delay: float = 3.0, logging_callback=None, chunk_size: int = 1048576, redirects=True, expected_size: Optional[int] = None, **kwargs) -> bool:
    # Always fetch expected_size if not provided
    if expected_size is None:
        try:
            from updaters.shared.fetch_expected_file_size import fetch_expected_file_size
            expected_size = fetch_expected_file_size(url)
            if logging_callback:
                logging_callback(f"[robust_download] Auto-fetched expected_size: {expected_size}")
        except Exception as e:
            if logging_callback:
                logging_callback(f"[robust_download] Failed to fetch expected_size: {e}")
    """
    Robustly download a file to disk with resume, progress, and retries. Returns True on success, False on failure.
    """
    def report(msg):
        if logging_callback:
            logging_callback(msg)
    attempt = 0
    RETRYABLE_STATUSES = {403, 408, 429, 500, 502, 503, 504}
    PERMANENT_FAILURE_STATUSES = {400, 401, 404, 410, 422, 451}
    # Track if we ever got a successful connection (locked in)
    locked_in = False
    MAX_HTTP_RETRIES = retries if retries != -1 else 10
    # Log the URL before starting
    if logging_callback:
        logging_callback(f"[robust_download] Download URL: {url}")
    # Check for unresolved placeholders
    if any(ph in url for ph in ['[[VER]]', '[[EDITION]]', '[[LANG]]']):
        if logging_callback:
            logging_callback(f"[robust_download] ERROR: Unresolved placeholder(s) in url: {url}")
        return False
    # Check for malformed URL
    if not (url.startswith('http://') or url.startswith('https://')):
        if logging_callback:
            logging_callback(f"[robust_download] ERROR: Malformed URL: {url}")
        return False
    download_started = False
    truncated_since_last_write = False
    max_total_size = 0
    consecutive_200_on_resume = 0
    while True:
        try:
            kwargs_no_headers = dict(kwargs)
            headers = kwargs_no_headers.pop("headers", {}).copy()
            part_file = Path(str(local_file) + ".part")
            resume_byte_pos = part_file.stat().st_size if part_file.exists() else 0
            if resume_byte_pos > 0:
                headers["Range"] = f"bytes={resume_byte_pos}-"

            with requests.request(method, url, stream=True, headers=headers, timeout=5, allow_redirects=redirects, **kwargs_no_headers) as r:
                if expected_size is not None:
                    total_size = expected_size
                else:
                    total_size = int(r.headers.get('content-length', 0))
                    if resume_byte_pos > 0 and total_size > 0:
                        total_size += resume_byte_pos
                # If file is smaller than chunk_size, set chunk_size to file size to avoid chunking
                effective_chunk_size = chunk_size
                if total_size and total_size < chunk_size:
                    effective_chunk_size = total_size
                if not download_started:
                    if resume_byte_pos > 0 and r.status_code == 200:
                        consecutive_200_on_resume += 1
                        report(f"[robust_download] Server responded with 200 OK instead of 206 Partial Content for resume request. Mirror does not support resume. ({consecutive_200_on_resume}/3)")
                        if consecutive_200_on_resume >= 3:
                            report(f"[robust_download] Received HTTP 200 on resume 3 times in a row. Deleting .part file and restarting from scratch.")
                            try:
                                part_file.unlink(missing_ok=True)
                            except Exception as e:
                                report(f"[robust_download] Failed to delete .part file: {e}")
                            consecutive_200_on_resume = 0
                            resume_byte_pos = 0
                        attempt += 1
                        if attempt > MAX_HTTP_RETRIES:
                            report(f"Exceeded maximum retries for {url} (HTTP 200 on resume)")
                            return False
                        time.sleep(delay)
                        continue
                    else:
                        consecutive_200_on_resume = 0
                    # If not 200 or 206, do not write any data
                    if r.status_code == 416:
                        report(f"[robust_download] HTTP 416 (Requested Range Not Satisfiable) received for {url}")
                        report(f"[robust_download] Response headers: {dict(r.headers)}")
                        try:
                            body_snippet = r.content[:10000].decode(errors='replace')
                        except Exception:
                            body_snippet = str(r.content[:10000])
                        report(f"[robust_download] Response body (first 10000 bytes): {body_snippet}")
                        # Check if .part file is already complete
                        part_file = Path(str(local_file) + ".part")
                        part_file_size = part_file.stat().st_size if part_file.exists() else 0
                        # Use expected_size if available, else try content-length, else skip check
                        expected = expected_size
                        if expected is None:
                            cl = r.headers.get('content-length')
                            if cl is not None:
                                try:
                                    expected = int(cl)
                                except Exception:
                                    expected = None
                        if expected is not None and part_file_size == expected:
                            report(f"[robust_download] .part file size matches expected size ({part_file_size} bytes). Treating as complete.")
                            local_file_path = Path(local_file)
                            os.replace(part_file, local_file_path)
                            report(f"[robust_download] Final file written: {local_file_path.resolve()}")
                            return True
                        elif expected is not None and part_file_size > expected:
                            report(f"[robust_download] Downloaded file is larger than expected: {part_file_size}/{expected} bytes. Aborting.")
                            return False
                    if r.status_code in RETRYABLE_STATUSES or r.status_code in PERMANENT_FAILURE_STATUSES or (r.status_code != 200 and r.status_code != 206):
                        attempt += 1
                        report(f"HTTP {r.status_code} (attempt {attempt}/{MAX_HTTP_RETRIES}): {url}")
                        if attempt > MAX_HTTP_RETRIES:
                            report(f"Exceeded maximum retries for {url} (HTTP {r.status_code})")
                            return False
                # If we get an HTTP error that is not handled above, count as a failed attempt
                if r.status_code not in (200, 206, 416) and r.status_code not in RETRYABLE_STATUSES and r.status_code not in PERMANENT_FAILURE_STATUSES:
                    attempt += 1
                    report(f"Unhandled HTTP status {r.status_code} (attempt {attempt}/{MAX_HTTP_RETRIES}): {url}")
                    if attempt > MAX_HTTP_RETRIES:
                        report(f"Exceeded maximum retries for {url} (HTTP {r.status_code})")
                        return False
                    time.sleep(delay)
                    continue

                desc = f"Downloading {os.path.basename(local_file)}"
                pbar = tqdm(total=total_size if total_size > 0 else None, unit='B', unit_scale=True, desc=desc, initial=resume_byte_pos, disable=not sys.stdout.isatty())
                try:
                    mode = 'ab' if resume_byte_pos > 0 else 'wb'
                    with open(part_file, mode) as f:
                        bytes_written = part_file.stat().st_size if mode == 'ab' else 0
                        for chunk in r.iter_content(chunk_size=effective_chunk_size):
                            if not chunk:
                                continue
                            # If we know the total size, only write up to the expected size
                            if total_size:
                                remaining = total_size - bytes_written
                                if len(chunk) > remaining:
                                    f.write(chunk[:remaining])
                                    pbar.update(remaining)
                                    bytes_written += remaining
                                    break
                                else:
                                    f.write(chunk)
                                    pbar.update(len(chunk))
                                    bytes_written += len(chunk)
                                if bytes_written >= total_size:
                                    break
                            else:
                                f.write(chunk)
                                pbar.update(len(chunk))
                                bytes_written += len(chunk)
                        # If chunking is disabled (small file), exit after first write
                        if total_size and total_size <= chunk_size:
                            pass  # Already handled by above logic
                    pbar.close()
                except Exception as e:
                    pbar.close()
                    raise e
                # If we get here, we have a successful connection, lock in
                locked_in = True
                download_started = True
                # After the first 200, if resuming, only allow 206 responses for writing
                if download_started and resume_byte_pos > 0 and r.status_code != 206:
                    if logging_callback:
                        logging_callback(f"[robust_download] Refusing to write data: expected 206 Partial Content for resume, got {r.status_code}. Will retry and keep .part file.")
                    # Do not delete the .part file, just retry
                    if not locked_in:
                        attempt += 1
                        if attempt > MAX_HTTP_RETRIES:
                            report(f"Exceeded maximum retries for {url} (HTTP {r.status_code} on resume)")
                            return False
                    # If locked_in, never stop retrying
                    time.sleep(delay)
                    continue
                # Save the biggest Content-Length header seen
                if "content-length" in r.headers:
                    this_total_size = int(r.headers["content-length"]) + resume_byte_pos
                    if this_total_size > max_total_size:
                        max_total_size = this_total_size
                else:
                    this_total_size = None
                total_size = max_total_size if max_total_size > 0 else this_total_size
                if total_size is None or total_size == 0:
                    # Content-Length missing: do not write any chunk, cannot determine completeness
                    if logging_callback:
                        logging_callback(f"[robust_download] Content-Length missing: cannot determine completeness. Not writing any data. Will always retry.")
                    time.sleep(delay)
                    continue
                mode = "ab" if part_file.exists() and part_file.stat().st_size > 0 else "wb"
                with open(str(part_file), mode) as f:
                    if logging_callback:
                        logging_callback(f"[robust_download] Writing to part file: {part_file.resolve()} (mode: {mode})")
                    bytes_downloaded = part_file.stat().st_size if mode == "ab" else 0
                    last_reported_mb = bytes_downloaded // (10 * 1024 * 1024)
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            bytes_downloaded += len(chunk)
                            current_mb = bytes_downloaded // (10 * 1024 * 1024)
                            if logging_callback and current_mb > last_reported_mb:
                                percent = (100 * bytes_downloaded / total_size) if total_size else None
                                msg = f"Downloading: {bytes_downloaded:,}" + (f"/{total_size:,} bytes ({percent:.1f}%)" if percent is not None else " bytes")
                                logging_callback(msg)
                                last_reported_mb = current_mb
                            truncated_since_last_write = False  # Reset after a successful write
                    if logging_callback:
                        logging_callback(f"[robust_download] {part_file.name}: Download chunk complete ({bytes_downloaded}/{total_size} bytes)")
                # Only move the part file to the final file if the download is complete
                part_file_size = part_file.stat().st_size if part_file.exists() else 0
                if part_file_size < total_size:
                    if logging_callback:
                        logging_callback(f"[robust_download] Incomplete download: {part_file_size}/{total_size} bytes. Will retry.")
                    time.sleep(delay)
                    continue
                if part_file_size > total_size:
                    if logging_callback:
                        logging_callback(f"[robust_download] Downloaded file is larger than expected: {part_file_size}/{total_size} bytes. Aborting.")
                    return False
                local_file_path = Path(local_file)
                if logging_callback:
                    logging_callback(f"[robust_download] Moving part file {part_file.resolve()} to final file {local_file_path.resolve()}")
                os.replace(part_file, local_file_path)
                if logging_callback:
                    logging_callback(f"[robust_download] Final file written: {local_file_path.resolve()}")
                return True
        except requests.exceptions.RequestException as e:
            report(f"Network error: {e}\nWaiting for connection to resume for {url}...")
            # Truncation logic is commented out for now
            # part_file = Path(str(local_file) + ".part")
            # if part_file.exists() and not truncated_since_last_write:
            #     try:
            #         file_size = part_file.stat().st_size
            #         new_size = max(0, file_size - chunk_size)
            #         with open(part_file, "rb+") as f:
            #             f.truncate(new_size)
            #         report(f"[robust_download] Truncated last chunk ({chunk_size} bytes) from .part file: {part_file}")
            #         truncated_since_last_write = True
            #     except Exception as te:
            #         report(f"[robust_download] Failed to truncate .part file after network error: {te}")
            time.sleep(3)
            continue
        except Exception as e:
            report(f"robust_download: Unexpected error: {e}")
            return False
