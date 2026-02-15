import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse, Response

from app.services.account_service import AccountManager, get_account_manager
from app.services.auth_service import AuthService

# ロガーの設定
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/login/{provider}")
async def login(request: Request, provider: str) -> Response:
    """指定されたSNSプロバイダーのログイン処理を開始します。

    Args:
        request (Request): FastAPIリクエスト。
        provider (str): プロバイダー名 ('twitter', 'bluesky', 'misskey')。

    Returns:
        Response: リダイレクト、またはログイン画面のレスポンス。
    """
    redirect_uri = str(request.url_for("auth_callback", provider=provider))

    # プロバイダー固有のリダイレクト処理がある場合はそれを実行
    redirect_resp = await AuthService.get_login_redirect(request, provider, redirect_uri)
    if redirect_resp:
        return redirect_resp

    # ログイン画面が必要なプロバイダーの処理
    if provider == "bluesky":
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
    try:
        if provider == "twitter":
            await AuthService.handle_twitter_callback(request, manager)
        elif provider == "misskey":
            await AuthService.callback_misskey(manager, request.session)

    except Exception as e:
        logger.error(f"Callback failed for {provider}: {e}")
        # エラー発生時もひとまずトップへ。本来はエラー表示すべきだが
        # 現状の挙動を維持（あるいは若干改善）
        return RedirectResponse(url="/", status_code=303)

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
