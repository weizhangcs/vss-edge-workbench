# 文件路径: apps/workflow/delivery/tasks.py

from celery import shared_task
import logging

from ..models import DeliveryJob, TranscodingJob
from apps.media_assets.services.storage import StorageService

logger = logging.getLogger(__name__)


@shared_task
def run_delivery_job(job_id):
    """
    执行一个具体的分发任务。
    """
    try:
        job = DeliveryJob.objects.get(id=job_id)
    except DeliveryJob.DoesNotExist:
        logger.error(f"找不到 ID 为 {job_id} 的分发任务。")
        return

    job.start()
    job.save()

    try:
        source_job = job.source_object
        # 确保源文件存在
        if not hasattr(source_job, 'output_file') or not source_job.output_file.path:
            raise ValueError(f"源对象 {source_job} 没有可用的 output_file。")

        local_file_path = source_job.output_file.path

        # 调用 StorageService 执行上传
        storage_service = StorageService()

        # --- 核心逻辑：根据源对象的类型调用不同的上传方法 ---
        # 这样设计可以轻松扩展，比如未来支持分发标注产物等
        if isinstance(source_job, TranscodingJob):
            final_url = storage_service.save_transcoded_video(
                local_temp_path=local_file_path,
                job=source_job
            )
        else:
            raise TypeError(f"不支持的源对象类型: {type(source_job)}")

        # 回写最终 URL 到 DeliveryJob 和源 Job
        job.delivery_url = final_url
        job.complete()
        job.save()

        # 也将 URL 更新回源 TranscodingJob
        source_job.output_url = final_url
        source_job.save(update_fields=['output_url'])

        logger.info(f"分发任务 {job_id} 成功完成！URL: {final_url}")

    except Exception as e:
        logger.error(f"分发任务 {job_id} 失败: {e}", exc_info=True)
        job.fail()
        job.save()
        raise e