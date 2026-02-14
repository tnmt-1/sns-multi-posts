from app.services.twitter import TwitterService


def test_twitter_service_text_length_with_url():
    """
    Twitterサービスにおいて、URLを含むテキストの長さが正しく計算されることを検証します。
    Twitterの仕様に従い、URLは一律23文字としてカウントされる必要があります。
    """
    # Arrange: テキストとTwitterサービスの準備
    service = TwitterService()
    text_with_url = "Check this out: https://example.com"
    # "Check this out: " (16文字) + URL (23文字) = 39文字
    expected_length = 39

    # Act: 文字数の計算
    actual_length = service.get_text_length(text_with_url)

    # Assert: 計算結果の検証
    assert actual_length == expected_length


def test_twitter_service_character_limit_is_correct():
    """
    Twitterサービスにおいて、日本語向けの文字数制限（140文字）が正しく取得できることを検証します。
    """
    # Arrange: Twitterサービスの準備
    service = TwitterService()
    expected_limit = 140

    # Act: 制限値の取得
    actual_limit = service.get_character_limit()

    # Assert: 制限値の検証
    assert actual_limit == expected_limit
