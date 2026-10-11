#!/bin/bash
# 随影提词器 - 生成局域网 HTTPS 自签证书（解锁 iPad/iPhone 语音跟随）
# 用法: bash gen-cert.sh 192.168.31.119   （换成你自己的局域网 IP）
set -e
IP="${1:?用法: bash gen-cert.sh <你的局域网IP>，在macOS上运行 ifconfig | grep inet 查看}"
CA_SUBJ="${2:-Suiying Dev CA}"

openssl req -x509 -new -nodes -keyout ca.key -sha256 -days 3650 -subj "/CN=$CA_SUBJ" -out ca.pem
openssl req -new -nodes -keyout key.pem -subj "/CN=$IP" -out server.csr
printf "subjectAltName=IP:%s,DNS:localhost,IP:127.0.0.1\n" "$IP" > san.ext
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial -out cert.pem -days 3650 -sha256 -extfile san.ext
rm -f server.csr san.ext ca.srl

echo "✅ 证书已生成: cert.pem + key.pem（重启 server.py 后自动启用 HTTPS:8443）"
echo "📲 下一步: 把 ca.pem 发到 iPad/iPhone → 安装描述文件 → 证书信任设置里开启完全信任"
