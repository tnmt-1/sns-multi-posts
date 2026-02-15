"""各SNSサービスのインスタンスを管理するレジストリモジュール。

サービス間の循環参照を避けるため、サービスインスタンスの生成と取得を
このモジュールで一括管理します。
"""

from .base_service import BaseSNSProvider
from .bluesky_service import BlueskyService
from .misskey_service import MisskeyService
from .twitter_service import TwitterService

_services: dict[str, BaseSNSProvider] = {
    "twitter": TwitterService(),
    "bluesky": BlueskyService(),
    "misskey": MisskeyService(),
}


def get_service(provider: str) -> BaseSNSProvider | None:
    """プロバイダー名に対応するサービスインスタンスを返します。"""
    return _services.get(provider)
