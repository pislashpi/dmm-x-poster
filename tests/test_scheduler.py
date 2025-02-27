"""
スケジューラサービスのテスト
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from dmm_x_poster.services.scheduler import SchedulerService
from dmm_x_poster.db.models import Product, Image, Post


class TestSchedulerService:
    """スケジューラサービスのテストクラス"""
    
    def test_init_app(self, app):
        """init_appメソッドが設定を正しく読み込むかテスト"""
        # 設定値を変更
        app.config['POSTS_PER_DAY'] = 5
        app.config['POST_START_HOUR'] = 10
        app.config['POST_END_HOUR'] = 23
        
        service = SchedulerService()
        service.init_app(app)
        
        assert service.posts_per_day == 5
        assert service.post_start_hour == 10
        assert service.post_end_hour == 23
    
    def test_generate_post_text(self, sample_product):
        """generate_post_textメソッドが適切なテキストを生成するかテスト"""
        # URLショートナーサービスをモック
        with patch('dmm_x_poster.services.scheduler.url_shortener_service') as mock_shortener:
            mock_shortener.shorten_url.return_value = "https://bit.ly/abc123"
            
            service = SchedulerService()
            post_text = service.generate_post_text(sample_product)
            
            # テキストに必要な情報が含まれているか
            assert f"【新着】{sample_product.title}" in post_text
            assert "出演: 女優A, 女優B" in post_text
            assert "ジャンル: ジャンルA, ジャンルB" in post_text
            assert "https://bit.ly/abc123" in post_text
    
    def test_generate_post_text_many_actresses(self, db):
        """出演者が多い場合のgenerate_post_textメソッドをテスト"""
        import json
        
        # 出演者が多い商品を作成
        many_actresses = ["女優A", "女優B", "女優C", "女優D", "女優E"]
        product = Product(
            dmm_product_id="test-many-actresses",
            title="出演者多数の商品",
            actresses=json.dumps(many_actresses, ensure_ascii=False),
            url="https://example.com/product/test-many-actresses",
            fetched_at=datetime.utcnow()
        )
        db.session.add(product)
        db.session.commit()
        
        # URLショートナーサービスをモック
        with patch('dmm_x_poster.services.scheduler.url_shortener_service') as mock_shortener:
            mock_shortener.shorten_url.return_value = "https://bit.ly/abc123"
            
            service = SchedulerService()
            post_text = service.generate_post_text(product)
            
            # 出演者は3名までと「他」が表示されるか
            assert "出演: 女優A, 女優B, 女優C他" in post_text
    
    def test_generate_post_text_without_shortener(self, sample_product):
        """URLショートナーがない場合のgenerate_post_textメソッドをテスト"""
        # URLショートナーサービスをNoneに設定
        with patch('dmm_x_poster.services.scheduler.url_shortener_service', None):
            service = SchedulerService()
            post_text = service.generate_post_text(sample_product)
            
            # 元のURLが含まれないこと（短縮URLがなければURLは含めない）
            assert sample_product.url not in post_text
    
    def test_calculate_next_post_time(self, app):
        """calculate_next_post_timeメソッドが適切な時間を計算するかテスト"""
        service = SchedulerService()
        service.init_app(app)
        
        # テスト用に時間設定
        service.post_start_hour = 9
        service.post_end_hour = 21
        service.posts_per_day = 3
        
        # 既存の投稿なしの場合（現在時刻が営業時間内）
        with patch('dmm_x_poster.services.scheduler.Post.query') as mock_query:
            mock_query.filter_by.return_value.order_by.return_value.first.return_value = None
            
            # 現在時刻を営業時間内に設定（13:00）
            now = datetime.now().replace(hour=13, minute=0, second=0, microsecond=0)
            
            with patch('dmm_x_poster.services.scheduler.datetime') as mock_datetime:
                mock_datetime.utcnow.return_value = now
                mock_datetime.now.return_value = now
                
                # 次の投稿時間を計算
                next_time = service.calculate_next_post_time()
                
                # 現在時刻から30分後であるか
                expected_time = now + timedelta(minutes=30)
                # マイクロ秒は無視して比較
                assert next_time.replace(microsecond=0) == expected_time.replace(microsecond=0)
    
    def test_calculate_next_post_time_before_hours(self, app):
        """営業時間前のcalculate_next_post_timeメソッドをテスト"""
        service = SchedulerService()
        service.init_app(app)
        
        # テスト用に時間設定
        service.post_start_hour = 9
        service.post_end_hour = 21
        
        # 既存の投稿なしの場合（現在時刻が営業時間前）
        with patch('dmm_x_poster.services.scheduler.Post.query') as mock_query:
            mock_query.filter_by.return_value.order_by.return_value.first.return_value = None
            
            # 現在時刻を営業時間前に設定（7:00）
            now = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)
            
            with patch('dmm_x_poster.services.scheduler.datetime') as mock_datetime:
                mock_datetime.utcnow.return_value = now
                mock_datetime.now.return_value = now
                
                # 次の投稿時間を計算
                next_time = service.calculate_next_post_time()
                
                # 今日の営業開始時間（9:00）であるか
                expected_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
                # マイクロ秒は無視して比較
                assert next_time.replace(microsecond=0) == expected_time.replace(microsecond=0)
    
    def test_calculate_next_post_time_after_hours(self, app):
        """営業時間後のcalculate_next_post_timeメソッドをテスト"""
        service = SchedulerService()
        service.init_app(app)
        
        # テスト用に時間設定
        service.post_start_hour = 9
        service.post_end_hour = 21
        
        # 既存の投稿なしの場合（現在時刻が営業時間後）
        with patch('dmm_x_poster.services.scheduler.Post.query') as mock_query:
            mock_query.filter_by.return_value.order_by.return_value.first.return_value = None
            
            # 現在時刻を営業時間後に設定（22:00）
            now = datetime.now().replace(hour=22, minute=0, second=0, microsecond=0)
            
            with patch('dmm_x_poster.services.scheduler.datetime') as mock_datetime:
                mock_datetime.utcnow.return_value = now
                mock_datetime.now.return_value = now
                
                # 次の投稿時間を計算
                next_time = service.calculate_next_post_time()
                
                # 翌日の営業開始時間（9:00）であるか
                expected_time = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
                # マイクロ秒は無視して比較
                assert next_time.replace(microsecond=0) == expected_time.replace(microsecond=0)
    
    def test_calculate_next_post_time_with_existing_posts(self, app, db):
        """既存の投稿がある場合のcalculate_next_post_timeメソッドをテスト"""
        # 最新の予定投稿を作成
        latest_post = Post(
            product_id=1,  # ダミーID
            status="scheduled",
            scheduled_at=datetime.utcnow().replace(hour=14, minute=0, second=0, microsecond=0)
        )
        db.session.add(latest_post)
        db.session.commit()
        
        service = SchedulerService()
        service.init_app(app)
        
        # テスト用に時間設定
        service.post_start_hour = 9
        service.post_end_hour = 21
        service.posts_per_day = 3
        
        # 営業時間内で間隔を空けた時間になるか
        next_time = service.calculate_next_post_time()
        
        # 最新の投稿から4時間後（3つの投稿で12時間を均等に分ける）
        expected_time = latest_post.scheduled_at + timedelta(hours=4)
        # 時間と分だけ比較（秒とマイクロ秒は考慮しない）
        assert next_time.hour == expected_time.hour
        assert next_time.minute == expected_time.minute
    
    def test_create_post(self, app, db, sample_product, sample_images):
        """create_postメソッドが投稿を作成するかテスト"""
        # URLショートナーサービスをモック
        with patch('dmm_x_poster.services.scheduler.url_shortener_service') as mock_shortener:
            mock_shortener.shorten_url.return_value = "https://bit.ly/abc123"
            
            # 次の投稿時間を固定
            next_time = datetime.utcnow() + timedelta(hours=2)
            
            with patch.object(SchedulerService, 'calculate_next_post_time') as mock_calc_time:
                mock_calc_time.return_value = next_time
                
                service = SchedulerService()
                service.init_app(app)
                
                # 投稿を作成
                post = service.create_post(sample_product.id)
                
                # 結果の検証
                assert post is not None
                assert post.product_id == sample_product.id
                assert post.status == "scheduled"
                assert post.scheduled_at == next_time
                assert "https://bit.ly/abc123" in post.post_text
                
                # 投稿画像関連の検証
                post_images = post.post_images.all()
                assert len(post_images) == 4  # 選択済みの4枚
    
    def test_create_post_no_images(self, app, db, sample_product):
        """選択された画像がない場合のcreate_postメソッドをテスト"""
        # 全ての画像を未選択に設定
        Image.query.filter_by(product_id=sample_product.id).update({
            'selected': False,
            'selection_order': None
        })
        db.session.commit()
        
        service = SchedulerService()
        service.init_app(app)
        
        # 投稿を作成
        post = service.create_post(sample_product.id)
        
        # 画像がないので投稿は作成されないはず
        assert post is None
    
    def test_schedule_unposted_products(self, app, db, sample_product, sample_images):
        """schedule_unposted_productsメソッドが未投稿商品をスケジュールするかテスト"""
        # create_postメソッドをモック
        with patch.object(SchedulerService, 'create_post') as mock_create_post:
            # 投稿作成成功を模擬
            mock_post = MagicMock()
            mock_post.id = 1
            mock_create_post.return_value = mock_post
            
            service = SchedulerService()
            service.init_app(app)
            
            # 未投稿商品をスケジュール
            count = service.schedule_unposted_products(limit=1)
            
            # 1件スケジュールされたか
            assert count == 1
            mock_create_post.assert_called_once_with(sample_product.id)
            
            # 商品が投稿済みとしてマークされたか
            db.session.refresh(sample_product)
            assert sample_product.posted is True
    
    def test_schedule_unposted_products_no_products(self, app, db):
        """未投稿商品がない場合のschedule_unposted_productsメソッドをテスト"""
        # すべての商品を投稿済みに設定
        Product.query.update({'posted': True})
        db.session.commit()
        
        # create_postメソッドをモック
        with patch.object(SchedulerService, 'create_post') as mock_create_post:
            service = SchedulerService()
            service.init_app(app)
            
            # 未投稿商品をスケジュール
            count = service.schedule_unposted_products()
            
            # スケジュールされなかったか
            assert count == 0
            mock_create_post.assert_not_called()
    
    def test_process_scheduled_posts(self, app):
        """process_scheduled_postsメソッドがTwitter APIを呼び出すかテスト"""
        with patch('dmm_x_poster.services.scheduler.twitter_api_service') as mock_twitter:
            # 認証済み状態を模擬
            mock_twitter.is_authenticated.return_value = True
            mock_twitter.process_scheduled_posts.return_value = 3
            
            service = SchedulerService()
            
            # 予定投稿を処理
            count = service.process_scheduled_posts()
            
            # Twitterサービスが呼び出されたか
            assert count == 3
            mock_twitter.is_authenticated.assert_called_once()
            mock_twitter.process_scheduled_posts.assert_called_once()
    
    def test_process_scheduled_posts_not_authenticated(self, app):
        """未認証状態でのprocess_scheduled_postsメソッドをテスト"""
        with patch('dmm_x_poster.services.scheduler.twitter_api_service') as mock_twitter:
            # 未認証状態を模擬
            mock_twitter.is_authenticated.return_value = False
            
            service = SchedulerService()
            
            # 予定投稿を処理
            count = service.process_scheduled_posts()
            
            # 処理されなかったか
            assert count == 0
            mock_twitter.is_authenticated.assert_called_once()
            mock_twitter.process_scheduled_posts.assert_not_called()