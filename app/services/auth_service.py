import logging
import uuid
from typing import Any

import httpx
from atproto import Client
from fastapi import HTTPException

from app.services.base import AccountManager, BlueskyAccount, MisskeyAccount, TwitterAccount, TwitterToken

logger = logging.getLogger(__name__)


class AuthService:
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
