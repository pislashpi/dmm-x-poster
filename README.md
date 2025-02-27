# DMM X自動投稿システム

DMM APIを利用してDVDの商品情報を取得し、X(Twitter)に自動投稿するシステム

## 機能概要

- DMM APIから商品情報を取得し、データベースに保存
- 投稿用の画像を選択・管理
- X(Twitter)への自動投稿スケジューリング
- 投稿ステータスの管理とモニタリング

## 技術スタック

- Python 3.9+
- Flask: Webフレームワーク
- SQLAlchemy: ORMデータベース
- Tweepy: X(Twitter) API連携
- APScheduler: タスクスケジューリング
- Bootstrap 5: フロントエンドデザイン

## 必要条件

- Python 3.9以上
- Rye (Pythonプロジェクト管理ツール)
- DMM API ID/アフィリエイトID
- X(Twitter) APIキーとアクセストークン
- Bitly APIキー (オプション)

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
2. 取得件数を指定して実行します

### 画像の選択

1. 商品一覧から対象商品を選択します
2. 商品詳細ページで投稿に使用する画像を最大4枚まで選択します
3. ドラッグ＆ドロップで画像の順序を調整できます

### 投稿スケジュール

1. 画像を選択した商品ページで「投稿作成」ボタンをクリックします
2. 自動的に最適な投稿時間がスケジュールされます
3. 投稿管理ページでスケジュールされた投稿を確認できます

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

## ライセンス

MIT License

## 作者

Your Name <your.email@example.com>