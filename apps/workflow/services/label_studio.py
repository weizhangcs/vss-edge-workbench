# 文件路径: apps/workflow/services/label_studio.py

import requests
from typing import Tuple, Optional
import logging

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.http import HttpRequest

from apps.media_assets.models import Media, Asset
from apps.workflow.jobs.annotationJob import AnnotationJob

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

    def create_project_for_asset(self, asset: Asset) -> Tuple[bool, str, Optional[int], dict]:
        """
        (V4.5 修正版)
        为给定的 Asset 创建 Label Studio 项目, 并为其下的每个 Media 文件导入为 Task。
        此方法不再保存任何内容，而是返回一个包含 media_id->task_id 映射的字典。
        返回 (success, message, project_id, task_mapping_dict)
        """
        try:
            admin_base_url = "http://localhost:8000"
            return_to_django_url = f"{admin_base_url}{reverse('admin:media_assets_asset_changelist')}"

            label_config_xml = render_to_string('ls_templates/video.xml')
            expert_instruction_html = f"<h4>操作指南</h4><p>请根据视频内容完成标注。</p><p>完成后请返回Django后台：<a href='{return_to_django_url}'>点击这里</a></p>"

            project_payload = {
                "title": f"{asset.title} - 标注项目",
                "expert_instruction": expert_instruction_html,
                "label_config": label_config_xml
            }

            project_response = requests.post(f"{self.internal_ls_url}/api/projects", json=project_payload,
                                             headers=self.headers)
            project_response.raise_for_status()
            project_data = project_response.json()
            project_id = project_data.get("id")

            if not project_id:
                return False, "API 调用成功，但未返回项目ID。", None, {}

            task_mapping = {}

            for media_item in asset.medias.all():
                if not media_item.source_video: continue

                video_url = f"{settings.LOCAL_MEDIA_URL_BASE}{media_item.source_video.url}"

                task_payload = {"data": {"video_url": video_url}}
                task_response = requests.post(f"{self.internal_ls_url}/api/projects/{project_id}/tasks",
                                              json=task_payload, headers=self.headers)

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

    def create_project_and_import_tasks(self, media: Media, request: HttpRequest) -> Tuple[bool, str, Optional[int]]:
        """
        (V2 重构版 & V4.5 同步修正)
        在 Label Studio 中创建项目并导入任务。
        成功时返回 (True, message, project_id)，失败时返回 (False, message, None)。
        """
        try:
            label_config_xml = render_to_string('ls_templates/video.xml')
            return_to_django_url = request.build_absolute_uri(
                reverse('admin:media_assets_media_change', args=[media.id]))

            expert_instruction_html = f"<h4>操作指南</h4><p>请根据视频内容完成标注。</p><p>完成后请返回Django后台：<a href='{return_to_django_url}'>点击这里</a></p>"

            project_payload = {"title": f"{media.title} - 标注项目", "expert_instruction": expert_instruction_html,
                               "label_config": label_config_xml}
            project_response = requests.post(f"{self.internal_ls_url}/api/projects", json=project_payload,
                                             headers=self.headers)
            project_response.raise_for_status()
            project_data = project_response.json()
            project_id = project_data.get("id")

            if not project_id:
                return False, "API 调用成功，但未返回项目ID。", None

            # 【V4.5 同步修正】使用 source_video 构建 URL
            # 注意：此方法与media直接关联，因此只处理该media对象
            if media.source_video:
                video_url = f"{settings.LOCAL_MEDIA_URL_BASE}{media.source_video.url}"
                task_payload = {"data": {"video_url": video_url}}
                task_response = requests.post(f"{self.internal_ls_url}/api/projects/{project_id}/tasks",
                                              json=task_payload, headers=self.headers)

                if task_response.status_code != 201:
                    logger.error(f"为 Media '{media.title}' 创建 Task 失败: {task_response.text}")

            message = f"成功在 Label Studio 中创建项目 (ID: {project_id})！"
            return True, message, project_id

        except Exception as e:
            logger.error(f"创建 LS 项目时发生未知错误: {e}", exc_info=True)
            return False, f"创建 LS 项目时发生未知错误: {e}", None