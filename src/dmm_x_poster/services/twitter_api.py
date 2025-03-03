"""
Twitter API連携サービス
"""
import os
import tempfile
import subprocess
from subprocess import PIPE
import json
import tweepy
import logging
from flask import current_app
from datetime import datetime, timezone, UTC
from zoneinfo import ZoneInfo


from dmm_x_poster.config import JST
from dmm_x_poster.db.models import db, Post, Image, PostImage

# Tweepyからの無効なエスケープシーケンス警告を抑制
import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning, module="tweepy")

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

def jst_to_utc(jst_datetime):
    if jst_datetime.tzinfo is None:
        jst_datetime = jst_datetime.replace(tzinfo=JST)
    return jst_datetime.astimezone(timezone.utc)

class TwitterAPIService:
    """Twitter APIと連携するサービスクラス"""
    
    def __init__(self, app=None):
        self.api = None
        self.client = None
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """アプリケーションコンテキストからAPI設定を初期化"""
        try:
            # V1.1 API用の認証情報
            auth = tweepy.OAuth1UserHandler(
                app.config.get('TWITTER_API_KEY'),
                app.config.get('TWITTER_API_SECRET'),
                app.config.get('TWITTER_ACCESS_TOKEN'),
                app.config.get('TWITTER_ACCESS_SECRET')
            )
            self.api = tweepy.API(auth)
            
            # V2 API用のクライアント
            self.client = tweepy.Client(
                consumer_key=app.config.get('TWITTER_API_KEY'),
                consumer_secret=app.config.get('TWITTER_API_SECRET'),
                access_token=app.config.get('TWITTER_ACCESS_TOKEN'),
                access_token_secret=app.config.get('TWITTER_ACCESS_SECRET')
            )
            
            # 認証確認
            self.api.verify_credentials()
            logger.info("Twitter API authenticated successfully")
        except Exception as e:
            logger.error(f"Twitter API authentication failed: {e}")
            self.api = None
            self.client = None
    
    def is_authenticated(self):
        """API認証状態をチェック"""
        return self.api is not None and self.client is not None
    
    def _get_video_duration(self, video_path):
        """動画の長さを秒数で取得"""
        try:
            # ffprobeで動画情報を取得
            result = subprocess.run([
                'ffprobe', 
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'json',
                video_path
            ], stdout=PIPE, stderr=PIPE)
            
            # 出力をJSONとしてパース
            data = json.loads(result.stdout)
            duration = float(data['format']['duration'])
            logger.info(f"Video duration: {duration} seconds")
            return duration
        except Exception as e:
            logger.error(f"Error getting video duration: {e}")
            return None
    
    def _trim_video(self, input_path, output_path, duration=139):
        """動画を指定秒数に切り取る"""
        try:
            # 一時ファイルを作成
            logger.info(f"Trimming video to {duration} seconds")
            
            # ffmpegで動画を切り取り
            result = subprocess.run([
                'ffmpeg',
                '-i', input_path,
                '-t', str(duration),
                '-c', 'copy',  # コーデックはコピー（高速）
                '-y',  # 既存ファイルを上書き
                output_path
            ], stdout=PIPE, stderr=PIPE)
            
            if result.returncode != 0:
                logger.error(f"ffmpeg error: {result.stderr.decode('utf-8')}")
                return False
            
            logger.info(f"Successfully trimmed video to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error trimming video: {e}")
            return False

    def upload_video(self, video_path):
        """チャンクアップロードを使って動画をTwitterにアップロード"""
        try:
            total_bytes = os.path.getsize(video_path)
            logger.info(f"Starting chunked upload for {video_path} ({total_bytes} bytes)")
            
            # INIT - アップロードを初期化
            init_response = self.api.request(
                'media/upload', 
                {
                    'command': 'INIT',
                    'media_type': 'video/mp4',
                    'total_bytes': total_bytes,
                    'media_category': 'tweet_video'
                }
            )
            
            if init_response.status_code != 200:
                logger.error(f"Failed to initialize upload: {init_response.text}")
                return None
                
            media_id = init_response.json()['media_id']
            logger.info(f"Initialized upload with media_id: {media_id}")
            
            # APPEND - ファイルデータをアップロード
            segment_id = 0
            chunk_size = 4*1024*1024  # 4MB chunks
            
            with open(video_path, 'rb') as video_file:
                while True:
                    chunk = video_file.read(chunk_size)
                    if not chunk:
                        break
                        
                    logger.info(f"Uploading segment {segment_id} ({len(chunk)} bytes)")
                    append_response = self.api.request(
                        'media/upload',
                        {
                            'command': 'APPEND',
                            'media_id': media_id,
                            'segment_index': segment_id
                        },
                        files={'media': chunk}
                    )
                    
                    if append_response.status_code != 200:
                        logger.error(f"Failed to append segment {segment_id}: {append_response.text}")
                        return None
                        
                    segment_id += 1
            
            # FINALIZE - アップロードを完了
            finalize_response = self.api.request(
                'media/upload',
                {
                    'command': 'FINALIZE',
                    'media_id': media_id
                }
            )
            
            if finalize_response.status_code != 200:
                logger.error(f"Failed to finalize upload: {finalize_response.text}")
                return None
                
            # アップロード処理が完了するまで待機
            process_response = finalize_response.json()
            if 'processing_info' in process_response:
                self._wait_for_video_processing(media_id)
                
            logger.info(f"Successfully uploaded video with media_id: {media_id}")
            return media_id
            
        except Exception as e:
            logger.error(f"Error in chunked upload: {e}")
            return None
        
    def _wait_for_video_processing(self, media_id, check_interval=5, max_checks=60):
        """動画の処理が完了するまで待機"""
        checks = 0
        
        while checks < max_checks:
            status_response = self.api.request(
                'media/upload',
                {
                    'command': 'STATUS',
                    'media_id': media_id
                }
            )
            
            if status_response.status_code != 200:
                logger.error(f"Failed to get status: {status_response.text}")
                return False
                
            status = status_response.json()
            
            if 'processing_info' not in status:
                # 処理情報がない = 処理完了
                return True
                
            state = status['processing_info']['state']
            logger.info(f"Media processing status: {state}")
            
            if state == 'succeeded':
                return True
            elif state == 'failed':
                logger.error(f"Media processing failed: {status['processing_info']}")
                return False
                
            # 次のチェックまでの待機時間
            wait_time = status['processing_info'].get('check_after_secs', check_interval)
            logger.info(f"Waiting {wait_time} seconds for processing...")
            time.sleep(wait_time)
            checks += 1
        
        logger.error(f"Video processing timed out after {max_checks} checks")
        return False

    def _sanitize_tweet_text(self, text):
        """ツイートテキストを浄化する"""
        if not text:
            return ""
        
        # 最大文字数を制限（240文字に制限して安全マージンを確保）
        if len(text) > 240:
            text = text[:237] + "..."
        
        # 問題になる可能性のある特殊文字を削除
        import re
        # Unicode制御文字を削除
        text = re.sub(r'[\u0000-\u001F\u007F-\u009F]', '', text)
        
        # 長いURLを短くする（必要に応じて）
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, text)
        for url in urls:
            if len(url) > 30:
                text = text.replace(url, url[:30] + "...")
        
        return text

    def post_with_media(self, post_id):
        """画像付きツイートを投稿"""
        if not self.is_authenticated():
            logger.error("Twitter API not authenticated")
            return False
        
        # 投稿データを取得
        post = db.session.get(Post, post_id)
        if not post:
            logger.error(f"Post not found: {post_id}")
            return False
        
        try:
            # メディアIDを格納するリスト
            media_ids = []
            images = post.get_images()
            
            logger.info(f"Post {post_id} has {len(images)} images")
            
            # 画像がない場合はテキストのみ投稿
            if not images:
                logger.warning(f"No images found for post {post_id}")
                response = self.client.create_tweet(text=post.post_text)
                tweet_id = response.data['id']
                
                # 投稿成功を記録
                post.status = 'posted'
                post.posted_at = datetime.now(JST)
                db.session.commit()
                logger.info(f"Posted text-only tweet: {tweet_id}")
                return True
            
            # 動画と通常画像を分類
            movie_images = [img for img in images if hasattr(img, 'image_type') and img.image_type == 'movie']
            standard_images = [img for img in images if not hasattr(img, 'image_type') or img.image_type != 'movie']
            
            logger.info(f"Found {len(movie_images)} movie images and {len(standard_images)} standard images")
            
            # 動画処理 - ダウンロード済みの動画があればTwitterに直接アップロード
            for movie in movie_images:
                if movie.downloaded and movie.local_path:
                    # 動画ファイルのパスを取得
                    video_path = os.path.join(current_app.root_path, movie.local_path)
                    
                    if os.path.exists(video_path):
                        try:
                            # 動画の長さを確認
                            duration = self._get_video_duration(video_path)
                            upload_path = video_path
                            
                            # 一時ファイルオブジェクト（クリーンアップのため）
                            temp_file = None
                            
                            # 140秒を超える場合、切り取る
                            if duration and duration > 140:
                                logger.info(f"Video is longer than 140 seconds ({duration}s), trimming...")
                                
                                # 一時ファイルを作成
                                temp_fd, temp_path = tempfile.mkstemp(suffix='.mp4')
                                os.close(temp_fd)  # ファイル記述子をクローズ
                                
                                # 動画を切り取り
                                if self._trim_video(video_path, temp_path):
                                    upload_path = temp_path
                                    temp_file = temp_path  # 後でクリーンアップするために保存
                                else:
                                    logger.warning("Failed to trim video, using original")
                            
                            # チャンクアップロードで動画をTwitterにアップロード
                            media_id = self.upload_video(upload_path)
                            
                            # 一時ファイルの削除
                            if temp_file and os.path.exists(temp_file):
                                os.remove(temp_file)
                                logger.info(f"Removed temporary file {temp_file}")
                            
                            if media_id:
                                media_ids.append(media_id)
                                logger.info(f"Successfully uploaded video to Twitter, media ID: {media_id}")
                                break
                            else:
                                # 動画アップロード失敗の場合はURLを追加
                                logger.warning("Failed to upload video, adding URL to tweet text")
                                post.post_text += f"\n\n動画: {post.product.url}"
                        except Exception as e:
                            logger.error(f"Error uploading video to Twitter: {e}")
                            # エラーの場合はURLを追加（バックアップ手段）
                            post.post_text += f"\n\n動画: {post.product.url}"
                            
                            # 一時ファイルのクリーンアップ
                            if 'temp_file' in locals() and temp_file and os.path.exists(temp_file):
                                try:
                                    os.remove(temp_file)
                                    logger.info(f"Removed temporary file {temp_file}")
                                except:
                                    pass
                    else:
                        logger.warning(f"Video file not found at {video_path}")
            
            # 通常画像の処理（動画がアップロードできなかった場合のバックアップ）
            if not media_ids:
                for image in standard_images:
                    # ローカルファイルパスの確認
                    if not image.local_path:
                        logger.warning(f"Image {image.id} has no local_path")
                        continue
                        
                    # 絶対パスを構築
                    app_root = current_app.root_path
                    absolute_path = os.path.join(app_root, image.local_path)
                        
                    # ファイルの存在確認
                    if not os.path.exists(absolute_path):
                        logger.warning(f"Image file not found: {absolute_path}")
                        continue
                    
                    try:
                        # 画像をアップロード
                        media = self.api.media_upload(absolute_path)
                        media_ids.append(media.media_id)
                        logger.info(f"Successfully uploaded image, media ID: {media.media_id}")
                    except Exception as e:
                        logger.error(f"Error uploading image: {e}")
            
            # Twitterへの投稿作成
            if media_ids:
                logger.info(f"Creating tweet with {len(media_ids)} media attachments")
                
                # テキストを短くして問題のある文字を除去
                sanitized_text = self._sanitize_tweet_text(post.post_text)
                
                try:
                    # 正しい形式でmedia_idsを渡す
                    # 数値またはリストではなく文字列であることを確認
                    string_media_ids = [str(media_id) for media_id in media_ids]
                    
                    response = self.client.create_tweet(
                        text=sanitized_text,
                        media_ids=string_media_ids
                    )
                    tweet_id = response.data['id']
                    
                    # 投稿成功を記録
                    post.status = 'posted'
                    post.posted_at = datetime.now(JST)
                    db.session.commit()
                    logger.info(f"Posted tweet with media: {tweet_id}")
                    return True
                except Exception as e:
                    logger.error(f"Error posting tweet: {e}")
                    
                    # 短いテキストでの再試行
                    try:
                        simplified_text = f"商品情報 #{datetime.now(JST).strftime('%H:%M:%S')}"
                        response = self.client.create_tweet(
                            text=simplified_text,
                            media_ids=string_media_ids
                        )
                        tweet_id = response.data['id']
                        
                        post.status = 'posted'
                        post.posted_at = datetime.now(JST)
                        db.session.commit()
                        logger.info(f"Posted tweet with simplified text: {tweet_id}")
                        return True
                    except Exception as e2:
                        logger.error(f"Error posting simplified tweet: {e2}")
                        post.status = 'failed'
                        post.error_message = f"{str(e)} (再試行: {str(e2)})"
                        db.session.commit()
                        return False
        
        except Exception as e:
            # エラー発生時
            logger.error(f"Error posting tweet: {e}")
            post.status = 'failed'
            post.error_message = str(e)
            db.session.commit()
            return False
    
    def process_scheduled_posts(self):
        """予定された投稿を処理"""
        if not self.is_authenticated():
            logger.error("Twitter API not authenticated")
            return 0
        
        # 現在時刻（JST）
        now = datetime.now(JST)
        
        # 予定投稿を検索（JST）
        posts = Post.query.filter_by(status='scheduled').filter(
            Post.scheduled_at <= now
        ).all()
        
        success_count = 0
        for post in posts:
            if self.post_with_media(post.id):
                success_count += 1
        
        return success_count


# アプリケーションファクトリで初期化するためのインスタンス
twitter_api_service = TwitterAPIService()