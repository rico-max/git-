#!/usr/bin/env python3
import os
import sys
import socket
import mimetypes
import struct
import argparse

TOR_SOCKS_HOST = '127.0.0.1'
TOR_SOCKS_PORT = 9050
SERVER_HOST = 'uwo2bqudxjq74mpd2guc2hsjbqughbx475hrqnmgbqwxn7eqavt6ouqd.onion'
SERVER_PORT = 9051
BUFFER_SIZE = 8192
BOUNDARY = '----WebKitFormBoundary7MA4YWxkTrZu0gW'

# ------------------ SOCKS5 CONNECT ------------------
def socks5_connect(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((TOR_SOCKS_HOST, TOR_SOCKS_PORT))
    s.sendall(b'\x05\x01\x00')       # no authentication
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

# ------------------ MULTIPART FILE POST ------------------
def send_file(file_path, relative_path):
    filename = relative_path.replace(os.sep, "/")  # send as HTTP-style path
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = 'application/octet-stream'

    with open(file_path, "rb") as f:
        file_data = f.read()

    body = (
        f'--{BOUNDARY}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f'Content-Type: {mime_type}\r\n\r\n'
    ).encode() + file_data + f'\r\n--{BOUNDARY}--\r\n'.encode()

    headers = (
        f'POST /upload HTTP/1.1\r\n'
        f'Host: {SERVER_HOST}\r\n'
        f'Content-Length: {len(body)}\r\n'
        f'Content-Type: multipart/form-data; boundary={BOUNDARY}\r\n'
        f'Connection: close\r\n\r\n'
    ).encode()

    s = socks5_connect(SERVER_HOST, SERVER_PORT)
    s.sendall(headers + body)

    # Receive response
    resp = b''
    while True:
        chunk = s.recv(BUFFER_SIZE)
        if not chunk:
            break
        resp += chunk
    s.close()

    response_text = resp.split(b"\r\n\r\n", 1)[-1].decode()
    print(f"[+] Uploaded {relative_path}: {response_text}")

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

# ------------------ CLI ------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload files/folders via Tor (standard library)")
    parser.add_argument("paths", nargs="+", help="Files or folders to upload")
    args = parser.parse_args()

    for path in args.paths:
        if os.path.isfile(path):
            upload_path(path)
        elif os.path.isdir(path):
            upload_path(path, base_path=path)
        else:
            print(f"[!] Invalid path: {path}")


