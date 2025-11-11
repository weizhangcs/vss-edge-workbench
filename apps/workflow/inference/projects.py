# 文件路径: apps/workflow/inference/projects.py

from django.db import models
from model_utils import Choices
from django_fsm import FSMField, transition

from apps.workflow.common.baseProject import BaseProject
from apps.workflow.common.baseJob import BaseJob
from apps.workflow.annotation.projects import AnnotationProject


def get_cloud_output_upload_path(instance, filename):
    """
    为 InferenceJob 产出物生成动态路径。
    """
    if instance.project and instance.project.annotation_project:
        return f'inference/{instance.project.annotation_project.id}/jobs/{instance.id}_{filename}'
    return f'inference/unknown/jobs/{instance.id}_{filename}'


class InferenceProject(BaseProject):
    """
    (已重构 V3)
    L3 云端推理项目。
    一个“容器”，严格一对一关联到“标注项目”。
    """
    annotation_project = models.OneToOneField(
        AnnotationProject,
        on_delete=models.CASCADE,
        related_name='inference_project',
        verbose_name="关联的标注项目"
    )

    class Meta:
        verbose_name = "L3 推理项目"
        verbose_name_plural = "L3 推理项目"

    def __str__(self):
        # 名字继承自 BaseProject，但 __str__ 可以更具体
        return f"推理: {self.name}"


class InferenceJob(BaseJob):
    """
    (已重构 V3.1)
    跟踪一个单独的、异步的云端推理任务。
    (已移除所有自定义 transition，现在 100% 继承 BaseJob 的状态方法)
    """

    TYPE = Choices(
        ('FACTS', '角色属性识别'),
        ('RAG_DEPLOYMENT', '知识图谱部署')
    )

    project = models.ForeignKey(
        InferenceProject,
        on_delete=models.CASCADE,
        related_name='jobs',
        verbose_name="所属推理项目"
    )

    job_type = models.CharField(
        max_length=20,
        choices=TYPE,
        verbose_name="任务类型"
    )

    # --- 输入 ---
    input_params = models.JSONField(blank=True, null=True, verbose_name="输入参数")

    # --- 外部跟踪 ---
    cloud_task_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="云端任务 ID")

    # [!!! 步骤 1: 添加这个缺失的字段 !!!]
    # (这个字段由 'start_cloud_facts_task' 填充)
    cloud_blueprint_path = models.CharField(max_length=1024, blank=True, null=True, verbose_name="云端蓝图路径")

    # (这个字段由 'finalize_facts_task' 填充)
    cloud_facts_path = models.CharField(max_length=1024, blank=True, null=True, verbose_name="云端角色属性路径")

    # --- 产出物 (由轮询任务填充) ---
    output_facts_file = models.FileField(
        upload_to=get_cloud_output_upload_path,
        blank=True, null=True, verbose_name="角色属性产出 (JSON)"
    )
    output_rag_report_file = models.FileField(
        upload_to=get_cloud_output_upload_path,
        blank=True, null=True, verbose_name="RAG 部署报告 (JSON)"
    )

    # [!!! 修复: 所有自定义 @transition 都已删除 !!!]
    # (InferenceJob 现在将使用 BaseJob 的 .start(), .complete(), .fail() 方法)

    class Meta:
        verbose_name = "L3 推理子任务"
        verbose_name_plural = "L3 推理子任务"
        ordering = ['-created']

    def __str__(self):
        return f"{self.get_job_type_display()} (ID: {self.id})"