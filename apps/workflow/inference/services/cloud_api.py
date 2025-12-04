# 文件路径: apps/workflow/annotation/services/cloud_api.py
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests

from apps.configuration.models import IntegrationSettings

logger = logging.getLogger(__name__)


class CloudApiService:
    """
    一个封装了与 Visify Story Studio Cloud API 交互逻辑的服务。
    """

    def __init__(self):
        # 1. 从 IntegrationSettings 模型安全地加载配置
        try:
            settings = IntegrationSettings.get_solo()
        except Exception:
            # 数据库或表未就绪时的安全回退
            settings = None

        # 使用 getattr 安全获取值，并提供硬编码的回退值
        self.BASE_URL = getattr(settings, "cloud_api_base_url", None) or "http://localhost:8080"
        self.INSTANCE_ID = getattr(settings, "cloud_instance_id", None)
        self.API_KEY = getattr(settings, "cloud_api_key", None)

        # 2. 验证检查
        if not self.BASE_URL or not self.INSTANCE_ID or not self.API_KEY:
            logger.warning("CloudApiService 凭证不完整或数据库不可访问。请检查 IntegrationSettings。")

    def _get_auth_headers(self) -> Dict[str, str]:
        """
        [cite_start][cite: 17, 18]
        """
        return {
            "X-Instance-ID": self.INSTANCE_ID,
            "X-Api-Key": self.API_KEY,
        }

    def upload_file(self, local_file_path: Path) -> Tuple[bool, Optional[str]]:
        """
        [cite_start]执行四步流程的 [第1步：上传] [cite: 21]
        """
        if not local_file_path.exists():
            logger.error(f"Cloud API: 无法上传，文件未找到: {local_file_path}")
            return False, "File not found"

        upload_url = f"{self.BASE_URL}/api/v1/files/upload/"
        headers = self._get_auth_headers()

        try:
            with open(local_file_path, "rb") as f:
                files = {"file": (local_file_path.name, f)}
                response = requests.post(upload_url, headers=headers, files=files, timeout=300)

            response.raise_for_status()

            response_data = response.json()
            relative_path = response_data.get("relative_path")

            if relative_path:
                logger.info(f"Cloud API: 文件上传成功: {relative_path}")
                return True, relative_path
            else:
                logger.error(f"Cloud API: 文件上传成功，但响应中缺少 'relative_path'。响应: {response.text}")
                return False, "Upload succeeded but response format is invalid."

        except requests.exceptions.RequestException as e:
            logger.error(f"Cloud API: 文件上传失败: {e}", exc_info=True)
            return False, str(e)

    def create_task(self, task_type: str, payload: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        [cite_start]执行四步流程的 [第2步：创建] [cite: 23]
        """
        create_url = f"{self.BASE_URL}/api/v1/tasks/"
        headers = self._get_auth_headers()
        headers["Content-Type"] = "application/json"

        full_payload = {"task_type": task_type, "payload": payload}

        logger.info(f"正在 POST 请求: {create_url}")  # 再次确认 URL

        try:
            response = requests.post(create_url, headers=headers, json=full_payload, timeout=60)

            if response.status_code == 404:
                logger.error("!!! 捕获到 404 错误 !!!")
                logger.error(f"请求 URL: {create_url}")
                logger.error(f"响应内容 (前500字符): {response.text[:500]}")
                # 如果是 JSON，打印解析后的详情
                try:
                    logger.error(f"响应 JSON: {response.json()}")
                except Exception:  # 明确指定 Exception
                    pass

            response.raise_for_status()

            response.raise_for_status()

            response_data = response.json()
            task_id = response_data.get("id")

            if task_id:
                logger.info(f"Cloud API: 成功创建任务 '{task_type}' (Task ID: {task_id})。")
                return True, response_data
            else:
                logger.error(f"Cloud API: 创建任务成功，但响应中缺少 'id'。响应: {response.text}")
                return False, "Create task succeeded but response format is invalid."

        except requests.exceptions.RequestException as e:
            logger.error(f"Cloud API: 创建任务失败: {e}", exc_info=True)
            return False, {"message": str(e)}

    def get_task_status(self, task_id: int) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        [cite_start]执行四步流程的 [第3步：轮询] [cite: 25]
        """
        status_url = f"{self.BASE_URL}/api/v1/tasks/{task_id}/"
        headers = self._get_auth_headers()

        try:
            response = requests.get(status_url, headers=headers, timeout=60)
            response.raise_for_status()

            response_data = response.json()
            status = response_data.get("status")

            if status:
                return True, response_data
            else:
                logger.error(f"Cloud API: 查询任务 {task_id} 成功，但响应中缺少 'status'。")
                return False, None

        except requests.exceptions.RequestException as e:
            logger.error(f"Cloud API: 查询任务 {task_id} 失败: {e}", exc_info=True)
            return False, None

    def download_task_result(self, download_url: str) -> Tuple[bool, Optional[bytes]]:
        """
        执行四步流程的 [第4步：下载]
        """
        # download_url 已经是完整的 URL
        if not download_url.startswith("http"):
            logger.error(f"Cloud API: 无效的 download_url (非 http): {download_url}")
            return False, None

        # --- [核心修复开始] ---
        # 针对 Cloud 端返回的 URL 端口丢失问题 (如返回 80 而实际配置是 8001) 进行智能修正。
        # 策略：如果 URL 路径以 '/api/v1/' 开头，说明是 Cloud 自有接口，
        # 我们信任本地配置的 self.BASE_URL (它包含了验证过的 IP 和端口)。
        if "/api/v1/" in download_url:
            try:
                parsed_url = urlparse(download_url)

                # 双重检查：确保路径匹配 API 特征
                if parsed_url.path.startswith("/api/v1/"):
                    # 提取原始路径 (path) 和查询参数 (query)
                    original_path = parsed_url.path
                    original_query = parsed_url.query

                    # 使用配置中的 BASE_URL 进行替换
                    # rstrip('/') 防止双斜杠
                    base = self.BASE_URL.rstrip("/")
                    path = original_path.lstrip("/")

                    new_url = f"{base}/{path}"
                    if original_query:
                        new_url += f"?{original_query}"

                    logger.info(f"Cloud API: 修正下载 URL: {download_url} -> {new_url}")
                    download_url = new_url
            except Exception as e:
                logger.warning(f"Cloud API: URL 修正失败，将使用原始 URL。错误: {e}")
        # --- [核心修复结束] ---

        headers = self._get_auth_headers()

        try:
            response = requests.get(download_url, headers=headers, timeout=300)
            response.raise_for_status()

            logger.info(f"Cloud API: 成功从 {download_url} 下载结果。")
            return True, response.content

        except requests.exceptions.RequestException as e:
            logger.error(f"Cloud API: 下载结果失败: {e}", exc_info=True)
            return False, None

    def download_general_file(self, file_path: str) -> Tuple[bool, Optional[bytes]]:
        """
        (新) 调用“通用资产下载接口” [cite: 216]
        用于下载 dubbing_script.json 中列出的 .wav 文件 [cite: 288]
        """
        # 构建带查询参数的 URL [cite: 219]
        download_url = f"{self.BASE_URL}/api/v1/files/download/"
        headers = self._get_auth_headers()
        params = {"path": file_path}

        try:
            response = requests.get(download_url, headers=headers, params=params, timeout=300)
            response.raise_for_status()

            logger.info(f"Cloud API: 成功下载通用文件: {file_path}")
            return True, response.content

        except requests.exceptions.RequestException as e:
            logger.error(f"Cloud API: 下载通用文件失败: {file_path}。错误: {e}", exc_info=True)
            return False, None
