# 文件路径: apps/media_assets/services/storage.py

import os
import shutil
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from django.conf import settings
from pathlib import Path
from typing import Optional

from apps.workflow.models import TranscodingJob
from apps.media_assets.models import Media


class StorageService:
    def __init__(self):
        self.storage_backend = settings.STORAGE_BACKEND
        # 只有当后端是 s3 时，才初始化 s3_client
        if self.storage_backend == 's3':
            self.s3_client = boto3.client('s3', region_name=settings.AWS_S3_REGION_NAME)

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
            return f"{settings.LOCAL_MEDIA_URL_BASE}{settings.MEDIA_URL}{relative_path}"

    # --- ↓↓↓ 核心修改部分 ↓↓↓ ---
    def save_transcoded_video(self, local_temp_path: str, job: TranscodingJob) -> str:
        """
        (V2.0 健壮版)
        保存转码后的视频文件。根据 STORAGE_BACKEND 的配置，
        智能地选择上传到 S3 或保存到本地。
        """
        asset_id = job.media.asset.id
        job_id = job.id
        container = job.profile.container
        final_filename = f"{job_id}.{container}"

        # --- 核心逻辑：增加 if/else 判断 ---
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
            # 注意：源文件是 job.output_file.path
            source_file_path = job.output_file.path
            if os.path.exists(source_file_path):
                shutil.move(source_file_path, final_path)

            relative_path = final_path.relative_to(Path(settings.MEDIA_ROOT))
            return f"{settings.LOCAL_MEDIA_URL_BASE}{settings.MEDIA_URL}{relative_path}"