# 文件路径: apps/workflow/tasks/annotation_tasks.py
import json
import logging
import csv
import io
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from celery import shared_task
from django.core.files.base import ContentFile

# 导入 Celery App 实例
from visify_ssw.celery import app as celery_app

from ..models import AnnotationProject, AnnotationJob
from ..common.baseJob import BaseJob
from .services.modeling.script_modeler import ScriptModeler
from .services.cloud_api import CloudApiService
from .services.audit_service import L1AuditService
from .services.metrics_service import CharacterMetricsCalculator

# 获取一个日志记录器实例
logger = logging.getLogger(__name__)


@shared_task(name="create_label_studio_project_for_annotation")
def create_label_studio_project_task(project_id: str):
    """
    一个Celery后台任务，负责为给定的AnnotationProject创建Label Studio项目，
    并为每一个关联的Media文件创建所有初始的AnnotationJob记录。
    """
    from apps.workflow.models import AnnotationProject, AnnotationJob
    from apps.workflow.annotation.services.label_studio import LabelStudioService

    try:
        project = AnnotationProject.objects.get(id=project_id)
    except AnnotationProject.DoesNotExist:
        logger.error(f"任务失败：找不到ID为 {project_id} 的 AnnotationProject。")
        return

    if project.label_studio_project_id:
        logger.warning(f"任务跳过：AnnotationProject (ID: {project_id}) 已有关联的Label Studio项目ID。")
        return

    logger.info(f"开始为 AnnotationProject (ID: {project_id}) 创建 Label Studio 项目...")

    service = LabelStudioService()

    success, message, ls_project_id, task_mapping = service.create_project_for_asset(project=project)

    if success:
        project.label_studio_project_id = ls_project_id
        logger.info(
            f"成功为 AnnotationProject (ID: {project_id}) 创建并关联了 Label Studio 项目 (LS ID: {ls_project_id})。")

        jobs_to_create = []
        # 统一为所有 media 创建 L1 和 L2/L3 Job
        all_media_ids = project.asset.medias.values_list('id', flat=True)
        for media_id in all_media_ids:
            # 创建 L1 Job (初始状态默认为 PENDING)
            jobs_to_create.append(
                AnnotationJob(project=project, media_id=media_id, job_type=AnnotationJob.TYPE.L1_SUBEDITING)
            )
            # 创建 L2/L3 Job (初始状态默认为 PENDING)，并关联 ls_task_id
            l2l3_task_id = task_mapping.get(media_id)
            jobs_to_create.append(
                AnnotationJob(project=project, media_id=media_id, job_type=AnnotationJob.TYPE.L2L3_SEMANTIC,
                              label_studio_task_id=l2l3_task_id)
            )

        if jobs_to_create:
            AnnotationJob.objects.bulk_create(jobs_to_create)
            logger.info(f"为项目 {project_id} 成功初始化了 {len(jobs_to_create)} 条标注任务记录。")

        # 最后再统一保存 project
        project.save(update_fields=['label_studio_project_id'])
    else:
        logger.error(f"为 AnnotationProject (ID: {project_id}) 创建 Label Studio 项目失败: {message}")

@shared_task(name="export_l2_output_from_label_studio")
def export_l2_output_task(project_id: str):
    """
    一个Celery后台任务，负责从Label Studio导出L2产出物并更新相关任务状态。
    """
    from apps.workflow.common.baseJob import BaseJob
    from apps.workflow.models import AnnotationProject, AnnotationJob
    from apps.workflow.annotation.services.label_studio import LabelStudioService

    try:
        project = AnnotationProject.objects.get(id=project_id)
        if not project.label_studio_project_id:
            logger.error(f"项目 {project.id} 缺少 LS Project ID，无法导出。")
            return

        # 1. 调用服务层执行导出
        service = LabelStudioService()
        success, message, file_content = service.export_project_annotations(project.label_studio_project_id)

        if not success:
            logger.error(f"从LS导出项目 {project.id} 失败: {message}")
            return

        # 2. 保存文件到项目模型
        file_name = f"ls_export_project_{project.label_studio_project_id}.json"
        project.label_studio_export_file.save(file_name, ContentFile(file_content), save=True)
        logger.info(f"成功为项目 {project.id} 导出并保存了标注数据。")

        # 3. 更新所有关联的 L2/L3 AnnotationJob 的状态
        jobs_to_complete = AnnotationJob.objects.filter(
            project=project,
            job_type=AnnotationJob.TYPE.L2L3_SEMANTIC,
            status=BaseJob.STATUS.PROCESSING
        )

        completed_count = 0
        for job in jobs_to_complete:
            job.complete()
            job.save()
            completed_count += 1

        logger.info(f"已将 {completed_count} 个关联的L2/L3标注任务标记为完成。")

    except AnnotationProject.DoesNotExist:
        logger.error(f"在导出任务中找不到 ID 为 {project_id} 的 AnnotationProject。")
    except Exception as e:
        logger.error(f"执行导出任务时发生未知错误 (Project ID: {project_id}): {e}", exc_info=True)

