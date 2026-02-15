from collections.abc import Mapping, MutableMapping
from typing import Any, Protocol, TypedDict, runtime_checkable

from fastapi import Request
from pydantic import BaseModel, ConfigDict


class PostResult(BaseModel):
    """SNSへの投稿結果を保持するモデル。

    Attributes:
        success (bool): 投稿が成功したかどうか。
        provider (str): 投稿先のプロバイダー名（twitter, bluesky, misskeyなど）。
        post_id (str | None): SNS側で発行された投稿ID。
        url (str | None): 投稿された内容のURL。
        error (str | None): 失敗時のエラーメッセージ。
    """

    success: bool
    provider: str
    post_id: str | None = None
    url: str | None = None
    error: str | None = None

    @property
    def translated_error(self) -> str:
        """エラー内容をユーザーフレンドリーな日本語に翻訳します。

        Returns:
            str: 翻訳されたエラーメッセージ。
        """
        if self.success:
            return ""

        msg = self.error or "Unknown error"
        msg_lower = msg.lower()

        if "429" in msg or "rate limit" in msg_lower:
            return "API制限にかかりました。少し待ってから再度お試しください。"
        if "401" in msg or "unauthorized" in msg_lower:
            return "認証に失敗しました。アカウントを再連携してください。"
        if "403" in msg or "forbidden" in msg_lower:
            return "アクセスが拒否されました。権限を確認してください。"

        return msg


# アカウント情報の基本構造（検証・パース用）
class AccountBase(BaseModel):
    """アカウント情報の基本モデル。

    Attributes:
        id (str | int): アカウントの一意な識別子。
        username (str): ユーザー名（@handleなど）。
        name (str): 表示名。
    """

    model_config = ConfigDict(extra="ignore")

    id: str | int
    username: str
    name: str


class BlueskyAccount(AccountBase):
    handle: str
    password: str


class MisskeyAccount(AccountBase):
    instance: str
    token: str


class TwitterToken(BaseModel):
    oauth_token: str
    oauth_token_secret: str


class TwitterAccount(AccountBase):
    token: TwitterToken


def migrate_accounts_session(accounts: dict[str, Any]) -> dict[str, Any]:
    """セッションに保存されている旧形式のアカウントデータを新形式に移行します。

    MisskeyのIDを `id@instance` 形式に変換し、マルチアカウント対応に伴う
    IDの重複を避けるための移行処理を行います。

    Args:
        accounts (dict[str, Any]): セッションから取得したアカウント辞書。

    Returns:
        dict[str, Any]: 移行処理後のアカウント辞書。
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


class RawAccountData(TypedDict):
    """セッションに格納されるアカウントの生データ形式。"""

    id: str | int
    username: str
    name: str


class AccountsDict(TypedDict):
    """プロバイダーごとのアカウントリストを保持する辞書形式。"""

    twitter: list[dict[str, Any]]
    bluesky: list[dict[str, Any]]
    misskey: list[dict[str, Any]]


class AccountManager:
    """セッション上のアカウント情報を一元管理するマネージャー。

    セッション辞書へのアクセスをカプセル化し、アカウントの検索、追加、
    および投稿対象の解決などのロジックを提供します。
    """

    def __init__(self, session: MutableMapping[str, Any]) -> None:
        """AccountManagerを初期化します。

        Args:
            session (MutableMapping[str, Any]): FastAPI/Starletteのセッションオブジェクト。
        """
        self._session = session
        data = session.get("accounts", {})
        self._accounts: dict[str, list[dict[str, Any]]] = migrate_accounts_session(data)

    @property
    def accounts(self) -> AccountsDict:
        """現在のアカウント情報を取得します。

        Returns:
            AccountsDict: プロバイダーごとのアカウント情報。
        """
        # Note: 実装上は dict ですが、期待される構造を TypedDict で示しています
        return self._accounts  # type: ignore

    def save(self) -> None:
        """変更をセッションに反映します。
        Mutable型（dict）の一部を破壊的に変更した場合、session["accounts"] = ...
        と代入しないとStarletteのSessionMiddlewareが変更を検知しない場合があります。
        """
        self._session["accounts"] = self._accounts

    def find(self, provider: str, account_id: str | int) -> dict[str, Any] | None:
        """特定のアカウントを検索します。

        Args:
            provider (str): プロバイダー名。
            account_id (str | int): 検索するアカウントID。

        Returns:
            dict[str, Any] | None: 見つかった場合はアカウント情報の辞書。
        """
        provider_list = self._accounts.get(provider, [])
        target_id_str = str(account_id)
        return next((acc for acc in provider_list if str(acc.get("id")) == target_id_str), None)

    def upsert(self, provider: str, account_model: AccountBase) -> None:
        """アカウント情報を追加または更新します。

        Args:
            provider (str): プロバイダー名。
            account_model (AccountBase): 追加・更新するアカウントモデル。
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
        """アカウントを削除します。

        Args:
            provider (str): プロバイダー名。
            account_id (str | int): 削除するアカウントID。
        """
        if provider not in self._accounts:
            return

        target_id_str = str(account_id)
        self._accounts[provider] = [acc for acc in self._accounts[provider] if str(acc.get("id")) != target_id_str]

    def resolve_targets(self, target_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        """投稿対象のIDリストを解決して、詳細なアカウント情報を取得します。

        Args:
            target_ids (list[str]): ユーザーが選択したID（形式: "provider:id"）。

        Returns:
            dict[str, list[dict[str, Any]]]: プロバイダー名をキー、アカウント情報のリストを値とする辞書。
        """
        targets: dict[str, list[dict[str, Any]]] = {
            "twitter": [],
            "bluesky": [],
            "misskey": [],
        }

        for identifier in target_ids:
            if ":" not in identifier:
                continue

            # identifier format: "provider:id"
            provider, acc_id = identifier.split(":", 1)
            acc = self.find(provider, acc_id)
            if acc:
                targets.setdefault(provider, []).append(acc)

        return targets


def get_account_manager(request: Request) -> AccountManager:
    """FastAPI 依存性注入用の AccountManager インスタンス取得関数。"""
    return AccountManager(request.session)


type ImageData = tuple[bytes, str]


@runtime_checkable
class SNSProvider(Protocol):
    """SNSプロバイダーが実装すべき共通インターフェース。"""

    def get_text_length(self, text: str) -> int:
        """SNS固有の文字数計算方法で長さを返します。

        Args:
            text (str): 計算対象の文字列。

        Returns:
            int: 文字数。
        """
        ...

    def get_character_limit(self) -> int:
        """SNSの文字数制限を返します。

        Returns:
            int: 最大文字数。
        """
        ...

    async def post(
        self,
        account: Mapping[str, Any],
        text: str,
        images: list[ImageData] | None = None,
        **kwargs: Any,
    ) -> PostResult:
        """SNSにメッセージを投稿します。

        Args:
            account (Mapping[str, Any]): 投稿に使用するアカウントの認証情報。
            text (str): 投稿する本文。
            images (list[ImageData] | None): 投稿する画像のリスト（バイトデータとMIMEタイプのタプル）。
            **kwargs (Any): 追加の引数。

        Returns:
            PostResult: 投稿結果。
        """
        ...
