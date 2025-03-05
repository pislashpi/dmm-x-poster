"""
DMM X自動投稿システムのメインアプリケーション
"""
import logging
from pathlib import Path
from typing import Optional, Any, Dict, Union

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

from dmm_x_poster.config import JST
from dmm_x_poster.config import Config
from dmm_x_poster.db.models import db, Product, Image, Post, PostImage, Setting
from dmm_x_poster.services.dmm_api import dmm_api_service
from dmm_x_poster.services.twitter_api import twitter_api_service
from dmm_x_poster.services.image_downloader import image_downloader_service
from dmm_x_poster.services.scheduler import scheduler_service

# ロギング設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# アプリケーション初期化時に設定テーブルを初期化
def init_settings(app):
    """設定テーブルの初期化"""
    try:
        with app.app_context():
            # 自動予約投稿設定（デフォルトはオン）
            if Setting.get('auto_schedule_enabled') is None:
                Setting.set(
                    'auto_schedule_enabled', 
                    'true',
                    '自動予約投稿機能の有効/無効'
                )
                logger.info("Initialized settings: auto_schedule_enabled=true")
    except Exception as e:
        # テーブルが存在しない場合など、初期化中にエラーが発生した場合はログを残す
        logger.warning(f"Settings initialization skipped: {e}")

def create_app(config_class: Optional[Any] = None) -> Flask:
    """アプリケーションファクトリ関数

    Args:
        config_class: 設定クラス（デフォルトはConfig）

    Returns:
        Flask: Flaskアプリケーションインスタンス
    """
    app = Flask(__name__)
    
    # 設定がなければデフォルト設定を使用
    if config_class is None:
        config_class = Config
    
    app.config.from_object(config_class)
    
    # データベース初期化
    db.init_app(app)
    migrate = Migrate(app, db)
    
    # サービス初期化
    dmm_api_service.init_app(app)
    twitter_api_service.init_app(app)
    image_downloader_service.init_app(app)
    scheduler_service.init_app(app)
    
    # 静的ファイルディレクトリを確認・作成
    images_dir = Path(app.root_path) / app.config.get('IMAGES_FOLDER', 'static/images')
    if not images_dir.exists():
        images_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created images directory: {images_dir}")
    
    # バックグラウンドタスクのセットアップ
    scheduler = BackgroundScheduler(timezone='Asia/Tokyo')
    
    # 毎時実行: スケジュールされた投稿を処理
    scheduler.add_job(
        func=lambda: process_scheduled_posts(app),
        trigger='interval',
        minutes=15,
        id='process_posts'
    )
    
    # 毎日実行: 新しい商品を取得
    scheduler.add_job(
        func=lambda: fetch_new_products(app),
        trigger='cron',
        hour=3,  # 毎日3時
        id='fetch_products'
    )
    
    # 毎日実行: 投稿スケジュールを作成
    scheduler.add_job(
        func=lambda: schedule_posts(app),
        trigger='cron',
        hour=4,  # 毎日4時
        id='schedule_posts'
    )
    
    scheduler.start()
    
    # ルート定義を含める
    register_routes(app)
    
    # エラーハンドラーを登録
    register_error_handlers(app)
    
    # 設定の初期化 - appコンテキスト内で実行
    with app.app_context():
        init_settings(app)

    return app


