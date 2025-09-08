# 文件路径: apps/workflow/projects/annotationProject.py

from django.db import models
from .baseProject import BaseProject # <-- 导入 BaseProject

def get_ls_export_upload_path(instance, filename):
    """为Label Studio导出文件生成动态路径"""
    return f'annotation/{instance.id}/ls_exports/{filename}'

def get_blueprint_upload_path(instance, filename):
    """为最终蓝图文件生成动态路径"""
    return f'annotation/{instance.id}/blueprints/{filename}'

class AnnotationProject(BaseProject):
    """
    一个具体的标注工作项目。
    它继承了 BaseProject 的所有通用字段，并可以添加自己独有的字段。
    """
    # --- 过程产出物字段 ---
    label_studio_project_id = models.IntegerField(blank=True, null=True, verbose_name="Label Studio 项目ID")
    label_studio_export_file = models.FileField(upload_to=get_ls_export_upload_path, blank=True, null=True, verbose_name="Label Studio 导出文件")

    character_audit_report = models.FileField(upload_to='audit_reports/l1_character/', blank=True, null=True, verbose_name="角色名审计报告 (CSV)")

    blueprint_validation_report = models.JSONField(blank=True, null=True, verbose_name="叙事蓝图验证报告")
    final_blueprint_file = models.FileField(upload_to=get_blueprint_upload_path, blank=True, null=True, verbose_name="最终叙事蓝图 (JSON)")

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

    def get_label_studio_project_url(self):
        if not self.label_studio_project_id: return None
        from django.conf import settings
        return f"{settings.LABEL_STUDIO_PUBLIC_URL}/projects/{self.label_studio_project_id}"

    def save(self, *args, **kwargs):
        """
        重写 save 方法，在首次创建 AnnotationProject 时，触发与 Label Studio 同步的后台任务。
        """
        from ..tasks.annotation_tasks import create_label_studio_project_task
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new:
            create_label_studio_project_task.delay(project_id=str(self.id))

    class Meta:
        verbose_name = "标注项目"
        verbose_name_plural = "标注项目"