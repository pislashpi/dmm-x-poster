"""
URL短縮サービスを提供するモジュール
"""
import logging
import pyshorteners
from flask import current_app

logger = logging.getLogger(__name__)

class URLShortenerService:
    """URL短縮サービスを提供するクラス"""
    
    def __init__(self, app=None):
        self.shortener = None
        self.api_key = None
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """アプリケーションコンテキストからAPI設定を初期化"""
        self.api_key = app.config.get('BITLY_API_KEY')
        try:
            # Bitly APIを使用
            if self.api_key:
                self.shortener = pyshorteners.Shortener(api_key=self.api_key)
                logger.info("URL Shortener service initialized with Bitly")
            else:
                # APIキーがない場合はTinyURLを使用（API制限あり）
                self.shortener = pyshorteners.Shortener()
                logger.warning("Using TinyURL as fallback (no Bitly API key)")
        except Exception as e:
            logger.error(f"Failed to initialize URL Shortener: {e}")
            self.shortener = None
    
    def shorten_url(self, url):
        """URLを短縮"""
        if not url:
            return None
            
        if not self.shortener:
            logger.error("URL Shortener not initialized")
            return url
        
        try:
            if self.api_key:
                # Bitlyを使用
                return self.shortener.bitly.short(url)
            else:
                # TinyURLを使用
                return self.shortener.tinyurl.short(url)
        except Exception as e:
            logger.error(f"URL shortening failed: {e}")
            return url
    
    def expand_url(self, short_url):
        """短縮URLを元に戻す（デバッグ用）"""
        if not short_url:
            return None
            
        if not self.shortener:
            logger.error("URL Shortener not initialized")
            return short_url
        
        try:
            if self.api_key:
                # Bitlyを使用
                return self.shortener.bitly.expand(short_url)
            else:
                # TinyURLではexpandがサポートされていない
                logger.warning("URL expansion not supported with TinyURL")
                return short_url
        except Exception as e:
            logger.error(f"URL expansion failed: {e}")
            return short_url


# アプリケーションファクトリで初期化するためのインスタンス
url_shortener_service = URLShortenerService()