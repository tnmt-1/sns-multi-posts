from typing import Any, TypedDict

from pydantic import BaseModel, ConfigDict


class AccountBase(BaseModel):
    """SNS アカウント情報の基底 Pydantic モデル。

    すべての SNS プロバイダーで共通の情報を定義します。

    Attributes:
        id (str | int): プロバイダー内での一意な ID。
        username (str): ユーザーを識別する名前 (ハンドル、スクリーンネーム等)。
        name (str): ユーザーの表示名。
    """

    model_config = ConfigDict(extra="ignore")

    id: str | int
    username: str
    name: str


class BlueskyAccount(AccountBase):
    """Bluesky 特有のアカウント認証情報を含むモデル。"""

    handle: str
    password: str


class MisskeyAccount(AccountBase):
    """Misskey 特有のアカウント認証情報を含むモデル。"""

    instance: str
    token: str


class TwitterToken(BaseModel):
    """Twitter OAuth 1.0a のトークン情報を保持するモデル。"""

    oauth_token: str
    oauth_token_secret: str


class TwitterAccount(AccountBase):
    """Twitter アカウント情報とトークンを保持するモデル。"""

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
