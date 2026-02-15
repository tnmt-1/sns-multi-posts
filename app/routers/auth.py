import logging
from typing import cast

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse, Response

from app.config import settings
from app.services.auth_service import AuthService
from app.services.base import AccountManager, get_account_manager

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
        return cast(Response, await oauth.twitter.authorize_redirect(request, redirect_uri))
    elif provider == "bluesky":
        return templates.TemplateResponse("auth/bluesky_login.html", {"request": request})
    elif provider == "misskey":
        return templates.TemplateResponse("auth/misskey_login.html", {"request": request})

    raise HTTPException(status_code=404, detail="Provider not found")


@router.post("/login/bluesky")
async def login_bluesky(
    request: Request,
    handle: str = Form(...),
    password: str = Form(...),
    manager: AccountManager = Depends(get_account_manager),
) -> Response:
    """BlueskyのID/パスワード認証を行い、アカウントをセッションに登録します。

    Args:
        request (Request): FastAPIリクエスト。
        handle (str): Blueskyのハンドル名。
        password (str): アプリパスワード。
        manager (AccountManager): アカウント管理マネージャー。

    Returns:
        Response: ホームへのリダイレクト、またはエラー時のログイン画面。
    """
    try:
        await AuthService.login_bluesky(manager, handle, password)
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
    callback_url = str(request.url_for("auth_callback", provider="misskey"))
    auth_url = AuthService.prepare_misskey_login(request.session, instance, callback_url)
    return RedirectResponse(url=auth_url, status_code=303)


@router.get("/callback/{provider}")
async def auth_callback(
    request: Request,
    provider: str,
    session: str | None = None,
    manager: AccountManager = Depends(get_account_manager),
) -> RedirectResponse:
    """各SNSプロバイダーからの認証コールバックを処理します。

    Args:
        request (Request): FastAPIリクエスト。
        provider (str): プロバイダー名。
        session (str | None): MisskeyのセッションID（URLクエリパラメータとして渡される場合）。
        manager (AccountManager): アカウント管理マネージャー。

    Returns:
        RedirectResponse: ホームへのリダイレクト。
    """
    if provider == "twitter":
        token = await oauth.twitter.authorize_access_token(request)

        # v1.1 verify_credentials を使用してユーザー情報を取得
        resp = await oauth.twitter.get("account/verify_credentials.json", token=token)
        if resp.status_code != 200:
            logger.error(f"Twitter verify_credentials failed: {resp.status_code} - {resp.text}")
            raise HTTPException(status_code=400, detail="Twitter authentication failed")

        AuthService.save_twitter_account(manager, resp.json(), token)

    elif provider == "misskey":
        await AuthService.callback_misskey(manager, request.session)

    return RedirectResponse(url="/", status_code=303)


@router.get("/disconnect/{provider}/{account_id}")
async def disconnect(
    request: Request,
    provider: str,
    account_id: str,
    manager: AccountManager = Depends(get_account_manager),
) -> Response:
    """指定されたアカウントの連携を解除（セッションから削除）します。

    Args:
        request (Request): FastAPIリクエスト。
        provider (str): プロバイダー名。
        account_id (str): 削除するアカウントID。
        manager (AccountManager): アカウント管理マネージャー。

    Returns:
        Response: ホームへのリダイレクト。
    """
    manager.remove(provider, account_id)
    manager.save()
    return RedirectResponse(url="/", status_code=303)
