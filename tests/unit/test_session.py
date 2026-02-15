from typing import Any

from app.services.account_service import migrate_accounts_session


def test_migrate_accounts_session_empty():
    """空のセッションは何もしないことを確認"""
    assert migrate_accounts_session({}) == {}


def test_migrate_accounts_session_misskey_old_format():
    """Misskey の旧形式 ID が id@instance 形式に移行されることを確認"""
    old_accounts = {
        "misskey": [
            {"id": "12345", "username": "user1", "instance": "misskey.io"},
            {"id": "67890", "username": "user2", "instance": "misskey.design"},
        ]
    }
    migrated = migrate_accounts_session(old_accounts)

    assert migrated["misskey"][0]["id"] == "12345@misskey.io"
    assert migrated["misskey"][1]["id"] == "67890@misskey.design"


def test_migrate_accounts_session_misskey_new_format_idempotent():
    """新形式 ID ( すでに @ が含まれる ) は変更されないことを確認 (冪等性)"""
    new_accounts = {"misskey": [{"id": "12345@misskey.io", "username": "user1", "instance": "misskey.io"}]}
    migrated = migrate_accounts_session(new_accounts)

    assert migrated["misskey"][0]["id"] == "12345@misskey.io"


def test_migrate_accounts_session_bluesky_untouched():
    """Bluesky など他プロバイダーの ID は変更されないことを確認"""
    accounts = {"bluesky": [{"id": "did:plc:abcde", "username": "user.bsky.social"}]}
    migrated = migrate_accounts_session(accounts)

    assert migrated["bluesky"][0]["id"] == "did:plc:abcde"


def test_migrate_accounts_session_invalid_structure():
    """予期しない構造が含まれていてもクラッシュしないことを確認"""
    invalid_accounts: dict[str, Any] = {"misskey": "not a list", "other": 123}
    # 例外が起きないこと
    assert migrate_accounts_session(invalid_accounts) == invalid_accounts