@shared_task(name="generate_narrative_blueprint_for_project")
def generate_narrative_blueprint_task(project_id: str):
    """
    为给定的 AnnotationProject 生成叙事蓝图。
    """
    project = None
    try:
        project = AnnotationProject.objects.get(id=project_id)

        # 1. 更新项目状态为“处理中”
        project.status = 'PROCESSING'
        project.save(update_fields=['status'])
        logger.info(f"开始为项目 {project.name} (ID: {project_id}) 生成叙事蓝图...")

        # 2. 检查输入文件是否就绪
        if not project.label_studio_export_file or not project.label_studio_export_file.path:
            raise ValueError(f"项目 {project.id} 缺少 L2 标注导出文件，无法生成蓝图。")

        # 3. 构建 task_id 到 L1产出物路径 的映射
        task_id_to_ass_map = {}
        l1_jobs = AnnotationJob.objects.filter(
            project=project,
            job_type=AnnotationJob.TYPE.L1_SUBEDITING
        ).select_related('media')

        for l1_job in l1_jobs:
            l2_job = AnnotationJob.objects.filter(
                project=project,
                media=l1_job.media,
                job_type=AnnotationJob.TYPE.L2L3_SEMANTIC
            ).first()

            if l2_job and l2_job.label_studio_task_id and l1_job.l1_output_file and l1_job.l1_output_file.path:
                task_id_to_ass_map[l2_job.label_studio_task_id] = {
                    "chapter_id": l1_job.media.sequence_number,
                    "ass_path": l1_job.l1_output_file.path
                }

        def get_mapping_from_db(task_id: int):
            return task_id_to_ass_map.get(task_id)

        # 4. 实例化并运行 ScriptModeler
        modeler = ScriptModeler(
            ls_json_path=Path(project.label_studio_export_file.path),
            project_name=project.name,
            language=project.asset.language,
            mapping_provider=get_mapping_from_db
        )
        final_structured_script = modeler.build()

        # 5. 保存最终产出物
        blueprint_content = json.dumps(final_structured_script, indent=2, ensure_ascii=False)
        blueprint_filename = f"narrative_blueprint_{project.id}.json"
        project.final_blueprint_file.save(blueprint_filename, ContentFile(blueprint_content.encode('utf-8')),
                                          save=False)

        # 6. 更新最终状态为“已完成”
        project.status = 'COMPLETED'
        project.save(update_fields=['final_blueprint_file', 'status'])
        logger.info(f"成功为项目 {project.name} 生成并保存了叙事蓝图！")

    except AnnotationProject.DoesNotExist:
        logger.error(f"在蓝图生成任务中找不到 ID 为 {project_id} 的项目。")
    except Exception as e:
        logger.error(f"为项目 {project_id} 生成叙事蓝图时发生错误: {e}", exc_info=True)
        if project:
            project.status = 'FAILED'
            project.save(update_fields=['status'])
        raise


