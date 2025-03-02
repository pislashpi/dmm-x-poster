"""
DMM APIと連携するサービスモジュール
"""
import json
import requests
import logging
from datetime import datetime
from urllib.parse import urlencode
from flask import current_app

from dmm_x_poster.config import JST
from dmm_x_poster.db.models import db, Product, Image

logger = logging.getLogger(__name__)

class DMMAPIService:
    """DMM APIと連携するサービスクラス"""
    
    BASE_URL = "https://api.dmm.com/affiliate/v3/ItemList"
    
    def __init__(self, app=None):
        self.api_id = None
        self.affiliate_id = None
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """アプリケーションコンテキストからAPI設定を初期化"""
        self.api_id = app.config.get('DMM_API_ID')
        self.affiliate_id = app.config.get('DMM_AFFILIATE_ID')
    
    def get_params(self, **kwargs):
        """APIリクエストパラメータを生成"""
        params = {
            'api_id': self.api_id,
            'affiliate_id': self.affiliate_id,
            'site': 'FANZA',
            'service': 'digital',  # serviceパラメータを追加
            'output': 'json',
            'hits': 20,
        }
        # 追加パラメータを統合
        params.update(kwargs)
        return params
    
    def search_items(self, floor='videoa', sort='date', article=None, article_id=None, **kwargs):
        """商品検索を実行"""
        params = self.get_params(floor=floor, sort=sort, **kwargs)
        
        # article（ジャンル指定）が提供されている場合は追加
        if article:
            params['article'] = article
        
        # article_id（ジャンルID）が提供されている場合は追加
        if article_id:
            params['article_id'] = article_id
            
        url = f"{self.BASE_URL}?{urlencode(params)}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            # レスポンスのフォーマットチェック
            if 'result' not in data or 'items' not in data['result']:
                logger.error(f"Unexpected API response format: {data}")
                return []
            
            return data['result']['items']
        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse API response: {e}")
            return []
        except Exception as e:
            # その他の例外も捕捉して空リストを返す
            logger.error(f"Unexpected error during API request: {e}")
            return []
    
    def save_items_to_db(self, items):
        """取得した商品情報をデータベースに保存"""
        saved_count = 0
        
        for item in items:
            try:
                # 既存の商品をチェック
                existing = Product.query.filter_by(dmm_product_id=item['content_id']).first()
                if existing:
                    logger.info(f"Product already exists: {item['title']}")
                    continue
                
                # 出演者リストを取得
                actresses = []
                if 'iteminfo' in item and 'actress' in item['iteminfo']:
                    actresses = [actress['name'] for actress in item['iteminfo']['actress']]
                
                # ジャンルリストを取得
                genres = []
                if 'iteminfo' in item and 'genre' in item['iteminfo']:
                    genres = [genre['name'] for genre in item['iteminfo']['genre']]
                
                # 発売日をパース
                release_date = None
                if 'date' in item:
                    try:
                        release_date = datetime.strptime(item['date'], '%Y-%m-%d %H:%M:%S').date()
                    except ValueError:
                        pass
                
                # 商品レコードを作成
                product = Product(
                    dmm_product_id=item['content_id'],
                    title=item['title'],
                    actresses=json.dumps(actresses, ensure_ascii=False),
                    url=item['URL'],
                    package_image_url=item.get('imageURL', {}).get('large'),
                    maker=item.get('iteminfo', {}).get('maker', [{}])[0].get('name', ''),
                    genres=json.dumps(genres, ensure_ascii=False),
                    release_date=release_date,
                    fetched_at=datetime.now(JST)
                )
                
                db.session.add(product)
                db.session.flush()  # IDを生成するためにflush
                
                # パッケージ画像を保存（選択可能にするため）
                if 'imageURL' in item and 'large' in item['imageURL']:
                    package_image = Image(
                        product_id=product.id,
                        image_url=item['imageURL']['large'],
                        image_type='package',  # 種類を示す属性を追加
                        created_at=datetime.now(JST)
                    )
                    db.session.add(package_image)
                
                # サムネイル画像を保存
                if 'sampleImageURL' in item:
                    # sample_l.image の取得
                    if 'sample_l' in item['sampleImageURL'] and 'image' in item['sampleImageURL']['sample_l']:
                        sample_images = item['sampleImageURL']['sample_l']['image']
                        for i, img_url in enumerate(sample_images):
                            image = Image(
                                product_id=product.id,
                                image_url=img_url,
                                image_type='sample',  # 種類を示す属性を追加
                                created_at=datetime.now(JST)
                            )
                            db.session.add(image)
                
                # サンプルムービーを保存 - APIレスポンスの構造に合わせて修正
                if 'samplemovieURL' in item:
                    # 利用可能なサイズを優先順位で試す
                    movie_sizes = ['size_720_480', 'size_644_414', 'size_560_360', 'size_476_306']
                    
                    for size in movie_sizes:
                        if size in item['samplemovieURL'] and item['samplemovieURL'][size]:
                            movie_url = item['samplemovieURL'][size]
                            
                            if movie_url:  # URLが存在するか確認
                                movie = Image(
                                    product_id=product.id,
                                    image_url=movie_url,
                                    image_type='movie',  # 種類を示す属性を追加
                                    created_at=datetime.now(JST)
                                )
                                db.session.add(movie)
                                logger.info(f"Added movie URL ({size}): {movie_url}")
                                # 1つのサイズが見つかれば十分
                                break
                
                saved_count += 1
                
            except Exception as e:
                logger.error(f"Error saving product: {e}")
                db.session.rollback()
        
        try:
            db.session.commit()
            logger.info(f"Saved {saved_count} new products to database")
        except Exception as e:
            logger.error(f"Error committing to database: {e}")
            db.session.rollback()
            saved_count = 0
        
        return saved_count
    
    def fetch_and_save_new_items(self, **kwargs):
        """新しい商品を取得して保存"""
        items = self.search_items(**kwargs)
        return self.save_items_to_db(items)


# アプリケーションファクトリで初期化するためのインスタンス
dmm_api_service = DMMAPIService()