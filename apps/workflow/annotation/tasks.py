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