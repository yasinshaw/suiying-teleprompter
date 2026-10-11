#!/usr/bin/env python3
"""随影提词器本地服务：静态页面 + 稿件库存储（服务器=唯一数据源，所有设备读写同一份）"""
import json, os, socket, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(ROOT, ".library.json")
_lock = threading.Lock()


def load_db():
    try:
        with _lock:
            with open(DB_FILE, encoding="utf-8") as f:
                d = json.load(f)
    except Exception:
        return {"library": [], "currentLibId": None}
    if not isinstance(d, dict):
        d = {}
    lib = d.get("library")
    if not isinstance(lib, list):
        lib = []
    # 轻校验：丢弃坏条目，防止一个脏字段毁掉整个库
    lib = [it for it in lib if isinstance(it, dict)
           and isinstance(it.get("id"), str) and isinstance(it.get("text"), str)]
    cur = d.get("currentLibId")
    if not isinstance(cur, str):
        cur = None
    return {"library": lib, "currentLibId": cur}


def save_db(d):
    tmp = DB_FILE + ".tmp"
    with _lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, DB_FILE)  # 原子替换，断电也不损坏


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class H(BaseHTTPRequestHandler):
    def _send(self, code, body=b"", ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/state":
            self._send(200, json.dumps(load_db(), ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
        elif path == "/info":
            self._send(200, json.dumps({"ip": lan_ip(), "port": 8899}).encode(), "application/json")
        elif path in ("/", "/index.html"):
            with open(os.path.join(ROOT, "index.html"), "rb") as f:
                self._send(200, f.read())
        else:
            self._send(404, b"not found")

    def do_POST(self):
        if self.path.split("?", 1)[0] == "/api/state":
            try:
                n = int(self.headers.get("Content-Length", 0))
                d = json.loads(self.rfile.read(n))
                lib, cur = d.get("library"), d.get("currentLibId")
                assert isinstance(lib, list) and (cur is None or isinstance(cur, str))
                save_db({"library": lib, "currentLibId": cur})
                self._send(200, b'{"ok":true}', "application/json")
            except Exception:
                self._send(400, b'{"ok":false}', "application/json")
        else:
            self._send(404, b"not found")

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    print("teleprompter serving on http://%s:8899 (LAN reachable)" % lan_ip(), flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8899), H).serve_forever()
