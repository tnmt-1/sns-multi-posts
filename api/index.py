# Vercelはhandler変数を必要としますが、FastAPIとvercel-pythonの組み合わせでは、
# 通常appインスタンスを公開するだけで十分です。
# ただし、Vercelが使用するWSGI/ASGIアダプターによっては、
# ラップが必要になる場合があります。
# @vercel/pythonビルダーは、'app'が公開されていればASGIアプリを直接サポートします。

import sys
from pathlib import Path

# インポートのために親ディレクトリをパスに追加します
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app  # noqa: F401
