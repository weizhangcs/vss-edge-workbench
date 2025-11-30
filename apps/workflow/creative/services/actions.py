# apps/workflow/creative/services/actions.py
import json
import logging
import os
from pathlib import Path
from typing import Tuple

from django.core.files.base import ContentFile

from apps.workflow.common.baseJob import BaseJob
from apps.workflow.creative.jobs import CreativeJob
from apps.workflow.creative.projects import CreativeProject
from apps.workflow.inference.services.cloud_api import CloudApiService
from visify_ssw import settings

logger = logging.getLogger(__name__)


class CreativeTaskAction:
    """
    [Service] 创作工作流动作处理器

    封装了与 DB 交互和 Cloud I/O 相关的副作用操作。
    旨在让 tasks.py 专注于流程编排，而非细节实现。
    """

    def __init__(self, project_id: str):
        self.project = CreativeProject.objects.get(id=project_id)
        self.cloud_service = CloudApiService()

    def get_asset_info(self) -> Tuple[str, str]:
        """获取标准化的资产信息 (Name, ID)"""
        return self.project.asset.title, str(self.project.asset.id)

    def create_job(self, job_type: str, config: dict) -> CreativeJob:
        """
        初始化一个创作子任务
        """
        job = CreativeJob.objects.create(
            project=self.project, job_type=job_type, status=BaseJob.STATUS.PENDING, input_params=config
        )
        job.start()  # FSM Transition: PENDING -> PROCESSING
        job.save()
        return job

    def update_project_status(self, status: str):
        """更新父级项目状态"""
        self.project.status = status
        self.project.save(update_fields=["status", "modified"])

    def ensure_blueprint_uploaded(self) -> str:
        """
        [核心逻辑] 智能获取云端蓝图路径。
        策略：优先上传本地最新的 final_blueprint_file；若本地缺失，尝试复用 InferenceJob 的历史云端记录。
        """
        inf_proj = self.project.inference_project
        if not inf_proj:
            raise ValueError("未找到关联的推理项目 (InferenceProject)")

        # 1. 优先策略: 上传本地最新文件
        local_bp = inf_proj.annotation_project.final_blueprint_file
        if local_bp and local_bp.path and Path(local_bp.path).exists():
            logger.info(f"正在上传本地蓝图: {local_bp.path}")
            success, path = self.cloud_service.upload_file(Path(local_bp.path))
            if success:
                return path
            # 上传失败不立即报错，尝试备用策略

        # 2. 备用策略: 复用历史云端路径
        # 查找该推理项目下，最近一个拥有 cloud_blueprint_path 的任务
        last_job = inf_proj.jobs.filter(cloud_blueprint_path__isnull=False).order_by("-modified").first()
        if last_job and last_job.cloud_blueprint_path:
            logger.warning(f"本地蓝图不可用，复用历史云端路径: {last_job.cloud_blueprint_path}")
            return last_job.cloud_blueprint_path

        raise ValueError("无法获取蓝图路径 (本地文件缺失且无云端历史记录)")

    def upload_file_field(self, file_field) -> str:
        """
        上传 Django FileField 指向的文件到云端
        """
        if not file_field or not file_field.path:
            raise ValueError("文件字段为空或文件不存在")

        path_obj = Path(file_field.path)
        if not path_obj.exists():
            raise FileNotFoundError(f"物理文件未找到: {path_obj}")

        success, cloud_path = self.cloud_service.upload_file(path_obj)
        if not success:
            raise Exception(f"文件上传失败: {path_obj.name}")

        return cloud_path

    def handle_callback_download(
        self, job_id: str, cloud_data: dict, target_file_field_name: str, filename_prefix: str
    ):
        """
        [核心逻辑] 通用的回调处理流程：
        1. 从云端回调数据中提取 download_url (或 result 里的数据)
        2. 下载内容
        3. 保存到指定的 Project 字段
        4. 标记 Job 完成
        """
        job = CreativeJob.objects.get(id=job_id)

        download_url = cloud_data.get("download_url")
        # V3 接口可能直接在 result 字段返回数据，也可能返回 download_url
        # 这里主要处理 download_url 模式

        content = None
        if download_url:
            success, content = self.cloud_service.download_task_result(download_url)
            if not success:
                raise Exception(f"从云端下载结果失败: {download_url}")
        else:
            raise ValueError("回调数据中缺少 download_url")

        # 动态获取字段并保存
        if not hasattr(self.project, target_file_field_name):
            raise AttributeError(f"Project 模型中不存在字段: {target_file_field_name}")

        target_field = getattr(self.project, target_file_field_name)

        # 构造文件名 (e.g. localized_script_en_123.json)
        # 如果是本地化任务，尝试在文件名里带上语言
        lang_suffix = ""
        if job.job_type == CreativeJob.TYPE.LOCALIZE_NARRATION:
            lang = job.input_params.get("target_lang", "xx")
            lang_suffix = f"_{lang}"

        file_name = f"{filename_prefix}{lang_suffix}_{job.id}.json"

        # 保存文件 (save=False 避免触发额外的 UPDATE)
        target_field.save(file_name, ContentFile(content), save=False)
        self.project.save()  # 统一保存 Project 变更

        # 完成 Job
        job.complete()
        job.save()

        logger.info(f"任务 {job_id} 处理完成，产出物已保存至 {target_field.name}")
        return job

    def download_assets_from_dubbing_script(self, job_id: str):
        """
        [核心补充] 解析配音脚本，下载所有关联的音频文件到本地，并回写本地路径。
        这是实现“云端配音 -> 本地合成”闭环的关键步骤。
        """
        job = CreativeJob.objects.get(id=job_id)

        # 1. 读取刚刚下载的 dubbing_script.json
        if not self.project.dubbing_script_file:
            raise ValueError("Dubbing script file missing on project.")

        # 重新打开文件读取内容
        self.project.dubbing_script_file.open("r")
        try:
            script_data = json.load(self.project.dubbing_script_file)
        except Exception as e:
            logger.error(f"Failed to parse dubbing script JSON: {e}")
            return
        finally:
            self.project.dubbing_script_file.close()

        dubbing_list = script_data.get("dubbing_script", [])
        if not dubbing_list:
            logger.warning("Dubbing script list is empty.")
            return

        # 2. 准备本地存储目录
        # 结构: media_root/creative/{project_id}/outputs/audio_{job_id}/
        relative_dir = f"creative/{self.project.id}/outputs/audio_{job.id}"
        abs_dir = Path(settings.MEDIA_ROOT) / relative_dir
        abs_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"开始下载 {len(dubbing_list)} 个音频文件到本地目录: {abs_dir}")

        updated_count = 0
        for item in dubbing_list:
            cloud_path = item.get("audio_file_path")  # e.g. "tmp/xxxx.mp3"
            if not cloud_path:
                continue

            # 3. 调用 Cloud API 通用下载接口
            # 注意：确保 CloudApiService 已实现 download_general_file
            success, content = self.cloud_service.download_general_file(cloud_path)

            if success:
                filename = os.path.basename(cloud_path)
                save_path = abs_dir / filename

                with open(save_path, "wb") as f:
                    f.write(content)

                # 4. [关键] 回写本地相对路径 (供 SynthesisService 使用)
                item["local_audio_path"] = f"{relative_dir}/{filename}"
                updated_count += 1
            else:
                logger.error(f"音频下载失败: {cloud_path}")
                item["error"] = "Download failed"

        # 5. 保存更新后的 JSON (包含 local_audio_path)
        if updated_count > 0:
            new_content = json.dumps(script_data, indent=2, ensure_ascii=False)

            # 使用 save 覆盖原文件
            # 获取原文件名
            original_name = os.path.basename(self.project.dubbing_script_file.name)
            self.project.dubbing_script_file.save(original_name, ContentFile(new_content.encode("utf-8")), save=False)
            self.project.save()
            logger.info(f"配音脚本已更新，成功下载并关联了 {updated_count} 个音频文件。")
