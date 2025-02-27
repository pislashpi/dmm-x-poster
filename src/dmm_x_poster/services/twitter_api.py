"""
Twitter API連携サービス
"""
import os
import tweepy
import logging
from flask import current_app
from datetime import datetime, UTC

from dmm_x_poster.db.models import db, Post, Image, PostImage

# Tweepyからの無効なエスケープシーケンス警告を抑制
import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning, module="tweepy")

logger = logging.getLogger(__name__)

class TwitterAPIService:
    """Twitter APIと連携するサービスクラス"""
    
    def __init__(self, app=None):
        self.api = None
        self.client = None
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """アプリケーションコンテキストからAPI設定を初期化"""
        try:
            # V1.1 API用の認証情報
            auth = tweepy.OAuth1UserHandler(
                app.config.get('TWITTER_API_KEY'),
                app.config.get('TWITTER_API_SECRET'),
                app.config.get('TWITTER_ACCESS_TOKEN'),
                app.config.get('TWITTER_ACCESS_SECRET')
            )
            self.api = tweepy.API(auth)
            
            # V2 API用のクライアント
            self.client = tweepy.Client(
                consumer_key=app.config.get('TWITTER_API_KEY'),
                consumer_secret=app.config.get('TWITTER_API_SECRET'),
                access_token=app.config.get('TWITTER_ACCESS_TOKEN'),
                access_token_secret=app.config.get('TWITTER_ACCESS_SECRET')
            )
            
            # 認証確認
            self.api.verify_credentials()
            logger.info("Twitter API authenticated successfully")
        except Exception as e:
            logger.error(f"Twitter API authentication failed: {e}")
            self.api = None
            self.client = None
    
    def is_authenticated(self):
        """API認証状態をチェック"""
        return self.api is not None and self.client is not None
    
    def post_with_media(self, post_id):
        """画像付きツイートを投稿"""
        if not self.is_authenticated():
            logger.error("Twitter API not authenticated")
            return False
        
        # 投稿データを取得
        post = db.session.get(Post, post_id)
        if not post:
            logger.error(f"Post not found: {post_id}")
            return False
        
        try:
            # 画像をアップロード
            media_ids = []
            images = post.get_images()
            
            # 画像がない場合はテキストのみ投稿
            if not images:
                response = self.client.create_tweet(text=post.post_text)
                tweet_id = response.data['id']
                
                # 投稿成功を記録
                post.status = 'posted'
                post.posted_at = datetime.now(UTC)
                db.session.commit()
                logger.info(f"Posted text-only tweet: {tweet_id}")
                return True
            
            # 画像を処理
            for image in images:
                if not image.local_path or not os.path.exists(image.local_path):
                    logger.warning(f"Image file not found: {image.local_path}")
                    continue
                
                # 画像をアップロード
                media = self.api.media_upload(image.local_path)
                media_ids.append(media.media_id)
            
            # 投稿を作成
            if media_ids:
                response = self.client.create_tweet(
                    text=post.post_text,
                    media_ids=media_ids
                )
                tweet_id = response.data['id']
                
                # 投稿成功を記録
                post.status = 'posted'
                post.posted_at = datetime.now(UTC)
                db.session.commit()
                logger.info(f"Posted tweet with media: {tweet_id}")
                return True
            else:
                # 画像処理に失敗した場合
                logger.error("Failed to upload any media")
                post.status = 'failed'
                post.error_message = "Failed to upload media files"
                db.session.commit()
                return False
            
        except Exception as e:
            # エラー発生時
            logger.error(f"Error posting tweet: {e}")
            post.status = 'failed'
            post.error_message = str(e)
            db.session.commit()
            return False
    
    def process_scheduled_posts(self):
        """予定された投稿を処理"""
        if not self.is_authenticated():
            logger.error("Twitter API not authenticated")
            return 0
        
        now = datetime.now(UTC)
        posts = Post.query.filter_by(status='scheduled').filter(
            Post.scheduled_at <= now
        ).all()
        
        success_count = 0
        for post in posts:
            if self.post_with_media(post.id):
                success_count += 1
        
        return success_count


# アプリケーションファクトリで初期化するためのインスタンス
twitter_api_service = TwitterAPIService()