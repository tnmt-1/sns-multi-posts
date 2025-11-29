# Vercel requires a handler variable, but for FastAPI with vercel-python,
# we usually just expose the app instance.
# However, depending on the WSGI/ASGI adapter used by Vercel,
# sometimes we need to wrap it.
# The @vercel/python builder supports ASGI apps directly if 'app' is exposed.

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
