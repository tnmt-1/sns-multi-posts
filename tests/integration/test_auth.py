from unittest.mock import AsyncMock, MagicMock, patch

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


def test_twitter_callback_success(client: TestClient):
    """Twitterの認証コールバックが成功し、アカウントが保存されることを検証"""
    with (
        patch("app.services.auth_service.oauth.twitter.authorize_access_token", new_callable=AsyncMock) as mock_token,
        patch("app.services.auth_service.oauth.twitter.get", new_callable=AsyncMock) as mock_get,
    ):
        mock_token.return_value = {"oauth_token": "token", "oauth_token_secret": "secret"}
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id_str": "tw123", "screen_name": "twuser", "name": "Twitter User"},
        )

        response = client.get("/auth/callback/twitter", follow_redirects=True)

        assert response.status_code == 200
        # セッションに保存されているか、トップ画面の表示で間接的に確認
        assert "Twitter User" in response.text


def test_misskey_callback_failure_no_pending(client: TestClient):
    """保留中のセッションがない場合にホームにリダイレクトされることを検証（簡略化されたエラーハンドリング）"""
    response = client.get("/auth/callback/misskey", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
