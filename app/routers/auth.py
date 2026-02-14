import logging
import uuid
from typing import cast

import httpx
from atproto import Client
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse, Response

from app.config import settings

# ロガーの設定
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

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


@router.get("/login/{provider}")
async def login(request: Request, provider: str) -> Response:
    redirect_uri = request.url_for("auth_callback", provider=provider)
    if provider == "twitter":
        # authorize_redirect は実際には Starlette Response を返すが、
        # ライブラリ側の型が Any になっているため Response として明示する
        return cast(Response, await oauth.twitter.authorize_redirect(request, redirect_uri))
    elif provider == "bluesky":
        return templates.TemplateResponse("auth/bluesky_login.html", {"request": request})
    elif provider == "misskey":
        return templates.TemplateResponse("auth/misskey_login.html", {"request": request})

    raise HTTPException(status_code=404, detail="Provider not found")


@router.post("/login/bluesky")
async def login_bluesky(request: Request, handle: str = Form(...), password: str = Form(...)) -> Response:
    try:
        client = Client()
        profile = client.login(handle, password)

        # セッションにアカウント情報を保存
        accounts = request.session.get("accounts", {})
        if "bluesky" not in accounts:
            accounts["bluesky"] = []

        account_info = {
            "id": profile.did,
            "username": profile.handle,
            "name": profile.display_name or profile.handle,
            "handle": handle,
            # 警告: パスワードをセッションに保存するのは理想的ではありませんが、フルOAuthなしで atproto クライアントを再利用するために必要です。
            "password": password,
            # 実際のアプリでは、可能であればセッション文字列やリフレッシュトークンを使用すべきです。
        }

        # 重複を避ける
        existing_ids = [acc["id"] for acc in accounts["bluesky"]]
        if account_info["id"] not in existing_ids:
            accounts["bluesky"].append(account_info)

        request.session["accounts"] = accounts
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("auth/bluesky_login.html", {"request": request, "error": str(e)})


@router.post("/login/misskey")
async def login_misskey(request: Request, instance: str = Form(...)) -> Response:
    session_id = str(uuid.uuid4())
    # インスタンスURLをクリーンアップ
    instance = instance.replace("https://", "").replace("http://", "").strip("/")

    callback_url = str(request.url_for("auth_callback", provider="misskey"))
    # 検証のために session_id をコールバックに追加するか、単純にセッションを使用します。
    # MiAuthはコールバックURLでカスタムステートを簡単に返さないため、session_id をキーとして使用します。

    # 認証待ち情報を保存
    request.session["misskey_pending"] = {"session_id": session_id, "instance": instance}

    # 画像アップロードでドライブにファイルを書き込む必要があるため、
    # MiAuth で drive の書き込み権限も要求する
    # Misskey の MiAuth では permission をカンマ区切りで指定できる
    permissions = "write:notes,write:drive"
    auth_url = (
        f"https://{instance}/miauth/{session_id}?name=SNSMultiPost&callback={callback_url}&permission={permissions}"
    )
    return RedirectResponse(url=auth_url, status_code=303)


@router.get("/callback/{provider}")
async def auth_callback(request: Request, provider: str, session: str | None = None) -> RedirectResponse:
    accounts = request.session.get("accounts", {})

    if provider == "twitter":
        token = await oauth.twitter.authorize_access_token(request)

        # v1.1 verify_credentials を使用してユーザー情報を取得
        resp = await oauth.twitter.get("account/verify_credentials.json", token=token)
        if resp.status_code != 200:
            logger.error(f"Twitter verify_credentials failed: {resp.status_code} - {resp.text}")
            raise HTTPException(status_code=400, detail="Twitter authentication failed")

        user_data = resp.json()

        # アカウント情報をセッションに保存
        accounts = request.session.get("accounts", {})
        if "twitter" not in accounts:
            accounts["twitter"] = []

        account_info = {
            "id": user_data.get("id_str"),
            "username": user_data.get("screen_name"),
            "name": user_data.get("name"),
            "token": token,
        }

        # 重複を避ける
        existing_ids = [acc["id"] for acc in accounts["twitter"]]
        if account_info["id"] not in existing_ids:
            accounts["twitter"].append(account_info)

        request.session["accounts"] = accounts

    elif provider == "misskey":
        pending = request.session.get("misskey_pending")
        if not pending:
            raise HTTPException(status_code=400, detail="No pending Misskey login")

        session_id = pending["session_id"]
        instance = pending["instance"]

        # 検証
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"https://{instance}/api/miauth/{session_id}/check")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Misskey auth failed")

            data = resp.json()
            if not data.get("ok"):
                raise HTTPException(status_code=400, detail="Misskey auth failed")

            token = data.get("token")
            user = data.get("user", {})

            if "misskey" not in accounts:
                accounts["misskey"] = []

            account_info = {
                "id": user.get("id"),
                "username": user.get("username"),
                "name": user.get("name"),
                "instance": instance,
                "token": token,
            }

            existing_ids = [acc["id"] for acc in accounts["misskey"]]
            if account_info["id"] not in existing_ids:
                accounts["misskey"].append(account_info)

            request.session["accounts"] = accounts
            request.session.pop("misskey_pending", None)

    return RedirectResponse(url="/")


@router.get("/disconnect/{provider}/{account_id}")
async def disconnect(request: Request, provider: str, account_id: str) -> RedirectResponse:
    accounts = request.session.get("accounts", {})
    if provider in accounts:
        # 一致するIDのアカウントを除外
        accounts[provider] = [acc for acc in accounts[provider] if acc.get("id") != account_id]

        # このプロバイダーAccountがなくなった場合、キーを削除
        if not accounts[provider]:
            del accounts[provider]

        if not accounts:
            request.session.pop("accounts", None)
        else:
            request.session["accounts"] = accounts

    return RedirectResponse(url="/")


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.pop("accounts", None)
    return RedirectResponse(url="/")
