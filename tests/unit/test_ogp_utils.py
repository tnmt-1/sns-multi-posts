import pytest
from app.utils.ogp_utils import extract_first_url, fetch_ogp, fetch_image
from unittest.mock import MagicMock, patch


def test_extract_first_url_should_return_first_url_from_text():
    """
    テキストから最初の URL を抽出できることを検証します。
    """
    # Arrange: 複数の URL を含むテキストの準備
    text = "Here is a link https://example.com and another http://test.org"
    expected_url = "https://example.com"

    # Act: URL の抽出
    actual_url = extract_first_url(text)

    # Assert: 最初の URL が正しく抽出されていること
    assert actual_url == expected_url


def test_extract_first_url_should_return_none_when_no_url_present():
    """
    URL が含まれないテキストの場合、None を返すことを検証します。
    """
    # Arrange: URL を含まないテキスト
    text = "No links here."

    # Act: URL の抽出
    actual_url = extract_first_url(text)

    # Assert: None が返されること
    assert actual_url is None


@pytest.mark.asyncio
async def test_fetch_ogp_should_extract_data_from_meta_tags():
    """
    HTML の meta タグから OGP 情報（タイトル、説明、画像）を正しく抽出できることを検証します。
    """
    # Arrange: OGP タグを含む HTML とモックの準備
    target_url = "https://example.com"
    mock_html = """
    <html>
        <head>
            <title>Ignored Title</title>
            <meta property="og:title" content="OGP Title">
            <meta property="og:description" content="OGP Description">
            <meta property="og:image" content="https://example.com/image.png">
        </head>
    </html>
    """
    
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = mock_html
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        # Act: OGP 情報の取得
        result = await fetch_ogp(target_url)
        
        # Assert: 各フィールドが正しく抽出されていること
        assert result["title"] == "OGP Title"
        assert result["description"] == "OGP Description"
        assert result["image_url"] == "https://example.com/image.png"
        assert result["url"] == target_url


@pytest.mark.asyncio
async def test_fetch_ogp_should_fallback_to_standard_tags_when_ogp_missing():
    """
    OGP タグが存在しない場合、通常の title タグや description メタタグから情報を補完することを検証します。
    """
    # Arrange: OGP タグを含まない標準的な HTML の準備
    target_url = "https://example.com"
    mock_html = """
    <html>
        <head>
            <title>Standard Title</title>
            <meta name="description" content="Standard Description">
        </head>
    </html>
    """
    
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = mock_html
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        # Act: OGP 情報の取得
        result = await fetch_ogp(target_url)
        
        # Assert: 標準タグから情報が取得され、画像が None であること
        assert result["title"] == "Standard Title"
        assert result["description"] == "Standard Description"
        assert result["image_url"] is None


@pytest.mark.asyncio
async def test_fetch_image_should_return_bytes_and_mime_type():
    """
    指定された URL から画像データと MIME タイプを正常に取得できることを検証します。
    """
    # Arrange: 画像データとレスポンスの準備
    target_url = "https://example.com/image.png"
    expected_content = b"fake-image-data"
    expected_mime = "image/png"
    
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.content = expected_content
        mock_resp.headers = {"Content-Type": expected_mime}
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        # Act: 画像の取得
        actual_content, actual_mime = await fetch_image(target_url)
        
        # Assert: 取得したデータが一致すること
        assert actual_content == expected_content
        assert actual_mime == expected_mime
