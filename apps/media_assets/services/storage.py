# 文件路径: apps/media_assets/services/storage.py (V5.2 - 修复 URL 重复)

import os
import shutil
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import logging
from django.conf import settings
from pathlib import Path
from typing import Optional

from apps.workflow.models import TranscodingJob
from apps.media_assets.models import Media
from apps.configuration.models import IntegrationSettings

logger = logging.getLogger(__name__)


# --- Helper to load dynamic settings ---
def get_integration_settings():
    """动态加载 IntegrationSettings，提供安全回退。"""
    try:
        # 使用 get_solo() 获取单例对象
        return IntegrationSettings.get_solo()
    except Exception:
        # 数据库未就绪或表不存在时的安全回退
        return None


class StorageService:
    """
    (V4.0 - 集成设置动态读取)
    基于 IntegrationSettings 动态切换本地存储或 S3 存储的通用服务。
    """

    def __init__(self):
        settings_obj = get_integration_settings()

        # [CRITICAL FIX] 优先从数据库加载 storage_backend。
        # 如果失败，则使用 settings.py 中定义的 FINAL_STORAGE_BACKEND 作为回退
        self.storage_backend = getattr(settings_obj, 'storage_backend', settings.FINAL_STORAGE_BACKEND)

        # 只有当后端是 s3 时，才初始化 s3_client
        if self.storage_backend == 's3':
            # 依赖 settings.py (V4.0) 中通过 IntegrationSettings 动态设置的 AWS 凭证
            # boto3 会自动查找 settings.AWS_ACCESS_KEY_ID 等配置
            self.s3_client = boto3.client('s3', region_name=settings.AWS_S3_REGION_NAME)
        else:
            self.s3_client = None

        logger.info(f"StorageService 初始化，后端类型: {self.storage_backend}")

    def save_processed_video(self, local_temp_path: str, media: Media) -> str:
        # ... (此方法保持不变) ...
        base_dir = Path(settings.MEDIA_ROOT) / 'source_files' / str(media.asset.id)
        processed_video_dir = base_dir / 'processed_media'
        processed_video_dir.mkdir(parents=True, exist_ok=True)
        processed_filename = f"{media.id}.mp4"
        final_path = processed_video_dir / processed_filename

        if self.storage_backend == 's3':
            s3_key = f"source_files/{media.asset.id}/processed_media/{processed_filename}"
            self.s3_client.upload_file(local_temp_path, settings.AWS_STORAGE_BUCKET_NAME, s3_key)
            # 确保返回正确的 URL 格式
            if settings.AWS_S3_CUSTOM_DOMAIN:
                return f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{s3_key}"
            else:
                return f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
        else:
            shutil.move(local_temp_path, final_path)
            relative_path = final_path.relative_to(Path(settings.MEDIA_ROOT))
            # [修复 1] 移除冗余的 LOCAL_MEDIA_URL_BASE，只使用 MEDIA_URL + 相对路径
            # MEDIA_URL 已经是绝对 URL (http://127.0.0.1:9999/media/)
            return f"{settings.MEDIA_URL}{relative_path}"

    def save_transcoded_video(self, local_temp_path: str, job: TranscodingJob) -> str:
        """
        (V2.0 健壮版)
        保存转码后的视频文件。
        """
        asset_id = job.media.asset.id
        job_id = job.id
        container = job.profile.container
        final_filename = f"{job_id}.{container}"

        if self.storage_backend == 's3':
            s3_key = f"transcoding_outputs/{asset_id}/{final_filename}"
            self.s3_client.upload_file(local_temp_path, settings.AWS_STORAGE_BUCKET_NAME, s3_key)

            if settings.AWS_S3_CUSTOM_DOMAIN:
                return f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{s3_key}"
            else:
                return f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
        else:
            # 本地存储逻辑
            final_dir = Path(settings.MEDIA_ROOT) / 'transcoding_outputs' / str(asset_id)
            final_dir.mkdir(parents=True, exist_ok=True)
            final_path = final_dir / final_filename

            # 将转码任务中记录的 output_file 的真实文件移动到这里
            source_file_path = job.output_file.path
            if os.path.exists(source_file_path):
                shutil.move(source_file_path, final_path)

            relative_path = final_path.relative_to(Path(settings.MEDIA_ROOT))
            # [修复 2] 移除冗余的 LOCAL_MEDIA_URL_BASE，只使用 MEDIA_URL + 相对路径
            # MEDIA_URL 已经是绝对 URL (http://127.0.0.1:9999/media/)
            return f"{settings.MEDIA_URL}{relative_path}"