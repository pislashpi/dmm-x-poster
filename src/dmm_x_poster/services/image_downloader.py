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
        
        if image.downloaded and image.local_path and os.path.exists(os.path.join(current_app.root_path, image.local_path)):
            logger.info(f"Image already downloaded: {image_id}")
            return True
        
        try:
            # 画像タイプに応じた処理
            image_type = getattr(image, 'image_type', 'sample')
            
            # 動画の場合は特別処理
            if image_type == 'movie':
                # 動画の場合はURLを保存するだけ（実際のダウンロードはしない）
                # 保存先パスを生成（実際にはファイルは保存しない）
                filename = f"product_{image.product_id}_movie_{image.id}.mp4"
                save_path = os.path.join(self.images_folder, filename)
                
                # データベースを更新
                image.local_path = os.path.join(current_app.config.get('IMAGES_FOLDER'), filename)
                image.downloaded = True  # ダウンロード済みとマーク
                db.session.commit()
                
                logger.info(f"Stored movie URL for image: {image_id}")
                return True
            else:
                # 画像URLから取得
                logger.info(f"Downloading image {image_id} from URL: {image.image_url}")
                response = requests.get(image.image_url, timeout=10)
                response.raise_for_status()
                
                # 画像形式を検証
                img = PILImage.open(BytesIO(response.content))
                
                # 保存先パスを生成
                extension = img.format.lower() if img.format else 'jpg'
                if image_type == 'package':
                    filename = f"product_{image.product_id}_package_{image.id}.{extension}"
                else:
                    filename = f"product_{image.product_id}_image_{image.id}.{extension}"
                    
                save_path = os.path.join(self.images_folder, filename)
                
                # 画像を保存
                img.save(save_path)
                logger.info(f"Saved image to: {save_path}")
                
                # データベースを更新
                image.local_path = os.path.join(current_app.config.get('IMAGES_FOLDER'), filename)
                image.downloaded = True
                db.session.commit()
                
                # 保存されたことを確認
                if os.path.exists(save_path):
                    logger.info(f"Confirmed image file exists at: {save_path}")
                    return True
                else:
                    logger.error(f"Failed to save image file at: {save_path}")
                    return False
                
        except requests.RequestException as e:
            logger.error(f"Failed to download image {image_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error processing image {image_id}: {e}")
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