# ConflictConfirmer

GitHubリポジトリのオープンPRにマージコンフリクトが発生したことを自動検知し、音とブラウザで即座に通知するツールです。

## 機能

- PRがマージされた瞬間にコンフリクトを検知
- **Glass音** で音通知（許可設定不要）
- **コンフリクトしたPRをブラウザで直接オープン**（許可設定不要）
- コンフリクトが解消されたときも通知
- macOS LaunchAgent による常時バックグラウンド稼働

## 動作の仕組み

```
起動
 └─ 初回コンフリクトチェック
    │
    ↓ ループ（10秒ごと）
    ├─ GitHub Events API をポーリング
    ├─ マージイベントを検知 → PR一覧のコンフリクトチェック
    │   └─ mergeable が計算中(null)の場合は5秒ごとに最大30秒リトライ
    └─ コンフリクト検知 → 音 + ブラウザでPRを開く
```

## セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/koukiuchida2000/ConflictConfirmer.git
cd ConflictConfirmer
```

### 2. 依存パッケージをインストール

```bash
pip3 install -r requirements.txt
```

### 3. GitHub Personal Access Token を取得

1. https://github.com/settings/tokens を開く
2. **"Generate new token (classic)"** をクリック
3. **Scopes**: `repo` にチェックを入れる
4. トークン（`ghp_...`）を生成してコピー

### 4. 設定ファイルを作成

```bash
cp .env.example .env
```

`.env` を編集：

```
GITHUB_TOKEN=ghp_ここにトークンを貼り付け
GITHUB_REPO=owner/repo
POLL_INTERVAL=10
```

| 設定項目 | 説明 |
|---|---|
| `GITHUB_TOKEN` | 手順3で取得したトークン（必須） |
| `GITHUB_REPO` | 監視対象リポジトリ（`owner/repo` 形式、必須） |
| `POLL_INTERVAL` | イベントポーリング間隔（秒）、デフォルト10 |

### 5. 動作確認（手動起動）

```bash
python3 conflict_checker.py
```

正常に起動すると以下が表示されます：

```
ConflictConfirmer 起動: owner/repo
イベントポーリング間隔: 10秒
[初回チェック] 2026-01-01 00:00:00
```

### 6. 常時稼働（LaunchAgent）

ターミナルを閉じても動き続けるバックグラウンドサービスとして登録します。

```bash
./setup.sh install
```

| コマンド | 内容 |
|---|---|
| `./setup.sh install` | サービス登録・起動（ログイン時に自動起動） |
| `./setup.sh status` | 稼働状態を確認 |
| `./setup.sh uninstall` | 停止・削除 |

ログの確認：

```bash
tail -f logs/output.log
```

## 通知について

macOS のシステム通知（バナー）は通知許可の設定が必要なため使用していません。
代わりに **許可設定が不要** な以下の方法で通知します。

| 通知 | タイミング |
|---|---|
| Glass音 + ブラウザでPRを開く | コンフリクト発生時 |
| Glass音のみ | コンフリクト解消時 |
