#!/usr/bin/env python3
import os
import subprocess
import sys
import time

import requests

GITHUB_API = "https://api.github.com"
MIN_POLL_INTERVAL = 10


def load_config():
    config = {}
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()

    for key in ("GITHUB_TOKEN", "GITHUB_REPO", "POLL_INTERVAL"):
        if key in os.environ:
            config[key] = os.environ[key]

    if "GITHUB_TOKEN" not in config:
        print("エラー: GITHUB_TOKEN が設定されていません。.env ファイルを確認してください。")
        sys.exit(1)
    if "GITHUB_REPO" not in config:
        print("エラー: GITHUB_REPO が設定されていません。.env ファイルを確認してください。")
        sys.exit(1)

    interval = int(config.get("POLL_INTERVAL", MIN_POLL_INTERVAL))
    config["POLL_INTERVAL"] = max(interval, MIN_POLL_INTERVAL)
    return config


def fetch_events(owner, repo, token, etag=None):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    if etag:
        headers["If-None-Match"] = etag

    resp = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/events",
        headers=headers,
        params={"per_page": 30},
        timeout=30,
    )
    new_etag = resp.headers.get("ETag", etag)

    if resp.status_code == 304:
        return new_etag, []

    resp.raise_for_status()
    return new_etag, resp.json()


def has_merge_event(events, last_event_id):
    for event in events:
        try:
            event_id = int(event["id"])
        except (KeyError, ValueError):
            continue

        if event_id <= last_event_id:
            break

        if event["type"] == "PullRequestEvent":
            payload = event.get("payload", {})
            pr = payload.get("pull_request", {})
            if payload.get("action") == "closed" and pr.get("merged"):
                return True

        elif event["type"] == "PushEvent":
            ref = event.get("payload", {}).get("ref", "")
            if ref in ("refs/heads/main", "refs/heads/master"):
                return True

    return False


def get_latest_event_id(events):
    try:
        return int(events[0]["id"])
    except (KeyError, ValueError, IndexError):
        return 0


def fetch_open_prs(owner, repo, token):
    prs = []
    page = 1
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    while True:
        resp = requests.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
            headers=headers,
            params={"state": "open", "per_page": 100, "page": page},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        prs.extend(data)
        if len(data) < 100:
            break
        page += 1
    return prs


def get_pr_mergeable(owner, repo, number, token):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    resp = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{number}",
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("mergeable")  # True / False / None


def send_notification(title, message, pr_url=None):
    # 音（許可不要・確実）
    subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], check=False)
    # コンフリクトしたPRをブラウザで開く（許可不要・最も視覚的）
    if pr_url:
        subprocess.run(["open", pr_url], check=False)


def run_check(owner, repo, token, notified_conflicts):
    try:
        prs = fetch_open_prs(owner, repo, token)
    except requests.RequestException as e:
        print(f"[警告] PR一覧の取得に失敗しました: {e}")
        return False

    open_pr_numbers = {pr["number"] for pr in prs}
    notified_conflicts &= open_pr_numbers  # クローズされたPRを削除

    has_pending = False
    for pr in prs:
        number = pr["number"]
        title = pr["title"]
        pr_url = pr.get("html_url", f"https://github.com/{owner}/{repo}/pull/{number}")
        try:
            mergeable = get_pr_mergeable(owner, repo, number, token)
        except requests.RequestException as e:
            print(f"[警告] PR #{number} の取得に失敗しました: {e}")
            continue

        if mergeable is None:
            # GitHub がまだ計算中 → 呼び出し元でリトライさせる
            print(f"[計算中] PR #{number} の mergeable を GitHub が計算中です。再チェックします")
            has_pending = True
        elif mergeable is False:
            if number not in notified_conflicts:
                msg = f"PR #{number}「{title}」にコンフリクトが発生しました"
                print(f"[コンフリクト検知] {msg}")
                send_notification(f"ConflictConfirmer: {owner}/{repo}", msg, pr_url)
                notified_conflicts.add(number)
        elif mergeable is True:
            if number in notified_conflicts:
                msg = f"PR #{number}「{title}」のコンフリクトが解消されました"
                print(f"[解消] {msg}")
                send_notification(f"ConflictConfirmer: {owner}/{repo}", msg)
                notified_conflicts.discard(number)

    return has_pending


def main():
    config = load_config()
    token = config["GITHUB_TOKEN"]
    repo_full = config["GITHUB_REPO"]
    poll_interval = config["POLL_INTERVAL"]

    if "/" not in repo_full:
        print("エラー: GITHUB_REPO は 'owner/repo' の形式で設定してください。")
        sys.exit(1)

    owner, repo = repo_full.split("/", 1)
    notified_conflicts: set = set()
    etag = None
    last_event_id = 0

    print(f"ConflictConfirmer 起動: {owner}/{repo}")
    print(f"イベントポーリング間隔: {poll_interval}秒")

    print(f"[初回チェック] {time.strftime('%Y-%m-%d %H:%M:%S')}")
    run_check(owner, repo, token, notified_conflicts)

    try:
        etag, events = fetch_events(owner, repo, token)
        last_event_id = get_latest_event_id(events)
    except requests.RequestException as e:
        print(f"[警告] 初回イベント取得に失敗しました: {e}")

    while True:
        time.sleep(poll_interval)

        try:
            etag, events = fetch_events(owner, repo, token, etag)
        except requests.RequestException as e:
            print(f"[警告] イベント取得に失敗しました: {e}")
            continue

        if events and has_merge_event(events, last_event_id):
            print(f"[マージ検知] {time.strftime('%Y-%m-%d %H:%M:%S')} コンフリクトチェックを開始します")
            pending = run_check(owner, repo, token, notified_conflicts)
            # mergeable が null のPRがある場合、計算完了まで5秒ごとに最大30秒リトライ
            retries = 0
            while pending and retries < 6:
                time.sleep(5)
                retries += 1
                pending = run_check(owner, repo, token, notified_conflicts)

        if events:
            last_event_id = get_latest_event_id(events)


if __name__ == "__main__":
    main()
