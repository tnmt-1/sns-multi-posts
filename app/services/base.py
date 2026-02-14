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
