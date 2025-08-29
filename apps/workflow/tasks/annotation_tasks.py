# 文件路径: apps/workflow/tasks/annotation_tasks.py

import logging
from celery import shared_task

# 获取一个日志记录器实例
logger = logging.getLogger(__name__)


@shared_task(name="create_label_studio_project_for_annotation")
def create_label_studio_project_task(project_id: str):
    """
    一个Celery后台任务，负责为给定的AnnotationProject创建Label Studio项目，
    并为每一个关联的Media文件创建所有初始的AnnotationJob记录。
    """
    from apps.workflow.models import AnnotationProject, AnnotationJob
    from apps.workflow.services.label_studio import LabelStudioService

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

    success, message, ls_project_id, task_mapping = service.create_project_for_asset(asset=project.asset)

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