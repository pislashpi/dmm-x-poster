"""
画像ダウンローダーサービスのテスト
"""
import os
import pytest
from io import BytesIO
from unittest.mock import MagicMock, patch
from PIL import Image as PILImage

from dmm_x_poster.services.image_downloader import ImageDownloaderService
from dmm_x_poster.db.models import Image


class TestImageDownloaderService:
    """画像ダウンローダーサービスのテストクラス"""
    
    def test_init_app(self, app, tmpdir):
        """init_appメソッドが設定を正しく読み込みディレクトリを作成するかテスト"""
        # 一時ディレクトリのパスを設定
        test_images_dir = os.path.join(tmpdir, "test_images")
        app.config['IMAGES_FOLDER'] = test_images_dir
        
        # ディレクトリが存在しないことを確認
        assert not os.path.exists(test_images_dir)
        
        service = ImageDownloaderService()
        service.init_app(app)
        
        # ディレクトリが作成されたか確認
        assert os.path.exists(test_images_dir)
        assert service.images_folder == os.path.join(app.root_path, test_images_dir)
    
    def test_download_image(self, app, db, sample_product, tmpdir):
        """download_imageメソッドが画像を正しくダウンロードするかテスト"""
        # テスト用画像を作成
        image = Image(
            product_id=sample_product.id,
            image_url="https://example.com/images/test.jpg",
            downloaded=False
        )
        db.session.add(image)
        db.session.commit()
        
        # 一時ディレクトリのパスを設定
        test_images_dir = os.path.join(tmpdir, "test_images")
        os.makedirs(test_images_dir, exist_ok=True)
        app.config['IMAGES_FOLDER'] = test_images_dir
        
        # リクエストとPIL画像のモック
        with patch('dmm_x_poster.services.image_downloader.requests.get') as mock_get:
            # モックレスポンスの作成
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            
            # テスト用のPNG画像データを生成
            test_image = PILImage.new('RGB', (100, 100), color='red')
            img_bytes = BytesIO()
            test_image.save(img_bytes, format='JPEG')
            img_bytes.seek(0)
            
            mock_response.content = img_bytes.getvalue()
            mock_get.return_value = mock_response
            
            # PILImage.openのモック
            with patch('dmm_x_poster.services.image_downloader.PILImage.open') as mock_pil_open:
                mock_image = MagicMock()
                mock_image.format = 'JPEG'
                mock_pil_open.return_value = mock_image
                
                service = ImageDownloaderService()
                service.images_folder = test_images_dir
                
                # 画像ダウンロードを実行
                result = service.download_image(image.id)
                
                # 結果の検証
                assert result is True
                
                # モックの検証
                mock_get.assert_called_once_with(image.image_url, timeout=10)
                mock_pil_open.assert_called_once()
                mock_image.save.assert_called_once()
                
                # データベースが更新されたか
                db.session.refresh(image)
                assert image.downloaded is True
                assert image.local_path is not None
                assert os.path.basename(image.local_path).startswith(f"product_{sample_product.id}_image_{image.id}")
    
    def test_download_image_already_downloaded(self, app, db, sample_product, tmpdir):
        """すでにダウンロード済みの画像の場合のdownload_imageメソッドをテスト"""
        # テスト用の画像ファイルパス
        test_images_dir = os.path.join(tmpdir, "test_images")
        os.makedirs(test_images_dir, exist_ok=True)
        app.config['IMAGES_FOLDER'] = test_images_dir
        local_path = os.path.join(app.config['IMAGES_FOLDER'], f"product_1_image_1.jpg")
        
        # テスト用の空ファイルを作成
        with open(os.path.join(test_images_dir, os.path.basename(local_path)), 'w') as f:
            f.write('')
        
        # ダウンロード済み画像を作成
        image = Image(
            product_id=sample_product.id,
            image_url="https://example.com/images/test.jpg",
            local_path=local_path,
            downloaded=True
        )
        db.session.add(image)
        db.session.commit()
        
        # リクエストのモックは不要（呼び出されないはず）
        service = ImageDownloaderService()
        service.images_folder = test_images_dir
        
        with patch('dmm_x_poster.services.image_downloader.os.path.exists') as mock_exists:
            # ファイルが存在するように設定
            mock_exists.return_value = True
            
            # ダウンロードを実行
            result = service.download_image(image.id)
            
            # 結果の検証
            assert result is True
            
            # ファイルの存在チェックが行われたか
            mock_exists.assert_called_once_with(image.local_path)
    
    def test_download_image_not_found(self, app):
        """存在しない画像IDのdownload_imageメソッドをテスト"""
        service = ImageDownloaderService()
        
        # 存在しないIDでダウンロードを実行
        result = service.download_image(99999)
        
        # 結果の検証
        assert result is False
    
    def test_download_image_request_error(self, app, db, sample_product):
        """リクエストエラー時のdownload_imageメソッドをテスト"""
        # テスト用画像を作成
        image = Image(
            product_id=sample_product.id,
            image_url="https://example.com/images/nonexistent.jpg",
            downloaded=False
        )
        db.session.add(image)
        db.session.commit()
        
        # リクエストのモック（例外発生）
        with patch('dmm_x_poster.services.image_downloader.requests.get') as mock_get:
            mock_get.side_effect = Exception("Connection error")
            
            service = ImageDownloaderService()
            
            # ダウンロードを実行
            result = service.download_image(image.id)
            
            # 結果の検証
            assert result is False
            
            # データベースが更新されていないか
            db.session.refresh(image)
            assert image.downloaded is False
            assert image.local_path is None
    
    def test_download_selected_images(self, app, db, sample_product, sample_images):
        """download_selected_imagesメソッドが選択された画像をダウンロードするかテスト"""
        # 選択済みの画像数を確認
        selected_images = Image.query.filter_by(
            product_id=sample_product.id,
            selected=True
        ).count()
        
        # 各画像のダウンロードをモック
        with patch.object(ImageDownloaderService, 'download_image') as mock_download:
            # 全て成功するよう設定
            mock_download.return_value = True
            
            service = ImageDownloaderService()
            
            # 選択済み画像をダウンロード
            count = service.download_selected_images(sample_product.id)
            
            # 結果の検証
            assert count == selected_images
            assert mock_download.call_count == selected_images
    
    def test_download_package_image(self, app, db, sample_product):
        """download_package_imageメソッドがパッケージ画像をダウンロードするかテスト"""
        # パッケージ画像URLを設定
        sample_product.package_image_url = "https://example.com/images/package.jpg"
        db.session.commit()
        
        # リクエストとPIL画像のモック
        with patch('dmm_x_poster.services.image_downloader.requests.get') as mock_get:
            # モックレスポンスの作成
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            
            # テスト用のPNG画像データを生成
            test_image = PILImage.new('RGB', (100, 100), color='red')
            img_bytes = BytesIO()
            test_image.save(img_bytes, format='JPEG')
            img_bytes.seek(0)
            
            mock_response.content = img_bytes.getvalue()
            mock_get.return_value = mock_response
            
            # PILImage.openのモック
            with patch('dmm_x_poster.services.image_downloader.PILImage.open') as mock_pil_open:
                mock_image = MagicMock()
                mock_image.format = 'JPEG'
                mock_pil_open.return_value = mock_image
                
                service = ImageDownloaderService()
                service.images_folder = app.config['IMAGES_FOLDER']
                
                # パッケージ画像ダウンロードを実行
                result = service.download_package_image(sample_product.id)
                
                # 結果の検証
                assert result is True
                
                # モックの検証
                mock_get.assert_called_once_with(sample_product.package_image_url, timeout=10)
                mock_pil_open.assert_called_once()
                mock_image.save.assert_called_once()
                
                # 新しいImageレコードが作成されたか
                package_image = Image.query.filter_by(
                    product_id=sample_product.id,
                    image_url=sample_product.package_image_url
                ).first()
                
                assert package_image is not None
                assert package_image.downloaded is True
                assert package_image.local_path is not None
                assert f"product_{sample_product.id}_package" in package_image.local_path
    
    def test_download_package_image_no_url(self, app, db, sample_product):
        """パッケージ画像URLがない場合のdownload_package_imageメソッドをテスト"""
        # パッケージ画像URLを空に設定
        sample_product.package_image_url = None
        db.session.commit()
        
        service = ImageDownloaderService()
        
        # パッケージ画像ダウンロードを実行
        result = service.download_package_image(sample_product.id)
        
        # 結果の検証
        assert result is False
        
        # 新しいImageレコードが作成されていないか
        package_image = Image.query.filter_by(
            product_id=sample_product.id,
            image_url=None
        ).first()
        
        assert package_image is None