@shared_task(bind=True, name="workflow.poll_cloud_task_status", max_retries=20, default_retry_delay=30)
def poll_cloud_task_status(self, project_id: str, cloud_task_id: int, on_complete_task_name: str,
                           on_complete_kwargs: dict):
    """
    通用的云端任务轮询器。
    """
    try:
        project = AnnotationProject.objects.get(id=project_id)
    except AnnotationProject.DoesNotExist:
        logger.error(f"[PollTask] 找不到项目 {project_id}，轮询任务终止。")
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

        # 动态调用链中的下一个任务
        # 我们将 cloud_task_data (完整的任务响应) 和 on_complete_kwargs (自定义参数) 合并传递
        celery_app.send_task(on_complete_task_name, kwargs={
            'project_id': project_id,
            'cloud_task_data': data,
            **on_complete_kwargs  #
        })

    elif status in ["PENDING", "RUNNING"]:
        logger.info(f"[PollTask] 云端任务 {cloud_task_id} 仍在 {status} 状态，将在 {self.default_retry_delay} 秒后重试。")
        self.retry()

    elif status == "FAILED":
        logger.error(f"[PollTask] 云端任务 {cloud_task_id} 报告失败。项目 {project_id} 状态已设为 FAILED。")
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = json.dumps(data)
        project.save()

    else:
        logger.error(
            f"[PollTask] 云端任务 {cloud_task_id} 返回未知状态: '{status}'。项目 {project_id} 状态已设为 FAILED。")
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = f"云端任务返回未知状态: '{status}'"
        project.save()


@shared_task(name="workflow.trigger_rag_deployment_task")
def trigger_rag_deployment_task(project_id: str, cloud_task_data: dict = None, **kwargs):
    """
    这是 CHARACTER_PIPELINE 或 CHARACTER_IDENTIFIER 任务成功后的回调。
    它负责启动 RAG 部署任务。
    """
    try:
        project = AnnotationProject.objects.get(id=project_id)
    except AnnotationProject.DoesNotExist:
        logger.error(f"[RAGDeploy] 找不到项目 {project_id}，任务终止。")
        return

    # 1. 从上一个任务 (cloud_task_data) 中提取产出物
    if cloud_task_data:
        # 提取云端路径
        facts_path = cloud_task_data.get("result", {}).get("output_file_path")
        if facts_path:
            project.cloud_facts_path = facts_path
            project.save(update_fields=['cloud_facts_path'])

        # 下载产出物文件
        service = CloudApiService()
        download_url = cloud_task_data.get("download_url")
        if download_url:
            success, content = service.download_task_result(download_url)
            if success:
                project.cloud_facts_result_file.save(f"facts_result_{project.id}.json", ContentFile(content), save=True)
            else:
                logger.warning(f"[RAGDeploy] 成功获取任务数据，但下载 facts_result_file 失败: {download_url}")

    # 2. 验证是否具备启动 RAG 任务的条件
    if not project.cloud_blueprint_path or not project.cloud_facts_path:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = f"无法部署 RAG：缺少 cloud_blueprint_path 或 cloud_facts_path。"
        project.save()
        logger.error(project.cloud_reasoning_error)
        return

    logger.info(f"[RAGDeploy] 项目 {project_id} 正在启动 RAG 部署...")
    project.cloud_reasoning_status = 'RAG_DEPLOYING'
    project.save(update_fields=['cloud_reasoning_status'])

    service = CloudApiService()
    payload = {
        "blueprint_input_path": project.cloud_blueprint_path,
        "facts_input_path": project.cloud_facts_path,
        "series_id": str(project.id)  #
    }

    success, task_data = service.create_task("DEPLOY_RAG_CORPUS", payload)

    if not success:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = task_data.get('message', 'Failed to create DEPLOY_RAG_CORPUS task')
        project.save()
        return

    # 3. 触发对 RAG 任务的轮询
    poll_cloud_task_status.delay(
        project_id=project_id,
        cloud_task_id=task_data['id'],
        on_complete_task_name='workflow.finalize_rag_deployment',  #
        on_complete_kwargs={}
    )


