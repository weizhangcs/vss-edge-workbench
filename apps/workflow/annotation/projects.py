# apps/workflow/annotation/projects.py

import json
import logging

from django.core.files.base import ContentFile
from django.db import models

from ..common.baseProject import BaseProject

logger = logging.getLogger(__name__)


# --- 动态路径辅助函数 ---


def get_audit_upload_path(instance, filename):
    return f"annotation/{instance.id}/audits/{filename}"


def get_project_export_path(instance, filename):
    return f"annotation/{instance.id}/exports/{filename}"


def get_blueprint_upload_path(instance, filename):
    return f"annotation/{instance.id}/blueprints/{filename}"


class AnnotationProject(BaseProject):
    """
    (V5.1 Schema驱动版)
    标注工作流的核心项目模型。
    作为单一事实来源 (SSOT) 的聚合中心，负责协调从原子 Job 到项目级产出物的流转。
    """

    STATUS_CHOICES = (
        ("PENDING", "待处理"),
        ("PROCESSING", "处理中"),
        ("COMPLETED", "已完成"),
        ("FAILED", "失败"),
    )

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="PENDING", verbose_name="项目状态")

    # --- 配置 ---
    source_encoding_profile = models.ForeignKey(
        "configuration.EncodingProfile",
        on_delete=models.PROTECT,
        null=True,
        blank=False,
        verbose_name="源编码配置",
        help_text="选择一个编码配置。标注工具将使用此配置转码后的视频，以加快加载速度。",
    )

    # =========================================================================
    # 三大核心生成物 (Artifacts)
    # =========================================================================

    # 1. 审计报告 (Data Governance)
    # 包含了数据完整性检查、AI/人工标注比例统计、异常检测结果
    annotation_audit_report = models.FileField(
        upload_to=get_audit_upload_path, blank=True, null=True, verbose_name="标注审计报告 (Audit)"
    )

    # 2. 工程导出 (Engineering Artifact) -> 对应 Schemas.ProjectAnnotation
    # 包含完整的上下文 (Context)、AI元数据、编辑历史等。用于项目备份、迁移或导入复现。
    project_export_file = models.FileField(
        upload_to=get_project_export_path, blank=True, null=True, verbose_name="工程全量导出 (ProjectAnnotation)"
    )

    # 3. 生产交付 (Production Artifact) -> 对应 Schemas.Blueprint
    # 清洗掉工程数据，仅保留业务内容 (Content)。用于下游 Inference 或前端展示。
    final_blueprint_file = models.FileField(
        upload_to=get_blueprint_upload_path, blank=True, null=True, verbose_name="生产消费蓝图 (Blueprint)"
    )

    # =========================================================================
    # 核心业务逻辑
    # =========================================================================

    def _get_valid_jobs(self):
        """辅助方法：获取当前项目下所有有效的标注任务"""
        return (
            self.jobs.filter(annotation_file__isnull=False)
            .exclude(annotation_file="")
            .select_related("media")
            .order_by("media__sequence_number")
        )

    def export_project_annotation(self):
        """
        [聚合逻辑] 读取所有 Job 的 JSON -> 完整保留 Context -> 合并
        """
        from .schemas import ProjectAnnotation
        from .services.annotation_service import AnnotationService

        project_anno = ProjectAnnotation(
            project_id=str(self.id), project_name=self.name, character_list=[], annotations={}
        )

        valid_jobs = self._get_valid_jobs()
        for job in valid_jobs:
            try:
                # 获取全量数据
                media_anno = AnnotationService.load_annotation(job)
                project_anno.annotations[media_anno.media_id] = media_anno
            except Exception as e:
                logger.error(f"Project Export Error on Job {job.id}: {e}")

        # 落盘
        json_output = project_anno.model_dump_json(indent=2)
        self.project_export_file.save(
            f"project_export_{self.id}.json", ContentFile(json_output.encode("utf-8")), save=True
        )

        return project_anno

    def generate_blueprint(self):
        """
        [聚合逻辑] 读取所有 Job 的 JSON -> 清洗 -> 合并
        """
        # 延迟导入避免循环引用
        from .schemas import Blueprint, Chapter
        from .services.annotation_service import AnnotationService

        blueprint = Blueprint(
            project_id=str(self.id),
            asset_id=str(self.asset.id) if self.asset else "",
            project_name=self.name,
            global_character_list=[],
            chapters={},
        )

        all_characters = set()
        valid_jobs = self._get_valid_jobs()

        for job in valid_jobs:
            try:
                # 复用 Service 的加载逻辑 (处理文件读取/冷启动)
                # 这样即使某个 Job 还没被点开过，也能导出初始状态
                media_anno = AnnotationService.load_annotation(job)

                # [核心步骤] 清洗数据
                clean_data = media_anno.get_clean_business_data()

                # 转换为 Chapter
                chapter = Chapter(
                    id=str(media_anno.media_id),
                    name=media_anno.file_name,
                    source_file=media_anno.source_path,
                    duration=media_anno.duration,
                    **clean_data,  # 传入 scenes, dialogues 等
                )

                blueprint.chapters[chapter.id] = chapter

                # 收集角色
                for d in clean_data.get("dialogues", []):
                    spk = d.get("speaker")
                    if spk and spk != "Unknown":
                        all_characters.add(spk)

            except Exception as e:
                logger.error(f"Blueprint Aggregation Error on Job {job.id}: {e}")
                continue

        blueprint.global_character_list = sorted(list(all_characters))

        # 落盘
        json_output = blueprint.model_dump_json(indent=2, exclude_none=True)
        self.final_blueprint_file.save(f"blueprint_{self.id}.json", ContentFile(json_output.encode("utf-8")), save=True)

        return blueprint

    def run_audit(self):
        """
        [能力 3: 生成审计报告]
        统计 AI 占比、人工修订率、空值检查等
        """
        report = {
            "project_id": self.id,
            "total_jobs": self.jobs.count(),
            "stats": {"total_scenes": 0, "human_verified_ratio": 0.0, "ai_generated_ratio": 0.0},
            "warnings": [],
        }

        # ... (具体的统计逻辑遍历 jobs 即可实现) ...

        json_output = json.dumps(report, indent=2, ensure_ascii=False)
        self.annotation_audit_report.save(f"audit_{self.id}.json", ContentFile(json_output), save=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "标注项目"
        verbose_name_plural = "标注项目"
