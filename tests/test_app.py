"""
メインアプリケーションのテスト
"""
import pytest
from flask import url_for
from flask.testing import FlaskClient


def test_index_page(client: FlaskClient):
    """ホームページが正常に表示されるかテスト"""
    response = client.get('/')
    assert response.status_code == 200
    assert b"DMM X\xe8\x87\xaa\xe5\x8b\x95\xe6\x8a\x95\xe7\xa8\xbf\xe3\x82\xb7\xe3\x82\xb9\xe3\x83\x86\xe3\x83\xa0" in response.data  # "DMM X自動投稿システム" in UTF-8


def test_products_page(client: FlaskClient):
    """商品一覧ページが正常に表示されるかテスト"""
    response = client.get('/products')
    assert response.status_code == 200
    assert b"\xe5\x95\x86\xe5\x93\x81\xe4\xb8\x80\xe8\xa6\xa7" in response.data  # "商品一覧" in UTF-8


def test_posts_page(client: FlaskClient):
    """投稿一覧ページが正常に表示されるかテスト"""
    response = client.get('/posts')
    assert response.status_code == 200
    assert b"\xe6\x8a\x95\xe7\xa8\xbf\xe7\xae\xa1\xe7\x90\x86" in response.data  # "投稿管理" in UTF-8


def test_product_detail_page(client: FlaskClient, sample_product):
    """商品詳細ページが正常に表示されるかテスト"""
    response = client.get(f'/products/{sample_product.id}')
    assert response.status_code == 200
    assert sample_product.title.encode('utf-8') in response.data


def test_product_detail_not_found(client: FlaskClient):
    """存在しない商品IDへのアクセスで404エラーになるかテスト"""
    response = client.get('/products/999999')
    assert response.status_code == 404


def test_fetch_new_products(client: FlaskClient, mocker):
    """新商品取得機能のテスト（APIモック）"""
    # DMM API サービスのfetch_and_save_new_itemsメソッドをモック
    mock_fetch = mocker.patch('dmm_x_poster.services.dmm_api.dmm_api_service.fetch_and_save_new_items')
    mock_fetch.return_value = 5  # 5件取得したと仮定
    
    response = client.post('/fetch_new', data={'hits': '20'})
    
    # リダイレクトされるか
    assert response.status_code == 302
    # モックが呼び出されたか
    mock_fetch.assert_called_once_with(floor='dvd', hits=20)


def test_select_images(client: FlaskClient, sample_product, sample_images, mocker):
    """画像選択機能のテスト"""
    # 画像ダウンロードサービスをモック
    mock_download = mocker.patch('dmm_x_poster.services.image_downloader.image_downloader_service.download_selected_images')
    mock_download.return_value = 4  # 4枚ダウンロードしたと仮定
    
    # 選択する画像IDを準備
    selected_image_ids = [image.id for image in sample_images[:3]]  # 最初の3枚を選択
    
    # フォーム送信
    response = client.post(
        f'/products/{sample_product.id}/select_images',
        data={'selected_images': selected_image_ids},
        follow_redirects=True
    )
    
    assert response.status_code == 200
    assert b"\xe7\x94\xbb\xe5\x83\x8f\xe3\x81\xae\xe9\x81\xb8\xe6\x8a\x9e\xe3\x82\x92\xe4\xbf\x9d\xe5\xad\x98\xe3\x81\x97\xe3\x81\xbe\xe3\x81\x97\xe3\x81\x9f" in response.data  # "画像の選択を保存しました" in UTF-8
    
    # モックが呼び出されたか
    mock_download.assert_called_once_with(sample_product.id)


def test_create_post(client: FlaskClient, sample_product, sample_images, mocker):
    """投稿作成機能のテスト"""
    # スケジューラサービスをモック
    mock_create_post = mocker.patch('dmm_x_poster.services.scheduler.scheduler_service.create_post')
    mock_post = mocker.MagicMock()
    mock_post.id = 1
    mock_create_post.return_value = mock_post  # 投稿が作成されたと仮定
    
    # フォーム送信
    response = client.post(
        f'/products/{sample_product.id}/create_post',
        follow_redirects=True
    )
    
    assert response.status_code == 200
    assert b"\xe6\x8a\x95\xe7\xa8\xbf\xe3\x81\x8c\xe3\x82\xb9\xe3\x82\xb1\xe3\x82\xb8\xe3\x83\xa5\xe3\x83\xbc\xe3\x83\xab\xe3\x81\x95\xe3\x82\x8c\xe3\x81\xbe\xe3\x81\x97\xe3\x81\x9f" in response.data  # "投稿がスケジュールされました" in UTF-8
    
    # モックが呼び出されたか
    mock_create_post.assert_called_once_with(sample_product.id)


def test_404_error(client: FlaskClient):
    """404エラーページが正常に表示されるかテスト"""
    response = client.get('/non_existent_page')
    assert response.status_code == 404
    assert b"404" in response.data
    assert b"\xe3\x83\x9a\xe3\x83\xbc\xe3\x82\xb8\xe3\x81\x8c\xe8\xa6\x8b\xe3\x81\xa4\xe3\x81\x8b\xe3\x82\x8a\xe3\x81\xbe\xe3\x81\x9b\xe3\x82\x93" in response.data  # "ページが見つかりません" in UTF-8