# 文件路径: apps/workflow/inference/tasks.py

import json
import logging
from pathlib import Path

from celery import shared_task
from django.core.files.base import ContentFile

# 导入 Celery App 实例
from visify_ssw.celery import app as celery_app

# [!!! 修复 1: 导入正确的模型 !!!]
from .projects import InferenceProject
from apps.workflow.models import AnnotationProject
from apps.workflow.annotation.services.cloud_api import CloudApiService  # (假设 CloudApiService 在 annotation app 中)

logger = logging.getLogger(__name__)


# [!!! 修复 2: 更新所有模型引用和任务名称 !!!]

@shared_task(bind=True, name="apps.workflow.inference.tasks.poll_cloud_task_status", max_retries=20,
             default_retry_delay=30)
def poll_cloud_task_status(self, project_id: str, cloud_task_id: int, on_complete_task_name: str,
                           on_complete_kwargs: dict):
    """
    (已迁移) 通用的云端任务轮询器。
    现在操作的是 InferenceProject。
    """
    try:
        # [!!! 修复 !!!]
        project = InferenceProject.objects.get(id=project_id)
    except InferenceProject.DoesNotExist:
        logger.error(f"[PollTask] 找不到 InferenceProject {project_id}，轮询任务终止。")
        return

    logger.info(f"[PollTask] 正在查询项目 {project_id} 的云端任务 {cloud_task_id} 状态...")
    service = CloudApiService()
    success, data = service.get_task_status(cloud_task_id)

    if not success:
        logger.warning(f"[PollTask] 查询云端任务 {cloud_task_id} 失败，将在 {self.default_retry_delay} 秒后重试。")
        self.retry()
        return

    status = data.get("status")

    if status == "COMPLETED":
        logger.info(f"[PollTask] 云端任务 {cloud_task_id} 已完成。触发后续任务: {on_complete_task_name}")
        celery_app.send_task(on_complete_task_name, kwargs={
            'project_id': project_id,
            'cloud_task_data': data,
            **on_complete_kwargs
        })

    elif status in ["PENDING", "RUNNING"]:
        logger.info(f"[PollTask] 云端任务 {cloud_task_id} 仍在 {status} 状态，将在 {self.default_retry_delay} 秒后重试。")
        self.retry()

    elif status == "FAILED":
        logger.error(f"[PollTask] 云端任务 {cloud_task_id} 报告失败。项目 {project_id} 状态已设为 FAILED。")
        # [!!! 修复 !!!]
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = json.dumps(data)
        project.save()

    else:
        logger.error(
            f"[PollTask] 云端任务 {cloud_task_id} 返回未知状态: '{status}'。项目 {project_id} 状态已设为 FAILED。")
        # [!!! 修复 !!!]
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = f"云端任务返回未知状态: '{status}'"
        project.save()


@shared_task(name="apps.workflow.inference.tasks.trigger_rag_deployment_task")
def trigger_rag_deployment_task(project_id: str, cloud_task_data: dict = None, **kwargs):
    """
    (已迁移) 这是 CHARACTER_PIPELINE 或 CHARACTER_IDENTIFIER 任务成功后的回调。
    """
    try:
        # [!!! 修复 !!!]
        project = InferenceProject.objects.get(id=project_id)
    except InferenceProject.DoesNotExist:
        logger.error(f"[RAGDeploy] 找不到 InferenceProject {project_id}，任务终止。")
        return

    # 1. 从上一个任务 (cloud_task_data) 中提取产出物
    if cloud_task_data:
        facts_path = cloud_task_data.get("result", {}).get("output_file_path")
        if facts_path:
            # [!!! 修复 !!!]
            project.cloud_facts_path = facts_path
            project.save(update_fields=['cloud_facts_path'])

        service = CloudApiService()
        download_url = cloud_task_data.get("download_url")
        if download_url:
            success, content = service.download_task_result(download_url)
            if success:
                # [!!! 修复 !!!]
                project.cloud_facts_result_file.save(f"facts_result_{project.id}.json", ContentFile(content), save=True)
            else:
                logger.warning(f"[RAGDeploy] 成功获取任务数据，但下载 facts_result_file 失败: {download_url}")

    # 2. 验证是否具备启动 RAG 任务的条件
    # [!!! 修复 !!!]
    if not project.cloud_blueprint_path or not project.cloud_facts_path:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = f"无法部署 RAG：缺少 cloud_blueprint_path 或 cloud_facts_path。"
        project.save()
        logger.error(project.cloud_reasoning_error)
        return

    logger.info(f"[RAGDeploy] 项目 {project_id} 正在启动 RAG 部署...")
    # [!!! 修复 !!!]
    project.cloud_reasoning_status = 'RAG_DEPLOYING'
    project.save(update_fields=['cloud_reasoning_status'])

    service = CloudApiService()
    payload = {
        "blueprint_input_path": project.cloud_blueprint_path,
        "facts_input_path": project.cloud_facts_path,
        "series_id": str(project.id)
    }

    success, task_data = service.create_task("DEPLOY_RAG_CORPUS", payload)

    if not success:
        # [!!! 修复 !!!]
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = task_data.get('message', 'Failed to create DEPLOY_RAG_CORPUS task')
        project.save()
        return

    # 3. 触发对 RAG 任务的轮询
    # [!!! 修复: 更新 on_complete_task_name !!!]
    poll_cloud_task_status.delay(
        project_id=project_id,
        cloud_task_id=task_data['id'],
        on_complete_task_name='apps.workflow.inference.tasks.finalize_rag_deployment',  # <-- 修复
        on_complete_kwargs={}
    )


