from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.bluesky_service import BlueskyPostContent, BlueskyService


def test_bluesky_service_text_length_calculation_should_return_character_count():
    """
    Blueskyサービスにおいて、テキストの長さ（文字数）が正しく計算されることを検証します。
    """
    # Arrange: テキストとサービスの準備
    service = BlueskyService()
    text = "Hello 日本語"
    expected_length = 9

    # Act: 文字数の計算
    actual_length = service.get_text_length(text)

    # Assert: 計算結果の検証
    assert actual_length == expected_length


def test_bluesky_service_character_limit_should_be_300():
    """
    Blueskyサービスにおいて、既定の文字数制限（300文字）が正しく取得できることを検証します。
    """
    # Arrange: サービスの準備
    service = BlueskyService()
    expected_limit = 300

    # Act: 制限値の取得
    actual_limit = service.get_character_limit()

    # Assert: 制限値の検証
    assert actual_limit == expected_limit


def test_bluesky_post_content_to_text_builder_should_extract_links():
    """
    BlueskyPostContent ドメインモデルが、テキスト内のURLを正しく検出し
    リンクファセットに変換することを検証します。
    """
    # Arrange: 複数のリンクを含むテキストの準備
    text = "Check: https://example.com and http://test.org"
    content = BlueskyPostContent(text)

    # Act: TextBuilder への変換
    tb = content.to_text_builder()

    # Assert: テキストが一致し、2つのリンクファセットが生成されていること
    assert tb.build_text() == text
    facets = tb.build_facets()
    assert len(facets) == 2
    assert facets[0].features[0].uri == "https://example.com"
    assert facets[1].features[0].uri == "http://test.org"


@pytest.mark.asyncio
async def test_bluesky_service_post_should_embed_ogp_when_url_present_and_no_images():
    """
    画像が添付されておらず、テキストに URL が含まれる場合、
    自動的に OGP 情報が取得され、外部リンク embed として構築されることを検証します。
    """
    # Arrange: 投稿データ、モック OGP データの準備
    service = BlueskyService()
    account = MagicMock()
    account.handle = "test.bsky.social"
    account.password = "password"
    text = "Check this out! https://example.com"

    mock_ogp = {
        "title": "Example Title",
        "description": "Example Description",
        "image_url": "https://example.com/image.png",
        "url": "https://example.com",
    }
    mock_image_data = (b"fake-image-data", "image/png")

    with (
        patch("app.services.bluesky_service.Client") as mock_client_class,
        patch("app.services.bluesky_service.fetch_ogp", new_callable=AsyncMock) as mock_fetch_ogp,
        patch("app.services.bluesky_service.fetch_image", new_callable=AsyncMock) as mock_fetch_image,
        patch("app.services.bluesky_service.models") as mock_models,
    ):
        mock_client = mock_client_class.return_value
        mock_fetch_ogp.return_value = mock_ogp
        mock_fetch_image.return_value = mock_image_data
        
        # サムネイル画像のアップロード結果をモック
        mock_blob_resp = MagicMock()
        mock_blob_resp.blob = "mock-thumbnail-blob"
        mock_client.upload_blob.return_value = mock_blob_resp

        # Act: 投稿処理の実行
        await service._post_internal(account, text)

        # Assert: OGP 情報と画像の取得が呼び出されていること
        mock_fetch_ogp.assert_called_once_with("https://example.com")
        mock_fetch_image.assert_called_once_with("https://example.com/image.png")
        
        # 外部リンク embed (External) が正しいパラメータで構築されていること
        mock_models.AppBskyEmbedExternal.External.assert_called_once_with(
            title="Example Title",
            description="Example Description",
            uri="https://example.com",
            thumb="mock-thumbnail-blob",
        )
        # 構築された External が Main embed に設定されていること
        mock_models.AppBskyEmbedExternal.Main.assert_called_once_with(
            external=mock_models.AppBskyEmbedExternal.External.return_value
        )
