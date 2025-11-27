# 文件路径: apps/workflow/annotation/projects.py

from django.db import models, transaction
from ..common.baseProject import BaseProject


# --- 动态路径辅助函数 ---

def get_ls_export_upload_path(instance, filename):
    """为Label Studio导出文件生成动态路径"""
    return f'annotation/{instance.id}/ls_exports/{filename}'


def get_blueprint_upload_path(instance, filename):
    """为最终蓝图文件生成动态路径"""
    return f'annotation/{instance.id}/blueprints/{filename}'


def get_cloud_output_upload_path(instance, filename):
    """为云端推理产出物生成动态路径"""
    return f'annotation/{instance.id}/cloud_outputs/{filename}'


# (移除了 get_l1_output_upload_path,因为它未在此文件中使用)

class AnnotationProject(BaseProject):
    """
    (V4.3 架构)
    标注工作流的核心项目模型。

    它继承了 BaseProject (name, description, asset 等)，
    并扩展了特定的状态和产出物字段，用于协调 L1, L2, 和 L3(本地) 的工作流。
    """

    # --- 状态 (覆盖 BaseProject) ---
    # 我们覆盖 BaseProject 的 'status' 字段，以提供更详细、
    # 专属于此工作流的状态。
    STATUS_CHOICES = (
        ('PENDING', '待处理'),
        ('PROCESSING', '处理中'),
        ('COMPLETED', '已完成'),
        ('FAILED', '失败'),
        # --- (以下是新增的特定后台任务状态) ---
        ('L1_AUDIT_PROCESSING', 'L1 审计中'),
        ('L2_EXPORTING', 'L2 导出中'),
        ('L3_BLUEPRINT_PROCESSING', 'L3 蓝图生成中'),
        ('L3_METRICS_PROCESSING', 'L3 矩阵计算中'),
    )

    status = models.CharField(
        max_length=30,  # 增加了长度以适应新状态
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name="项目状态"
    )

    # --- L2 标注配置 ---
    source_encoding_profile = models.ForeignKey(
        'configuration.EncodingProfile',
        on_delete=models.PROTECT,
        null=True,
        blank=False,
        verbose_name="源编码配置",
        help_text="选择一个编码配置。标注工具将使用此配置转码后的视频，以加快加载速度。"
    )

    label_studio_project_id = models.IntegerField(blank=True, null=True, verbose_name="Label Studio 项目ID")
    label_studio_export_file = models.FileField(upload_to=get_ls_export_upload_path, blank=True, null=True,
                                                verbose_name="Label Studio 导出文件")

    # --- L1 审计产出物 ---
    character_audit_report = models.FileField(upload_to='audit_reports/l1_character/', blank=True, null=True,
                                              verbose_name="角色审计报告 (摘要)")
    character_occurrence_report = models.FileField(
        upload_to='audit_reports/l1_character_occurrences/',
        blank=True, null=True,
        verbose_name="角色出现详情 (日志)"
    )

    # --- L3 建模产出物 (本地) ---
    blueprint_validation_report = models.JSONField(blank=True, null=True, verbose_name="叙事蓝图验证报告")
    final_blueprint_file = models.FileField(upload_to=get_blueprint_upload_path, blank=True, null=True,
                                            verbose_name="最终叙事蓝图 (JSON)")
    local_metrics_result_file = models.FileField(
        upload_to=get_cloud_output_upload_path,
        blank=True, null=True,
        verbose_name="角色矩阵产出 (本地)"
    )

    # --- 辅助方法 ---

    def get_label_studio_project_url(self):
        """
        生成一个指向此项目在 Label Studio 中对应页面的公共 URL。
        """
        if not self.label_studio_project_id: return None
        from django.conf import settings
        return f"{settings.LABEL_STUDIO_PUBLIC_URL}/projects/{self.label_studio_project_id}"

    def save(self, *args, **kwargs):
        """
        重写 save 方法。
        在首次创建 AnnotationProject 时 (is_new=True)，
        自动触发一个后台任务来创建 Label Studio 项目和 AnnotationJob 记录。
        """
        from .tasks import create_label_studio_project_task

        # 1. 检查是否是新建记录 (必须在 super().save() 之前判断)
        is_new = self._state.adding

        # 2. 执行保存 (此时数据已写入事务，但尚未提交)
        super().save(*args, **kwargs)

        # 3. 事务提交后触发任务
        if is_new:
            # [核心修正] 使用 transaction.on_commit
            # 只有当当前的数据库事务成功 Commit 后，这个 lambda 才会执行。
            # 这确保了当 Celery Worker 收到任务去查询数据库时，数据一定已经存在了。
            transaction.on_commit(
                lambda: create_label_studio_project_task.delay(project_id=str(self.id))
            )

    class Meta:
        verbose_name = "标注项目"
        verbose_name_plural = "标注项目"