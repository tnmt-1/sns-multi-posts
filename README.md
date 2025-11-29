# SNS Multi-Post

複数のSNS（X/Twitter、Bluesky、Misskey）に同時投稿できるWebアプリケーションです。各SNSに個別にログインして投稿する手間を省きます。

### 主な機能

- 複数SNS対応: X (Twitter)、Bluesky、Misskeyに対応
- 画像投稿: 最大4枚の画像を添付可能（各SNSの仕様に準拠）
- 一括投稿: 選択したアカウントに同時投稿
- 文字数制限チェック: 選択したSNSの最小文字数制限に自動対応
- Misskey公開範囲設定: Public、Home、Followers、Directから選択可能
- PWA対応: スマートフォンにインストールして使用可能

### 技術スタック

- バックエンド: FastAPI (Python)
- フロントエンド: HTML + Tailwind CSS + Vanilla JavaScript
- 認証: OAuth 1.0a (Twitter)、MiAuth (Misskey)、atproto (Bluesky)
- デプロイ: Vercel対応

## インストール方法

### 必要要件

- Python 3.12以上
- [uv](https://github.com/astral-sh/uv)

### 1. リポジトリのクローン

```bash
git clone https://github.com/yourusername/sns-multi-posts.git
cd sns-multi-posts
```

### 2. 依存関係のインストール

```bash
uv sync --dev
```

### 3. 環境変数の設定

このプロジェクトはVercelでの実行を前提としており、環境変数もVercelで管理します。

#### Vercel CLIのインストール

```bash
npm install -g vercel
```

#### Vercelプロジェクトのセットアップ

```bash
# Vercelにログイン
vercel login

# プロジェクトをリンク
vercel link
```

#### 環境変数の設定

Vercelダッシュボードまたはコマンドラインで環境変数を設定します。

```bash
# コマンドラインで設定する場合
vercel env add SECRET_KEY
vercel env add TWITTER_CLIENT_ID
vercel env add TWITTER_CLIENT_SECRET
```

または、[Vercelダッシュボード](https://vercel.com/dashboard)で

1. プロジェクトを選択
2. Settings → Environment Variables
3. 以下の環境変数を追加：
   - `SECRET_KEY`: セッション暗号化用のランダムな文字列
   - `TWITTER_CLIENT_ID`: Twitter API Key (Consumer Key)
   - `TWITTER_CLIENT_SECRET`: Twitter API Key Secret (Consumer Secret)

#### Twitter API認証情報の取得方法

> [!WARNING]
> OAuth 1.0aを使用するため、Consumer Keys（API Key / API Key Secret）が必要です。OAuth 2.0のClient IDとは異なります。

1. [Twitter Developer Portal](https://developer.twitter.com/en/portal/dashboard)にアクセス
2. アプリを作成または選択
3. Settings → User authentication settings → Edit
4. App permissionsを「Read and Write」に設定
5. Keys and tokensタブの「Consumer Keys」セクションから以下を取得
   - API Key (Consumer Key) → `TWITTER_CLIENT_ID`
   - API Key Secret (Consumer Secret) → `TWITTER_CLIENT_SECRET`

### 4. アプリケーションの起動

#### 開発環境

```bash
vercel dev
```

ブラウザで `http://localhost:3000` にアクセスしてください。

#### 本番環境へのデプロイ

```bash
# プレビューデプロイ
vercel

# 本番デプロイ
vercel --prod
```

## 使い方

### 1. アカウント連携

1. トップページの右側「Accounts」セクションから各SNSの「Connect」ボタンをクリック
2. 各SNSの認証画面で許可を与える
3. 連携が完了すると、アカウント一覧に表示されます

### 2. 投稿する

1. 投稿先・Misskey設定セクションを開く
2. 投稿したいアカウントにチェックを入れる
3. Misskeyを選択した場合は、公開範囲を選択
4. テキストエリアに投稿内容を入力
5. （オプション）画像をアップロード（最大4枚）
6. 「Post Now」ボタンをクリック

### 3. 画像付き投稿

- 画像アップロードエリアをクリックまたはドラッグ&ドロップで画像を選択
- 対応形式: JPEG、PNG、GIF
- 最大4枚まで添付可能
- プレビューが表示されます

### 4. ログアウト

- 「Disconnect All」ボタンをクリックすると、すべてのアカウント連携が解除されます
