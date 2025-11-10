# 文件路径: apps/workflow/projects/annotationProject.py

from django.db import models
from ..common.baseProject import BaseProject # <-- 导入 BaseProject

def get_ls_export_upload_path(instance, filename):
    """为Label Studio导出文件生成动态路径"""
    return f'annotation/{instance.id}/ls_exports/{filename}'

def get_l1_output_upload_path(instance, filename):
    """为Label Studio导出文件生成动态路径"""
    return f'annotation/{instance.id}/l1_exports/{filename}'

def get_blueprint_upload_path(instance, filename):
    """为最终蓝图文件生成动态路径"""
    return f'annotation/{instance.id}/blueprints/{filename}'

def get_cloud_output_upload_path(instance, filename):
    """为云端推理产出物生成动态路径"""
    return f'annotation/{instance.id}/cloud_outputs/{filename}'

class AnnotationProject(BaseProject):
    """
    一个具体的标注工作项目。
    它继承了 BaseProject 的所有通用字段，并可以添加自己独有的字段。
    """
    source_encoding_profile = models.ForeignKey(
        'configuration.EncodingProfile',
        on_delete=models.PROTECT,
        null=True, # 允许为空，但我们会在 admin 中设为必填
        blank=False,
        verbose_name="源编码配置",
        help_text="选择一个编码配置。标注工具将使用此配置转码后的视频，以加快加载速度。"
    )

    # --- 过程产出物字段 ---
    label_studio_project_id = models.IntegerField(blank=True, null=True, verbose_name="Label Studio 项目ID")
    label_studio_export_file = models.FileField(upload_to=get_ls_export_upload_path, blank=True, null=True, verbose_name="Label Studio 导出文件")

    character_audit_report = models.FileField(upload_to='audit_reports/l1_character/', blank=True, null=True, verbose_name="角色名审计报告 (CSV)")
    character_occurrence_report = models.FileField(
        upload_to='audit_reports/l1_character_occurrences/',
        blank=True, null=True,
        verbose_name="角色出现详情 (日志)"
    )

    blueprint_validation_report = models.JSONField(blank=True, null=True, verbose_name="叙事蓝图验证报告")
    final_blueprint_file = models.FileField(upload_to=get_blueprint_upload_path, blank=True, null=True, verbose_name="最终叙事蓝图 (JSON)")
    local_metrics_result_file = models.FileField(
        upload_to=get_cloud_output_upload_path,  # 复用 L3 产出物的路径
        blank=True, null=True,
        verbose_name="角色矩阵产出 (本地)"
    )

    BLUEPRINT_STATUS_CHOICES = (
        ('PENDING', '未开始'),
        ('PROCESSING', '生成中'),
        ('COMPLETED', '已完成'),
        ('FAILED', '失败'),
    )
    blueprint_status = models.CharField(
        max_length=20,
        choices=BLUEPRINT_STATUS_CHOICES,
        default='PENDING',
        verbose_name="蓝图生成状态"
    )

    # --- [!!! 新增字段 !!!] ---
    CLOUD_REASONING_STATUS_CHOICES = (
        ('PENDING', '未开始'),
        ('BLUEPRINT_UPLOADING', '上传蓝图'),
        ('METRICS_RUNNING', '分析角色矩阵'),
        ('WAITING_FOR_SELECTION', '等待角色选择'),  # “中断”状态
        ('FACTS_RUNNING', '识别角色属性'),
        ('PIPELINE_RUNNING', '执行自动流水线'),
        ('RAG_DEPLOYING', '部署知识图谱'),
        ('COMPLETED', '已完成'),
        ('FAILED', '失败'),
    )
    cloud_reasoning_status = models.CharField(
        max_length=30,
        choices=CLOUD_REASONING_STATUS_CHOICES,
        default='PENDING',
        verbose_name="云端推理状态"
    )
    cloud_reasoning_error = models.TextField(blank=True, null=True, verbose_name="推理失败信息")

    # --- 存储云端任务 ID 和路径 ---
    cloud_blueprint_path = models.CharField(max_length=1024, blank=True, null=True, verbose_name="云端蓝图路径")
    cloud_facts_path = models.CharField(max_length=1024, blank=True, null=True, verbose_name="云端角色属性路径")

    # --- 存储云端任务产出物 ---
    cloud_metrics_result_file = models.FileField(
        upload_to=get_cloud_output_upload_path,
        blank=True, null=True, verbose_name="角色矩阵产出 (JSON)"
    )
    cloud_facts_result_file = models.FileField(
        upload_to=get_cloud_output_upload_path,
        blank=True, null=True, verbose_name="角色属性产出 (JSON)"
    )
    cloud_rag_report_file = models.FileField(
        upload_to=get_cloud_output_upload_path,
        blank=True, null=True, verbose_name="RAG 部署报告 (JSON)"
    )

    def get_label_studio_project_url(self):
        if not self.label_studio_project_id: return None
        from django.conf import settings
        return f"{settings.LABEL_STUDIO_PUBLIC_URL}/projects/{self.label_studio_project_id}"

    def save(self, *args, **kwargs):
        """
        重写 save 方法，在首次创建 AnnotationProject 时，触发与 Label Studio 同步的后台任务。
        """
        from .tasks import create_label_studio_project_task
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new:
            create_label_studio_project_task.delay(project_id=str(self.id))

    class Meta:
        verbose_name = "标注项目"
        verbose_name_plural = "标注项目"