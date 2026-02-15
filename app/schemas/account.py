from typing import Any, TypedDict

from pydantic import BaseModel, ConfigDict


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
