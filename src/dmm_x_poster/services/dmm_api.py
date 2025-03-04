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
    
    def search_items(self, floor='videoa', sort='date', offset=1, **kwargs):
        """商品検索を実行
        
        Args:
            floor (str): 検索対象のフロア（'videoa', 'videoc'など）
            sort (str): 並び順（'date'=新着順, 'rank'=人気順, '+price'=価格が安い順, '-price'=価格が高い順）
            offset (int): 検索結果の開始位置（1〜1000）
            **kwargs: その他の検索オプション
        
        Returns:
            list: 検索結果のアイテムリスト
        """
        # 基本パラメータ
        params = self.get_params(floor=floor, sort=sort, offset=offset)
        
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
            total_count = data['result'].get('total_count', 0)
            result_count = data['result'].get('result_count', 0)
            first_position = data['result'].get('first_position', offset)
            
            logger.info(f"API returned {item_count} items (total: {total_count}, result: {result_count}, position: {first_position})")
            
            # アイテム情報のデバッグログ
            for idx, item in enumerate(data['result']['items']):
                has_movie = 'sampleMovieURL' in item
                logger.debug(f"商品 #{idx+1} ({item.get('content_id', 'unknown')}): " +
                            f"動画情報あり={has_movie}")
                
                # アフィリエイトURL情報をログに記録
                logger.debug(f"  URL: {item.get('URL', 'N/A')}")
                logger.debug(f"  AffiliateURL: {item.get('affiliateURL', 'N/A')}")
                
                if has_movie:
                    available_sizes = []
                    movie_sizes = ['size_720_480', 'size_644_414', 'size_560_360', 'size_476_306']
                    for size in movie_sizes:
                        if size in item['sampleMovieURL'] and item['sampleMovieURL'][size]:
                            available_sizes.append(size)
                    
                    logger.debug(f"  利用可能な動画サイズ: {', '.join(available_sizes) if available_sizes else 'なし'}")
            
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
    
    def get_request_params(self):
        """リクエスト共通パラメータ（クッキーとヘッダー）を返す"""
        return {
            'cookies': {"age_check_done": "1"},
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            },
            'timeout': 15
        }

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
                    url=item.get('affiliateURL') if item.get('affiliateURL') else item.get('URL'),  # affiliateURLを優先、なければURLを使用
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
                if 'URL' in item:  # affiliateURLを使用
                    affiliate_url = item['URL']
                    logger.info(f"Extracting video URL from product page: {affiliate_url}")
                    
                    # 商品ページから動画URLを抽出
                    video_url = self.extract_video_url_from_page(affiliate_url)
                    
                    if video_url:
                        # 動画URLを保存
                        movie = Image(
                            product_id=product.id,
                            image_url=video_url,
                            image_type='movie',
                            created_at=datetime.now(JST)
                        )
                        db.session.add(movie)
                        logger.info(f"Added video URL from product page: {video_url}")
                
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
    
    def _modify_video_url(self, video_url):
        """動画URLを_dm_w.mp4形式に変換"""
        if video_url and video_url.endswith('.mp4'):
            # .mp4の前に_dm_wを挿入
            modified_url = video_url.replace('.mp4', '_dm_w.mp4')
            logger.debug(f"Modified video URL from {video_url} to {modified_url}")
            return modified_url
        return video_url

    def extract_video_url_from_page(self, page_url):
        """商品詳細ページから動画URLを抽出"""
        try:
            import requests
            from bs4 import BeautifulSoup
            import re
            import json
            
            logger.info(f"Attempting to extract video URL from page: {page_url}")
            
            # リクエストパラメータを取得
            request_params = self.get_request_params()
            
            # ページのHTMLを取得（年齢認証クッキー付き）
            response = requests.get(
                page_url, 
                cookies=request_params['cookies'],
                headers=request_params['headers'],
                timeout=request_params['timeout']
            )
            response.raise_for_status()
            
            # デバッグ用に最初の数バイトを記録
            logger.info(f"Response received, length: {len(response.text)} bytes")
            
            # HTMLをパース
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 年齢認証ページかどうかチェック
            if "年齢確認" in response.text and "あなたは18歳以上ですか" in response.text:
                logger.warning("Age verification page detected instead of product page")
                return None
            
            # JSONLDを探す（最も信頼性の高い方法）
            jsonld_scripts = soup.find_all('script', type='application/ld+json')
            logger.debug(f"Found {len(jsonld_scripts)} JSONLD scripts")
            
            for script in jsonld_scripts:
                if not script.string:
                    continue
                    
                try:
                    data = json.loads(script.string)
                    # Product構造体かチェック
                    if isinstance(data, dict) and data.get('@type') == 'Product':
                        logger.debug("Found Product type in JSONLD")
                        # subjectOf内のVideoObjectを確認
                        if 'subjectOf' in data and data['subjectOf'].get('@type') == 'VideoObject':
                            logger.debug("Found VideoObject in JSONLD")
                            content_url = data['subjectOf'].get('contentUrl')
                            if content_url and 'cc3001.dmm.co.jp/litevideo' in content_url:
                                # 動画URLが見つかったら、_dm_w.mp4形式に変換して返す
                                modified_url = self._modify_video_url(content_url)
                                logger.info(f"Found video URL in JSONLD: {modified_url}")
                                return modified_url
                except Exception as e:
                    logger.error(f"Error parsing JSONLD: {e}")
            
            # 全スクリプトタグを調査（バックアップ方法）
            script_count = len(soup.find_all('script'))
            logger.debug(f"Searching through {script_count} script tags")

            for script in soup.find_all('script'):
                if not script.string:
                    continue
                    
                # cc3001.dmm.co.jp/litevideo のパターンを探す
                if script.string and 'cc3001.dmm.co.jp/litevideo' in script.string:
                    logger.debug("Found script with litevideo reference")
                
                # 正規表現で動画URLを検索
                patterns = [
                    r'contentUrl[\s:"\']+([^"\']+cc3001\.dmm\.co\.jp/litevideo/[^"\']+\.mp4)["\']',
                    r'(https://cc3001\.dmm\.co\.jp/litevideo/freepv/[^\'"]+\.mp4)',
                    r'(https?://cc3001\.dmm\.co\.jp/litevideo/[^\'"]+\.mp4)'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, script.string)
                    if match:
                        video_url = match.group(1)
                        # 動画URLを変換して返す
                        modified_url = self._modify_video_url(video_url)
                        logger.info(f"Found video URL in script: {modified_url}")
                        return modified_url
            
            # HTMLソース全体で検索（最後の手段）
            if 'cc3001.dmm.co.jp/litevideo' in response.text:
                broader_match = re.search(r'(https://cc3001\.dmm\.co\.jp/litevideo/[^\'"]+\.mp4)', response.text)
                if broader_match:
                    video_url = broader_match.group(1)
                    # 動画URLを変換して返す
                    modified_url = self._modify_video_url(video_url)
                    logger.info(f"Found video URL with broader search: {modified_url}")
                    return modified_url
            
            logger.warning("No video URL found in product page")
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