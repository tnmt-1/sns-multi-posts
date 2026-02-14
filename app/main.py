import os

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.routers import auth, post

# 環境変数の検証
REQUIRED_ENV_VARS = ["SECRET_KEY", "TWITTER_CLIENT_ID", "TWITTER_CLIENT_SECRET"]
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]

if missing_vars:
    # 開発中は、本番環境（VERCEL=1）でなければデフォルトのSECRET_KEYを許可できますが、
    # Twitterキーについては警告を出すか例外を発生させるべきです。
    if "SECRET_KEY" in missing_vars and os.getenv("VERCEL") != "1":
        print("Warning: SECRET_KEY is not set. Using a default key for development.")
        missing_vars.remove("SECRET_KEY")

    if missing_vars:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")

app = FastAPI(title="SNS Multi-Post")

# セッション暗号化用のシークレットキー
SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key_change_me")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# ディレクトリが存在する場合のみ静的ファイルをマウント
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# テンプレート設定
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth.router)
app.include_router(post.router)


@app.get("/")
async def read_root(request: Request) -> Response:
    accounts = request.session.get("accounts", {})

    # セッションからフラッシュメッセージを取得
    flash_message = request.session.pop("flash_message", None)
    flash_type = request.session.pop("flash_type", None)

    context = {"request": request, "accounts": accounts}

    if flash_message:
        if flash_type == "success":
            context["message"] = flash_message
        else:
            context["error"] = flash_message

    return templates.TemplateResponse("index.html", context)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
