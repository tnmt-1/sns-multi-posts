import logging
import uuid

import httpx
from atproto import Client
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse, Response

from app.config import settings
from app.services.base import AccountManager, BlueskyAccount, MisskeyAccount, TwitterAccount

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
    """指定されたSNSプロバイダーのログイン処理を開始します。

    Args:
        request (Request): FastAPIリクエスト。
        provider (str): プロバイダー名 ('twitter', 'bluesky', 'misskey')。

    Returns:
        Response: リダイレクト、またはログイン画面のレスポンス。
    """
    redirect_uri = request.url_for("auth_callback", provider=provider)
    if provider == "twitter":
        # authorize_redirect は実際には Starlette Response を返すが、
        # ライブラリ側の型が Any になっているため Response として明示する
        return await oauth.twitter.authorize_redirect(request, redirect_uri)
    elif provider == "bluesky":
        return templates.TemplateResponse("auth/bluesky_login.html", {"request": request})
    elif provider == "misskey":
        return templates.TemplateResponse("auth/misskey_login.html", {"request": request})

    raise HTTPException(status_code=404, detail="Provider not found")


@router.post("/login/bluesky")
async def login_bluesky(request: Request, handle: str = Form(...), password: str = Form(...)) -> Response:
    """BlueskyのID/パスワード認証を行い、アカウントをセッションに登録します。

    Args:
        request (Request): FastAPIリクエスト。
        handle (str): Blueskyのハンドル名。
        password (str): アプリパスワード。

    Returns:
        Response: ホームへのリダイレクト、またはエラー時のログイン画面。
    """
    try:
        client = Client()
        profile = client.login(handle, password)

        # Pydantic モデルを使用してデータを検証
        account_model = BlueskyAccount(
            id=profile.did,
            username=profile.handle,
            name=profile.display_name or profile.handle,
            handle=handle,
            password=password,
        )

        # AccountManager を使用してアカウントを保存
        manager = AccountManager(request.session)
        manager.upsert("bluesky", account_model)
        manager.save()

        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("auth/bluesky_login.html", {"request": request, "error": str(e)})


@router.post("/login/misskey")
async def login_misskey(request: Request, instance: str = Form(...)) -> Response:
    """MisskeyのMiAuthを開始するためのリダイレクトを行います。

    Args:
        request (Request): FastAPIリクエスト。
        instance (str): Misskeyインスタンスのホスト名。

    Returns:
        Response: Misskey認証URLへのリダイレクト。
    """
    session_id = str(uuid.uuid4())
    # インスタンスURLをクリーンアップ
    instance = instance.replace("https://", "").replace("http://", "").strip("/")

    callback_url = str(request.url_for("auth_callback", provider="misskey"))
    # 検証のために session_id をコールバックに追加するか、単純にセッションを使用します。
    # MiAuthはコールバックURLでカスタムステートを簡単に返さないため、session_id をキーとして使用します。

    # 認証待ち情報を保存
    request.session["misskey_pending"] = {
        "session_id": session_id,
        "instance": instance,
    }

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
    """各SNSプロバイダーからの認証コールバックを処理します。

    Args:
        request (Request): FastAPIリクエスト。
        provider (str): プロバイダー名。
        session (str | None): MisskeyのセッションID（URLクエリパラメータとして渡される場合）。

    Returns:
        RedirectResponse: ホームへのリダイレクト。
    """
    manager = AccountManager(request.session)

    if provider == "twitter":
        token = await oauth.twitter.authorize_access_token(request)

        # v1.1 verify_credentials を使用してユーザー情報を取得
        resp = await oauth.twitter.get("account/verify_credentials.json", token=token)
        if resp.status_code != 200:
            logger.error(f"Twitter verify_credentials failed: {resp.status_code} - {resp.text}")
            raise HTTPException(status_code=400, detail="Twitter authentication failed")

        user_data = resp.json()

        # Pydantic モデルを使用してデータを検証
        account_model = TwitterAccount(
            id=user_data.get("id_str"),
            username=user_data.get("screen_name"),
            name=user_data.get("name"),
            token=token,
        )

        manager.upsert("twitter", account_model)
        manager.save()

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
                logger.error(f"Misskey check failed: {resp.status_code} - {resp.text}")
                raise HTTPException(status_code=400, detail="Misskey authentication failed")

            auth_info = resp.json()
            if not auth_info.get("ok"):
                raise HTTPException(status_code=401, detail="Misskey authentication rejected")

            user = auth_info["user"]
            token = auth_info["token"]

            # Pydantic モデルを使用してデータを検証
            account_model = MisskeyAccount(
                # ID を id@instance 形式にして重複を避ける
                id=f"{user['id']}@{instance}",
                username=user["username"],
                name=user["name"] or user["username"],
                instance=instance,
                token=token,
            )

            manager.upsert("misskey", account_model)
            manager.save()

        # 一時的なセッション情報を削除
        request.session.pop("misskey_pending", None)

    return RedirectResponse(url="/", status_code=303)


@router.get("/disconnect/{provider}/{account_id}")
async def disconnect(request: Request, provider: str, account_id: str) -> Response:
    """指定されたアカウントの連携を解除（セッションから削除）します。

    Args:
        request (Request): FastAPIリクエスト。
        provider (str): プロバイダー名。
        account_id (str): 削除するアカウントID。

    Returns:
        Response: ホームへのリダイレクト。
    """
    manager = AccountManager(request.session)
    manager.remove(provider, account_id)
    manager.save()
    return RedirectResponse(url="/", status_code=303)
