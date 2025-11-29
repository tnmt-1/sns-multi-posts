import os

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.routers import auth, post

app = FastAPI(title="SNS Multi-Post")

# Secret key for session encryption. In production, use an env var.
SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key_change_me")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Mount static files only if directory exists
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth.router)
app.include_router(post.router)


@app.get("/")
async def read_root(request: Request) -> Response:
    accounts = request.session.get("accounts", {})

    # Get flash message from session
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
