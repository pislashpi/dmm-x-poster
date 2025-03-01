"""
データベースモデル定義
"""
import json
import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import declarative_base
from dmm_x_poster.config import JST

db = SQLAlchemy()
Base = declarative_base()

class Product(db.Model):
    """商品テーブル"""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    dmm_product_id = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.Text, nullable=False)
    actresses = db.Column(db.Text)  # JSON形式
    url = db.Column(db.Text, nullable=False)
    package_image_url = db.Column(db.Text)
    maker = db.Column(db.Text)
    genres = db.Column(db.Text)  # JSON形式
    release_date = db.Column(db.Date)
    fetched_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(JST))
    posted = db.Column(db.Boolean, default=False)
    last_posted_at = db.Column(db.DateTime)
    
    # リレーションシップ
    images = db.relationship('Image', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    posts = db.relationship('Post', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    
    def get_actresses_list(self):
        """女優名のリストを取得"""
        if self.actresses:
            return json.loads(self.actresses)
        return []
    
    def get_genres_list(self):
        """ジャンルのリストを取得"""
        if self.genres:
            return json.loads(self.genres)
        return []
    
    def get_selected_images(self, limit=4):
        """選択された画像を順序通りに取得"""
        return Image.query.filter_by(
            product_id=self.id, 
            selected=True
        ).order_by(Image.selection_order).limit(limit).all()


class Image(db.Model):
    """画像テーブル"""
    __tablename__ = 'images'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    image_url = db.Column(db.Text, nullable=False)
    local_path = db.Column(db.Text)
    downloaded = db.Column(db.Boolean, default=False)
    selected = db.Column(db.Boolean, default=False)
    selection_order = db.Column(db.Integer)
    image_type = db.Column(db.String(20), default='sample')  # 'sample', 'package', 'movie'
    created_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(JST))
    
    # リレーションシップ
    post_images = db.relationship('PostImage', backref='image', lazy='dynamic', cascade='all, delete-orphan')


class Post(db.Model):
    """投稿テーブル"""
    __tablename__ = 'posts'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    post_text = db.Column(db.Text)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, posted, failed
    scheduled_at = db.Column(db.DateTime, nullable=False)
    posted_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    
    # リレーションシップ
    post_images = db.relationship('PostImage', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    
    def get_images(self):
        """投稿に関連する画像を取得"""
        return db.session.query(Image).join(
            PostImage
        ).filter(
            PostImage.post_id == self.id
        ).order_by(PostImage.display_order).all()


class PostImage(db.Model):
    """投稿画像関連テーブル"""
    __tablename__ = 'post_images'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'), nullable=False)
    display_order = db.Column(db.Integer, nullable=False)