def register_routes(app: Flask) -> None:
    """アプリケーションにルートを登録する

    Args:
        app: Flaskアプリケーションインスタンス
    """
    
    @app.route('/')
    def index():
        """ホームページ"""
        # 最近追加された商品
        recent_products = Product.query.order_by(
            Product.fetched_at.desc()
        ).limit(10).all()
        
        # 次の予定投稿
        next_posts = Post.query.filter_by(
            status='scheduled'
        ).order_by(Post.scheduled_at).limit(5).all()
        
        # 最近の投稿
        recent_posts = Post.query.filter_by(
            status='posted'
        ).order_by(Post.posted_at.desc()).limit(5).all()
        
        return render_template(
            'index.html',
            recent_products=recent_products,
            next_posts=next_posts,
            recent_posts=recent_posts
        )
    
    @app.route('/settings', methods=['GET'])
    def settings():
        """システム設定画面を表示"""
        # すべての設定を取得
        all_settings = Setting.query.all()
        
        # 辞書形式に変換
        settings_dict = {s.key: s.value for s in all_settings}
        
        # フラッシュメッセージがあれば取得
        success_message = request.args.get('success')
        
        return render_template(
            'settings.html',
            settings=settings_dict,
            success_message=success_message
        )

    @app.route('/settings/update', methods=['POST'])
    def update_settings():
        """システム設定を更新"""
        # 自動予約投稿設定
        auto_schedule_enabled = 'true' if request.form.get('auto_schedule_enabled') else 'false'
        Setting.set('auto_schedule_enabled', auto_schedule_enabled, '自動予約投稿機能の有効/無効')
        
        flash('設定を更新しました', 'success')
        return redirect(url_for('settings', success='設定を保存しました'))


    @app.route('/products')
    def products():
        """商品一覧"""
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # 検索フィルター
        query = Product.query
        
        # キーワード検索
        keyword = request.args.get('keyword', '')
        if keyword:
            query = query.filter(Product.title.like(f'%{keyword}%'))
        
        # 発売状況によるフィルター
        release_status = request.args.get('release_status', 'all')
        today = datetime.now(JST).date()
        if release_status == 'released':
            # 発売済み商品（発売日が今日以前）
            query = query.filter(Product.release_date <= today)
        elif release_status == 'preorder':
            # 予約商品（発売日が今日より後）
            query = query.filter(Product.release_date > today)
        
        # お気に入りのみフィルター
        favorite_only = request.args.get('favorite_only') == 'true'
        if favorite_only:
            query = query.filter(Product.is_favorite == True)
        
        # ジャンルによるフィルター
        genres_str = request.args.get('genres', '')
        if genres_str:
            genres_list = [genre.strip() for genre in genres_str.split(',') if genre.strip()]
            # 複数ジャンルでAND検索
            for genre in genres_list:
                query = query.filter(Product.genres.like(f'%{genre}%'))
        
        # 女優名によるフィルター（新機能）
        actress_str = request.args.get('actress', '')
        if actress_str:
            actresses_list = [actress.strip() for actress in actress_str.split(',') if actress.strip()]
            # 複数女優でAND検索
            for actress in actresses_list:
                query = query.filter(Product.actresses.like(f'%{actress}%'))
        
        # 並び替え
        sort = request.args.get('sort', 'latest')
        if sort == 'latest':
            query = query.order_by(Product.fetched_at.desc())
        elif sort == 'title':
            query = query.order_by(Product.title)
        elif sort == 'release':
            query = query.order_by(Product.release_date.desc())
        
        # ページネーション
        products = query.paginate(page=page, per_page=per_page)
        
        return render_template(
            'products.html',
            products=products,
            keyword=keyword,
            sort=sort,
            release_status=release_status,
            genres_str=genres_str,
            actress_str=actress_str,  # 新しいパラメータを追加
            favorite_only=favorite_only
        )
    
    def favorites():
        """お気に入り商品一覧"""
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # お気に入り商品のみ取得
        query = Product.query.filter_by(is_favorite=True)
        
        # キーワード検索
        keyword = request.args.get('keyword', '')
        if keyword:
            query = query.filter(Product.title.like(f'%{keyword}%'))
        
        # ジャンルによるフィルター
        genres_str = request.args.get('genres', '')
        if genres_str:
            genres_list = [genre.strip() for genre in genres_str.split(',') if genre.strip()]
            # 複数ジャンルでAND検索
            for genre in genres_list:
                query = query.filter(Product.genres.like(f'%{genre}%'))
        
        # 女優名によるフィルター（新機能）
        actress_str = request.args.get('actress', '')
        if actress_str:
            actresses_list = [actress.strip() for actress in actress_str.split(',') if actress.strip()]
            # 複数女優でAND検索
            for actress in actresses_list:
                query = query.filter(Product.actresses.like(f'%{actress}%'))
        
        # 並び替え
        sort = request.args.get('sort', 'latest')
        if sort == 'latest':
            query = query.order_by(Product.fetched_at.desc())
        elif sort == 'title':
            query = query.order_by(Product.title)
        elif sort == 'release':
            query = query.order_by(Product.release_date.desc())
        
        # ページネーション
        products = query.paginate(page=page, per_page=per_page)
        
        return render_template(
            'favorites.html',
            products=products,
            keyword=keyword,
            sort=sort,
            genres_str=genres_str,
            actress_str=actress_str,  # 新しいパラメータを追加
        )
    
    @app.route('/products/<int:product_id>')
    def product_detail(product_id):
        """商品詳細"""
        product = db.session.get(Product, product_id)
        if not product:
            abort(404)
            
        images = Image.query.filter_by(product_id=product_id).all()
        selected_images = [img for img in images if img.selected]
        
        return render_template(
            'product_detail.html',
            product=product,
            images=images,
            selected_images=selected_images
        )
    
    @app.route('/products/<int:product_id>/select_images', methods=['POST'])
    def select_images(product_id):
        """画像選択処理"""
        product = db.session.get(Product, product_id)
        if not product:
            abort(404)
            
        # 既存の選択をリセット
        Image.query.filter_by(product_id=product_id).update({
            'selected': False,
            'selection_order': None
        })
        
        # 選択された画像IDの取得
        selected_ids = request.form.getlist('selected_images', type=int)
        
        # 最大4枚まで
        selected_ids = selected_ids[:4]
        
        # 選択状態を更新
        for i, image_id in enumerate(selected_ids):
            image = db.session.get(Image, image_id)
            if image and image.product_id == product_id:
                image.selected = True
                image.selection_order = i + 1
        
        db.session.commit()
        flash('画像の選択を保存しました', 'success')
        
        # 選択された画像をダウンロード
        image_downloader_service.download_selected_images(product_id)
        
        return redirect(url_for('product_detail', product_id=product_id))
    
    @app.route('/products/<int:product_id>/create_post', methods=['POST'])
    def create_post(product_id):
        """投稿を作成"""
        post_type = request.form.get('post_type', 'scheduled')
        scheduled_at = request.form.get('scheduled_at')
        custom_text = request.form.get('custom_text', '')
        
        # 選択された画像があるか確認
        product = db.session.get(Product, product_id)
        if not product or not product.get_selected_images():
            flash('投稿の作成に失敗しました。画像が選択されているか確認してください。', 'danger')
            return redirect(url_for('product_detail', product_id=product_id))
        
        if post_type == 'now':
            # 即時投稿
            post = scheduler_service.create_immediate_post(product_id, custom_text)
        else:
            # 予約投稿
            post = scheduler_service.create_post(product_id, scheduled_at, custom_text)
        
        if post:
            # 成功時
            product = db.session.get(Product, product_id)
            product.posted = True
            db.session.commit()
            
            if post_type == 'now':
                flash('投稿が完了しました', 'success')
            else:
                flash('投稿がスケジュールされました', 'success')
        else:
            # 失敗時
            flash('投稿の作成に失敗しました。システムログを確認してください。', 'danger')
        
        return redirect(url_for('product_detail', product_id=product_id))

    
    @app.route('/download_image/<int:image_id>')
    def download_image(image_id):
        """画像ダウンロード処理"""
        image = db.session.get(Image, image_id)
        if not image:
            abort(404)
            
        success = image_downloader_service.download_image(image_id)
        
        if success:
            flash('動画をダウンロードしました', 'success')
        else:
            flash('動画ダウンロードに失敗しました', 'danger')
        
        return redirect(url_for('product_detail', product_id=image.product_id))

    @app.route('/posts')
    def posts():
        """投稿一覧"""
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # 検索フィルター
        query = Post.query
        
        # ステータスフィルター
        status = request.args.get('status', '')
        if status:
            query = query.filter(Post.status == status)
        
        # 並び替え
        sort = request.args.get('sort', 'scheduled')
        if sort == 'scheduled':
            query = query.order_by(Post.scheduled_at)
        elif sort == 'posted':
            query = query.order_by(Post.posted_at.desc())
        
        # ページネーション
        posts = query.paginate(page=page, per_page=per_page)
        
        return render_template(
            'posts.html',
            posts=posts,
            status=status,
            sort=sort
        )
        
    @app.route('/posts/<int:post_id>')
    def post_detail(post_id):
        """投稿詳細"""
        post = db.session.get(Post, post_id)
        if not post:
            abort(404)
            
        images = post.get_images()
        
        return render_template(
            'post_detail.html',
            post=post,
            images=images
        )
        
    @app.route('/posts/<int:post_id>/delete', methods=['POST'])
    def delete_post(post_id):
        """投稿を削除"""
        post = db.session.get(Post, post_id)
        if not post:
            abort(404)
            
        # 投稿を削除
        db.session.delete(post)
        db.session.commit()
        
        flash('投稿が削除されました', 'success')
        return redirect(url_for('posts'))
        
    @app.route('/fetch_new', methods=['POST'])
    def fetch_new():
        """新しい商品を取得（手動）"""
        hits = request.form.get('hits', 20, type=int)
        floor = request.form.get('floor', 'videoa')
        release_status = request.form.get('release_status', 'released')  # デフォルトを発売済みに
        sort = request.form.get('sort', 'date')  # 追加：並び順
        offset = request.form.get('offset', 1, type=int)  # 追加：取得開始位置
        
        # ジャンルIDリスト取得
        genre_ids_str = request.form.get('genre_ids', '')
        genre_ids = [id.strip() for id in genre_ids_str.split(',') if id.strip()]
        
        # 女優IDリスト取得
        actress_ids_str = request.form.get('actress_ids', '')
        actress_ids = [id.strip() for id in actress_ids_str.split(',') if id.strip()]
        
        # APIパラメータの準備
        kwargs = {
            'floor': floor,
            'hits': hits,
            'service': 'digital',
            'sort': sort,  # 追加：並び順
            'offset': offset  # 追加：取得開始位置
        }
        
        # 発売ステータスに応じた日付フィルター追加
        # DMM APIの日付形式: YYYY-MM-DDT00:00:00
        today = datetime.now(JST).strftime('%Y-%m-%dT00:00:00')
        if release_status == 'released':
            # 発売済み作品（今日以前の発売日）
            kwargs['lte_date'] = today
        elif release_status == 'preorder':
            # 予約商品（今日より後の発売日）
            kwargs['gte_date'] = today
        # allの場合はフィルターなし
        
        # ジャンルIDの処理
        if genre_ids:
            kwargs['article_genre'] = genre_ids
        
        # 女優IDの処理
        if actress_ids:
            kwargs['article_actress'] = actress_ids
        
        logger.info(f"Fetching items with parameters: {kwargs}")
        count = dmm_api_service.fetch_and_save_new_items(**kwargs)
        
        flash(f'{count}件の新しい商品を取得しました', 'success')
        return redirect(url_for('index'))
    
    @app.route('/products/<int:product_id>/toggle_favorite', methods=['POST'])
    def toggle_favorite(product_id):
        """商品のお気に入り状態を切り替え"""
        product = db.session.get(Product, product_id)
        if not product:
            abort(404)
            
        # お気に入り状態を反転
        product.is_favorite = not product.is_favorite
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Ajaxリクエストの場合はJSON応答
            return jsonify({
                'success': True,
                'is_favorite': product.is_favorite
            })
        else:
            # 通常のフォーム送信の場合はリダイレクト
            if product.is_favorite:
                flash('お気に入りに追加しました', 'success')
            else:
                flash('お気に入りから削除しました', 'info')
            return redirect(url_for('product_detail', product_id=product_id))

    @app.route('/favorites')
    def favorites():
        """お気に入り商品一覧"""
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # お気に入り商品のみ取得
        query = Product.query.filter_by(is_favorite=True)
        
        # 並び替え
        sort = request.args.get('sort', 'latest')
        if sort == 'latest':
            query = query.order_by(Product.fetched_at.desc())
        elif sort == 'title':
            query = query.order_by(Product.title)
        elif sort == 'release':
            query = query.order_by(Product.release_date.desc())
        
        # ページネーション
        products = query.paginate(page=page, per_page=per_page)
        
        return render_template(
            'favorites.html',
            products=products,
            sort=sort
        )

    @app.route('/api/select_image', methods=['POST'])
    def api_select_image():
        """画像選択API（Ajax用）"""
        data = request.json
        image_id = data.get('image_id')
        selected = data.get('selected', True)
        
        image = db.session.get(Image, image_id)
        if not image:
            return jsonify({'success': False, 'error': 'Image not found'})
        
        # 選択状態を更新
        image.selected = selected
        
        # 選択順序を更新
        if selected:
            # すでに選択されている画像の数を取得
            count = Image.query.filter_by(
                product_id=image.product_id,
                selected=True
            ).count()
            
            image.selection_order = count + 1
        else:
            image.selection_order = None
        
        db.session.commit()
        
        return jsonify({'success': True})
    
    @app.route('/api/reorder_images', methods=['POST'])
    def api_reorder_images():
        """画像並べ替えAPI（Ajax用）"""
        data = request.json
        ordered_ids = data.get('image_ids', [])
        
        for i, image_id in enumerate(ordered_ids):
            image = db.session.get(Image, image_id)
            if image:
                image.selection_order = i + 1
        
        db.session.commit()
        
        return jsonify({'success': True})
    
    @app.route('/api/extract_jsonld')
    def api_extract_jsonld():
        """商品ページからJSONLDを抽出するAPI"""
        url = request.args.get('url')
        if not url:
            return jsonify({'error': 'URL parameter is required'})
        
        try:
            import requests
            from bs4 import BeautifulSoup
            import json
            
            # ページを取得
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            # HTMLをパース
            soup = BeautifulSoup(response.text, 'lxml')
            
            # JSONLDを検索
            jsonld_scripts = soup.find_all('script', type='application/ld+json')
            results = []
            
            for script in jsonld_scripts:
                try:
                    data = json.loads(script.string)
                    results.append(data)
                except:
                    results.append({'error': 'Invalid JSON', 'content': script.string[:100] + '...'})
            
            return jsonify({
                'count': len(results),
                'results': results
            })
        except Exception as e:
            return jsonify({'error': str(e)})


def register_error_handlers(app: Flask) -> None:
    """エラーハンドラーを登録する

    Args:
        app: Flaskアプリケーションインスタンス
    """
    
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Server error: {e}")
        return render_template('500.html'), 500


# バックグラウンドタスク関数
def process_scheduled_posts(app: Flask) -> None:
    """スケジュールされた投稿を処理"""
    with app.app_context():
        logger.info("Processing scheduled posts...")
        count = scheduler_service.process_scheduled_posts()
        logger.info(f"Processed {count} posts")


def fetch_new_products(app: Flask) -> None:
    """新しい商品を取得"""
    with app.app_context():
        logger.info("Fetching new products...")
        count = dmm_api_service.fetch_and_save_new_items()
        logger.info(f"Fetched {count} new products")


def schedule_posts(app: Flask) -> None:
    """投稿をスケジュール"""
    with app.app_context():
        logger.info("Scheduling posts...")
        count = scheduler_service.schedule_unposted_products()
        logger.info(f"Scheduled {count} new posts")


# 直接実行時はアプリケーションを起動
if __name__ == '__main__':
    app = create_app()
    
    # テーブル作成（開発時のみ）
    with app.app_context():
        db.create_all()
    
    app.run(debug=True)