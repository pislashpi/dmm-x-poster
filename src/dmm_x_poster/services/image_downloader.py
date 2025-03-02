"""
画像をダウンロードするサービスモジュール
"""
import os
import requests
import logging
from PIL import Image as PILImage
from io import BytesIO
from flask import current_app

from dmm_x_poster.db.models import db, Image, Product

logger = logging.getLogger(__name__)

class ImageDownloaderService:
    """画像をダウンロードするサービスクラス"""
    
    def __init__(self, app=None):
        self.images_folder = None
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """アプリケーションコンテキストから設定を初期化"""
        self.images_folder = os.path.join(app.root_path, app.config.get('IMAGES_FOLDER'))
        
        # 画像保存用フォルダがなければ作成
        if not os.path.exists(self.images_folder):
            os.makedirs(self.images_folder)
            logger.info(f"Created images folder: {self.images_folder}")
    
    def download_image(self, image_id):
        """指定されたIDの画像をダウンロード"""
        image = Image.query.get(image_id)
        if not image:
            logger.error(f"Image not found: {image_id}")
            return False
        
        # 画像がすでにダウンロード済みか確認
        if image.downloaded and image.local_path:
            app_root = current_app.root_path
            absolute_path = os.path.join(app_root, image.local_path)
            if os.path.exists(absolute_path):
                logger.info(f"Image already downloaded: {image_id} at {absolute_path}")
                return True
            else:
                logger.warning(f"Image marked as downloaded but file not found: {absolute_path}")
        
        try:
            # 画像タイプを取得
            image_type = getattr(image, 'image_type', 'sample')
            
            # 画像URLが実際にmp4ファイルかチェック
            is_mp4 = image.image_url and image.image_url.endswith('.mp4')
            
            # 動画の場合は特別処理
            if image_type == 'movie':
                # mp4ファイルURLの場合
                if is_mp4:
                    # 実際に動画をダウンロード
                    logger.info(f"Downloading movie {image_id} from URL: {image.image_url}")
                    response = requests.get(image.image_url, timeout=60)  # 動画は大きいので長めのタイムアウト
                    response.raise_for_status()
                    
                    # ファイル名を決定
                    filename = f"product_{image.product_id}_movie_{image.id}.mp4"
                    save_path = os.path.join(self.images_folder, filename)
                    
                    # 動画を保存
                    with open(save_path, 'wb') as f:
                        f.write(response.content)
                    
                    logger.info(f"Saved movie to: {save_path}")
                    
                    # データベースを更新
                    rel_path = os.path.join(current_app.config.get('IMAGES_FOLDER'), filename)
                    image.local_path = rel_path
                    image.downloaded = True
                    db.session.commit()
                    
                    return True
                else:
                    # mp4ファイルではない場合は参照情報として保存
                    filename = f"movie_ref_{image.product_id}_{image.id}.txt"
                    save_path = os.path.join(self.images_folder, filename)
                    
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write(image.image_url)
                    
                    rel_path = os.path.join(current_app.config.get('IMAGES_FOLDER'), filename)
                    image.local_path = rel_path
                    image.downloaded = True
                    db.session.commit()
                    
                    logger.info(f"Stored movie reference for image: {image_id}")
                    return True
            else:
                # 画像処理
                try:
                    img = PILImage.open(BytesIO(response.content))
                    
                    # 拡張子を取得
                    extension = img.format.lower() if img.format else 'jpg'
                    
                    # ファイル名を決定
                    if image_type == 'package':
                        filename = f"product_{image.product_id}_package_{image.id}.{extension}"
                    else:
                        filename = f"product_{image.product_id}_image_{image.id}.{extension}"
                        
                    # 保存先のフルパス
                    save_path = os.path.join(self.images_folder, filename)
                    
                    # 画像を保存
                    img.save(save_path)
                    logger.info(f"Saved image to: {save_path}")
                    
                    # データベースを更新
                    rel_path = os.path.join(current_app.config.get('IMAGES_FOLDER'), filename)
                    image.local_path = rel_path
                    image.downloaded = True
                    db.session.commit()
                    
                    # 保存確認
                    abs_path = os.path.join(current_app.root_path, rel_path)
                    if os.path.exists(abs_path):
                        logger.info(f"Confirmed image file exists at: {abs_path}")
                        return True
                    else:
                        logger.error(f"Failed to save image file at: {abs_path}")
                        return False
                except Exception as e:
                    logger.error(f"Error processing image: {e}")
                    return False
                
        except requests.RequestException as e:
            logger.error(f"Failed to download {image_type} {image_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error processing {image_type} {image_id}: {e}")
            return False
    
    def download_selected_images(self, product_id):
        """選択された画像をダウンロード"""
        images = Image.query.filter_by(product_id=product_id, selected=True).all()
        success_count = 0
        
        for image in images:
            if self.download_image(image.id):
                success_count += 1
        
        return success_count
    
    def download_package_image(self, product_id):
        """パッケージ画像をダウンロード"""
        product = Product.query.get(product_id)
        if not product or not product.package_image_url:
            logger.error(f"Product not found or no package image: {product_id}")
            return False
        
        try:
            # 画像URLから取得
            response = requests.get(product.package_image_url, timeout=10)
            response.raise_for_status()
            
            # 画像形式を検証
            img = PILImage.open(BytesIO(response.content))
            
            # 保存先パスを生成
            filename = f"product_{product_id}_package.{img.format.lower()}"
            save_path = os.path.join(self.images_folder, filename)
            
            # 画像を保存
            img.save(save_path)
            
            # データベースを更新（パッケージ画像用の項目がないため、新しいImageレコードを作成）
            image = Image(
                product_id=product_id,
                image_url=product.package_image_url,
                local_path=os.path.join(current_app.config.get('IMAGES_FOLDER'), filename),
                downloaded=True
            )
            db.session.add(image)
            db.session.commit()
            
            logger.info(f"Downloaded package image for product: {product_id}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Failed to download package image for product {product_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error processing package image for product {product_id}: {e}")
            return False


# アプリケーションファクトリで初期化するためのインスタンス
image_downloader_service = ImageDownloaderService()