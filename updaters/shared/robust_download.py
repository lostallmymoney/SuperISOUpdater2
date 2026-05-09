import time
import requests
from pathlib import Path
import os
from tqdm import tqdm
import sys
from typing import Optional


def robust_download(
    url: str,
    local_file,
    logging_callback,
    method: str = "GET",
    retries: int = 4,
    delay: float = 3.0,
    chunk_size: int = 1024 * 1024,
    redirects: bool = True,
    expected_size: Optional[int] = None,
    **kwargs
) -> bool:

    def log(msg):
        logging_callback(f"[robust_download] {msg}")

    log(f"URL: {url}")

    # -------------------------
    # sanity checks
    # -------------------------
    if any(x in url for x in ("[[VER]]", "[[EDITION]]", "[[LANG]]")):
        log("ERROR: unresolved placeholder")
        return False

    if not url.startswith(("http://", "https://")):
        log("ERROR: invalid URL")
        return False

    # -------------------------
    # optional expected size (ONLY fallback, never override if provided)
    # -------------------------
    if expected_size is None:
        try:
            from updaters.shared.fetch_expected_file_size import fetch_expected_file_size
            expected_size = fetch_expected_file_size(url, logging_callback)
            log(f"expected_size={expected_size}")
        except Exception as e:
            log(f"size fetch failed: {e}")

    part_file = Path(str(local_file) + ".part")
    final_file = Path(local_file)

    attempt = 0

    resume_fail_counter = 0
    resume_enabled = True

    while attempt <= retries or retries == -1:
        try:

            resume = part_file.stat().st_size if part_file.exists() else 0

            headers = dict(kwargs.pop("headers", {}))

            # =========================================================
            # FIX: prevent gzip decoding corruption during resume/stream
            # =========================================================
            headers["Accept-Encoding"] = "identity"

            if resume > 0 and resume_enabled:
                headers["Range"] = f"bytes={resume}-"

            with requests.request(
                method,
                url,
                stream=True,
                headers=headers,
                timeout=15,
                allow_redirects=redirects,
                **kwargs
            ) as r:

                # -------------------------
                # RETRYABLE ERRORS
                # -------------------------
                if r.status_code in (403, 408, 429, 500, 502, 503, 504):
                    attempt += 1
                    log(f"retryable HTTP {r.status_code} (attempt {attempt})")
                    time.sleep(delay)
                    continue

                if r.status_code >= 400 and r.status_code not in (206,):
                    log(f"fatal HTTP {r.status_code}")
                    return False

                # -------------------------
                # 416 recovery
                # -------------------------
                if r.status_code == 416:
                    log("416 → invalid resume state, resetting download")

                    try:
                        part_file.unlink(missing_ok=True)
                    except Exception:
                        pass

                    resume_fail_counter = 0
                    resume = 0
                    attempt += 1
                    time.sleep(delay)
                    continue

                # -------------------------
                # size calculation
                # -------------------------
                remote_len = r.headers.get("content-length")
                remote_size = int(remote_len) if remote_len else None

                if expected_size is not None:
                    total_size = expected_size
                else:
                    total_size = remote_size

                # -------------------------
                # progress bar
                # -------------------------
                pbar = tqdm(
                    total=total_size,
                    initial=resume,
                    unit="B",
                    unit_scale=True,
                    disable=not sys.stdout.isatty()
                )

                bytes_written = resume
                mode = "ab" if resume else "wb"

                with open(part_file, mode) as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue

                        # safety cap
                        if total_size is not None:
                            remaining = total_size - bytes_written
                            if remaining <= 0:
                                break
                            if len(chunk) > remaining:
                                chunk = chunk[:remaining]

                        f.write(chunk)
                        bytes_written += len(chunk)
                        pbar.update(len(chunk))

                pbar.close()

                # -------------------------
                # resume learning logic
                # -------------------------
                if resume > 0 and r.status_code == 200:
                    resume_fail_counter += 1
                    log(f"resume ignored by server (200) [{resume_fail_counter}/6]")

                    if resume_fail_counter >= 6:
                        log("disabling resume for this host (fallback mode)")
                        resume_enabled = False
                        try:
                            part_file.unlink(missing_ok=True)
                        except Exception:
                            pass
                        resume = 0
                        continue

                if r.status_code == 206:
                    resume_fail_counter = max(0, resume_fail_counter - 1)

                # -------------------------
                # validation
                # -------------------------
                final_size = part_file.stat().st_size

                if expected_size is not None:
                    if final_size < expected_size:
                        log(f"incomplete {final_size}/{expected_size}")
                        attempt += 1
                        time.sleep(delay)
                        continue

                    if final_size > expected_size:
                        log(f"ERROR oversize {final_size}/{expected_size}")
                        return False

                else:
                    if total_size is not None and final_size < total_size:
                        log(f"incomplete {final_size}/{total_size}")
                        attempt += 1
                        time.sleep(delay)
                        continue

                    if total_size is not None and final_size > total_size:
                        log(f"ERROR oversize {final_size}/{total_size}")
                        return False

                os.replace(part_file, final_file)
                log(f"completed → {final_file}")
                return True

        except requests.exceptions.RequestException as e:
            attempt += 1
            log(f"network error: {e} (attempt {attempt})")
            time.sleep(delay)

        except Exception as e:
            log(f"unexpected error: {e}")
            return False

    log("failed after retries")
    return False