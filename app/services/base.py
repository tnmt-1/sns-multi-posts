from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class PostResult(BaseModel):
    success: bool
    provider: str
    post_id: str | None = None
    url: str | None = None
    error: str | None = None


# アカウント情報の基本構造（検証・パース用）
class AccountBase(BaseModel):
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


# セッションに保存されるアカウント情報の構造
type AccountsSession = dict[str, list[dict[str, Any]]]


def migrate_accounts_session(accounts: dict[str, Any]) -> dict[str, Any]:
    """
    セッションに保存されている旧形式のアカウントデータを新形式に移行します。
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


type ImageData = tuple[bytes, str]


@runtime_checkable
class SNSProvider(Protocol):
    def get_text_length(self, text: str) -> int:
        """SNS固有の文字数計算方法で長さを返します。"""
        ...

    def get_character_limit(self) -> int:
        """SNSの文字数制限を返します。"""
        ...

    async def post(
        self,
        account: Mapping[str, Any],
        text: str,
        images: list[ImageData] | None = None,
        **kwargs: Any,
    ) -> PostResult:
        """SNSに投稿します。"""
        ...
