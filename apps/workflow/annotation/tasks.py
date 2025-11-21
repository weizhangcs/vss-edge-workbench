# 文件路径: apps/workflow/annotation/tasks.py
import json
import logging
from datetime import datetime
from pathlib import Path

from celery import shared_task
from django.core.files.base import ContentFile

from ..models import AnnotationProject, AnnotationJob
from .services.modeling.script_modeler import ScriptModeler
from .services.audit_service import L1AuditService
from .services.metrics_service import CharacterMetricsCalculator

# 获取一个日志记录器实例
logger = logging.getLogger(__name__)


@shared_task(name="create_label_studio_project_for_annotation")
def create_label_studio_project_task(project_id: str):
    """
    (AnnotationProject save() 触发)
    一个Celery后台任务，负责为给定的AnnotationProject创建Label Studio项目，
    并为每一个关联的Media文件创建所有初始的AnnotationJob记录。
    """
    # (此任务中的导入是局部的，以避免潜在的循环导入问题)
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

        # 统一为所有 media 创建 L1 (字幕) 和 L2 (语义) Job
        jobs_to_create = []
        all_media_ids = project.asset.medias.values_list('id', flat=True)
        for media_id in all_media_ids:
            jobs_to_create.append(
                AnnotationJob(project=project, media_id=media_id, job_type=AnnotationJob.TYPE.L1_SUBEDITING)
            )
            l2l3_task_id = task_mapping.get(media_id)
            jobs_to_create.append(
                AnnotationJob(project=project, media_id=media_id, job_type=AnnotationJob.TYPE.L2L3_SEMANTIC,
                              label_studio_task_id=l2l3_task_id)
            )

        if jobs_to_create:
            AnnotationJob.objects.bulk_create(jobs_to_create)
            logger.info(f"为项目 {project_id} 成功初始化了 {len(jobs_to_create)} 条标注任务记录。")

        project.save(update_fields=['label_studio_project_id'])
    else:
        logger.error(f"为 AnnotationProject (ID: {project_id}) 创建 Label Studio 项目失败: {message}")
        # (注意: 此时项目状态仍为 PENDING)


@shared_task(name="export_l2_output_from_label_studio")
def export_l2_output_task(project_id: str):
    """
    (L2 Tab 按钮触发)
    一个Celery后台任务，负责从Label Studio导出L2产出物并更新相关任务状态。
    """
    # (此任务中的导入是局部的，以避免潜在的循环导入问题)
    from apps.workflow.common.baseJob import BaseJob
    from apps.workflow.models import AnnotationProject, AnnotationJob
    from apps.workflow.annotation.services.label_studio import LabelStudioService

    project = None  # (在 try 块之外定义，以便 except 块可以访问)
    try:
        project = AnnotationProject.objects.get(id=project_id)

        # 1. 设置项目状态为 "L2 导出中"
        project.status = 'L2_EXPORTING'
        project.save(update_fields=['status'])

        if not project.label_studio_project_id:
            raise ValueError(f"项目 {project.id} 缺少 LS Project ID，无法导出。")

        # 2. 调用服务层执行导出
        service = LabelStudioService()
        success, message, file_content = service.export_project_annotations(project.label_studio_project_id)

        if not success:
            raise Exception(f"从LS导出项目 {project.id} 失败: {message}")

        # 3. 保存文件到项目模型
        file_name = f"ls_export_project_{project.label_studio_project_id}.json"
        project.label_studio_export_file.save(file_name, ContentFile(file_content), save=False)  # (延迟 save)
        logger.info(f"成功为项目 {project.id} 导出并保存了标注数据。")

        # 4. 更新所有关联的 L2/L3 AnnotationJob 的状态
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

        # 5. 任务完成，重置项目状态
        project.status = 'PENDING'
        project.save(update_fields=['label_studio_export_file', 'status'])
        logger.info(f"已将 {completed_count} 个关联的L2标注任务标记为完成。")

    except Exception as e:
        logger.error(f"执行导出任务时发生未知错误 (Project ID: {project_id}): {e}", exc_info=True)
        if project:
            project.status = 'FAILED'
            project.save(update_fields=['status'])


