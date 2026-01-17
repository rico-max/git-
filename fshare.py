#!/usr/bin/env python3
import os
import sys
import socket
import mimetypes
import argparse
import struct

TOR_SOCKS_HOST = '127.0.0.1'
TOR_SOCKS_PORT = 9050
SERVER_HOST = 'uwo2bqudxjq74mpd2guc2hsjbqughbx475hrqnmgbqwxn7eqavt6ouqd.onion'
SERVER_PORT = 9051
BUFFER_SIZE = 8192

BOUNDARY = '----WebKitFormBoundary7MA4YWxkTrZu0gW'

# -------- SOCKS5 CONNECT --------
def socks5_connect(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((TOR_SOCKS_HOST, TOR_SOCKS_PORT))

    # Greeting: no auth
    s.sendall(b'\x05\x01\x00')
    resp = s.recv(2)
    if resp != b'\x05\x00':
        raise Exception("SOCKS5 proxy rejected handshake")

    # Connect request
    host_bytes = host.encode()
    req = b'\x05\x01\x00\x03' + bytes([len(host_bytes)]) + host_bytes + struct.pack('>H', port)
    s.sendall(req)
    resp = s.recv(10)
    if resp[1] != 0x00:
        raise Exception(f"SOCKS5 connection failed with code {resp[1]}")
    return s

# -------- HTTP multipart POST --------
def send_file(file_path):
    filename = os.path.basename(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = 'application/octet-stream'

    with open(file_path, 'rb') as f:
        content = f.read()

    # Build multipart body
    body = (
        f'--{BOUNDARY}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f'Content-Type: {mime_type}\r\n\r\n'
    ).encode() + content + f'\r\n--{BOUNDARY}--\r\n'.encode()

    # Build HTTP headers
    headers = (
        f'POST /upload HTTP/1.1\r\n'
        f'Host: {SERVER_HOST}\r\n'
        f'Content-Length: {len(body)}\r\n'
        f'Content-Type: multipart/form-data; boundary={BOUNDARY}\r\n'
        f'Connection: close\r\n\r\n'
    ).encode()

    # Connect over Tor SOCKS5
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

    # Decode response safely
    response_text = resp.split(b"\r\n\r\n", 1)[-1].decode()
    print(f"[+] Uploaded {file_path}: {response_text}")


# -------- Recursive folder upload --------
def upload_path(path):
    if os.path.isfile(path):
        send_file(path)
    elif os.path.isdir(path):
        for root, _, files in os.walk(path):
            for f in files:
                send_file(os.path.join(root, f))
    else:
        print(f"[!] Path does not exist: {path}")

# -------- CLI --------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload file/folder via Tor using standard library")
    parser.add_argument("paths", nargs="+", help="Files or folders to upload")
    args = parser.parse_args()

    for path in args.paths:
        upload_path(path)

