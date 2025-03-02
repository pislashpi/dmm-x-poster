"""
Twitter API連携サービス
"""
import os
import tweepy
import logging
from flask import current_app
from datetime import datetime, timezone, UTC
from zoneinfo import ZoneInfo


from dmm_x_poster.config import JST
from dmm_x_poster.db.models import db, Post, Image, PostImage

# Tweepyからの無効なエスケープシーケンス警告を抑制
import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning, module="tweepy")

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

def jst_to_utc(jst_datetime):
    if jst_datetime.tzinfo is None:
        jst_datetime = jst_datetime.replace(tzinfo=JST)
    return jst_datetime.astimezone(timezone.utc)

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
            
            logger.info(f"Post {post_id} has {len(images)} images")
            
            # 画像がない場合はテキストのみ投稿
            if not images:
                logger.warning(f"No images found for post {post_id}")
                response = self.client.create_tweet(text=post.post_text)
                tweet_id = response.data['id']
                
                # 投稿成功を記録
                post.status = 'posted'
                post.posted_at = datetime.now(JST)
                db.session.commit()
                logger.info(f"Posted text-only tweet: {tweet_id}")
                return True
            
            # 画像と動画を区別して処理
            movie_images = [img for img in images if hasattr(img, 'image_type') and img.image_type == 'movie']
            standard_images = [img for img in images if not hasattr(img, 'image_type') or img.image_type != 'movie']
            
            logger.info(f"Found {len(movie_images)} movie images and {len(standard_images)} standard images")
            
            # mp4動画ファイルを検出
            mp4_videos = [img for img in movie_images if img.image_url and img.image_url.endswith('.mp4')]
            
            # 動画処理のフラグ
            has_video_content = False
            
            # mp4動画があり、ローカルにダウンロードされている場合
            if mp4_videos:
                has_video_content = True
                logger.info(f"Found mp4 video: {mp4_videos[0].image_url}")
                
                # 動画URLが存在する場合は、テキストに追加
                video_urls = [video.image_url for video in mp4_videos if video.image_url]
                if video_urls:
                    # 投稿テキストに動画があることを追記
                    tweet_text = f"{post.post_text}\n\n動画: {post.product.url}"
                    logger.info(f"Creating tweet with video reference: {tweet_text}")
                    
                    # テキスト投稿
                    response = self.client.create_tweet(text=tweet_text)
                    tweet_id = response.data['id']
                    
                    # 投稿成功を記録
                    post.status = 'posted'
                    post.posted_at = datetime.now(JST)
                    db.session.commit()
                    logger.info(f"Posted tweet with video reference: {tweet_id}")
                    return True
            
            # 動画コンテンツがない、または処理に失敗した場合は通常の画像投稿
            if not has_video_content:
                # 通常の画像投稿処理
                for image in standard_images:
                    # ローカルファイルパスの確認
                    if not image.local_path:
                        logger.warning(f"Image {image.id} has no local_path")
                        continue
                        
                    # 絶対パスを構築
                    app_root = current_app.root_path
                    absolute_path = os.path.join(app_root, image.local_path)
                        
                    # ファイルの存在確認
                    if not os.path.exists(absolute_path):
                        logger.warning(f"Image file not found: {absolute_path}")
                        logger.warning(f"Also tried relative path: {image.local_path}")
                        continue
                    
                    try:
                        # 画像をアップロード（絶対パスを使用）
                        logger.info(f"Uploading image from {absolute_path}")
                        media = self.api.media_upload(absolute_path)
                        media_ids.append(media.media_id)
                        logger.info(f"Successfully uploaded media ID: {media.media_id}")
                    except Exception as e:
                        logger.error(f"Error uploading media: {e}")
                        continue
                
                # 投稿を作成
                if media_ids:
                    logger.info(f"Creating tweet with {len(media_ids)} media attachments")
                    response = self.client.create_tweet(
                        text=post.post_text,
                        media_ids=media_ids
                    )
                    tweet_id = response.data['id']
                    
                    # 投稿成功を記録
                    post.status = 'posted'
                    post.posted_at = datetime.now(JST)
                    db.session.commit()
                    logger.info(f"Posted tweet with media: {tweet_id}")
                    return True
                else:
                    # 画像処理に失敗した場合、テキストのみで投稿を試みる
                    logger.warning("Failed to upload any media, falling back to text-only tweet")
                    
                    try:
                        # テキストのみの投稿を試みる
                        response = self.client.create_tweet(text=post.post_text)
                        tweet_id = response.data['id']
                        
                        # 投稿成功を記録
                        post.status = 'posted'
                        post.posted_at = datetime.now(JST)
                        db.session.commit()
                        logger.info(f"Posted text-only tweet (fallback): {tweet_id}")
                        return True
                    except Exception as e:
                        logger.error(f"Error posting fallback text-only tweet: {e}")
                        post.status = 'failed'
                        post.error_message = f"Failed to post: {str(e)}"
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
        
        # 現在時刻（JST）
        now = datetime.now(JST)
        
        # 予定投稿を検索（JST）
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