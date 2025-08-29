# 文件路径: apps/media_assets/services/storage.py

import os
import shutil
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from django.conf import settings
from pathlib import Path
from typing import Optional

# 导入 Media 模型用于类型提示
from apps.media_assets.models import Media


class StorageService:
    """
    (V4.1 路径修正版)
    存储服务，使用以 Asset ID 为核心的目录结构。
    """

    def __init__(self):
        self.storage_backend = settings.STORAGE_BACKEND
        if self.storage_backend == 's3':
            self.s3_client = boto3.client('s3', region_name=settings.AWS_S3_REGION_NAME)

    def save_processed_video(self, local_temp_path: str, media: Media) -> str:
        """
        保存处理后的视频文件到 'processed_media' 子目录。
        """
        # --- 核心修复：使用新的目录结构 ---
        base_dir = Path(settings.MEDIA_ROOT) / 'source_files' / str(media.asset.id)
        processed_video_dir = base_dir / 'processed_media'
        processed_video_dir.mkdir(parents=True, exist_ok=True)

        # 使用 media.id 命名，避免同名文件冲突
        processed_filename = f"{media.id}.mp4"
        final_path = processed_video_dir / processed_filename

        if self.storage_backend == 's3':
            # S3 key 也使用新结构
            s3_key = f"source_files/{media.asset.id}/processed_media/{processed_filename}"
            self.s3_client.upload_file(local_temp_path, settings.AWS_STORAGE_BUCKET_NAME, s3_key)
            return f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{s3_key}"
        else:
            shutil.move(local_temp_path, final_path)
            # URL 也反映新结构
            relative_path = final_path.relative_to(Path(settings.MEDIA_ROOT))
            return f"{settings.LOCAL_MEDIA_URL_BASE}{settings.MEDIA_URL}{relative_path}"