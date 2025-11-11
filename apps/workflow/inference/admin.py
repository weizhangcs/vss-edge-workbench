# 文件路径: apps/workflow/inference/admin.py

import json
import logging
from django.contrib import admin, messages
from django.core.paginator import Paginator
from django.http import HttpRequest
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import path, reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from .projects import InferenceProject, InferenceJob
from .forms import InferenceProjectForm, CharacterSelectionForm
from apps.workflow.models import AnnotationProject
from ..common.baseJob import BaseJob  # (用于 status_choices)

logger = logging.getLogger(__name__)


# [!!! 步骤 2: 添加新的 Tab 生成器 (复制自 annotation/admin.py) !!!]
def get_inference_project_tabs(request: HttpRequest) -> list[dict]:
    """
    (新)
    为 InferenceProject 动态生成 Tab 导航。
    (在 settings.py 中被 "tabs" 键引用)
    """
    object_id = None
    if request.resolver_match and "object_id" in request.resolver_match.kwargs:
        object_id = request.resolver_match.kwargs.get("object_id")

    current_view_name = request.resolver_match.view_name

    # 必须与 InferenceProjectAdmin.change_view 匹配
    default_change_view_name = "admin:workflow_inferenceproject_change"

    tab_items = []
    if object_id:
        tab_items = [
            {
                "title": "第一步：识别",
                "link": reverse("admin:workflow_inferenceproject_tab_1_facts", args=[object_id]),
                "active": current_view_name in [
                    "admin:workflow_inferenceproject_tab_1_facts",
                    default_change_view_name  # (将 change_view 视为 Tab 1)
                ]
            },
            {
                "title": "第二步：更新知识图谱",
                "link": reverse("admin:workflow_inferenceproject_tab_2_rag", args=[object_id]),
                "active": current_view_name == "admin:workflow_inferenceproject_tab_2_rag"
            },
        ]

    return [
        {
            "models": [
                {
                    "name": "workflow.inferenceproject",
                    "detail": True,
                }
            ],
            "items": tab_items,
        }
    ]

class InferenceJobInline(TabularInline):
    """
    (新) 用于在 InferenceProject 页面中显示子任务。
    """
    model = InferenceJob
    extra = 0
    can_delete = False

    list_display = ('job_type', 'status', 'cloud_task_id', 'created', 'modified')
    readonly_fields = ('job_type', 'status', 'cloud_task_id', 'created', 'modified',
                       'input_params', 'cloud_facts_path', 'output_facts_file',
                       'output_rag_report_file')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(InferenceProject)
