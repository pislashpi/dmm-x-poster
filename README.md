# DMM X自動投稿システム

DMM APIを利用してDVDの商品情報を取得し、X(Twitter)に自動投稿するシステム

## 機能概要

- DMM APIから商品情報を取得し、データベースに保存（発売済み/予約商品の切り替え可能）
- ジャンル、女優IDによる絞り込み検索
- 投稿用の画像・動画を選択・管理
- X(Twitter)への投稿（即時投稿と予約投稿）
- 投稿ステータスの管理とモニタリング

## 技術スタック

- Python 3.8+
- Flask: Webフレームワーク
- SQLAlchemy: ORMデータベース
- Tweepy: X(Twitter) API連携
- APScheduler: タスクスケジューリング
- Bootstrap 5: フロントエンドデザイン
- BeautifulSoup4 & lxml: Webスクレイピング

## 必要条件

- Python 3.8以上
- Rye (Pythonプロジェクト管理ツール)
- DMM API ID/アフィリエイトID
- X(Twitter) APIキーとアクセストークン

## セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/yourusername/dmm-x-poster.git
cd dmm-x-poster
```

### 2. 依存関係のインストール

```bash
# Ryeがインストールされていることを前提とします
rye sync
```

### 3. 環境変数の設定

`.env.sample`をコピーして`.env`ファイルを作成し、必要な情報を入力します。

```bash
cp .env.sample .env
# エディタで.envを編集
```

必須の設定項目:
- `SECRET_KEY`: アプリケーションの秘密鍵
- `DMM_API_ID`: DMM API ID
- `DMM_AFFILIATE_ID`: DMM アフィリエイトID
- `TWITTER_API_KEY`: X(Twitter) API Key
- `TWITTER_API_SECRET`: X(Twitter) API Secret
- `TWITTER_ACCESS_TOKEN`: X(Twitter) Access Token
- `TWITTER_ACCESS_SECRET`: X(Twitter) Access Token Secret

### 4. データベースの初期化

```bash
# Ryeシェルを起動
rye shell

# データベースを初期化
cd src
flask --app dmm_x_poster.app db init
flask --app dmm_x_poster.app db migrate -m "Initial migration"
flask --app dmm_x_poster.app db upgrade
```

## 使用方法

### 開発モードでの実行

```bash
rye shell
cd src
flask --app dmm_x_poster.app run --debug
```

ブラウザで http://localhost:5000 にアクセスしてください。

### 本番環境での実行

```bash
rye shell
cd src
gunicorn -w 4 -b 0.0.0.0:8000 "dmm_x_poster.app:create_app()"
```

## 主要機能の使い方

### 商品情報の取得

1. ホームページの「新着取得」ボタンをクリックします
2. 取得設定で以下を指定できます:
   - 取得件数
   - フロア（ビデオ/一般、素人、アニメ、同人）
   - 発売ステータス（発売済み、予約商品、すべて）
   - ジャンルID（カンマ区切りで複数指定可能）
   - 女優ID（カンマ区切りで複数指定可能）

### 商品検索

1. 商品一覧ページで以下の検索条件を指定できます:
   - キーワード検索
   - 並び替え（新着順、タイトル順、発売日順）
   - 発売ステータス（全商品、発売済み、予約商品）
   - ジャンル検索（カンマ区切りでAND検索）

### 画像の選択

1. 商品一覧から対象商品を選択します
2. 商品詳細ページで投稿に使用する画像を最大4枚まで選択できます:
   - サンプル画像
   - パッケージ画像
   - サンプル動画
3. ドラッグ＆ドロップで画像の順序を調整できます

### 投稿作成

1. 画像を選択した商品ページで「投稿作成」ボタンをクリックします
2. 投稿方法を選択できます:
   - 即時投稿: すぐにX(Twitter)に投稿
   - 予約投稿: 指定した日時に投稿（システムが自動実行）
3. 投稿管理ページで投稿ステータスを確認できます

## プロジェクト構造

### 主要ファイルの役割

- **app.py**: Flaskアプリケーションの中核、ルーティング定義
- **config.py**: アプリケーション設定、環境変数読み込み
- **db/models.py**: データベースモデル定義
- **services/dmm_api.py**: DMM APIとの連携、商品情報取得
- **services/image_downloader.py**: 画像・動画のダウンロード処理
- **services/scheduler.py**: 投稿スケジューリング管理
- **services/twitter_api.py**: X(Twitter) APIとの連携、投稿処理
- **templates/**: 画面表示用のHTMLテンプレート
  - index.html: ホーム画面
  - products.html: 商品一覧
  - product_detail.html: 商品詳細・画像選択
  - posts.html: 投稿管理
  - post_detail.html: 投稿詳細

### データ構造

- **Product**: 商品情報（タイトル、出演者、ジャンル、URL等）
- **Image**: 画像・動画情報（URL、タイプ、ダウンロード状態等）
- **Post**: 投稿情報（テキスト、状態、予定日時等）
- **PostImage**: 投稿と画像の関連付け

## 開発者向け情報

### テストの実行

```bash
rye shell
pytest
```

### コード品質チェック

```bash
rye shell
black src tests
flake8 src tests
mypy src
```

### データベースのリセット

データベース構造を変更した場合:

```bash
# app.dbを削除
rm app.db

# マイグレーションディレクトリをクリア
rm -rf src/migrations/versions/*

# データベースを再初期化
cd src
flask --app dmm_x_poster.app db init
flask --app dmm_x_poster.app db migrate -m "Initial migration"
flask --app dmm_x_poster.app db upgrade
```

## ライセンス

MIT License
