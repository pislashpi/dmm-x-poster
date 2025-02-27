"""
URL短縮サービスのテスト
"""
import pytest
from unittest.mock import MagicMock, patch

from dmm_x_poster.services.url_shortener import URLShortenerService


class TestURLShortenerService:
    """URL短縮サービスのテストクラス"""
    
    def test_init_app_with_api_key(self, app):
        """API設定ありでinit_appメソッドをテスト"""
        # Bitly APIキーあり
        with patch('dmm_x_poster.services.url_shortener.pyshorteners.Shortener') as mock_shortener:
            service = URLShortenerService()
            service.init_app(app)
            
            mock_shortener.assert_called_once_with(api_key=app.config.get('BITLY_API_KEY'))
            assert service.api_key == app.config.get('BITLY_API_KEY')
    
    def test_init_app_without_api_key(self, app):
        """API設定なしでinit_appメソッドをテスト"""
        # Bitly APIキーなし
        app.config['BITLY_API_KEY'] = None
        
        with patch('dmm_x_poster.services.url_shortener.pyshorteners.Shortener') as mock_shortener:
            service = URLShortenerService()
            service.init_app(app)
            
            mock_shortener.assert_called_once_with()
            assert service.api_key is None
    
    def test_shorten_url_with_bitly(self, app):
        """Bitlyでshorten_urlメソッドをテスト"""
        with patch('dmm_x_poster.services.url_shortener.pyshorteners.Shortener') as mock_shortener:
            # モックの設定
            shortener_instance = MagicMock()
            shortener_instance.bitly.short.return_value = "https://bit.ly/abc123"
            mock_shortener.return_value = shortener_instance
            
            # サービスの設定
            service = URLShortenerService()
            service.api_key = app.config.get('BITLY_API_KEY')
            service.shortener = shortener_instance
            
            # テスト実行
            original_url = "https://example.com/very/long/url/that/needs/shortening"
            short_url = service.shorten_url(original_url)
            
            # 結果の検証
            assert short_url == "https://bit.ly/abc123"
            shortener_instance.bitly.short.assert_called_once_with(original_url)
    
    def test_shorten_url_with_tinyurl(self, app):
        """TinyURLでshorten_urlメソッドをテスト"""
        with patch('dmm_x_poster.services.url_shortener.pyshorteners.Shortener') as mock_shortener:
            # モックの設定
            shortener_instance = MagicMock()
            shortener_instance.tinyurl.short.return_value = "https://tinyurl.com/abc123"
            mock_shortener.return_value = shortener_instance
            
            # サービスの設定（APIキーなし）
            service = URLShortenerService()
            service.api_key = None
            service.shortener = shortener_instance
            
            # テスト実行
            original_url = "https://example.com/very/long/url/that/needs/shortening"
            short_url = service.shorten_url(original_url)
            
            # 結果の検証
            assert short_url == "https://tinyurl.com/abc123"
            shortener_instance.tinyurl.short.assert_called_once_with(original_url)
    
    def test_shorten_url_with_error(self, app):
        """エラー発生時のshorten_urlメソッドをテスト"""
        with patch('dmm_x_poster.services.url_shortener.pyshorteners.Shortener') as mock_shortener:
            # モックの設定（例外発生）
            shortener_instance = MagicMock()
            shortener_instance.bitly.short.side_effect = Exception("API error")
            mock_shortener.return_value = shortener_instance
            
            # サービスの設定
            service = URLShortenerService()
            service.api_key = app.config.get('BITLY_API_KEY')
            service.shortener = shortener_instance
            
            # テスト実行
            original_url = "https://example.com/test-url"
            short_url = service.shorten_url(original_url)
            
            # エラー時は元のURLが返るか
            assert short_url == original_url
    
    def test_shorten_url_not_initialized(self, app):
        """未初期化状態でのshorten_urlメソッドをテスト"""
        service = URLShortenerService()
        service.shortener = None
        
        original_url = "https://example.com/test-url"
        short_url = service.shorten_url(original_url)
        
        # 未初期化時は元のURLが返るか
        assert short_url == original_url
    
    def test_shorten_url_with_none(self, app):
        """Noneを入力したときのshorten_urlメソッドをテスト"""
        service = URLShortenerService()
        
        # Noneを入力
        short_url = service.shorten_url(None)
        
        # Noneが返るか
        assert short_url is None
    
    def test_expand_url_with_bitly(self, app):
        """Bitlyでexpand_urlメソッドをテスト"""
        with patch('dmm_x_poster.services.url_shortener.pyshorteners.Shortener') as mock_shortener:
            # モックの設定
            shortener_instance = MagicMock()
            shortener_instance.bitly.expand.return_value = "https://example.com/original/url"
            mock_shortener.return_value = shortener_instance
            
            # サービスの設定
            service = URLShortenerService()
            service.api_key = app.config.get('BITLY_API_KEY')
            service.shortener = shortener_instance
            
            # テスト実行
            short_url = "https://bit.ly/abc123"
            original_url = service.expand_url(short_url)
            
            # 結果の検証
            assert original_url == "https://example.com/original/url"
            shortener_instance.bitly.expand.assert_called_once_with(short_url)
    
    def test_expand_url_with_tinyurl(self, app):
        """TinyURLでexpand_urlメソッドをテスト（サポートなし）"""
        with patch('dmm_x_poster.services.url_shortener.pyshorteners.Shortener') as mock_shortener:
            # モックの設定
            shortener_instance = MagicMock()
            mock_shortener.return_value = shortener_instance
            
            # サービスの設定（APIキーなし）
            service = URLShortenerService()
            service.api_key = None
            service.shortener = shortener_instance
            
            # テスト実行
            short_url = "https://tinyurl.com/abc123"
            original_url = service.expand_url(short_url)
            
            # TinyURLではexpandがサポートされないので元のURLが返るか
            assert original_url == short_url