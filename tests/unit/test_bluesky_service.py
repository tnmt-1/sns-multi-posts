from app.services.bluesky_service import BlueskyService


def test_bluesky_service_text_length_calculation():
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


def test_bluesky_service_character_limit_is_correct():
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
