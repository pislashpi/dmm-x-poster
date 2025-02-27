"""
アプリケーション設定
"""
import os
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

class Config:
    """アプリケーション設定クラス"""
    # アプリケーション基本設定
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # DMM API設定
    DMM_API_ID = os.environ.get('DMM_API_ID')
    DMM_AFFILIATE_ID = os.environ.get('DMM_AFFILIATE_ID')
    
    # Twitter API設定
    TWITTER_API_KEY = os.environ.get('TWITTER_API_KEY')
    TWITTER_API_SECRET = os.environ.get('TWITTER_API_SECRET')
    TWITTER_ACCESS_TOKEN = os.environ.get('TWITTER_ACCESS_TOKEN')
    TWITTER_ACCESS_SECRET = os.environ.get('TWITTER_ACCESS_SECRET')
    
    # 短縮URL設定（Bitly）
    BITLY_API_KEY = os.environ.get('BITLY_API_KEY')
    
    # 画像保存設定
    IMAGES_FOLDER = os.path.join('static', 'images')
    MAX_IMAGES_PER_POST = 4
    
    # 投稿スケジュール設定
    POSTS_PER_DAY = int(os.environ.get('POSTS_PER_DAY', 3))
    POST_START_HOUR = int(os.environ.get('POST_START_HOUR', 9))  # 9:00
    POST_END_HOUR = int(os.environ.get('POST_END_HOUR', 22))     # 22:00