# 文件路径: apps/workflow/services/label_studio.py

import requests
from typing import Tuple, Optional
import logging

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.http import HttpRequest

from apps.media_assets.models import Media, Asset
from apps.workflow.models import AnnotationProject, TranscodingJob

logger = logging.getLogger(__name__)


class LabelStudioService:
    """
    一个封装了与 Label Studio API 交互逻辑的服务。
    """

    def __init__(self):
        self.internal_ls_url = settings.LABEL_STUDIO_URL
        self.api_token = settings.LABEL_STUDIO_ACCESS_TOKEN
        self.headers = {
            "Authorization": f"Token {self.api_token}",
            "Content-Type": "application/json",
        }

    def create_project_for_asset(self, project: AnnotationProject) -> Tuple[bool, str, Optional[int], dict]:
        """
        (V5.0 CDN 加速版)
        为给定的 AnnotationProject 创建 LS 项目, 并为其下的每个 Media 文件导入为 Task。
        会智能判断使用 CDN 转码文件还是原始文件。
        """
        try:
            asset = project.asset # 从 project 中获取 asset
            admin_base_url = "http://localhost:8000" # 在容器内通信使用
            return_to_django_url = f"{admin_base_url}{reverse('admin:media_assets_asset_changelist')}"

            label_config_xml = render_to_string('ls_templates/video.xml')
            expert_instruction_html = f"<h4>操作指南</h4><p>请根据视频内容完成标注。</p><p>完成后请返回Django后台：<a href='{return_to_django_url}'>点击这里</a></p>"

            project_payload = {
                "title": f"{asset.title} - {project.name}",
                "expert_instruction": expert_instruction_html,
                "label_config": label_config_xml
            }

            project_response = requests.post(f"{self.internal_ls_url}/api/projects", json=project_payload, headers=self.headers)
            project_response.raise_for_status()
            project_data = project_response.json()
            project_id = project_data.get("id")

            if not project_id:
                return False, "API 调用成功，但未返回项目ID。", None, {}

            task_mapping = {}
            for media_item in asset.medias.all():
                if not media_item.source_video: continue

                # --- ↓↓↓ 核心查找逻辑 ↓↓↓ ---
                video_url = None
                # 检查项目是否设置了源编码配置
                if project.source_encoding_profile:
                    # 查找与此媒体文件和编码配置匹配的、已完成的转码任务
                    transcoding_job = TranscodingJob.objects.filter(
                        media=media_item,
                        profile=project.source_encoding_profile,
                        status=TranscodingJob.STATUS.COMPLETED
                    ).order_by('-modified').first() # 取最新的一个

                    if transcoding_job and transcoding_job.output_url:
                        video_url = transcoding_job.output_url
                        logger.info(f"为 Media '{media_item.title}' 找到了 CDN 转码文件: {video_url}")

                # 如果没有找到 CDN 文件，或者项目未设置编码配置，则回退到使用原始文件
                if not video_url:
                    video_url = f"{settings.LOCAL_MEDIA_URL_BASE}{media_item.source_video.url}"
                    logger.info(f"为 Media '{media_item.title}' 使用原始文件: {video_url}")
                # --- ↑↑↑ 查找逻辑结束 ↑↑↑ ---

                task_payload = {"data": {"video_url": video_url}}
                task_response = requests.post(f"{self.internal_ls_url}/api/projects/{project_id}/tasks", json=task_payload, headers=self.headers)

                if task_response.status_code == 201:
                    task_id = task_response.json().get('id')
                    task_mapping[media_item.id] = task_id
                else:
                    logger.error(f"为 Media '{media_item.title}' 创建 Task 失败: {task_response.text}")

            message = f"成功在 Label Studio 中创建项目 (ID: {project_id}) 并为 {len(task_mapping)} 个媒体文件准备了任务！"
            return True, message, project_id, task_mapping

        except Exception as e:
            logger.error(f"创建 LS 项目时发生未知错误: {e}", exc_info=True)
            return False, f"创建 LS 项目时发生未知错误: {e}", None, {}

    def export_project_annotations(self, ls_project_id: int) -> Tuple[bool, str, Optional[bytes]]:
        """
        从 Label Studio 导出指定项目的所有标注数据。
        成功时返回 (True, "Success", file_content_bytes)，失败时返回 (False, error_message, None)。
        """
        try:
            logger.info(f"开始从 LS 导出 Project {ls_project_id} 的全部数据...")
            export_url = f"{self.internal_ls_url}/api/projects/{ls_project_id}/export"

            # 使用 stream=True 适合处理可能的大文件
            response = requests.get(export_url, headers=self.headers, stream=True, timeout=300)  # 增加超时
            response.raise_for_status()

            return True, "Export successful", response.content

        except requests.exceptions.RequestException as e:
            logger.error(f"导出 LS 数据时发生API请求错误: {e}", exc_info=True)
            return False, f"API request failed: {e}", None
        except Exception as e:
            logger.error(f"导出 LS 数据时发生未知错误: {e}", exc_info=True)
            return False, f"Unknown error during export: {e}", None