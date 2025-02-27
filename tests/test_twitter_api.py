"""
Twitter APIサービスのテスト
"""
import os
import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import MagicMock, patch

from dmm_x_poster.services.twitter_api import TwitterAPIService
from dmm_x_poster.db.models import db, Post, PostImage


class TestTwitterAPIService:
    """Twitter APIサービスのテストクラス"""
    
    def test_init_app(self, app):
        """init_appメソッドが設定を正しく読み込むかテスト"""
        with patch('dmm_x_poster.services.twitter_api.tweepy.OAuth1UserHandler') as mock_handler:
            with patch('dmm_x_poster.services.twitter_api.tweepy.API') as mock_api:
                with patch('dmm_x_poster.services.twitter_api.tweepy.Client') as mock_client:
                    # モックの設定
                    mock_api_instance = MagicMock()
                    mock_api_instance.verify_credentials.return_value = True
                    mock_api.return_value = mock_api_instance
                    
                    # サービスの初期化
                    service = TwitterAPIService()
                    service.init_app(app)
                    
                    # 検証
                    assert service.api is not None
                    assert service.client is not None
                    mock_handler.assert_called_once_with(
                        app.config.get('TWITTER_API_KEY'),
                        app.config.get('TWITTER_API_SECRET'),
                        app.config.get('TWITTER_ACCESS_TOKEN'),
                        app.config.get('TWITTER_ACCESS_SECRET')
                    )
                    mock_api_instance.verify_credentials.assert_called_once()
    
    def test_is_authenticated(self):
        """is_authenticatedメソッドが認証状態を正しく判定するかテスト"""
        service = TwitterAPIService()
        
        # 未認証の場合
        service.api = None
        service.client = None
        assert not service.is_authenticated()
        
        # 認証済みの場合
        service.api = MagicMock()
        service.client = MagicMock()
        assert service.is_authenticated()
    
    @patch('os.path.exists')
    def test_post_with_media(self, mock_exists, app, db, sample_product, sample_images):
        """post_with_mediaメソッドが正しく投稿するかテスト"""
        # 投稿データの準備
        post = Post(
            product_id=sample_product.id,
            post_text="テスト投稿です #テスト",
            status="scheduled",
            scheduled_at=datetime.now(UTC)
        )
        db.session.add(post)
        db.session.flush()
        
        # サンプル画像にlocal_pathを設定
        for image in sample_images:
            image.local_path = f"/tmp/test_image_{image.id}.jpg"
            db.session.add(image)
        
        # 投稿画像の関連付け
        for i, image in enumerate(sample_images[:2]):
            post_image = PostImage(
                post_id=post.id,
                image_id=image.id,
                display_order=i + 1
            )
            db.session.add(post_image)
        
        db.session.commit()
        
        # ファイルパスが存在するようにモック
        mock_exists.return_value = True
        
        # Twitter APIモックの設定
        with patch.object(TwitterAPIService, 'is_authenticated') as mock_auth:
            mock_auth.return_value = True
            
            service = TwitterAPIService()
            service.api = MagicMock()
            service.client = MagicMock()
            
            # media_uploadのモック
            media_mock = MagicMock()
            media_mock.media_id = 123456789
            service.api.media_upload.return_value = media_mock
            
            # create_tweetのモック
            response_mock = MagicMock()
            response_mock.data = {'id': 987654321}
            service.client.create_tweet.return_value = response_mock
            
            # TwitterAPIの実装を修正するパッチ
            with patch('dmm_x_poster.services.twitter_api.db.session.get') as mock_get:
                mock_get.return_value = post
                
                # テスト実行
                result = service.post_with_media(post.id)
                
                # 結果検証
                assert result is True
                
                # API呼び出しの検証
                assert service.api.media_upload.call_count == 2  # 2枚の画像をアップロード
                service.client.create_tweet.assert_called_once()
                
                # 投稿ステータスの検証
                db.session.refresh(post)
                assert post.status == "posted"
                assert post.posted_at is not None
    
    def test_post_with_media_not_authenticated(self, app, db, sample_product):
        """未認証状態での投稿テスト"""
        # 投稿データの準備
        post = Post(
            product_id=sample_product.id,
            post_text="テスト投稿です #テスト",
            status="scheduled",
            scheduled_at=datetime.now(UTC)
        )
        db.session.add(post)
        db.session.commit()
        
        # サービスの未認証状態を設定
        service = TwitterAPIService()
        service.api = None
        service.client = None
        
        # テスト実行
        result = service.post_with_media(post.id)
        
        # 結果検証
        assert result is False
    
    def test_post_with_media_api_error(self, app, db, sample_product, sample_images):
        """API呼び出しエラー時のテスト"""
        # 投稿データの準備
        post = Post(
            product_id=sample_product.id,
            post_text="テスト投稿です #テスト",
            status="scheduled",
            scheduled_at=datetime.now(UTC)
        )
        db.session.add(post)
        db.session.flush()
        
        # サンプル画像にlocal_pathを設定
        for image in sample_images:
            image.local_path = f"/tmp/test_image_{image.id}.jpg"
            db.session.add(image)
        
        # 投稿画像の関連付け
        post_image = PostImage(
            post_id=post.id,
            image_id=sample_images[0].id,
            display_order=1
        )
        db.session.add(post_image)
        db.session.commit()
        
        # Twitter APIモックの設定
        with patch.object(TwitterAPIService, 'is_authenticated') as mock_auth:
            mock_auth.return_value = True
            
            service = TwitterAPIService()
            service.api = MagicMock()
            service.client = MagicMock()
            
            # エラーが発生するように設定
            service.api.media_upload.side_effect = Exception("API error")
            
            # TwitterAPIの実装を修正するパッチ
            with patch('dmm_x_poster.services.twitter_api.db.session.get') as mock_get:
                mock_get.return_value = post
                
                # テスト実行
                result = service.post_with_media(post.id)
                
                # 結果検証
                assert result is False
                
                # 投稿ステータスの検証
                db.session.refresh(post)
                assert post.status == "failed"
                # TwitterAPIサービスでエラーメッセージが変換されるため、正確なメッセージのチェックは行わない
                assert post.error_message is not None
    
    def test_process_scheduled_posts(self, app, db, sample_product):
        """process_scheduled_postsメソッドが予定投稿を処理するかテスト"""
        # 複数の投稿を準備
        now = datetime.now(UTC)
        posts = []
        
        # 過去の予定投稿（処理対象）
        post1 = Post(
            product_id=sample_product.id,
            post_text="テスト投稿1",
            status="scheduled",
            scheduled_at=now - timedelta(minutes=30)
        )
        db.session.add(post1)
        posts.append(post1)
        
        # 過去の予定投稿（処理対象）
        post2 = Post(
            product_id=sample_product.id,
            post_text="テスト投稿2",
            status="scheduled",
            scheduled_at=now - timedelta(minutes=15)
        )
        db.session.add(post2)
        posts.append(post2)
        
        # 未来の予定投稿（処理対象外）
        post3 = Post(
            product_id=sample_product.id,
            post_text="テスト投稿3",
            status="scheduled",
            scheduled_at=now + timedelta(minutes=30)
        )
        db.session.add(post3)
        
        db.session.commit()
        
        # post_with_mediaメソッドをモック
        with patch.object(TwitterAPIService, 'is_authenticated') as mock_auth:
            mock_auth.return_value = True
            
            with patch.object(TwitterAPIService, 'post_with_media') as mock_post:
                # 1つ目の投稿は成功、2つ目は失敗と仮定
                mock_post.side_effect = [True, False]
                
                # サービスの設定
                service = TwitterAPIService()
                service.api = MagicMock()
                service.client = MagicMock()
                
                # datetime.utcnowをモック
                with patch('dmm_x_poster.services.twitter_api.datetime') as mock_datetime:
                    mock_datetime.now.return_value = now
                    mock_datetime.UTC = UTC
                    
                    # テスト実行
                    count = service.process_scheduled_posts()
                    
                    # 結果の検証
                    assert count == 1  # 成功した投稿数
                    assert mock_post.call_count == 2  # 呼び出し回数
                    
                    # 呼び出し順序の検証
                    mock_post.assert_any_call(post1.id)
                    mock_post.assert_any_call(post2.id)