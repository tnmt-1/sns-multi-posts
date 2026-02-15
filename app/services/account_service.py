from collections.abc import MutableMapping
from typing import Any

from fastapi import Request

from app.schemas.account import AccountBase, AccountsDict


def migrate_accounts_session(accounts: dict[str, Any]) -> dict[str, Any]:
    """セッションに保存されている旧形式のアカウントデータを新形式に移行します。

    MisskeyのIDを `id@instance` 形式に変換し、マルチアカウント対応に伴う
    IDの重複を避けるための移行処理を行います。
    """
    if not accounts:
        return accounts

    # Misskey: ID を id@instance 形式に移行
    if "misskey" in accounts and isinstance(accounts["misskey"], list):
        for acc in accounts["misskey"]:
            current_id = str(acc.get("id", ""))
            instance = acc.get("instance")
            # すでに @ が含まれている場合は移行済みとみなす
            if instance and "@" not in current_id:
                acc["id"] = f"{current_id}@{instance}"

    return accounts


class AccountManager:
    """セッション上のアカウント情報を一元管理するマネージャー。

    FastAPI のセッション (Starlette Session) 内に保存された SNS アカウント情報を
    CRUD 操作し、整合性を保つ役割を担います。
    """

    def __init__(self, session: MutableMapping[str, Any]) -> None:
        """アカウントマネージャーを初期化します。

        セッションからアカウントデータを読み込み、必要に応じてデータ移行を行います。

        Args:
            session (MutableMapping[str, Any]): FastAPI/Starlette のセッションオブジェクト。
        """
        self._session = session
        data = session.get("accounts", {})
        self._accounts: dict[str, list[dict[str, Any]]] = migrate_accounts_session(data)

    @property
    def accounts(self) -> AccountsDict:
        """現在管理されている全アカウント情報を取得します。

        Returns:
            AccountsDict: プロバイダー名をキー、アカウント情報のリストを値とする辞書。
        """
        return self._accounts  # type: ignore

    def save(self) -> None:
        """現在のメモリ上のアカウント情報をセッションに永続化します。"""
        self._session["accounts"] = self._accounts

    def find(self, provider: str, account_id: str | int) -> dict[str, Any] | None:
        """指定されたプロバイダーと ID に一致するアカウントを探します。

        Args:
            provider (str): プロバイダー名 ('twitter', 'bluesky', 'misskey')。
            account_id (str | int): アカウントの一意識別子。

        Returns:
            dict[str, Any] | None: 見つかった場合はアカウント情報の辞書、そうでない場合は None。
        """
        provider_list = self._accounts.get(provider, [])
        target_id_str = str(account_id)
        return next((acc for acc in provider_list if str(acc.get("id")) == target_id_str), None)

    def upsert(self, provider: str, account_model: AccountBase) -> None:
        """アカウント情報を新規登録または更新します。

        Args:
            provider (str): プロバイダー名。
            account_model (AccountBase): 更新するアカウントデータモデル。
        """
        if provider not in self._accounts:
            self._accounts[provider] = []

        account_data = account_model.model_dump()
        existing_index = next(
            (i for i, acc in enumerate(self._accounts[provider]) if str(acc["id"]) == str(account_model.id)),
            None,
        )

        if existing_index is not None:
            self._accounts[provider][existing_index] = account_data
        else:
            self._accounts[provider].append(account_data)

    def remove(self, provider: str, account_id: str | int) -> None:
        """指定されたアカウントを削除します。

        Args:
            provider (str): プロバイダー名。
            account_id (str | int): 削除するアカウントの ID。
        """
        if provider not in self._accounts:
            return

        target_id_str = str(account_id)
        self._accounts[provider] = [acc for acc in self._accounts[provider] if str(acc.get("id")) != target_id_str]

    def resolve_targets(self, target_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        """`provider:id` 形式の識別子のリストから、実際のアカウントデータの辞書を作成します。

        Args:
            target_ids (list[str]): `twitter:123` のような形式の文字列リスト。

        Returns:
            dict[str, list[dict[str, Any]]]: プロバイダーごとのアカウントリスト。
        """
        targets: dict[str, list[dict[str, Any]]] = {
            "twitter": [],
            "bluesky": [],
            "misskey": [],
        }

        for identifier in target_ids:
            if ":" not in identifier:
                continue

            provider, acc_id = identifier.split(":", 1)
            acc = self.find(provider, acc_id)
            if acc:
                targets.setdefault(provider, []).append(acc)

        return targets


def get_account_manager(request: Request) -> AccountManager:
    """FastAPI の依存注入 (DI) 用のヘルパー。

    リクエストから AccountManager インスタンスを作成して返します。

    Args:
        request (Request): FastAPI リクエスト。

    Returns:
        AccountManager: 初期化済みのマネージャー。
    """
    return AccountManager(request.session)
