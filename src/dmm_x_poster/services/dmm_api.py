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
    
    def search_items(self, floor='videoa', sort='date', **kwargs):
        """商品検索を実行"""
        # 基本パラメータ
        params = self.get_params(floor=floor, sort=sort)
        
        # 複数ジャンルの処理
        if 'article_genre' in kwargs and kwargs['article_genre']:
            genre_ids = kwargs.pop('article_genre')
            for i, genre_id in enumerate(genre_ids):
                params[f'article[{i}]'] = 'genre'
                params[f'article_id[{i}]'] = genre_id
        
        # 複数女優の処理
        elif 'article_actress' in kwargs and kwargs['article_actress']:
            actress_ids = kwargs.pop('article_actress')
            for i, actress_id in enumerate(actress_ids):
                params[f'article[{i}]'] = 'actress'
                params[f'article_id[{i}]'] = actress_id
        
        # 日付フィルターの処理 (YYYY-MM-DDT00:00:00 形式)
        if 'lte_date' in kwargs:
            params['lte_date'] = kwargs.pop('lte_date')
            logger.info(f"Filtering for items released on or before: {params['lte_date']}")
        if 'gte_date' in kwargs:
            params['gte_date'] = kwargs.pop('gte_date')
            logger.info(f"Filtering for items released on or after: {params['gte_date']}")
        
        # その他のパラメータを追加
        for key, value in kwargs.items():
            if key not in ['article_genre', 'article_actress']:
                params[key] = value
        
        url = f"{self.BASE_URL}?{urlencode(params)}"
        logger.info(f"DMM API request URL: {url}")
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            # レスポンスのフォーマットチェック
            if 'result' not in data or 'items' not in data['result']:
                logger.error(f"Unexpected API response format: {data}")
                return []
            
            # 結果件数をログに記録
            item_count = len(data['result']['items'])
            logger.info(f"API returned {item_count} items")
            
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
                
                # サンプルムービーを保存
                if 'samplemovieURL' in item:
                    # 利用可能なサイズを優先順位で試す
                    movie_sizes = ['size_720_480', 'size_644_414', 'size_560_360', 'size_476_306']
                    
                    for size in movie_sizes:
                        if size in item['samplemovieURL'] and item['samplemovieURL'][size]:
                            movie_page_url = item['samplemovieURL'][size]
                            
                            if movie_page_url:  # URLが存在するか確認
                                logger.info(f"Found movie page URL: {movie_page_url}")
                                
                                # 実際の動画ファイルURLを抽出
                                real_video_url = self.extract_video_url_from_page(movie_page_url)
                                
                                if real_video_url:
                                    movie = Image(
                                        product_id=product.id,
                                        image_url=real_video_url,  # 実際のmp4ファイルURLを保存
                                        image_type='movie',
                                        created_at=datetime.now(JST)
                                    )
                                    db.session.add(movie)
                                    logger.info(f"Added real movie URL: {real_video_url}")
                                else:
                                    # 実際のURLが取得できなかった場合は、ページURLを保存
                                    movie = Image(
                                        product_id=product.id,
                                        image_url=movie_page_url,
                                        image_type='movie',
                                        created_at=datetime.now(JST)
                                    )
                                    db.session.add(movie)
                                    logger.info(f"Added movie page URL as fallback: {movie_page_url}")
                                
                                # 最初のサイズが見つかれば十分
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
    
    def extract_video_url_from_page(self, page_url):
        """商品詳細ページから動画URLを抽出"""
        try:
            import requests
            from bs4 import BeautifulSoup
            import re
            
            logger.info(f"Attempting to extract video URL from page: {page_url}")
            
            # ページのHTMLを取得
            response = requests.get(page_url, timeout=15)
            response.raise_for_status()
            
            # デバッグ用に最初の数バイトを記録
            logger.info(f"Response received, length: {len(response.text)} bytes")
            logger.info(f"First 100 chars: {response.text[:100]}")
            
            # HTMLをパース
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 全スクリプトタグを調査
            script_count = 0
            for script in soup.find_all('script'):
                script_count += 1
                if script.string:
                    # cc3001.dmm.co.jp/litevideo のパターンを探す
                    if 'cc3001.dmm.co.jp/litevideo' in script.string:
                        # デバッグ用に部分的にスクリプト内容を表示
                        snippet = script.string[:100] + "..." if len(script.string) > 100 else script.string
                        logger.info(f"Found potential script with video URL reference: {snippet}")
                    
                    # 正規表現で動画URLを検索
                    patterns = [
                        r'(https://cc3001\.dmm\.co\.jp/litevideo/freepv/[^\'"]+\.mp4)',
                        r'(https?://.*?\.mp4)'
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, script.string)
                        if match:
                            video_url = match.group(1)
                            logger.info(f"Found video URL: {video_url}")
                            return video_url
            
            logger.warning(f"No video URL found in page, searched {script_count} script tags")
            
            # htmlソースをざっと確認
            if 'cc3001.dmm.co.jp/litevideo' in response.text:
                logger.info("Found video URL pattern in HTML, but couldn't extract it properly")
                
                # より広範な検索を実行
                broader_match = re.search(r'(https://cc3001\.dmm\.co\.jp/litevideo/[^\'"]+\.mp4)', response.text)
                if broader_match:
                    video_url = broader_match.group(1)
                    logger.info(f"Found video URL with broader search: {video_url}")
                    return video_url
                    
            return None
        except Exception as e:
            logger.error(f"Error extracting video URL from {page_url}: {e}")
            return None

    def fetch_and_save_new_items(self, **kwargs):
        """新しい商品を取得して保存"""
        items = self.search_items(**kwargs)
        return self.save_items_to_db(items)


# アプリケーションファクトリで初期化するためのインスタンス
dmm_api_service = DMMAPIService()