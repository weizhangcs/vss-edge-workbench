# 文件路径: apps/workflow/annotation/jobs.py

import logging

from django.core.files.storage import FileSystemStorage
from django.db import models
from django_fsm import transition

from apps.media_assets.models import Media

from ..common.baseJob import BaseJob

logger = logging.getLogger(__name__)

# 定义存储位置 (保持原有的 Docker 卷映射逻辑)
fs = FileSystemStorage(location="/app/media_root")


def get_annotation_upload_path(instance, filename):
    """
    为原子工程文件生成动态路径。
    结构: annotation/<project_id>/jobs/<job_id>_<filename>
    例如: annotation/10/jobs/55_scene_data.json
    """
    return f"annotation/{instance.project.id}/jobs/{instance.id}_{filename}"


class AnnotationJob(BaseJob):
    """
    (V5.1 重构版)
    标注工作流的“原子任务”模型。
    对应 Schemas.MediaAnnotation。

    职责：
    1. 维护 Media 与 Project 的多对一关系。
    2. 存储该 Media 对应的全量工程数据 (JSON)。
    3. 跟踪任务状态 (Pending -> Processing -> Completed)。
    """

    # --- 关联关系 ---
    project = models.ForeignKey(
        "AnnotationProject", on_delete=models.CASCADE, related_name="jobs", verbose_name="所属标注项目"
    )

    media = models.ForeignKey(Media, on_delete=models.CASCADE, related_name="annotation_jobs", verbose_name="关联媒体文件")

    # --- 核心产出物 (SSOT) ---
    # 存储 Schemas.MediaAnnotation 的 JSON 文件
    # 包含：Scenes, Dialogues, Captions, Highlights 及其 Context (is_verified, origin)
    annotation_file = models.FileField(
        storage=fs, upload_to=get_annotation_upload_path, blank=True, null=True, verbose_name="标注工程文件 (JSON)"
    )

    # --- 状态机转换 (继承自 BaseJob 的 'status' 字段) ---

    @transition(field="status", source=BaseJob.STATUS.PENDING, target=BaseJob.STATUS.PROCESSING)
    def start_annotation(self):
        """
        开始标注 (PENDING -> PROCESSING)
        通常由用户在 Workbench 中首次加载或点击“开始”触发。
        """
        pass

    @transition(
        field="status",
        source=[
            BaseJob.STATUS.PROCESSING,
            BaseJob.STATUS.REVISING,
            BaseJob.STATUS.ERROR,
        ],
        target=BaseJob.STATUS.COMPLETED,
    )
    def complete_annotation(self):
        """
        完成标注 (PROCESSING/REVISING -> COMPLETED)
        用户点击“提交/完成”时触发，表明该文件的标注已通过人工确认。
        """
        pass

    @transition(field="status", source=BaseJob.STATUS.COMPLETED, target=BaseJob.STATUS.REVISING)
    def revise(self):
        """
        修订任务 (COMPLETED -> REVISING)
        当已完成的任务需要重新修改时触发。

        [注]: 旧版这里有 l1_output_file 的备份逻辑。
        在 V5.1 中，建议将"版本控制"逻辑移至 Service 层 (如 AnnotationService.save_annotation)，
        在保存新 JSON 前自动备份旧 JSON，保持 Model 层纯净。
        """
        super().revise()

    def __str__(self):
        return f"Job {self.id} | {self.media.title} ({self.get_status_display()})"

    class Meta:
        verbose_name = "标注任务"
        verbose_name_plural = verbose_name
        # 默认按媒体序列号排序，保证生成 Blueprint 时章节顺序正确
        ordering = ["media__sequence_number", "id"]
