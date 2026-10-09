"""Bounded authenticated localhost WebSocket JSON-RPC; never logs tokens."""
import base64
import hashlib
import json
import os
import socket
import struct
import time
import threading
from urllib.parse import urlparse

class AppServerRPC:
    def __init__(self, endpoint, token, verify_owner, timeout=10):
        parsed = urlparse(endpoint)
        if parsed.scheme != "ws" or parsed.hostname != "127.0.0.1" or parsed.path not in ("", "/"):
            raise ValueError("owned localhost backend only")
        self.socket = socket.create_connection((parsed.hostname, parsed.port), timeout=timeout)
        self.stream = self.socket.makefile("rb")
        try:
            verify_owner(self.socket)
        except BaseException:
            self.close()
            raise
        self.sequence, self.timeout = 0, timeout
        self.on_notification = None
        self.reader = None
        self.waiters = {}
        self.waiter_lock = threading.Lock()
        self.write_lock = threading.Lock()
        nonce = base64.b64encode(os.urandom(16)).decode()
        self.socket.sendall(("GET / HTTP/1.1\r\nHost: " + parsed.netloc + "\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: " + nonce + "\r\nAuthorization: Bearer " + token + "\r\n\r\n").encode())
        if not self.stream.readline(4096).startswith(b"HTTP/1.1 101 "):
            self.close()
            raise RuntimeError("owned backend authentication refused")
        headers = {}
        while True:
            line = self.stream.readline(4096)
            if line == b"\r\n":
                break
            if not line:
                raise RuntimeError("incomplete websocket handshake")
            name, value = line.decode().split(":", 1)
            headers[name.lower()] = value.strip()
        expected = base64.b64encode(hashlib.sha1((nonce + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        if headers.get("sec-websocket-accept") != expected or headers.get("upgrade", "").lower() != "websocket":
            self.close()
            raise RuntimeError("wrong owned backend handshake")
        self.call("initialize", {"clientInfo": {"name": "win35_root_guardian", "version": "1"}, "capabilities": {"experimentalApi": True}})
        self.send({"method": "initialized", "params": {}})

    def send_frame(self, opcode, data):
        mask = os.urandom(4)
        size = len(data)
        header = bytes((0x80 | opcode, 0x80 | size)) if size < 126 else bytes((0x80 | opcode, 0x80 | 126)) + struct.pack("!H", size) if size < 65536 else bytes((0x80 | opcode, 0x80 | 127)) + struct.pack("!Q", size)
        with self.write_lock:
            self.socket.sendall(header + mask + bytes(value ^ mask[i % 4] for i, value in enumerate(data)))

    def start_reader(self, notification, server_request):
        if self.reader is not None: raise RuntimeError("one native reader only")
        self.socket.settimeout(None)
        def read():
            try:
                while True:
                    message=self.receive()
                    if "method" in message:
                        if "id" in message:
                            try: result=server_request(message)
                            except Exception: result={"contentItems":[{"type":"inputText","text":"Guarded tool unavailable; preserve custody."}],"success":False}
                            self.send({"id":message["id"],"result":result})
                        else: notification(message)
                    elif "id" in message:
                        with self.waiter_lock: waiter=self.waiters.get(message["id"])
                        if waiter: waiter[1].update(message);waiter[0].set()
            except Exception:
                with self.waiter_lock:
                    for event,box in self.waiters.values():box["error"]={};event.set()
        self.reader=threading.Thread(target=read,daemon=True)
        self.reader.start()

    def send(self, message):
        self.send_frame(1, json.dumps(message).encode())

    def exact(self, size):
        data = self.stream.read(size)
        if len(data) != size:
            raise RuntimeError("owned backend disconnected")
        return data

    def receive(self):
        parts = bytearray()
        while True:
            first, second = self.exact(2)
            if first & 0x70 or second & 0x80:
                raise RuntimeError("unsupported websocket framing")
            opcode, size = first & 15, second & 127
            if size == 126:
                size = struct.unpack("!H", self.exact(2))[0]
            elif size == 127:
                size = struct.unpack("!Q", self.exact(8))[0]
            if size > 4 * 1024 * 1024 or len(parts) + size > 4 * 1024 * 1024:
                raise RuntimeError("oversized backend message")
            data = self.exact(size)
            if opcode == 8:
                raise RuntimeError("owned backend closed")
            if opcode == 9:
                self.send_frame(10, data)
                continue
            if opcode == 10:
                continue
            if opcode not in (0, 1):
                raise RuntimeError("unsupported backend frame")
            parts.extend(data)
            if first & 0x80:
                return json.loads(parts)

    def call(self, method, params):
        with self.waiter_lock:
            self.sequence += 1
            sequence = self.sequence
            event, box=threading.Event(),{}
            if self.reader is not None:self.waiters[sequence]=(event,box)
        self.send({"id": sequence, "method": method, "params": params})
        if self.reader is not None:
            try:
                if not event.wait(self.timeout): raise TimeoutError("owned backend response deadline")
                if "error" in box:raise RuntimeError("native app-server method rejected")
                return box["result"]
            finally:
                with self.waiter_lock:self.waiters.pop(sequence,None)
        until = time.monotonic() + self.timeout
        while time.monotonic() < until:
            self.socket.settimeout(max(.001, until - time.monotonic()))
            message = self.receive()
            if self.on_notification and "method" in message:
                self.on_notification(message)
            if message.get("id") == sequence:
                if "error" in message:
                    raise RuntimeError("native app-server method rejected")
                return message["result"]
        raise TimeoutError("owned backend response deadline")

    def close(self):
        try:self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:pass
        self.socket.close()
        self.stream.close()
        reader=getattr(self,"reader",None)
        if reader is not None and reader is not threading.current_thread():reader.join(1)
