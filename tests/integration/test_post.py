from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

from app.services.base import PostResult


@pytest.fixture
def mock_accounts():
    """
    テスト用のSNSアカウント情報のモックデータを提供します。
    """
    return {
        "twitter": [
            {
                "id": "tw123",
                "username": "twuser",
                "name": "Twitter User",
                "token": {"oauth_token": "t", "oauth_token_secret": "s"},
            }
        ],
        "misskey": [
            {"id": "mk123", "username": "mkuser", "name": "Misskey User", "instance": "misskey.io", "token": "mktok"}
        ],
    }


def test_create_post_should_success_when_valid_input(client, mock_accounts):
    """
    有効な入力（テキスト、選択されたアカウント）が与えられたとき、
    各サービスへの投稿処理が正常に呼び出され、成功メッセージが表示されることを検証します。
    """
    # Arrange: セッションと各サービスの投稿メソッドをモック
    with patch("starlette.requests.Request.session", new_callable=PropertyMock) as mock_session:
        mock_session.return_value = {"accounts": mock_accounts}

        with (
            patch("app.services.twitter.TwitterService.post", new_callable=AsyncMock) as mock_tw_post,
            patch("app.services.misskey.MisskeyService.post", new_callable=AsyncMock) as mock_mk_post,
        ):
            mock_tw_post.return_value = PostResult(success=True, provider="twitter", post_id="123")
            mock_mk_post.return_value = PostResult(success=True, provider="misskey", post_id="456")

            # Act: 投稿リクエストの送信
            response = client.post(
                "/post/",
                data={
                    "text": "Hello World",
                    "selected_accounts": ["twitter:tw123", "misskey:mk123@misskey.io"],
                    "misskey_visibility": "public",
                },
                follow_redirects=True,
            )

            # Assert: 期待される結果の検証
            assert response.status_code == 200
            assert "2 個のアカウントに投稿しました" in response.text
            assert mock_tw_post.called
            assert mock_mk_post.called


def test_create_post_validation_error_too_many_images(client, mock_accounts):
    """画像が4枚を超えた場合にバリデーションエラーが発生することを検証"""
    with patch("starlette.requests.Request.session", new_callable=PropertyMock) as mock_session:
        mock_session.return_value = {"accounts": mock_accounts}

        # 5つの空の画像を作成
        files = [("images", (f"img{i}.jpg", b"content", "image/jpeg")) for i in range(5)]

        response = client.post(
            "/post/",
            data={
                "text": "Too many images",
                "selected_accounts": ["twitter:tw123"],
                "misskey_visibility": "public",
            },
            files=files,
        )

        assert response.status_code == 200
        assert "最大4枚まで画像を添付できます" in response.text


def test_create_post_validation_error_text_limit(client, mock_accounts):
    """文字数制限を超えた場合にバリデーションエラーが発生することを検証"""
    with patch("starlette.requests.Request.session", new_callable=PropertyMock) as mock_session:
        mock_session.return_value = {"accounts": mock_accounts}

        # Twitterの140文字制限を超える長い文字列
        long_text = "a" * 150

        response = client.post(
            "/post/",
            data={
                "text": long_text,
                "selected_accounts": ["twitter:tw123"],
                "misskey_visibility": "public",
            },
        )

        assert response.status_code == 200
        assert "Twitter の文字数制限を超えています" in response.text


def test_create_post_should_fail_when_text_exceeds_twitter_limit(client, mock_accounts):
    """
    入力されたテキストがTwitterの文字数制限を超えている場合、
    投稿が実行されず、適切なエラーメッセージが表示されることを検証します。
    """
    # Arrange: セッションのモックと制限超過テキストの準備
    with patch("starlette.requests.Request.session", new_callable=PropertyMock) as mock_session:
        mock_session.return_value = {"accounts": mock_accounts}
        # 日本語として判定されるため140文字が上限。141文字でエラーを誘発。
        long_text = "a" * 141

        # Act: 投稿リクエストの送信
        response = client.post(
            "/post/", data={"text": long_text, "selected_accounts": ["twitter:tw123"], "misskey_visibility": "public"}
        )

        # Assert: エラーメッセージの検証
        assert response.status_code == 200
        assert "Twitter の文字数制限を超えています" in response.text


def test_create_post_partial_failure(client, mock_accounts):
    """一部のSNS投稿が失敗した場合に警告メッセージが表示されることを検証"""
    with patch("starlette.requests.Request.session", new_callable=PropertyMock) as mock_session:
        mock_session.return_value = {"accounts": mock_accounts}

        with (
            patch("app.services.twitter.TwitterService.post", new_callable=AsyncMock) as mock_tw_post,
            patch("app.services.misskey.MisskeyService.post", new_callable=AsyncMock) as mock_mk_post,
        ):
            # Twitterは成功、Misskeyは失敗
            mock_tw_post.return_value = PostResult(success=True, provider="twitter", post_id="123")
            mock_mk_post.return_value = PostResult(success=False, provider="misskey", error="Failed to connect")

            response = client.post(
                "/post/",
                data={
                    "text": "Hello partial failure",
                    "selected_accounts": ["twitter:tw123", "misskey:mk123@misskey.io"],
                    "misskey_visibility": "public",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert "1 個のアカウントに投稿しました" in response.text
            assert "失敗: misskey: Failed to connect" in response.text
