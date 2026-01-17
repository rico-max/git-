#!/usr/bin/env python3
import os
import sys
import socket
import mimetypes
import struct
import argparse
import time
import json
import uuid

TOR_SOCKS_HOST = '127.0.0.1'
TOR_SOCKS_PORT = 9050
SERVER_HOST = 'uwo2bqudxjq74mpd2guc2hsjbqughbx475hrqnmgbqwxn7eqavt6ouqd.onion'
SERVER_PORT = 9051
BUFFER_SIZE = 8192
BOUNDARY = '----WebKitFormBoundary7MA4YWxkTrZu0gW'

SESSION_ID = str(uuid.uuid4())  # unique session per run

# ------------------ SOCKS5 CONNECT ------------------
def socks5_connect(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((TOR_SOCKS_HOST, TOR_SOCKS_PORT))
    s.sendall(b'\x05\x01\x00')
    resp = s.recv(2)
    if resp != b'\x05\x00':
        raise Exception("SOCKS5 handshake failed")
    host_bytes = host.encode()
    req = b'\x05\x01\x00\x03' + bytes([len(host_bytes)]) + host_bytes + struct.pack('>H', port)
    s.sendall(req)
    resp = s.recv(10)
    if resp[1] != 0x00:
        raise Exception(f"SOCKS5 connection failed with code {resp[1]}")
    return s

# ------------------ SEND FILE IN CHUNKS ------------------
def send_file(file_path, relative_path):
    filename = relative_path.replace(os.sep, "/")
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = 'application/octet-stream'

    preamble = (
        f'--{BOUNDARY}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f'Content-Type: {mime_type}\r\n\r\n'
    ).encode()
    postamble = f'\r\n--{BOUNDARY}--\r\n'.encode()
    total_size = os.path.getsize(file_path) + len(preamble) + len(postamble)

    headers = (
        f'POST /upload HTTP/1.1\r\n'
        f'Host: {SERVER_HOST}\r\n'
        f'X-Upload-Session: {SESSION_ID}\r\n'
        f'Content-Length: {total_size}\r\n'
        f'Content-Type: multipart/form-data; boundary={BOUNDARY}\r\n'
        f'Connection: close\r\n\r\n'
    ).encode()

    print(f"\n[+] Uploading {filename} ({os.path.getsize(file_path)/1024:.2f} KB, {mime_type})")
    uploaded = 0
    start_time = time.time()
    s = socks5_connect(SERVER_HOST, SERVER_PORT)
    s.sendall(headers + preamble)
    uploaded += len(preamble)

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(BUFFER_SIZE)
            if not chunk:
                break
            s.sendall(chunk)
            uploaded += len(chunk)
            percent = (uploaded / total_size) * 100
            elapsed = time.time() - start_time
            eta = (elapsed / uploaded) * (total_size - uploaded) if uploaded else 0
            sys.stdout.write(f"\rProgress: {percent:.2f}% | ETA: {eta:.1f}s")
            sys.stdout.flush()

    s.sendall(postamble)
    uploaded += len(postamble)

    # receive response
    resp = b''
    while True:
        chunk = s.recv(BUFFER_SIZE)
        if not chunk:
            break
        resp += chunk
    s.close()

    response_text = resp.split(b"\r\n\r\n", 1)[-1].decode()
    print(f"\n[+] Upload complete: {filename} -> {response_text}")

# ------------------ RECURSIVE FOLDER UPLOAD ------------------
def upload_path(path, base_path=""):
    if os.path.isfile(path):
        relative_path = os.path.relpath(path, base_path) if base_path else os.path.basename(path)
        send_file(path, relative_path)
    elif os.path.isdir(path):
        for root, _, files in os.walk(path):
            for f in files:
                full_path = os.path.join(root, f)
                relative_path = os.path.relpath(full_path, base_path or root)
                send_file(full_path, relative_path)
    else:
        print(f"[!] Path does not exist: {path}")

# ------------------ GENERATE MANIFEST ------------------
def generate_manifest(paths):
    manifest = []
    for path in paths:
        if os.path.isfile(path):
            manifest.append(os.path.basename(path))
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for f in files:
                    full_path = os.path.join(root, f)
                    relative_path = os.path.relpath(full_path, path)
                    manifest.append(os.path.join(os.path.basename(path), relative_path))
    manifest_path = f"manifest_{SESSION_ID}.json"
    with open(manifest_path, "w") as mf:
        json.dump(manifest, mf)
    return manifest_path

# ------------------ CLI ------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload files/folders via Tor with manifest")
    parser.add_argument("paths", nargs="+", help="Files or folders to upload")
    args = parser.parse_args()

    # Generate manifest
    manifest_file = generate_manifest(args.paths)

    # Upload files
    for path in args.paths:
        upload_path(path, base_path=path if os.path.isdir(path) else "")

    # Upload manifest file last
    send_file(manifest_file, os.path.basename(manifest_file))




