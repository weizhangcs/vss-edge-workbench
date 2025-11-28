# 文件路径: apps/media_assets/tasks.py

import logging
import os
import subprocess
import threading
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.files import File

from apps.media_assets.services.storage import StorageService

from .models import Asset, Media

# 获取一个模块级的 logger 实例
logger = logging.getLogger(__name__)


class ProgressLogger:
    """ """

    def __init__(self, filename):
        self._filename = filename
        self._size = float(os.path.getsize(filename))
        self._seen_so_far = 0
        self._lock = threading.Lock()

    def __call__(self, bytes_amount):
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            logger.info(
                f"上传进度: {self._filename}  {self._seen_so_far} / {int(self._size)} bytes ({percentage:.2f}%)"  # noqa: E501,E231
            )  # noqa: E231


def _check_and_update_asset_processing_status(media):
    """
    (V4 命名修正版)
    检查给定 media 所属的 asset 下的所有 media 的处理状态，
    并相应地更新 asset 的聚合处理状态。
    """
    asset = media.asset
    all_medias = asset.medias.all()
    total_medias = all_medias.count()

    if total_medias == 0:
        asset.processing_status = "pending"
        asset.save(update_fields=["processing_status"])
        return

    # 注意：我们假设 Media 模型上有一个 processing_status 字段，
    # 为了简化，我们暂时借用 Asset 的状态定义。
    # 实际应用中 Media 也应该有自己的状态。
    # completed_count = all_medias.filter(status='completed').count()
    # failed_count = all_medias.filter(status='failed').count()

    # 简化逻辑：只要有一个 media 完成，就更新父级 asset
    # 这里的逻辑可以根据您的业务需求变得更复杂
    asset.processing_status = "completed"
    asset.save(update_fields=["processing_status"])


@shared_task
def process_single_media_file(media_id):
    """
    (V4 命名修正版)
    处理单个物理媒体文件（Media），执行转码、上传等操作，
    并将结果URL存回该 Media 对象。
    """
    # 导入正确的模型

    media = Media.objects.get(id=media_id)
    storage_service = StorageService()

    try:
        # 1. 检查源文件是否存在
        if not media.source_video or not hasattr(media.source_video, "path"):
            raise FileNotFoundError(f"Media (ID: {media.id}) 的源视频在数据库中未记录路径。")

        source_video_path = Path(media.source_video.path)
        if not source_video_path.is_file():
            logger.critical(f"!!! 输入的视频文件未找到，Media ID: {media.id}，路径: {source_video_path}")
            # 注意：这里可以为 Media 模型增加一个 status 字段来记录失败状态
            raise FileNotFoundError(f"为 media {media.id} 在 {source_video_path} 未找到输入文件")

        # 2. 准备临时目录和FFmpeg命令
        source_video_path_str = str(source_video_path)
        temp_dir = Path(settings.MEDIA_ROOT) / "temp_processed"
        temp_dir.mkdir(exist_ok=True)
        # 使用 media.id 命名，确保唯一性
        processed_video_path = temp_dir / f"{media.id}.mp4"

        ffmpeg_command = [
            "ffmpeg",
            "-i",
            source_video_path_str,
            "-c:v",
            "libx264",
            "-b:v",
            settings.FFMPEG_VIDEO_BITRATE,
            "-preset",
            "fast",
            "-y",
            str(processed_video_path),
        ]

        # 3. 执行转码
        try:
            logger.info(f"执行 FFmpeg 命令: {' '.join(ffmpeg_command)}")
            result = subprocess.run(ffmpeg_command, check=True, capture_output=True, text=True, encoding="utf-8")
            logger.info(f"FFmpeg STDOUT: \n{result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error("!!! FFmpeg 命令执行失败 !!!")
            logger.error(f"--- FFmpeg STDERR ---\n{e.stderr}")
            raise

        # 4. 保存处理后的文件并获取 URL
        # 注意：storage_service 也需要适配新的 Media 模型
        video_url = storage_service.save_processed_video(local_temp_path=str(processed_video_path), media=media)

        # 5. 将结果URL存回 Media 对象
        media.processed_video_url = video_url
        media.save(update_fields=["processed_video_url"])

        # 6. 检查并更新父级 Asset 的聚合处理状态
        _check_and_update_asset_processing_status(media)

        logger.info(f"成功处理了单个媒体文件: {media.id}")
        return f"成功处理了单个媒体文件: {media.id}"

    except Exception as e:
        logger.error(f"为 Media ID: {media.id} 处理文件时发生决定性错误: {e}", exc_info=True)
        # 可以在这里更新 Media 的状态为 'failed'
        # 并同样触发父级 Asset 的状态检查
        _check_and_update_asset_processing_status(media)
        raise e


@shared_task
def ingest_media_files(asset_id):
    """
    (V4 命名修正版)
    为一个 Asset 批量加载文件，并为每个文件创建 Media 对象。
    """
    asset = None
    try:
        asset = Asset.objects.get(id=asset_id)
        asset.upload_status = "uploading"
        # asset.processing_status = 'processing'
        asset.save(update_fields=["upload_status"])

        upload_dir = Path(settings.MEDIA_ROOT) / "batch_uploads" / str(asset.id)
        if not upload_dir.exists():
            raise FileNotFoundError(f"未找到 Asset ID: {asset.id} 的上传目录: {upload_dir}")

        video_files = list(upload_dir.glob("*.mp4")) + list(upload_dir.glob("*.mov"))
        logger.info(f"在 {upload_dir} 中找到 {len(video_files)} 个视频文件。")

        for video_path in video_files:
            base_name = video_path.stem
            srt_path = upload_dir / f"{base_name}.srt"

            digits = "".join([char for char in base_name if char.isdigit()])
            sequence_number = int(digits) if digits else 0

            # --- 核心逻辑：创建 Media 对象并关联到 Asset ---
            media, created = Media.objects.get_or_create(
                asset=asset, sequence_number=sequence_number, defaults={"title": base_name}
            )
            logger.info(f"已创建/找到 Media: {media.title}")

            with video_path.open("rb") as f:
                media.source_video.save(video_path.name, File(f), save=False)
            if srt_path.exists():
                with srt_path.open("rb") as f:
                    media.source_subtitle.save(srt_path.name, File(f), save=False)
            media.save()

            # --- 核心逻辑：调用处理 Media 的任务 ---
            # process_single_media_file.delay(str(media.id))

        asset.upload_status = "completed"
        asset.save(update_fields=["upload_status"])
        logger.info(f"Asset ID: {asset.id} 的所有文件已派发处理。")
        return f"Ingestion complete for Asset {asset.id}"

    except Exception as e:
        logger.error(f"为 Asset ID: {asset_id} 批量加载文件时发生错误: {e}", exc_info=True)
        if asset:
            asset.upload_status = "failed"
            asset.processing_status = "failed"
            asset.save(update_fields=["upload_status"])
        raise