class InferenceProjectAdmin(ModelAdmin):
    """
    (已重构 V3)
    L3 推理项目的 Admin 界面。
    """
    form = InferenceProjectForm
    list_display = ('name', 'annotation_project', 'created', 'modified', 'go_to_annotation')
    list_display_links = ('name',)
    search_fields = ('name', 'annotation_project__name')

    add_fieldsets = (
        (None, {'fields': ('name', 'description', 'annotation_project')}),
    )
    fieldsets = (
        (None, {'fields': ('name', 'description', 'annotation_project')}),
    )
    inlines = [InferenceJobInline]

    # --- (核心方法) ---

    def get_urls(self):
        """
        (新) 注册 "第一步" 和 "第二步" 的自定义 Tab 视图。
        """
        urls = super().get_urls()

        def get_url_name(view_name):
            return f"{self.model._meta.app_label}_{self.model._meta.model_name}_{view_name}"

        custom_urls = [
            path(
                '<uuid:object_id>/change/tab-1-facts/',
                self.admin_site.admin_view(self.tab_1_facts_view),
                name=get_url_name('tab_1_facts')
            ),
            path(
                '<uuid:object_id>/change/tab-2-rag/',
                self.admin_site.admin_view(self.tab_2_rag_view),
                name=get_url_name('tab_2_rag')
            ),
        ]
        return custom_urls + urls

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('annotation_project',)
        return ()

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.add_fieldsets
        # [!!! 修复 1: 确保 'change' 视图使用 'fieldsets' !!!]
        return self.fieldsets

    def change_view(self, request, object_id, form_url="", extra_context=None):
        # ... (this is fine) ...
        return self.tab_1_facts_view(request, object_id, extra_context)

    def add_view(self, request, form_url="", extra_context=None):
        # ... (this is fine) ...
        self.change_form_template = None
        return super().add_view(request, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        # ... (this is fine) ...
        if not change:
            annotation_project = form.cleaned_data['annotation_project']
            obj.asset = annotation_project.asset
        super().save_model(request, obj, form, change)

    # --- (自定义 Tab 视图) ---

    def tab_1_facts_view(self, request, object_id, extra_context=None):
        """
        (新) 渲染 "第一步：识别" Tab。
        """
        context = extra_context or {}
        project = self.get_object(request, object_id)
        metrics_data = None

        try:
            if project.annotation_project.local_metrics_result_file:
                with project.annotation_project.local_metrics_result_file.open('r') as f:
                    metrics_data = json.load(f)
            else:
                messages.error(request, "错误：找不到 角色矩阵产出 (本地) 文件。请返回标注项目生成。")
        except Exception as e:
            logger.error(f"无法加载 local_metrics_result_file (项目: {project.id}): {e}", exc_info=True)
            messages.error(request, f"无法加载角色矩阵文件: {e}")

        if metrics_data:
            form_data = request.POST if request.method == 'POST' else None
            context['character_selection_form'] = CharacterSelectionForm(form_data, metrics_data=metrics_data)

        jobs_list = InferenceJob.objects.filter(
            project=project,
            job_type=InferenceJob.TYPE.FACTS
        ).order_by('-created')
        paginator = Paginator(jobs_list, 10)
        page_obj = paginator.get_page(request.GET.get('page'))
        context.update({'job_list': page_obj, 'status_choices': BaseJob.STATUS})

        # [!!! 修复 2: 使用 'self.fieldsets' 而不是 'self.base_fieldsets' !!!]
        self.fieldsets = self.fieldsets
        self.change_form_template = "admin/workflow/project/inference/tab_1_facts.html"

        # [!!! 步骤 1.1: 修复 FORM URL !!!]
        # 将主表单的 'action' 指向我们的自定义视图
        form_url = reverse('workflow:inference_trigger_cloud_facts', args=[project.id])

        return super().changeform_view(request, str(object_id), form_url=form_url, extra_context=context)

    def tab_2_rag_view(self, request, object_id, extra_context=None):
        """
        (新) 渲染 "第二步： 更新知识图谱" Tab。
        """
        context = extra_context or {}
        project = self.get_object(request, object_id)
        jobs_list = InferenceJob.objects.filter(
            project=project,
            job_type=InferenceJob.TYPE.RAG_DEPLOYMENT
        ).order_by('-created')
        paginator = Paginator(jobs_list, 10)
        page_obj = paginator.get_page(request.GET.get('page'))
        context.update({'job_list': page_obj, 'status_choices': BaseJob.STATUS})

        self.fieldsets = self.fieldsets
        self.change_form_template = "admin/workflow/project/inference/tab_2_rag.html"

        # [!!! 步骤 1.2: 修复 FORM URL !!!]
        form_url = reverse('workflow:inference_trigger_rag_deployment', args=[project.id])

        return super().changeform_view(request, str(object_id), form_url=form_url, extra_context=context)

    @admin.display(description="关联标注项目")
    def go_to_annotation(self, obj):
        try:
            # [!!! 步骤 1.3: 修复 URL Name (与 annotation/admin.py 一致) !!!]
            url = reverse('admin:workflow_annotationproject_change', args=[obj.annotation_project.pk])
            return format_html('<a href="{}" class="button">进入标注</a>', url)
        except Exception:
            return "N/A"