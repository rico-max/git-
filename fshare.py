#!/usr/bin/env python3
import os
import sys
import argparse
import mimetypes
import requests

# -------- CONFIGURATION --------
TOR_SOCKS_PROXY = "socks5h://127.0.0.1:9050"  # leave None if not using Tor
SERVER_URL = "http://uwo2bqudxjq74mpd2guc2hsjbqughbx475hrqnmgbqwxn7eqavt6ouqd.onion:9051/upload"
# --------------------------------

def upload_file(file_path):
    # Detect MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    # Prepare POST request
    files = {"file": (os.path.basename(file_path), open(file_path, "rb"), mime_type)}

    # Use Tor proxy if configured
    proxies = {"http": TOR_SOCKS_PROXY, "https": TOR_SOCKS_PROXY} if TOR_SOCKS_PROXY else None

    print(f"[+] Uploading {file_path} ({mime_type}) ...")
    try:
        r = requests.post(SERVER_URL, files=files, proxies=proxies)
        if r.status_code == 200:
            print(f"[+] Upload successful: {file_path}")
        else:
            print(f"[!] Upload failed ({r.status_code}): {file_path}")
    except Exception as e:
        print(f"[!] Error uploading {file_path}: {e}")


def upload_folder(folder_path):
    for root, _, files in os.walk(folder_path):
        for f in files:
            full_path = os.path.join(root, f)
            upload_file(full_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload files/folders to Tor server")
    parser.add_argument("paths", nargs="+", help="File(s) or folder(s) to upload")
    args = parser.parse_args()

    for path in args.paths:
        if os.path.isfile(path):
            upload_file(path)
        elif os.path.isdir(path):
            upload_folder(path)
        else:
            print(f"[!] Path does not exist: {path}")
