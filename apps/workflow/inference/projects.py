# 文件路径: apps/workflow/inference/models.py

from django.db import models

from apps.workflow.common.baseProject import BaseProject
from apps.workflow.annotation.projects import AnnotationProject

def get_cloud_output_upload_path(instance, filename):
    if instance.annotation_project:
        return f'inference/{instance.annotation_project.id}/cloud_outputs/{filename}'
    return f'inference/unknown/cloud_outputs/{filename}'

class InferenceProject(BaseProject):
    """
    (新) L3 云端推理项目。
    严格一对一关联到“标注项目”。
    """
    annotation_project = models.OneToOneField(
        AnnotationProject,
        on_delete=models.CASCADE,
        related_name='inference_project',
        verbose_name="关联的标注项目"
    )

    # (从 AnnotationProject 迁移过来的所有 cloud_... 字段)
    CLOUD_REASONING_STATUS_CHOICES = (
        ('PENDING', '未开始'),
        ('BLUEPRINT_UPLOADING', '上传蓝图'),
        ('METRICS_RUNNING', '分析角色矩阵'),
        ('WAITING_FOR_SELECTION', '等待角色选择'),
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
    cloud_blueprint_path = models.CharField(max_length=1024, blank=True, null=True, verbose_name="云端蓝图路径")
    cloud_facts_path = models.CharField(max_length=1024, blank=True, null=True, verbose_name="云端角色属性路径")

    cloud_facts_result_file = models.FileField(
        upload_to=get_cloud_output_upload_path,
        blank=True, null=True, verbose_name="角色属性产出 (JSON)"
    )
    cloud_rag_report_file = models.FileField(
        upload_to=get_cloud_output_upload_path,
        blank=True, null=True, verbose_name="RAG 部署报告 (JSON)"
    )

    class Meta:
        verbose_name = "L3 推理项目"
        verbose_name_plural = "L3 推理项目"

    def __str__(self):
        return f"推理: {self.annotation_project.name}"