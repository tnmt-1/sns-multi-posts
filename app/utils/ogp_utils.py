import logging
import re
from typing import TypedDict

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class OGPData(TypedDict):
    """OGP データを表す型。"""

    title: str | None
    description: str | None
    image_url: str | None
    url: str


async def fetch_ogp(url: str) -> OGPData | None:
    """指定された URL から OGP 情報を取得します。

    Args:
        url (str): OGP を取得する URL。

    Returns:
        OGPData | None: 取得した OGP 情報。取得に失敗した場合は None。
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            title = None
            if tag := soup.find("meta", property="og:title"):
                title = tag.get("content")
            elif tag := soup.find("title"):
                title = tag.text

            description = None
            if tag := soup.find("meta", property="og:description"):
                description = tag.get("content")
            elif tag := soup.find("meta", attrs={"name": "description"}):
                description = tag.get("content")

            image_url = None
            if tag := soup.find("meta", property="og:image"):
                image_url = tag.get("content")

            # title が空の場合は、URL 自体をタイトルとして使用する
            if not title:
                title = url

            return {
                "title": str(title) if title else None,
                "description": str(description) if description else None,
                "image_url": str(image_url) if image_url else None,
                "url": url,
            }
    except Exception as e:
        logger.warning(f"Failed to fetch OGP for {url}: {e}")
        return None


async def fetch_image(url: str) -> tuple[bytes, str] | None:
    """指定された URL から画像データを取得します。

    Args:
        url (str): 画像を取得する URL。

    Returns:
        tuple[bytes, str] | None: 画像のバイトデータと MIME タイプのタプル。取得に失敗した場合は None。
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            mime_type = resp.headers.get("Content-Type", "image/jpeg")
            return resp.content, mime_type
    except Exception as e:
        logger.warning(f"Failed to fetch image for OGP from {url}: {e}")
        return None


def extract_first_url(text: str) -> str | None:
    """テキストから最初の URL を抽出します。

    Args:
        text (str): 抽出対象のテキスト。

    Returns:
        str | None: 抽出した URL。見つからない場合は None。
    """
    match = re.search(r"https?://[^\s]+", text)
    return match.group(0) if match else None
