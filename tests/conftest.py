"""
テスト用の共通フィクスチャと設定
"""
import os
import sys
import tempfile
import pytest
from flask import Flask
from flask.testing import FlaskClient

# プロジェクトのsrcディレクトリをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from dmm_x_poster.app import create_app
from dmm_x_poster.db.models import db as _db


class TestConfig:
    """テスト用の設定クラス"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    
    # テスト用モックAPI設定
    DMM_API_ID = "test_api_id"
    DMM_AFFILIATE_ID = "test_affiliate_id"
    TWITTER_API_KEY = "test_twitter_key"
    TWITTER_API_SECRET = "test_twitter_secret" 
    TWITTER_ACCESS_TOKEN = "test_twitter_token"
    TWITTER_ACCESS_SECRET = "test_twitter_token_secret"
    BITLY_API_KEY = "test_bitly_key"
    
    # 画像フォルダをテンポラリディレクトリに設定
    IMAGES_FOLDER = os.path.join(tempfile.gettempdir(), "test_images")


@pytest.fixture(scope="session")
def app() -> Flask:
    """テスト用Flaskアプリケーションを作成"""
    # テスト用の設定でアプリケーションを作成
    _app = create_app(TestConfig)
    
    # 画像保存用のテンポラリディレクトリを作成
    os.makedirs(TestConfig.IMAGES_FOLDER, exist_ok=True)
    
    # アプリケーションコンテキストをセットアップ
    with _app.app_context():
        # テスト用データベースの初期化
        _db.create_all()
        
        yield _app  # テスト実行
        
        # テスト後のクリーンアップ
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope="function")
def db(app: Flask):
    """テスト用データベースへのアクセスを提供"""
    with app.app_context():
        _db.create_all()
        
        yield _db
        
        # 各テスト後にデータをクリア
        _db.session.rollback()
        _db.session.close()
        _db.drop_all()
        _db.create_all()


@pytest.fixture(scope="function")
def client(app: Flask) -> FlaskClient:
    """テスト用HTTPクライアント"""
    return app.test_client()


@pytest.fixture(scope="function")
def runner(app: Flask):
    """テスト用CLIランナー"""
    return app.test_cli_runner()


@pytest.fixture(scope="function")
def sample_product(db):
    """テスト用サンプル商品データ"""
    from dmm_x_poster.db.models import Product
    import json
    import datetime
    
    product = Product(
        dmm_product_id="test-product-001",
        title="サンプル商品タイトル",
        actresses=json.dumps(["女優A", "女優B"], ensure_ascii=False),
        url="https://example.com/product/test-product-001",
        package_image_url="https://example.com/images/test-product-001.jpg",
        maker="サンプルメーカー",
        genres=json.dumps(["ジャンルA", "ジャンルB"], ensure_ascii=False),
        release_date=datetime.date(2023, 1, 15),
        fetched_at=datetime.datetime.utcnow(),
        posted=False
    )
    
    db.session.add(product)
    db.session.commit()
    
    return product


@pytest.fixture(scope="function")
def sample_images(db, sample_product):
    """テスト用サンプル画像データ"""
    from dmm_x_poster.db.models import Image
    import datetime
    
    images = []
    for i in range(5):
        image = Image(
            product_id=sample_product.id,
            image_url=f"https://example.com/images/test-product-001-{i}.jpg",
            downloaded=False,
            selected=(i < 4),  # 最初の4枚は選択済み
            selection_order=(i + 1) if i < 4 else None,  # 選択済みの場合は順序付け
            created_at=datetime.datetime.utcnow()
        )
        db.session.add(image)
        images.append(image)
    
    db.session.commit()
    
    return images