@shared_task(name="workflow.finalize_rag_deployment")
def finalize_rag_deployment(project_id: str, cloud_task_data: dict, **kwargs):
    """
    RAG 部署任务成功后的回调。
    """
    try:
        project = AnnotationProject.objects.get(id=project_id)
    except AnnotationProject.DoesNotExist:
        logger.error(f"[RAGFinal] 找不到项目 {project_id}，任务终止。")
        return

    service = CloudApiService()
    download_url = cloud_task_data.get("download_url")
    if download_url:
        success, content = service.download_task_result(download_url)
        if success:
            project.cloud_rag_report_file.save(f"rag_report_{project.id}.json", ContentFile(content), save=True)
        else:
            logger.warning(f"[RAGFinal] 任务已完成，但下载 RAG 报告失败: {download_url}")

    project.cloud_reasoning_status = 'COMPLETED'
    project.save(update_fields=['cloud_reasoning_status', 'cloud_rag_report_file'])
    logger.info(f"[RAGFinal] 项目 {project_id} 的云端推理工作流已全部完成！")


@shared_task(name="workflow.start_cloud_pipeline_task")
def start_cloud_pipeline_task(project_id: str, top_n: int = 3):
    """
    触发器任务：启动“模式 B”（自动流水线）。
    """
    try:
        project = AnnotationProject.objects.get(id=project_id)
    except AnnotationProject.DoesNotExist:
        logger.error(f"[AutoPipe] 找不到项目 {project_id}，任务终止。")
        return

    if not project.final_blueprint_file or not project.final_blueprint_file.path:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = "无法启动：本地 final_blueprint_file 未找到。"
        project.save()
        return

    service = CloudApiService()

    # 1. 上传蓝图
    project.cloud_reasoning_status = 'BLUEPRINT_UPLOADING'
    project.save(update_fields=['cloud_reasoning_status'])

    success, blueprint_path = service.upload_file(Path(project.final_blueprint_file.path))

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
        "threshold": {
            "top_n": top_n
        },
        "service_params": {
            "lang": project.asset.language.split('-')[0] if project.asset.language else "zh",
            "model": "gemini-2.5-flash",  # <-- 新增的硬编码
            "temp": 0.1  # <-- 新增的硬编码
        }
    }

    success, task_data = service.create_task("CHARACTER_PIPELINE", payload)

    if not success:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = task_data.get('message', 'Failed to create CHARACTER_PIPELINE task')
        project.save()
        return

    # 3. 触发轮询
    poll_cloud_task_status.delay(
        project_id=project_id,
        cloud_task_id=task_data['id'],
        on_complete_task_name='workflow.trigger_rag_deployment_task',  #
        on_complete_kwargs={}
    )


@shared_task(name="workflow.start_cloud_metrics_task")
def start_cloud_metrics_task(project_id: str):
    """
    触发器任务：启动“模式 A”（手动流程）的第1步。
    """
    try:
        project = AnnotationProject.objects.get(id=project_id)
    except AnnotationProject.DoesNotExist:
        logger.error(f"[MetricsTask] 找不到项目 {project_id}，任务终止。")
        return

    if not project.final_blueprint_file or not project.final_blueprint_file.path:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = "无法启动：本地 final_blueprint_file 未找到。"
        project.save()
        return

    service = CloudApiService()

    # 1. 上传蓝图
    project.cloud_reasoning_status = 'BLUEPRINT_UPLOADING'
    project.save(update_fields=['cloud_reasoning_status'])

    success, blueprint_path = service.upload_file(Path(project.final_blueprint_file.path))

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
    poll_cloud_task_status.delay(
        project_id=project_id,
        cloud_task_id=task_data['id'],
        on_complete_task_name='workflow.finalize_metrics_task',  #
        on_complete_kwargs={}
    )


@shared_task(name="workflow.finalize_metrics_task")
def finalize_metrics_task(project_id: str, cloud_task_data: dict, **kwargs):
    """
    CHARACTER_METRICS 任务成功后的回调。
    """
    try:
        project = AnnotationProject.objects.get(id=project_id)
    except AnnotationProject.DoesNotExist:
        logger.error(f"[MetricsFinal] 找不到项目 {project_id}，任务终止。")
        return

    service = CloudApiService()
    download_url = cloud_task_data.get("download_url")
    if download_url:
        success, content = service.download_task_result(download_url)
        if success:
            project.cloud_metrics_result_file.save(f"metrics_result_{project.id}.json", ContentFile(content), save=True)
            project.cloud_reasoning_status = 'WAITING_FOR_SELECTION'  #
            project.save(update_fields=['cloud_metrics_result_file', 'cloud_reasoning_status'])
            logger.info(f"[MetricsFinal] 项目 {project_id} 已完成角色矩阵分析，等待用户选择。")
        else:
            project.cloud_reasoning_status = 'FAILED'
            project.cloud_reasoning_error = "下载角色矩阵文件失败。"
            project.save()
    else:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = "云端任务未返回 download_url。"
        project.save()


