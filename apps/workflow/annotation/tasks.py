import logging

from celery import shared_task

from .projects import AnnotationProject

logger = logging.getLogger(__name__)


@shared_task
def generate_blueprint_task(project_id):
    """
    [异步] 生成生产蓝图 (Blueprint)
    """
    try:
        project = AnnotationProject.objects.get(id=project_id)
        project.generate_blueprint()
        return f"Blueprint generated for {project.name}"
    except Exception as e:
        logger.error(f"Blueprint Error {project_id}: {e}", exc_info=True)
        raise e


@shared_task
def export_project_package_task(project_id):
    """
    [异步] 导出工程包 (Context Full)
    """
    try:
        project = AnnotationProject.objects.get(id=project_id)
        project.export_project_annotation()
        return f"Project package exported for {project.name}"
    except Exception as e:
        logger.error(f"Export Error {project_id}: {e}", exc_info=True)
        raise e


@shared_task
def run_project_audit_task(project_id):
    """
    [异步] 执行数据审计
    """
    try:
        project = AnnotationProject.objects.get(id=project_id)
        project.run_audit()
        return f"Audit finished for {project.name}"
    except Exception as e:
        logger.error(f"Audit Error {project_id}: {e}", exc_info=True)
        raise e
