import logging
import uuid
from typing import Any, cast

import httpx
from atproto import Client
from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, Request
from starlette.responses import Response

from app.config import settings
from app.schemas.account import BlueskyAccount, MisskeyAccount, TwitterAccount, TwitterToken
from app.services.account_service import AccountManager

logger = logging.getLogger(__name__)

oauth = OAuth()

# Twitter (X) の設定
oauth.register(
    name="twitter",
    client_id=settings.twitter_client_id,
    client_secret=settings.twitter_client_secret,
    request_token_url="https://api.twitter.com/oauth/request_token",
    request_token_params=None,
    access_token_url="https://api.twitter.com/oauth/access_token",
    access_token_params=None,
    authorize_url="https://api.twitter.com/oauth/authenticate",
    authorize_params=None,
    api_base_url="https://api.twitter.com/1.1/",
    client_kwargs=None,
)


class AuthService:
    @staticmethod
    async def get_login_redirect(request: Request, provider: str, redirect_uri: str) -> Response | None:
        """指定されたプロバイダーのログインリダイレクトレスポンスを返します。

        Twitterの場合は OAuth のリダイレクトレスポンスを返します。
        Bluesky/Misskey の場合は None を返し、ルーター側でログイン画面を表示させます。
        """
        if provider == "twitter":
            return cast(Response, await oauth.twitter.authorize_redirect(request, redirect_uri))
        return None

    @staticmethod
    async def handle_twitter_callback(request: Request, manager: AccountManager) -> None:
        """Twitter の認証コールバックを処理し、アカウント情報を保存します。"""
        token = await oauth.twitter.authorize_access_token(request)
        resp = await oauth.twitter.get("account/verify_credentials.json", token=token)
        if resp.status_code != 200:
            logger.error(f"Twitter verify_credentials failed: {resp.status_code} - {resp.text}")
            raise HTTPException(status_code=400, detail="Twitter authentication failed")

        user_data = resp.json()
        AuthService.save_twitter_account(manager, user_data, token)

    @staticmethod
    async def login_bluesky(manager: AccountManager, handle: str, password: str) -> None:
        """Blueskyにログインし、アカウント情報を保存します。"""
        client = Client()
        profile = client.login(handle, password)

        account_model = BlueskyAccount(
            id=profile.did,
            username=profile.handle,
            name=profile.display_name or profile.handle,
            handle=handle,
            password=password,
        )
        manager.upsert("bluesky", account_model)
        manager.save()

    @staticmethod
    def prepare_misskey_login(session: dict[str, Any], instance: str, callback_url: str) -> str:
        """Misskeyの認証URLを生成し、セッションに保留情報を保存します。"""
        session_id = str(uuid.uuid4())
        instance = instance.replace("https://", "").replace("http://", "").strip("/")

        session["misskey_pending"] = {
            "session_id": session_id,
            "instance": instance,
        }

        permissions = "write:notes,write:drive"
        return (
            f"https://{instance}/miauth/{session_id}?name=SNSMultiPost&callback={callback_url}&permission={permissions}"
        )

    @staticmethod
    async def callback_misskey(manager: AccountManager, session: dict[str, Any]) -> None:
        """Misskeyの認証コールバックを処理します。"""
        pending = session.get("misskey_pending")
        if not pending:
            raise HTTPException(status_code=400, detail="No pending Misskey login")

        session_id = pending["session_id"]
        instance = pending["instance"]

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"https://{instance}/api/miauth/{session_id}/check")
            if resp.status_code != 200:
                logger.error(f"Misskey check failed: {resp.status_code} - {resp.text}")
                raise HTTPException(status_code=400, detail="Misskey authentication failed")

            auth_info = resp.json()
            if not auth_info.get("ok"):
                raise HTTPException(status_code=401, detail="Misskey authentication rejected")

            user = auth_info["user"]
            token = auth_info["token"]

            account_model = MisskeyAccount(
                id=f"{user['id']}@{instance}",
                username=user["username"],
                name=user["name"] or user["username"],
                instance=instance,
                token=token,
            )

            manager.upsert("misskey", account_model)
            manager.save()
            session.pop("misskey_pending", None)

    @staticmethod
    def save_twitter_account(manager: AccountManager, user_data: dict[str, Any], token: dict[str, Any]) -> None:
        """Twitterアカウント情報を保存します。"""
        account_model = TwitterAccount(
            id=str(user_data.get("id_str", "")),
            username=str(user_data.get("screen_name", "")),
            name=str(user_data.get("name", "")),
            token=TwitterToken.model_validate(token),
        )
        manager.upsert("twitter", account_model)
        manager.save()
