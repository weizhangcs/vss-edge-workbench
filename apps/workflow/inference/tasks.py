# 文件路径: apps/workflow/inference/tasks.py

import json
import logging
from pathlib import Path

from celery import shared_task
from django.core.files.base import ContentFile

# 导入 Celery App 实例，用于链式调用
from visify_ssw.celery import app as celery_app

from .projects import InferenceProject, InferenceJob
from apps.workflow.models import AnnotationProject
from apps.workflow.common.baseJob import BaseJob
from .services.cloud_api import CloudApiService

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="apps.workflow.inference.tasks.poll_cloud_task_status", max_retries=20,
             default_retry_delay=30)
def poll_cloud_task_status(self, job_id: str, cloud_task_id: int, on_complete_task_name: str,
                           on_complete_kwargs: dict):
    """
    (已重构)
    通用的云端任务轮询器。
    接收一个 InferenceJob ID。
    """
    job = None
    try:
        job = InferenceJob.objects.get(id=job_id)
    except InferenceJob.DoesNotExist:
        logger.error(f"[PollTask] 找不到 InferenceJob {job_id}，轮询任务终止。")
        return

    logger.info(f"[PollTask] 正在查询 job {job_id} 的云端任务 {cloud_task_id} 状态...")
    service = CloudApiService()
    success, data = service.get_task_status(cloud_task_id)

    if not success:
        logger.warning(
            f"[PollTask] 查询云端任务 {cloud_task_id} 失败 (Job: {job_id})，将在 {self.default_retry_delay} 秒后重试。")
        self.retry()
        return

    status = data.get("status")

    if status == "COMPLETED":
        logger.info(f"[PollTask] 云端任务 {cloud_task_id} (Job: {job_id}) 已完成。触发后续任务: {on_complete_task_name}")
        celery_app.send_task(on_complete_task_name, kwargs={
            'job_id': job_id,
            'cloud_task_data': data,
            **on_complete_kwargs
        })

    elif status in ["PENDING", "RUNNING"]:
        logger.info(
            f"[PollTask] 云端任务 {cloud_task_id} (Job: {job_id}) 仍在 {status} 状态，将在 {self.default_retry_delay} 秒后重试。")
        self.retry()

    elif status == "FAILED":
        logger.error(f"[PollTask] 云端任务 {cloud_task_id} (Job: {job_id}) 报告失败。")
        # [!!! 修复: 使用 BaseJob.fail() !!!]
        job.fail()
        # job.error_message = json.dumps(data) # (如果你在 BaseJob 中有 error_message 字段)
        job.save()

    else:
        logger.error(
            f"[PollTask] 云端任务 {cloud_task_id} (Job: {job_id}) 返回未知状态: '{status}'。")
        # [!!! 修复: 使用 BaseJob.fail() !!!]
        job.fail()
        # job.error_message = f"云端任务返回未知状态: '{status}'"
        job.save()


