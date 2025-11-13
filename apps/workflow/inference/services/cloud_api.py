# 文件路径: apps/workflow/annotation/services/cloud_api.py
import requests
import logging
from typing import Tuple, Optional, Dict, Any
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)


class CloudApiService:
    """
    一个封装了与 Visify Story Studio Cloud API 交互逻辑的服务。
    """

    def __init__(self):
        self.base_url = settings.CLOUD_API_BASE_URL
        self.instance_id = settings.CLOUD_INSTANCE_ID
        self.api_key = settings.CLOUD_API_KEY

        if not self.base_url or not self.instance_id or not self.api_key:
            logger.error("Cloud API 客户端未配置！请检查 .env 文件中的 CLOUD_API_... 变量。")
            raise ValueError("Cloud API 客户端未正确配置。")

    def _get_auth_headers(self) -> Dict[str, str]:
        """
        [cite_start][cite: 17, 18]
        """
        return {
            "X-Instance-ID": self.instance_id,
            "X-Api-Key": self.api_key,
        }

    def upload_file(self, local_file_path: Path) -> Tuple[bool, Optional[str]]:
        """
        [cite_start]执行四步流程的 [第1步：上传] [cite: 21]
        """
        if not local_file_path.exists():
            logger.error(f"Cloud API: 无法上传，文件未找到: {local_file_path}")
            return False, "File not found"

        upload_url = f"{self.base_url}/api/v1/files/upload/"
        headers = self._get_auth_headers()

        try:
            with open(local_file_path, 'rb') as f:
                files = {'file': (local_file_path.name, f)}
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
        create_url = f"{self.base_url}/api/v1/tasks/"
        headers = self._get_auth_headers()
        headers["Content-Type"] = "application/json"

        full_payload = {
            "task_type": task_type,
            "payload": payload
        }

        try:
            response = requests.post(create_url, headers=headers, json=full_payload, timeout=60)
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
        status_url = f"{self.base_url}/api/v1/tasks/{task_id}/"
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
        [cite_start]执行四步流程的 [第4步：下载] [cite: 27]
        """
        # download_url 已经是完整的 URL
        if not download_url.startswith('http'):
            logger.error(f"Cloud API: 无效的 download_url (非 http): {download_url}")
            return False, None

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
        download_url = f"{self.base_url}/api/v1/files/download/"
        headers = self._get_auth_headers()
        params = {'path': file_path}

        try:
            response = requests.get(download_url, headers=headers, params=params, timeout=300)
            response.raise_for_status()

            logger.info(f"Cloud API: 成功下载通用文件: {file_path}")
            return True, response.content

        except requests.exceptions.RequestException as e:
            logger.error(f"Cloud API: 下载通用文件失败: {file_path}。错误: {e}", exc_info=True)
            return False, None