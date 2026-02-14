from fastapi.testclient import TestClient


def test_should_display_bluesky_login_page_correctly(client: TestClient):
    """
    Blueskyのログイン連携ページが正しく表示されることを検証します。
    """
    # Arrange: URLの準備
    url = "/auth/login/bluesky"

    # Act: 画面へのアクセス
    response = client.get(url)

    # Assert: レスポンス内容の検証
    assert response.status_code == 200
    assert "Connect Bluesky" in response.text


def test_should_display_misskey_login_page_correctly(client: TestClient):
    """
    Misskeyのログイン連携ページが正しく表示されることを検証します。
    """
    # Arrange: URLの準備
    url = "/auth/login/misskey"

    # Act: 画面へのアクセス
    response = client.get(url)

    # Assert: レスポンス内容の検証
    assert response.status_code == 200
    assert "Connect Misskey" in response.text


def test_should_return_404_for_unsupported_provider(client: TestClient):
    """
    非対応のプロバイダー（例: unknown）を指定した場合に、404エラーを返すことを検証します。
    """
    # Arrange: 未知のプロバイダー用URL
    url = "/auth/login/unknown"

    # Act: アクセス
    response = client.get(url)

    # Assert: 404ステータスの検証
    assert response.status_code == 404
