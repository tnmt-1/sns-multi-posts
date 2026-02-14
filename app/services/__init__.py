from .base import SNSProvider
from .bluesky import BlueskyService
from .misskey import MisskeyService
from .twitter import TwitterService

services: dict[str, SNSProvider] = {
    "twitter": TwitterService(),
    "bluesky": BlueskyService(),
    "misskey": MisskeyService(),
}


def get_service(provider: str) -> SNSProvider | None:
    return services.get(provider)