@shared_task(name="apps.workflow.inference.tasks.finalize_rag_deployment")
def finalize_rag_deployment(project_id: str, cloud_task_data: dict, **kwargs):
    """
    (已迁移) RAG 部署任务成功后的回调。
    """
    try:
        # [!!! 修复 !!!]
        project = InferenceProject.objects.get(id=project_id)
    except InferenceProject.DoesNotExist:
        logger.error(f"[RAGFinal] 找不到 InferenceProject {project_id}，任务终止。")
        return

    service = CloudApiService()
    download_url = cloud_task_data.get("download_url")
    if download_url:
        success, content = service.download_task_result(download_url)
        if success:
            # [!!! 修复 !!!]
            project.cloud_rag_report_file.save(f"rag_report_{project.id}.json", ContentFile(content), save=True)
        else:
            logger.warning(f"[RAGFinal] 任务已完成，但下载 RAG 报告失败: {download_url}")

    # [!!! 修复 !!!]
    project.cloud_reasoning_status = 'COMPLETED'
    project.save(update_fields=['cloud_reasoning_status', 'cloud_rag_report_file'])
    logger.info(f"[RAGFinal] 项目 {project_id} 的云端推理工作流已全部完成！")


@shared_task(name="apps.workflow.inference.tasks.start_cloud_pipeline_task")
def start_cloud_pipeline_task(project_id: str, top_n: int = 3):
    """
    (已迁移) 触发器任务：启动“模式 B”（自动流水线）。
    """
    try:
        # [!!! 修复 !!!]
        project = InferenceProject.objects.get(id=project_id)
        annotation_project = project.annotation_project
    except InferenceProject.DoesNotExist:
        logger.error(f"[AutoPipe] 找不到 InferenceProject {project_id}，任务终止。")
        return

    # [!!! 修复: 检查关联的 annotation_project !!!]
    if not annotation_project.final_blueprint_file or not annotation_project.final_blueprint_file.path:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = "无法启动：本地 final_blueprint_file 未找到。"
        project.save()
        return

    service = CloudApiService()

    # 1. 上传蓝图
    project.cloud_reasoning_status = 'BLUEPRINT_UPLOADING'
    project.save(update_fields=['cloud_reasoning_status'])

    # [!!! 修复: 上传关联的蓝图 !!!]
    success, blueprint_path = service.upload_file(Path(annotation_project.final_blueprint_file.path))

    if not success:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = f"蓝图上传失败: {blueprint_path}"
        project.save()
        return

    project.cloud_blueprint_path = blueprint_path
    project.cloud_reasoning_status = 'PIPELINE_RUNNING'
    project.save(update_fields=['cloud_blueprint_path', 'cloud_reasoning_status'])

    # 2. 创建 CHARACTER_PIPELINE 任务
    payload = {
        "input_file_path": blueprint_path,
        "mode": "threshold",
        "threshold": {"top_n": top_n},
        "service_params": {
            # [!!! 修复: 从关联的 asset 获取语言 !!!]
            "lang": annotation_project.asset.language.split('-')[0] if annotation_project.asset.language else "zh",
            "model": "gemini-2.5-flash",
            "temp": 0.1
        }
    }

    success, task_data = service.create_task("CHARACTER_PIPELINE", payload)

    if not success:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = task_data.get('message', 'Failed to create CHARACTER_PIPELINE task')
        project.save()
        return

    # 3. 触发轮询
    # [!!! 修复: 更新 on_complete_task_name !!!]
    poll_cloud_task_status.delay(
        project_id=project_id,
        cloud_task_id=task_data['id'],
        on_complete_task_name='apps.workflow.inference.tasks.trigger_rag_deployment_task',  # <-- 修复
        on_complete_kwargs={}
    )


