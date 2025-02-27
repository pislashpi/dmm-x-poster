"""
投稿スケジューリングを管理するサービスモジュール
"""
import logging
import random
from datetime import datetime, timedelta
from flask import current_app

from dmm_x_poster.db.models import db, Product, Post, Image, PostImage
from dmm_x_poster.services.url_shortener import url_shortener_service
from dmm_x_poster.services.twitter_api import twitter_api_service

logger = logging.getLogger(__name__)

class SchedulerService:
    """投稿スケジューリングを管理するサービスクラス"""
    
    def __init__(self, app=None):
        self.posts_per_day = 3
        self.post_start_hour = 9  # 9:00
        self.post_end_hour = 22   # 22:00
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """アプリケーションコンテキストから設定を初期化"""
        self.posts_per_day = app.config.get('POSTS_PER_DAY', 3)
        self.post_start_hour = app.config.get('POST_START_HOUR', 9)
        self.post_end_hour = app.config.get('POST_END_HOUR', 22)
    
    def generate_post_text(self, product):
        """投稿テキストを生成"""
        # 出演者とジャンルを取得
        actresses = product.get_actresses_list()
        genres = product.get_genres_list()
        
        # 基本テキスト
        text = f"【新着】{product.title}"
        
        # 出演者情報を追加
        if actresses:
            if len(actresses) <= 3:
                text += f"\n出演: {', '.join(actresses)}"
            else:
                text += f"\n出演: {', '.join(actresses[:3])}他"
        
        # ジャンル情報を追加（文字数制限を考慮）
        if genres and len(text) < 200:
            selected_genres = genres[:3] if len(genres) > 3 else genres
            text += f"\nジャンル: {', '.join(selected_genres)}"
        
        # 短縮URLを追加
        if product.url and url_shortener_service:
            short_url = url_shortener_service.shorten_url(product.url)
            if short_url:
                text += f"\n{short_url}"
        
        return text
    
    def create_post(self, product_id):
        """投稿を作成"""
        product = Product.query.get(product_id)
        if not product:
            logger.error(f"Product not found: {product_id}")
            return None
        
        # 選択された画像を取得
        selected_images = product.get_selected_images()
        if not selected_images:
            logger.warning(f"No selected images for product: {product_id}")
            return None
        
        # 短縮URLを生成
        short_url = None
        if url_shortener_service:
            short_url = url_shortener_service.shorten_url(product.url)
        
        # 投稿テキストを生成
        post_text = self.generate_post_text(product)
        
        # 次の投稿時間を計算
        next_time = self.calculate_next_post_time()
        
        # 投稿レコードを作成
        post = Post(
            product_id=product_id,
            post_text=post_text,
            short_url=short_url,
            status='scheduled',
            scheduled_at=next_time
        )
        
        db.session.add(post)
        db.session.flush()  # IDを生成するために必要
        
        # 投稿画像の関連付け
        for i, image in enumerate(selected_images):
            post_image = PostImage(
                post_id=post.id,
                image_id=image.id,
                display_order=i + 1
            )
            db.session.add(post_image)
        
        db.session.commit()
        logger.info(f"Created post for product {product_id}, scheduled at {next_time}")
        
        return post
    
    def calculate_next_post_time(self):
        """次の投稿時間を計算"""
        now = datetime.utcnow()
        
        # 投稿間隔を計算（営業時間内に均等に配置）
        hours_per_day = self.post_end_hour - self.post_start_hour
        interval_hours = hours_per_day / self.posts_per_day
        
        # 最新の予定投稿を取得
        latest_post = Post.query.filter_by(status='scheduled').order_by(
            Post.scheduled_at.desc()
        ).first()
        
        if latest_post:
            # 最新投稿から間隔を空けて次の時間を設定
            next_time = latest_post.scheduled_at + timedelta(hours=interval_hours)
            
            # 営業時間外なら翌日の開始時間に設定
            if next_time.hour >= self.post_end_hour:
                next_time = next_time.replace(
                    hour=self.post_start_hour,
                    minute=0,
                    second=0,
                    microsecond=0
                )
                next_time += timedelta(days=1)
        else:
            # 投稿がまだない場合は現在時刻から計算
            if now.hour < self.post_start_hour:
                # 今日の営業開始時間
                next_time = now.replace(
                    hour=self.post_start_hour,
                    minute=0,
                    second=0,
                    microsecond=0
                )
            elif now.hour >= self.post_end_hour:
                # 翌日の営業開始時間
                next_time = now.replace(
                    hour=self.post_start_hour,
                    minute=0,
                    second=0,
                    microsecond=0
                )
                next_time += timedelta(days=1)
            else:
                # 現在時刻から少し間隔を空ける
                next_time = now + timedelta(minutes=30)
        
        # ミリ秒をランダムに設定して同時投稿を避ける
        next_time = next_time.replace(microsecond=random.randint(0, 999999))
        
        return next_time
    
    def schedule_unposted_products(self, limit=5):
        """未投稿の商品を投稿スケジュールに追加"""
        # 未投稿かつ画像が選択されている商品を取得
        products = db.session.query(Product).join(
            Image, Product.id == Image.product_id
        ).filter(
            Product.posted == False,
            Image.selected == True
        ).distinct().limit(limit).all()
        
        scheduled_count = 0
        for product in products:
            post = self.create_post(product.id)
            if post:
                # 投稿済みとしてマーク
                product.posted = True
                db.session.commit()
                scheduled_count += 1
        
        return scheduled_count
    
    def process_scheduled_posts(self):
        """予定された投稿を処理"""
        if not twitter_api_service.is_authenticated():
            logger.error("Twitter API not authenticated")
            return 0
        
        return twitter_api_service.process_scheduled_posts()


# アプリケーションファクトリで初期化するためのインスタンス
scheduler_service = SchedulerService()