@shared_task(name="generate_narrative_blueprint_for_project")
def generate_narrative_blueprint_task(project_id: str):
    """
    (L3 Tab 按钮触发)
    为给定的 AnnotationProject 生成叙事蓝图。
    成功后，链式触发 'calculate_local_metrics_task'。
    """
    project = None
    try:
        project = AnnotationProject.objects.get(id=project_id)

        # 1. 更新项目状态为“蓝图生成中”
        project.status = 'L3_BLUEPRINT_PROCESSING'
        project.save(update_fields=['status'])
        logger.info(f"开始为项目 {project.name} (ID: {project_id}) 生成叙事蓝图...")

        # 2. 检查输入文件是否就绪
        if not project.label_studio_export_file or not project.label_studio_export_file.path:
            raise ValueError(f"项目 {project.id} 缺少 L2 标注导出文件，无法生成蓝图。")

        # 3. 构建 task_id (L2 Job) -> ass_path (L1 Job) 的映射
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

        # 6. 更新最终状态为“待处理” (等待下一步矩阵计算)
        project.status = 'PENDING'
        project.save(update_fields=['final_blueprint_file', 'status'])
        logger.info(f"成功为项目 {project.name} 生成并保存了叙事蓝图！")

        # 7. 链式调用：立即触发本地矩阵计算
        calculate_local_metrics_task.delay(project_id=str(project.id))

    except Exception as e:
        logger.error(f"为项目 {project_id} 生成叙事蓝图时发生错误: {e}", exc_info=True)
        if project:
            project.status = 'FAILED'
            project.save(update_fields=['status'])
        raise  # 重新引发异常，Celery 会将其标记为 FAILED


@shared_task
def trigger_character_audit_task(project_id: str):
    """
    (L1 Tab 按钮触发)
    Celery 任务触发器。
    所有复杂的业务逻辑都已移至 L1AuditService。
    """
    logger.info(f"Task trigger_character_audit_task received for project_id: {project_id}")
    project = None
    try:
        service = L1AuditService(project_id=project_id)
        project = service.project  # 获取 project 实例以备 except 块使用

        # 1. 设置项目状态为“L1 审计中”
        project.status = 'L1_AUDIT_PROCESSING'
        project.save(update_fields=['status'])

        # 2. 执行审计 (这会保存两个 CSV 文件)
        service.generate_audit_report()

        # 3. 任务完成，重置项目状态
        project.status = 'PENDING'
        project.save(update_fields=['status'])

    except Exception as e:
        logger.error(f"L1 审计任务失败 (Project ID: {project_id}): {e}", exc_info=True)
        if project:
            project.status = 'FAILED'
            project.save(update_fields=['status'])
        # (如果 L1AuditService 初始化失败, project 将为 None, 无法设置 FAILED 状态)


@shared_task
def calculate_local_metrics_task(project_id: str):
    """
    (L3 Tab 按钮触发 / 或由蓝图任务链式调用)
    在本地计算角色矩阵。
    读取 'final_blueprint_file'，运行计算器，
    并保存到 'local_metrics_result_file'。
    """
    logger.info(f"开始为 project {project_id} 本地计算角色矩阵...")
    project = None
    try:
        project = AnnotationProject.objects.get(id=project_id)

        # 1. 设置项目状态为“L3 矩阵计算中”
        project.status = 'L3_METRICS_PROCESSING'
        project.save(update_fields=['status'])
    except AnnotationProject.DoesNotExist:
        logger.error(f"Task: Project {project_id} not found.")
        return

    # 2. 确保蓝图文件存在
    if not project.final_blueprint_file:
        error_msg = f"Task: Project {project_id} 没有 final_blueprint_file，无法计算矩阵。"
        logger.error(error_msg)
        project.status = 'FAILED'
        # (你可能还想在这里保存一个错误信息字段)
        project.save(update_fields=['status'])
        return

    try:
        # 3. 读取蓝图文件 (已修复: 'rb' -> .read() -> .decode())
        with project.final_blueprint_file.open('rb') as f:
            blueprint_bytes = f.read()
        blueprint_str = blueprint_bytes.decode('utf-8')
        blueprint_data = json.loads(blueprint_str)

        # 4. 运行计算器 (Code 2 逻辑)
        calculator = CharacterMetricsCalculator()
        report_data = calculator.execute(blueprint_data)

        # 5. 将结果 (字典) 转换回 JSON 字符串
        report_json_str = json.dumps(report_data, ensure_ascii=False, indent=2)
        file_name = f"local_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # 6. 保存到新字段 (延迟 save)
        project.local_metrics_result_file.save(
            file_name,
            ContentFile(report_json_str.encode('utf-8')),
            save=False
        )

        # 7. 任务完成，标记项目为“已完成”
        # (这是 annotation 工作流的最后一个本地步骤)
        project.status = 'COMPLETED'
        project.save(update_fields=['local_metrics_result_file', 'status'])
        logger.info(f"Project {project_id} 的本地角色矩阵已成功计算并保存。")

    except Exception as e:
        logger.error(f"为 {project_id} 计算本地角色矩阵时失败: {e}", exc_info=True)
        if project:
            project.status = 'FAILED'
            project.save(update_fields=['status'])