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
        elif path == "/ca.pem":
            ca = os.path.join(ROOT, "ca.pem")
            if os.path.exists(ca):
                with open(ca, "rb") as f:
                    self._send(200, f.read(), "application/x-x509-ca-cert")
            else:
                self._send(404, b"no CA generated; run gen-cert.sh")
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
    # HTTP 8899 照常服务；若存在证书则额外开 HTTPS 8443
    # （iPad/iPhone 语音跟随需要 HTTPS——局域网 HTTP 属非安全上下文，浏览器不给语音识别 API）
    import threading

    def serve(httpd):
        httpd.serve_forever()

    httpd = ThreadingHTTPServer(("0.0.0.0", 8899), H)
    threading.Thread(target=serve, args=(httpd,), daemon=True).start()
    print("HTTP  serving on port 8899", flush=True)

    cert, key = os.path.join(ROOT, "cert.pem"), os.path.join(ROOT, "key.pem")
    if os.path.exists(cert) and os.path.exists(key):
        import ssl
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        httpsd = ThreadingHTTPServer(("0.0.0.0", 8443), H)
        httpsd.socket = ctx.wrap_socket(httpsd.socket, server_side=True)
        print("HTTPS serving on port 8443 (iOS 语音跟随已解锁: https://%s:8443)" % lan_ip(), flush=True)
        httpsd.serve_forever()
    else:
        print("tip: bash gen-cert.sh <局域网IP> 可开启 HTTPS（iPad/iPhone 语音跟随需要）", flush=True)
        print("teleprompter serving on http://%s:8899 (LAN reachable)" % lan_ip(), flush=True)
        httpd.serve_forever()  # 主线程守HTTP，进程不退出
