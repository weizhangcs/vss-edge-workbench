# 文件路径: apps/workflow/annotation/jobs.py

import logging

from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import models
from django_fsm import transition

from apps.media_assets.models import Media

from ..common.baseJob import BaseJob

logger = logging.getLogger(__name__)

# 定义存储位置 (保持原有的 Docker 卷映射逻辑)
fs = FileSystemStorage(location="/app/media_root")


def get_annotation_upload_path(instance, filename):
    # 动态路径: annotation/<project_id>/jobs/<job_id>_<filename>
    return f"annotation/{instance.project.id}/jobs/{instance.id}_{filename}"


class AnnotationJob(BaseJob):
    """
    (V5.2 A/B 双缓冲版)
    标注工作流的“原子任务”模型。
    新增 Current/Backup 版本管理机制。
    """

    # --- 关联关系 ---
    project = models.ForeignKey(
        "AnnotationProject", on_delete=models.CASCADE, related_name="jobs", verbose_name="所属标注项目"
    )

    media = models.ForeignKey(Media, on_delete=models.CASCADE, related_name="annotation_jobs", verbose_name="关联媒体文件")

    # --- 核心产出物 (SSOT) ---

    # 1. Current (当前工作版本)
    annotation_file = models.FileField(
        storage=fs, upload_to=get_annotation_upload_path, blank=True, null=True, verbose_name="标注工程文件 (Current)"
    )

    # 2. Backup (上一版本/修订前快照)
    # [新增] 用于支持 A/B 轮转和 Revise 回滚
    annotation_file_backup = models.FileField(
        storage=fs, upload_to=get_annotation_upload_path, blank=True, null=True, verbose_name="标注工程文件 (Backup)"
    )

    # --- 基础设施: A/B 轮转逻辑 ---

    def rotate_and_save(self, content_str: str, save_to_db: bool = True):
        """
        [Job级 A/B 轮转]
        当保存新的标注数据时调用：
        1. Current -> Backup
        2. New -> Current
        """
        # 1. 备份 Current -> Backup
        if self.annotation_file:
            try:
                self.annotation_file.open("rb")
                existing_content = self.annotation_file.read()
                self.annotation_file.close()

                if existing_content:
                    backup_filename = f"job_{self.id}_backup.json"
                    self.annotation_file_backup.save(backup_filename, ContentFile(existing_content), save=False)
            except Exception as e:
                logger.warning(f"Job {self.id}: Failed to rotate backup: {e}")

        # 2. 写入 New -> Current
        new_filename = f"job_{self.id}_annotation.json"
        self.annotation_file.save(
            new_filename, ContentFile(content_str.encode("utf-8")), save=save_to_db  # 由调用者决定是否立即落盘
        )

    def rollback_to_backup(self):
        """
        [回滚能力]
        当用户点击“放弃修订”或“回退”时调用。
        将 Backup 覆盖回 Current。
        """
        if not self.annotation_file_backup:
            return False, "No backup available."

        try:
            self.annotation_file_backup.open("rb")
            backup_content = self.annotation_file_backup.read()
            self.annotation_file_backup.close()

            # 覆盖 Current
            self.annotation_file.save(f"job_{self.id}_annotation.json", ContentFile(backup_content), save=True)
            return True, "Rollback successful."
        except Exception as e:
            return False, str(e)

    # --- 状态机转换 ---

    @transition(field="status", source=BaseJob.STATUS.PENDING, target=BaseJob.STATUS.PROCESSING)
    def start_annotation(self):
        """开始标注"""
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
        """完成标注"""
        pass

    @transition(field="status", source=BaseJob.STATUS.COMPLETED, target=BaseJob.STATUS.REVISING)
    def revise(self):
        """
        [修订逻辑增强]
        当任务从 COMPLETED 变为 REVISING 时，强制执行一次备份。
        这样如果修订改乱了，用户可以用 rollback_to_backup 恢复到 COMPLETED 时的状态。
        """
        # 显式触发一次“原地轮转”：把 Current 复制给 Backup，Current 保持不变
        if self.annotation_file:
            try:
                self.annotation_file.open("rb")
                content = self.annotation_file.read()
                self.annotation_file.close()

                # 写入 Backup
                self.annotation_file_backup.save(
                    f"job_{self.id}_revise_backup.json",
                    ContentFile(content),
                    save=False,  # 状态转换通常会在 View 层调 save()，这里先更新内存
                )
            except Exception as e:
                logger.warning(f"Job {self.id}: Failed to create revise backup: {e}")

        # 状态变更交给 django-fsm
        super().revise()

    def __str__(self):
        return f"Job {self.id} | {self.media.title} ({self.get_status_display()})"

    class Meta:
        verbose_name = "标注任务"
        verbose_name_plural = verbose_name
        ordering = ["media__sequence_number", "id"]
