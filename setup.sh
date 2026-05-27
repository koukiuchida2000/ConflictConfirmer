#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.conflictconfirmer"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
LOG_DIR="$SCRIPT_DIR/logs"
PYTHON="/usr/bin/python3"

install_agent() {
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        echo "エラー: .env ファイルが見つかりません。"
        echo "  cp .env.example .env  で作成してから GITHUB_TOKEN と GITHUB_REPO を設定してください。"
        exit 1
    fi

    mkdir -p "$LOG_DIR"

    cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${SCRIPT_DIR}/conflict_checker.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/output.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/error.log</string>
</dict>
</plist>
EOF

    launchctl load "$PLIST_PATH"
    echo "インストール完了: ConflictConfirmer をバックグラウンドサービスとして起動しました"
    echo "  ログ確認: tail -f $LOG_DIR/output.log"
}

uninstall_agent() {
    if [ -f "$PLIST_PATH" ]; then
        launchctl unload "$PLIST_PATH" 2>/dev/null || true
        rm "$PLIST_PATH"
        echo "アンインストール完了: ConflictConfirmer を停止・削除しました"
    else
        echo "ConflictConfirmer はインストールされていません"
    fi
}

status_agent() {
    if launchctl list | grep -q "$PLIST_NAME"; then
        echo "稼働中"
        launchctl list | grep "$PLIST_NAME"
    else
        echo "停止中"
    fi
}

case "${1:-}" in
    install)   install_agent ;;
    uninstall) uninstall_agent ;;
    status)    status_agent ;;
    *)
        echo "使い方: $0 [install|uninstall|status]"
        echo ""
        echo "  install   - バックグラウンドサービスとして登録・起動（ログイン時に自動起動）"
        echo "  uninstall - サービスを停止・削除"
        echo "  status    - 稼働状態を確認"
        exit 1
        ;;
esac