@shared_task(name="apps.workflow.inference.tasks.start_rag_deployment_task")
def start_rag_deployment_task(job_id: str, **kwargs):
    """
    (已重构 V3.2)
    由视图 (view) 直接触发，接收 job_id。
    重用 FACTS 任务已上传的路径。
    """
    job = None
    try:
        job = InferenceJob.objects.get(id=job_id)
        project = job.project

        job.start()  # PENDING -> PROCESSING
        job.save()

    except InferenceJob.DoesNotExist:
        logger.error(f"[RAGDeploy] 找不到 InferenceJob {job_id}，任务终止。")
        return
    except Exception as e:
        logger.error(f"[RAGDeploy] 无法将 Job {job_id} 设为 PROCESSING: {e}", exc_info=True)
        return

    try:
        # 1. 从 input_params 获取源 Job ID
        source_facts_job_id = job.input_params.get('source_facts_job_id')
        if not source_facts_job_id:
            raise ValueError("input_params 中缺少 'source_facts_job_id'。")

        source_job = InferenceJob.objects.get(id=source_facts_job_id, status=BaseJob.STATUS.COMPLETED)

        # [!!! 步骤 3.1: 重用已有的路径 !!!]
        # (我们不再需要重新上传蓝图)
        if not source_job.cloud_blueprint_path:
            raise ValueError(f"源 Job {source_facts_job_id} 缺少 'cloud_blueprint_path'。")
        if not source_job.cloud_facts_path:
            raise ValueError(f"源 Job {source_facts_job_id} 缺少 'cloud_facts_path'。")

        logger.info(f"[RAGDeploy] Job {job_id} 正在启动 RAG 部署...")
        logger.info(f"[RAGDeploy] 重用 Blueprint 路径: {source_job.cloud_blueprint_path}")
        logger.info(f"[RAGDeploy] 重用 Facts 路径: {source_job.cloud_facts_path}")

        # 2. 将路径保存到 *这个* Job (用于追踪)
        job.cloud_blueprint_path = source_job.cloud_blueprint_path
        job.cloud_facts_path = source_job.cloud_facts_path

        service = CloudApiService()

        # 3. 创建 DEPLOY_RAG_CORPUS 任务 (API 文档 [cite: 91-100])
        payload = {
            "blueprint_input_path": job.cloud_blueprint_path,
            "facts_input_path": job.cloud_facts_path,
            "series_id": str(project.id)
        }
        success, task_data = service.create_task("DEPLOY_RAG_CORPUS", payload)
        if not success:
            raise Exception(task_data.get('message', 'Failed to create DEPLOY_RAG_CORPUS task'))

        job.cloud_task_id = task_data['id']
        job.save()  # (保存所有新字段)

        # 4. 触发轮询
        poll_cloud_task_status.delay(
            job_id=job_id,
            cloud_task_id=task_data['id'],
            on_complete_task_name='apps.workflow.inference.tasks.finalize_rag_deployment',
            on_complete_kwargs={}
        )
    except Exception as e:
        logger.error(f"[RAGDeploy] Job {job_id} 失败: {e}", exc_info=True)
        if job:
            job.fail()
            # job.error_message = str(e)
            job.save()


@shared_task(name="apps.workflow.inference.tasks.finalize_rag_deployment")
def finalize_rag_deployment(job_id: str, cloud_task_data: dict, **kwargs):
    """
    (已重构)
    RAG 部署任务成功后的回调。
    """
    job = None
    try:
        job = InferenceJob.objects.get(id=job_id)
    except InferenceJob.DoesNotExist:
        logger.error(f"[RAGFinal] 找不到 InferenceJob {job_id}，任务终止。")
        return

    try:
        service = CloudApiService()
        download_url = cloud_task_data.get("download_url")
        if download_url:
            success, content = service.download_task_result(download_url)
            if success:
                job.output_rag_report_file.save(f"rag_report_{job_id}.json", ContentFile(content), save=False)
            else:
                logger.warning(f"[RAGFinal] 任务已完成，但下载 RAG 报告失败: {download_url}")

        # [!!! 修复: 使用 BaseJob.complete() !!!]
        job.complete()
        job.save()

        logger.info(f"[RAGFinal] Job {job_id} (项目 {job.project.id}) 的云端推理工作流已全部完成！")
    except Exception as e:
        logger.error(f"[RAGFinal] Job {job_id} 最终化处理失败: {e}", exc_info=True)
        if job:
            # [!!! 修复: 使用 BaseJob.fail() !!!]
            job.fail()
            # job.error_message = str(e)
            job.save()


