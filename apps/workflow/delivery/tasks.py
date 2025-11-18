# 文件路径: apps/workflow/delivery/tasks.py

from celery import shared_task
import logging

from ..common.baseJob import BaseJob
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

    # [FIX 4a] 检查源任务，如果源任务不是 QA_PENDING，则不应运行
    source_job = job.source_object
    if not source_job:
        logger.error(f"分发任务 {job_id} 找不到源对象。任务失败。")
        job.fail()
        job.save()
        return

    if source_job.status != BaseJob.STATUS.QA_PENDING:
        logger.error(f"源任务 {source_job.id} 状态为 {source_job.status} (不是 QA_PENDING)。分发任务 {job_id} 中止。")
        # 如果源任务已经失败，我们也标记分发失败
        job.fail()
        job.save()
        return

    # 源任务状态正确 (QA_PENDING)，我们开始处理
    job.start()
    job.save()

    try:
        # 确保源文件存在
        if not hasattr(source_job, 'output_file') or not source_job.output_file.path:
            raise ValueError(f"源对象 {source_job} 没有可用的 output_file。")

        local_file_path = source_job.output_file.path

        # 调用 StorageService 执行上传
        storage_service = StorageService()

        # --- 核心逻辑：根据源对象的类型调用不同的上传方法 ---
        if isinstance(source_job, TranscodingJob):
            final_url = storage_service.save_transcoded_video(
                local_temp_path=local_file_path,
                job=source_job
            )
        else:
            raise TypeError(f"不支持的源对象类型: {type(source_job)}")

        # 回写最终 URL 到 DeliveryJob
        job.delivery_url = final_url
        job.complete()
        job.save()

        # [FIX 4b] 将 URL 更新回源 TranscodingJob 并将其标记为 COMPLETED
        source_job.output_url = final_url
        source_job.complete()  # (现在 'QA_PENDING' -> 'COMPLETED' 是允许的)
        source_job.save(update_fields=['output_url', 'status'])

        logger.info(f"分发任务 {job_id} 成功完成！URL: {final_url}")

    except Exception as e:
        logger.error(f"分发任务 {job_id} 失败: {e}", exc_info=True)
        job.fail()
        job.save()

        # [FIX 4c] 如果分发失败，将源 TranscodingJob 标记为 ERROR
        try:
            source_job.fail() # ( 'QA_PENDING' -> 'ERROR' 是允许的)
            source_job.save(update_fields=['status'])
        except Exception as e_inner:
            logger.error(f"无法将源任务 {source_job.id} 标记为失败: {e_inner}")

        raise e