@shared_task(name="apps.workflow.inference.tasks.start_cloud_metrics_task")
def start_cloud_metrics_task(project_id: str):
    """
    (已迁移) 触发器任务：启动“模式 A”（手动流程）的第1步。
    """
    try:
        # [!!! 修复 !!!]
        project = InferenceProject.objects.get(id=project_id)
        annotation_project = project.annotation_project
    except InferenceProject.DoesNotExist:
        logger.error(f"[MetricsTask] 找不到 InferenceProject {project_id}，任务终止。")
        return

    # [!!! 修复: 检查关联的 annotation_project !!!]
    if not annotation_project.final_blueprint_file or not annotation_project.final_blueprint_file.path:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = "无法启动：本地 final_blueprint_file 未找到。"
        project.save()
        return

    service = CloudApiService()

    # 1. 上传蓝图
    project.cloud_reasoning_status = 'BLUEPRINT_UPLOADING'
    project.save(update_fields=['cloud_reasoning_status'])

    # [!!! 修复: 上传关联的蓝图 !!!]
    success, blueprint_path = service.upload_file(Path(annotation_project.final_blueprint_file.path))

    if not success:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = f"蓝图上传失败: {blueprint_path}"
        project.save()
        return

    project.cloud_blueprint_path = blueprint_path
    project.cloud_reasoning_status = 'METRICS_RUNNING'
    project.save(update_fields=['cloud_blueprint_path', 'cloud_reasoning_status'])

    # 2. 创建 CHARACTER_METRICS 任务
    payload = {
        "input_file_path": blueprint_path,
        "service_params": {}
    }

    success, task_data = service.create_task("CHARACTER_METRICS", payload)

    if not success:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = task_data.get('message', 'Failed to create CHARACTER_METRICS task')
        project.save()
        return

    # 3. 触发轮询
    # [!!! 修复: 更新 on_complete_task_name !!!]
    poll_cloud_task_status.delay(
        project_id=project_id,
        cloud_task_id=task_data['id'],
        on_complete_task_name='apps.workflow.inference.tasks.finalize_metrics_task',  # <-- 修复
        on_complete_kwargs={}
    )


@shared_task(name="apps.workflow.inference.tasks.finalize_metrics_task")
def finalize_metrics_task(project_id: str, cloud_task_data: dict, **kwargs):
    """
    (已迁移) CHARACTER_METRICS 任务成功后的回调。
    """
    try:
        # [!!! 修复 !!!]
        project = InferenceProject.objects.get(id=project_id)
    except InferenceProject.DoesNotExist:
        logger.error(f"[MetricsFinal] 找不到 InferenceProject {project_id}，任务终止。")
        return

    service = CloudApiService()
    download_url = cloud_task_data.get("download_url")
    if download_url:
        success, content = service.download_task_result(download_url)
        if success:
            # [!!! 修复: 将 'cloud_metrics_result_file' 保存回 *AnnotationProject* !!!]
            # (根据你之前的要求，这个“旧”字段暂时保留在 AnnotationProject 上)
            project.annotation_project.cloud_metrics_result_file.save(f"metrics_result_{project.id}.json",
                                                                      ContentFile(content), save=True)

            project.cloud_reasoning_status = 'WAITING_FOR_SELECTION'
            # (我们同时保存 project 和 annotation_project)
            project.save(update_fields=['cloud_reasoning_status'])
            logger.info(f"[MetricsFinal] 项目 {project_id} 已完成角色矩阵分析，等待用户选择。")
        else:
            project.cloud_reasoning_status = 'FAILED'
            project.cloud_reasoning_error = "下载角色矩阵文件失败。"
            project.save()
    else:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = "云端任务未返回 download_url。"
        project.save()


@shared_task(name="apps.workflow.inference.tasks.continue_cloud_facts_task")
def continue_cloud_facts_task(project_id: str, characters_to_analyze: list):
    """
    (已迁移) 触发器任务：启动“模式 A”（手动流程）的第3步。
    """
    try:
        # [!!! 修复 !!!]
        project = InferenceProject.objects.get(id=project_id)
        annotation_project = project.annotation_project
    except InferenceProject.DoesNotExist:
        logger.error(f"[FactsTask] 找不到 InferenceProject {project_id}，任务终止。")
        return

    # [!!! 修复 !!!]
    if not project.cloud_blueprint_path:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = "无法启动：cloud_blueprint_path 未找到。"
        project.save()
        return

    if not characters_to_analyze:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = "无法启动：未选择任何角色。"
        project.save()
        return

    project.cloud_reasoning_status = 'FACTS_RUNNING'
    project.save(update_fields=['cloud_reasoning_status'])

    service = CloudApiService()
    payload = {
        "input_file_path": project.cloud_blueprint_path,
        "service_params": {
            "characters_to_analyze": characters_to_analyze,
            # [!!! 修复: 从关联的 asset 获取语言 !!!]
            "lang": annotation_project.asset.language.split('-')[0] if annotation_project.asset.language else "zh",
            "model": "gemini-2.5-flash",
            "temp": 0.1
        }
    }

    success, task_data = service.create_task("CHARACTER_IDENTIFIER", payload)

    if not success:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = task_data.get('message', 'Failed to create CHARACTER_IDENTIFIER task')
        project.save()
        return

    # [!!! 修复: 更新 on_complete_task_name !!!]
    poll_cloud_task_status.delay(
        project_id=project_id,
        cloud_task_id=task_data['id'],
        on_complete_task_name='apps.workflow.inference.tasks.trigger_rag_deployment_task',  # <-- 修复
        on_complete_kwargs={}
    )