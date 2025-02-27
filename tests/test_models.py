"""
データベースモデルのテスト
"""
import json
import pytest
from datetime import datetime

from dmm_x_poster.db.models import Product, Image, Post, PostImage


class TestProductModel:
    """商品モデルのテストクラス"""
    
    def test_create_product(self, db):
        """商品の作成と基本属性のテスト"""
        product = Product(
            dmm_product_id="test-001",
            title="テスト商品",
            url="https://example.com/product/test-001",
            fetched_at=datetime.utcnow()
        )
        db.session.add(product)
        db.session.commit()
        
        # IDが自動生成されるか
        assert product.id is not None
        
        # 取得できるか
        saved_product = Product.query.filter_by(dmm_product_id="test-001").first()
        assert saved_product is not None
        assert saved_product.title == "テスト商品"
        assert saved_product.posted is False  # デフォルト値
    
    def test_get_actresses_list(self, db):
        """get_actresses_listメソッドのテスト"""
        # JSON文字列として保存
        actresses = ["女優A", "女優B", "女優C"]
        product = Product(
            dmm_product_id="test-002",
            title="テスト商品",
            actresses=json.dumps(actresses, ensure_ascii=False),
            url="https://example.com/product/test-002",
            fetched_at=datetime.utcnow()
        )
        db.session.add(product)
        db.session.commit()
        
        # リストとして取得できるか
        retrieved_actresses = product.get_actresses_list()
        assert isinstance(retrieved_actresses, list)
        assert len(retrieved_actresses) == 3
        assert "女優A" in retrieved_actresses
        assert "女優B" in retrieved_actresses
        assert "女優C" in retrieved_actresses
    
    def test_get_actresses_list_empty(self, db):
        """get_actresses_listメソッドが空の場合のテスト"""
        product = Product(
            dmm_product_id="test-003",
            title="テスト商品",
            actresses=None,  # 空
            url="https://example.com/product/test-003",
            fetched_at=datetime.utcnow()
        )
        db.session.add(product)
        db.session.commit()
        
        # 空リストが返るか
        retrieved_actresses = product.get_actresses_list()
        assert isinstance(retrieved_actresses, list)
        assert len(retrieved_actresses) == 0
    
    def test_get_genres_list(self, db):
        """get_genres_listメソッドのテスト"""
        # JSON文字列として保存
        genres = ["ジャンルA", "ジャンルB"]
        product = Product(
            dmm_product_id="test-004",
            title="テスト商品",
            genres=json.dumps(genres, ensure_ascii=False),
            url="https://example.com/product/test-004",
            fetched_at=datetime.utcnow()
        )
        db.session.add(product)
        db.session.commit()
        
        # リストとして取得できるか
        retrieved_genres = product.get_genres_list()
        assert isinstance(retrieved_genres, list)
        assert len(retrieved_genres) == 2
        assert "ジャンルA" in retrieved_genres
        assert "ジャンルB" in retrieved_genres
    
    def test_get_selected_images(self, db):
        """get_selected_imagesメソッドのテスト"""
        # 商品を作成
        product = Product(
            dmm_product_id="test-005",
            title="テスト商品",
            url="https://example.com/product/test-005",
            fetched_at=datetime.utcnow()
        )
        db.session.add(product)
        db.session.flush()  # IDを生成
        
        # 5枚の画像を作成（3枚は選択済み）
        images = []
        for i in range(5):
            image = Image(
                product_id=product.id,
                image_url=f"https://example.com/images/test-005-{i}.jpg",
                selected=(i < 3),  # 最初の3枚は選択済み
                selection_order=(i + 1) if i < 3 else None  # 選択済みの場合は順序付け
            )
            db.session.add(image)
            images.append(image)
        
        db.session.commit()
        
        # 選択された画像を取得
        selected_images = product.get_selected_images()
        assert len(selected_images) == 3
        
        # 順序通りに取得されるか
        assert selected_images[0].selection_order == 1
        assert selected_images[1].selection_order == 2
        assert selected_images[2].selection_order == 3
        
        # 制限付きで取得
        limited_images = product.get_selected_images(limit=2)
        assert len(limited_images) == 2


class TestImageModel:
    """画像モデルのテストクラス"""
    
    def test_create_image(self, db, sample_product):
        """画像の作成と基本属性のテスト"""
        image = Image(
            product_id=sample_product.id,
            image_url="https://example.com/images/test-image.jpg",
            created_at=datetime.utcnow()
        )
        db.session.add(image)
        db.session.commit()
        
        # IDが自動生成されるか
        assert image.id is not None
        
        # 取得できるか
        saved_image = Image.query.filter_by(product_id=sample_product.id).first()
        assert saved_image is not None
        assert saved_image.image_url == "https://example.com/images/test-image.jpg"
        assert saved_image.downloaded is False  # デフォルト値
        assert saved_image.selected is False  # デフォルト値


class TestPostModel:
    """投稿モデルのテストクラス"""
    
    def test_create_post(self, db, sample_product):
        """投稿の作成と基本属性のテスト"""
        now = datetime.utcnow()
        post = Post(
            product_id=sample_product.id,
            post_text="テスト投稿です #テスト",
            status="scheduled",
            scheduled_at=now
        )
        db.session.add(post)
        db.session.commit()
        
        # IDが自動生成されるか
        assert post.id is not None
        
        # 取得できるか
        saved_post = Post.query.filter_by(product_id=sample_product.id).first()
        assert saved_post is not None
        assert saved_post.post_text == "テスト投稿です #テスト"
        assert saved_post.status == "scheduled"
        assert saved_post.scheduled_at.replace(microsecond=0) == now.replace(microsecond=0)
    
    def test_get_images(self, db, sample_product, sample_images):
        """get_imagesメソッドのテスト"""
        # 投稿を作成
        post = Post(
            product_id=sample_product.id,
            post_text="テスト投稿です",
            status="scheduled",
            scheduled_at=datetime.utcnow()
        )
        db.session.add(post)
        db.session.flush()  # IDを生成
        
        # 投稿に画像を関連付け
        for i, image in enumerate(sample_images[:3]):
            post_image = PostImage(
                post_id=post.id,
                image_id=image.id,
                display_order=i + 1
            )
            db.session.add(post_image)
        
        db.session.commit()
        
        # 関連画像を取得
        post_images = post.get_images()
        assert len(post_images) == 3
        
        # 順序通りに取得されるか
        assert post_images[0].id == sample_images[0].id
        assert post_images[1].id == sample_images[1].id
        assert post_images[2].id == sample_images[2].id


class TestPostImageModel:
    """投稿画像関連モデルのテストクラス"""
    
    def test_create_post_image(self, db, sample_product, sample_images):
        """投稿画像関連の作成と基本属性のテスト"""
        # 投稿を作成
        post = Post(
            product_id=sample_product.id,
            post_text="テスト投稿です",
            status="scheduled",
            scheduled_at=datetime.utcnow()
        )
        db.session.add(post)
        db.session.flush()  # IDを生成
        
        # 投稿画像関連を作成
        post_image = PostImage(
            post_id=post.id,
            image_id=sample_images[0].id,
            display_order=1
        )
        db.session.add(post_image)
        db.session.commit()
        
        # IDが自動生成されるか
        assert post_image.id is not None
        
        # 取得できるか
        saved_post_image = PostImage.query.filter_by(post_id=post.id).first()
        assert saved_post_image is not None
        assert saved_post_image.image_id == sample_images[0].id
        assert saved_post_image.display_order == 1
        
        # リレーションシップが機能するか
        assert saved_post_image.post.id == post.id
        assert saved_post_image.image.id == sample_images[0].id