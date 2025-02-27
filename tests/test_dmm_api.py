"""
DMM APIサービスのテスト
"""
import json
import pytest
from unittest.mock import MagicMock, patch

from dmm_x_poster.services.dmm_api import DMMAPIService


class TestDMMAPIService:
    """DMM APIサービスのテストクラス"""
    
    def test_init_app(self, app):
        """init_appメソッドが設定を正しく読み込むかテスト"""
        service = DMMAPIService()
        service.init_app(app)
        
        assert service.api_id == app.config['DMM_API_ID']
        assert service.affiliate_id == app.config['DMM_AFFILIATE_ID']
    
    def test_get_params(self, app):
        """get_paramsメソッドが正しいパラメータを返すかテスト"""
        service = DMMAPIService()
        service.init_app(app)
        
        # 基本パラメータのみ
        params = service.get_params()
        assert params['api_id'] == app.config['DMM_API_ID']
        assert params['affiliate_id'] == app.config['DMM_AFFILIATE_ID']
        assert params['site'] == 'FANZA'
        assert params['output'] == 'json'
        assert params['hits'] == 20
        
        # 追加パラメータあり
        params = service.get_params(floor='dvd', sort='date', keyword='テスト')
        assert params['floor'] == 'dvd'
        assert params['sort'] == 'date'
        assert params['keyword'] == 'テスト'
    
    @patch('dmm_x_poster.services.dmm_api.requests.get')
    def test_search_items_success(self, mock_get, app):
        """search_itemsメソッドが正常な場合のテスト"""
        # モックレスポンスの設定
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "result": {
                "status": 200,
                "items": [
                    {
                        "content_id": "test-123",
                        "title": "テスト商品",
                        "URL": "https://example.com/product/test-123",
                        "date": "2023-01-15 00:00:00",
                        "imageURL": {
                            "large": "https://example.com/images/test-123.jpg"
                        },
                        "iteminfo": {
                            "actress": [
                                {"name": "女優A"},
                                {"name": "女優B"}
                            ],
                            "genre": [
                                {"name": "ジャンルA"},
                                {"name": "ジャンルB"}
                            ],
                            "maker": [
                                {"name": "サンプルメーカー"}
                            ]
                        },
                        "sampleImageURL": {
                            "sample_s": [
                                "https://example.com/samples/test-123-1.jpg",
                                "https://example.com/samples/test-123-2.jpg"
                            ]
                        }
                    }
                ]
            }
        }
        mock_get.return_value = mock_response
        
        # サービスの設定とテスト実行
        service = DMMAPIService()
        service.init_app(app)
        items = service.search_items(floor='dvd', sort='date')
        
        # 結果の検証
        assert len(items) == 1
        assert items[0]['content_id'] == 'test-123'
        assert items[0]['title'] == 'テスト商品'
        assert items[0]['URL'] == 'https://example.com/product/test-123'
        
        # APIコールの検証
        mock_get.assert_called_once()
        # URLに正しいパラメータが含まれているか
        call_args = mock_get.call_args[0][0]
        assert 'api_id=' in call_args
        assert 'affiliate_id=' in call_args
        assert 'floor=dvd' in call_args
        assert 'sort=date' in call_args
    
    @patch('dmm_x_poster.services.dmm_api.requests.get')
    def test_search_items_api_error(self, mock_get, app):
        """search_itemsメソッドがAPI呼び出しエラー時に空リストを返すかテスト"""
        # モックレスポンスの設定（例外発生）
        import requests
        mock_get.side_effect = requests.RequestException("API error")
        
        # サービスの設定とテスト実行
        service = DMMAPIService()
        service.init_app(app)
        items = service.search_items()
        
        # 結果の検証
        assert items == []
    
    @patch('dmm_x_poster.services.dmm_api.requests.get')
    def test_search_items_invalid_format(self, mock_get, app):
        """search_itemsメソッドが不正なレスポンス形式の場合に空リストを返すかテスト"""
        # モックレスポンスの設定（不正な形式）
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"error": "Invalid format"}
        mock_get.return_value = mock_response
        
        # サービスの設定とテスト実行
        service = DMMAPIService()
        service.init_app(app)
        items = service.search_items()
        
        # 結果の検証
        assert items == []
    
    def test_save_items_to_db(self, app, db):
        """save_items_to_dbメソッドが商品を正しく保存するかテスト"""
        from dmm_x_poster.db.models import Product, Image
        
        # テスト用データ
        items = [
            {
                "content_id": "test-123",
                "title": "テスト商品",
                "URL": "https://example.com/product/test-123",
                "date": "2023-01-15 00:00:00",
                "imageURL": {
                    "large": "https://example.com/images/test-123.jpg"
                },
                "iteminfo": {
                    "actress": [
                        {"name": "女優A"},
                        {"name": "女優B"}
                    ],
                    "genre": [
                        {"name": "ジャンルA"},
                        {"name": "ジャンルB"}
                    ],
                    "maker": [
                        {"name": "サンプルメーカー"}
                    ]
                },
                "sampleImageURL": {
                    "sample_s": [
                        "https://example.com/samples/test-123-1.jpg",
                        "https://example.com/samples/test-123-2.jpg"
                    ]
                }
            }
        ]
        
        # サービスの設定とテスト実行
        service = DMMAPIService()
        service.init_app(app)
        saved_count = service.save_items_to_db(items)
        
        # 結果の検証
        assert saved_count == 1
        
        # データベースの検証
        product = Product.query.filter_by(dmm_product_id="test-123").first()
        assert product is not None
        assert product.title == "テスト商品"
        assert product.url == "https://example.com/product/test-123"
        assert product.package_image_url == "https://example.com/images/test-123.jpg"
        
        # 女優情報の検証
        actresses = json.loads(product.actresses)
        assert "女優A" in actresses
        assert "女優B" in actresses
        
        # ジャンル情報の検証
        genres = json.loads(product.genres)
        assert "ジャンルA" in genres
        assert "ジャンルB" in genres
        
        # 画像情報の検証
        images = Image.query.filter_by(product_id=product.id).all()
        assert len(images) == 2
        assert images[0].image_url == "https://example.com/samples/test-123-1.jpg"
        assert images[1].image_url == "https://example.com/samples/test-123-2.jpg"
    
    @patch('dmm_x_poster.services.dmm_api.DMMAPIService.search_items')
    def test_fetch_and_save_new_items(self, mock_search_items, app, db):
        """fetch_and_save_new_itemsメソッドが正しく機能するかテスト"""
        # モックの設定
        mock_search_items.return_value = [
            {
                "content_id": "test-123",
                "title": "テスト商品",
                "URL": "https://example.com/product/test-123",
                "date": "2023-01-15 00:00:00",
                "imageURL": {
                    "large": "https://example.com/images/test-123.jpg"
                },
                "iteminfo": {
                    "actress": [
                        {"name": "女優A"}
                    ],
                    "genre": [
                        {"name": "ジャンルA"}
                    ],
                    "maker": [
                        {"name": "サンプルメーカー"}
                    ]
                },
                "sampleImageURL": {
                    "sample_s": [
                        "https://example.com/samples/test-123-1.jpg"
                    ]
                }
            }
        ]
        
        # サービスの設定とテスト実行
        service = DMMAPIService()
        service.init_app(app)
        saved_count = service.fetch_and_save_new_items(floor='dvd', sort='date')
        
        # 結果の検証
        assert saved_count == 1
        
        # モックの検証
        mock_search_items.assert_called_once_with(floor='dvd', sort='date')