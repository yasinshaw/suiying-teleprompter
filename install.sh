#!/bin/bash
# 叶哥提词器 - 一键安装 launchd 常驻服务（macOS）
# 用法: bash install.sh
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="ai.yasin.suiying-teleprompter"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

pkill -f "suiying-teleprompter/server.py" 2>/dev/null || true

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$DIR/server.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

launchctl bootstrap gui/$(id -u) "$PLIST" 2>/dev/null || launchctl load "$PLIST"
echo "✅ 已安装并启动。打开 http://127.0.0.1:8899 即可使用（开机自启）"
echo "   卸载: launchctl bootout gui/$(id -u)/$LABEL && rm $PLIST"