@shared_task(name="workflow.continue_cloud_facts_task")
def continue_cloud_facts_task(project_id: str, characters_to_analyze: list):
    """
    触发器任务：启动“模式 A”（手动流程）的第3步（在用户选择角色后）。
    """
    try:
        project = AnnotationProject.objects.get(id=project_id)
    except AnnotationProject.DoesNotExist:
        logger.error(f"[FactsTask] 找不到项目 {project_id}，任务终止。")
        return

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
            "lang": project.asset.language.split('-')[0] if project.asset.language else "zh",
            "model": "gemini-2.5-flash",  # <-- 新增的硬编码
            "temp": 0.1  # <-- 新增的硬编码
        }
    }

    success, task_data = service.create_task("CHARACTER_IDENTIFIER", payload)

    if not success:
        project.cloud_reasoning_status = 'FAILED'
        project.cloud_reasoning_error = task_data.get('message', 'Failed to create CHARACTER_IDENTIFIER task')
        project.save()
        return

    #
    poll_cloud_task_status.delay(
        project_id=project_id,
        cloud_task_id=task_data['id'],
        on_complete_task_name='workflow.trigger_rag_deployment_task',  #
        on_complete_kwargs={}
    )


@shared_task
def trigger_character_audit_task(project_id: str):
    """
    (已重构)
    Celery 任务触发器。
    所有复杂的业务逻辑都已移至 L1AuditService。
    """
    logger.info(f"Task trigger_character_audit_task received for project_id: {project_id}")
    try:
        # 初始化服务 (这会获取 project)
        service = L1AuditService(project_id=project_id)

        # 执行主方法
        service.generate_audit_report()

    except Exception as e:
        # 捕获在服务中可能发生的任何错误 (例如 Project.DoesNotExist)
        logger.error(f"L1 审计任务失败 (Project ID: {project_id}): {e}", exc_info=True)


@shared_task
def calculate_local_metrics_task(project_id: str):
    """
    (新) 在本地计算角色矩阵。
    读取 'final_blueprint_file'，运行计算器，
    并保存到 'local_metrics_result_file'。
    """
    logger.info(f"开始为 project {project_id} 本地计算角色矩阵...")
    try:
        project = AnnotationProject.objects.get(id=project_id)
    except AnnotationProject.DoesNotExist:
        logger.error(f"Task: Project {project_id} not found.")
        return

    # 1. 确保蓝图文件存在
    if not project.final_blueprint_file:
        logger.error(f"Task: Project {project_id} 没有 final_blueprint_file，无法计算矩阵。")
        return

    try:
        # [!!! 修复从这里开始 !!!]

        # 1. 以 'rb' (read binary) 模式打开文件
        with project.final_blueprint_file.open('rb') as f:
            # 2. 读取原始 bytes
            blueprint_bytes = f.read()

        # 3. 将 bytes 解码为 string
        blueprint_str = blueprint_bytes.decode('utf-8')

        # 4. 将 string 加载为 JSON
        blueprint_data = json.loads(blueprint_str)

        # [!!! 修复到这里结束 !!!]

        # 5. 运行计算器 (Code 2)
        calculator = CharacterMetricsCalculator()
        report_data = calculator.execute(blueprint_data)

        # 6. 将结果 (字典) 转换回 JSON 字符串
        report_json_str = json.dumps(report_data, ensure_ascii=False, indent=2)
        file_name = f"local_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # 7. 保存到新字段
        project.local_metrics_result_file.save(
            file_name,
            ContentFile(report_json_str.encode('utf-8')),
            save=True
        )
        logger.info(f"Project {project_id} 的本地角色矩阵已成功计算并保存。")

    except Exception as e:
        logger.error(f"为 {project_id} 计算本地角色矩阵时失败: {e}", exc_info=True)