@shared_task(name="apps.workflow.inference.tasks.start_cloud_facts_task")
def start_cloud_facts_task(job_id: str, **kwargs):
    """
    (已重构 V3.2)
    由视图 (view) 直接触发，接收 job_id。
    (现在可以正确保存 cloud_blueprint_path)
    """
    job = None
    try:
        job = InferenceJob.objects.get(id=job_id)
        project = job.project
        annotation_project = project.annotation_project

        job.start()  # PENDING -> PROCESSING
        job.save()
    except InferenceJob.DoesNotExist:
        logger.error(f"[FactsTask] 找不到 InferenceJob {job_id}，任务终止。")
        return
    except Exception as e:
        logger.error(f"[FactsTask] 无法将 Job {job_id} 设为 PROCESSING: {e}", exc_info=True)
        return

    try:
        # 1. 验证输入
        if not annotation_project.final_blueprint_file:
            raise ValueError(f"关联的 AnnotationProject {annotation_project.id} 缺少 'final_blueprint_file'。")

        characters_to_analyze = job.input_params.get('characters')
        if not characters_to_analyze:
            raise ValueError("input_params 中缺少 'characters'。")

        logger.info(f"[FactsTask] Job {job_id} 正在启动 FACTS 识别...")
        service = CloudApiService()

        # 2. 上传蓝图
        logger.info(f"[FactsTask] 正在上传蓝图 {annotation_project.final_blueprint_file.name}...")
        success, blueprint_path = service.upload_file(Path(annotation_project.final_blueprint_file.path))
        if not success:
            raise Exception(f"蓝图上传失败: {blueprint_path}")

        # [!!! 步骤 3.2: 保存新字段 !!!]
        job.cloud_blueprint_path = blueprint_path  # 保存路径

        # 3. 创建 CHARACTER_IDENTIFIER 任务 (API 文档 [cite: 63-71])
        payload = {
            "input_file_path": job.cloud_blueprint_path,
            "service_params": {
                "characters_to_analyze": characters_to_analyze,
                "lang": annotation_project.asset.language.split('-')[0] if annotation_project.asset.language else "zh",
                "model": "gemini-2.5-flash",
                "temp": 0.1
            }
        }
        success, task_data = service.create_task("CHARACTER_IDENTIFIER", payload)
        if not success:
            raise Exception(task_data.get('message', 'Failed to create CHARACTER_IDENTIFIER task'))

        job.cloud_task_id = task_data['id']

        # (这是修复 'ValueError' 的地方)
        job.save(update_fields=['cloud_blueprint_path', 'cloud_task_id'])

        # 4. 触发轮询
        poll_cloud_task_status.delay(
            job_id=job_id,
            cloud_task_id=task_data['id'],
            on_complete_task_name='apps.workflow.inference.tasks.finalize_facts_task',
            on_complete_kwargs={}
        )
    except Exception as e:
        logger.error(f"[FactsTask] Job {job_id} 失败: {e}", exc_info=True)
        if job:
            job.fail()
            # job.error_message = str(e)
            job.save()


@shared_task(name="apps.workflow.inference.tasks.finalize_facts_task")
def finalize_facts_task(job_id: str, cloud_task_data: dict, **kwargs):
    """
    (已重构)
    CHARACTER_IDENTIFIER 任务成功后的回调。
    """
    job = None
    try:
        job = InferenceJob.objects.get(id=job_id)
    except InferenceJob.DoesNotExist:
        logger.error(f"[FactsFinal] 找不到 InferenceJob {job_id}，任务终止。")
        return

    try:
        # 1. 从上一个任务 (cloud_task_data) 中提取产出物
        facts_path = cloud_task_data.get("result", {}).get("output_file_path")
        if facts_path:
            job.cloud_facts_path = facts_path

        service = CloudApiService()
        download_url = cloud_task_data.get("download_url")
        if download_url:
            success, content = service.download_task_result(download_url)
            if success:
                job.output_facts_file.save(f"facts_result_{job_id}.json", ContentFile(content), save=False)
            else:
                logger.warning(f"[FactsFinal] 任务已完成，但下载 facts_result_file 失败: {download_url}")

        # [!!! 修复: 使用 BaseJob.complete() !!!]
        job.complete()
        job.save()

        logger.info(f"[FactsFinal] Job {job_id} (项目 {job.project.id}) 的角色属性识别已完成！")
    except Exception as e:
        logger.error(f"[FactsFinal] Job {job_id} 最终化处理失败: {e}", exc_info=True)
        if job:
            # [!!! 修复: 使用 BaseJob.fail() !!!]
            job.fail()
            # job.error_message = str(e)
            job.save()