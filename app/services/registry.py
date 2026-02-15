"""各SNSサービスのインスタンスを管理するレジストリモジュール。

サービス間の循環参照を避けるため、サービスインスタンスの生成と取得を
このモジュールで一括管理します。
"""

from .base import SNSProvider
from .bluesky import BlueskyService
from .misskey import MisskeyService
from .twitter import TwitterService

_services: dict[str, SNSProvider] = {
    "twitter": TwitterService(),
    "bluesky": BlueskyService(),
    "misskey": MisskeyService(),
}


def get_service(provider: str) -> SNSProvider | None:
    """プロバイダー名に対応するサービスインスタンスを返します。"""
    return _services.get(provider)
