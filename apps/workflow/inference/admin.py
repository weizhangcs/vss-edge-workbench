# 文件路径: apps/workflow/inference/admin.py

import json
import logging

from django.contrib import admin
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpRequest
from django.urls import path, reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from .forms import InferenceProjectForm
from .projects import InferenceJob, InferenceProject

logger = logging.getLogger(__name__)


# --- Tab 导航定义 (保留 Tab 2) ---
def get_inference_project_tabs(request: HttpRequest) -> list[dict]:
    resolver = request.resolver_match
    if not (resolver and resolver.view_name.startswith("admin:workflow_inferenceproject_")):
        return []

    object_id = resolver.kwargs.get("object_id")
    if not object_id:
        return []

    current_view_name = resolver.view_name
    default_change_view_name = "admin:workflow_inferenceproject_change"

    tab_items = []
    if object_id:
        tab_items = [
            {
                # 修改标题，体现功能合并
                "title": "第一步：识别与部署",
                "link": reverse("admin:workflow_inferenceproject_tab_1_facts", args=[object_id]),
                "active": current_view_name
                in ["admin:workflow_inferenceproject_tab_1_facts", default_change_view_name],
            },
            {
                # 保留 Tab 2，标记为预留
                "title": "第二步：高级功能 (预留)",
                "link": reverse("admin:workflow_inferenceproject_tab_2_rag", args=[object_id]),
                "active": current_view_name == "admin:workflow_inferenceproject_tab_2_rag",
            },
        ]

    return [
        {
            "models": [{"name": "workflow.inferenceproject", "detail": True}],
            "items": tab_items,
        }
    ]


class InferenceJobInline(TabularInline):
    model = InferenceJob
    extra = 0
    can_delete = False
    hide_title = True
    list_display = ("job_type", "status", "cloud_task_id", "created")
    readonly_fields = ("job_type", "status", "cloud_task_id", "created", "modified", "input_params")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(InferenceProject)
class InferenceProjectAdmin(ModelAdmin):
    form = InferenceProjectForm
    list_display = ("name", "asset", "status", "created", "view_current_project", "go_to_annotation")
    list_display_links = ("name",)
    list_per_page = 20
    search_fields = ("name", "annotation_project__name")

    add_fieldsets = ((None, {"fields": ("name", "description", "annotation_project")}),)
    fieldsets = ((None, {"fields": ("name", "description", "annotation_project")}),)

    # inlines = [InferenceJobInline]

    def get_urls(self):
        urls = super().get_urls()

        def get_url_name(view_name):
            return f"{self.model._meta.app_label}_{self.model._meta.model_name}_{view_name}"

        custom_urls = [
            path(
                "<uuid:object_id>/change/tab-1-facts/",
                self.admin_site.admin_view(self.tab_1_facts_view),
                name=get_url_name("tab_1_facts"),
            ),
            # 保留 Tab 2 URL
            path(
                "<uuid:object_id>/change/tab-2-rag/",
                self.admin_site.admin_view(self.tab_2_rag_view),
                name=get_url_name("tab_2_rag"),
            ),
        ]
        return custom_urls + urls

    def change_view(self, request, object_id, form_url="", extra_context=None):
        return self.tab_1_facts_view(request, object_id, extra_context)

    def add_view(self, request, form_url="", extra_context=None):
        self.change_form_template = None
        return super().add_view(request, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        if not change:
            annotation_project = form.cleaned_data["annotation_project"]
            obj.asset = annotation_project.asset
        super().save_model(request, obj, form, change)

    # --- 视图逻辑 ---

    def tab_1_facts_view(self, request, object_id, extra_context=None):
        """
        [Tab 1] 事实提取 + RAG 部署入口
        """
        context = extra_context or {}
        context.update({"show_save": False, "show_save_and_continue": False, "show_save_and_add_another": False})

        project = self.get_object(request, object_id)

        # 1. 读取角色矩阵 (逻辑不变)
        character_data = {"all_characters": [], "importance_scores": {}, "min_score": 0, "max_score": 0}
        metrics_loaded = False
        error_msg = None

        try:
            if project.annotation_project and project.annotation_project.local_metrics_result_file:
                with project.annotation_project.local_metrics_result_file.open("r") as f:
                    metrics_data = json.load(f)
                    all_chars = metrics_data.get("all_characters_found", [])
                    scores = metrics_data.get("importance_scores", {})

                    if all_chars and scores:
                        character_data["all_characters"] = all_chars
                        character_data["importance_scores"] = scores
                        all_values = list(scores.values())
                        if all_values:
                            character_data["min_score"] = max(0, min(all_values))
                            character_data["max_score"] = max(all_values)
                        metrics_loaded = True
                    else:
                        error_msg = "角色矩阵文件内容不完整。"
            else:
                error_msg = "未找到关联的‘角色矩阵’文件。"
        except Exception as e:
            logger.error(f"Error loading metrics: {e}")
            error_msg = f"读取角色矩阵文件失败: {str(e)}"

        # 2. 历史列表 (注入 ragActionUrl)
        jobs_list = InferenceJob.objects.filter(project=project, job_type=InferenceJob.TYPE.FACTS).order_by("-created")
        history_items = []

        # 预先生成部署接口的 Base URL
        rag_deploy_url_base = reverse("workflow:inference_trigger_rag_deployment", args=[project.id])

        for job in jobs_list:
            input_data = job.input_params if isinstance(job.input_params, dict) else {}

            # [核心合并逻辑] 只有成功的任务，才允许触发部署
            rag_action_url = rag_deploy_url_base if job.status == "COMPLETED" else None

            history_items.append(
                {
                    "id": str(job.id),
                    "status": job.status,
                    "statusDisplay": job.get_status_display(),
                    "created": job.created.strftime("%Y-%m-%d %H:%M"),
                    "input": input_data,
                    "output": {},
                    "ragActionUrl": rag_action_url,  # 传递给前端
                }
            )

        context["server_data_json"] = json.dumps(
            {
                "meta": {"metricsLoaded": metrics_loaded, "errorMsg": error_msg},
                "character_data": character_data,
                "items": history_items,
                "urls": {"submit": reverse("workflow:inference_trigger_cloud_facts", args=[project.id])},
            },
            cls=DjangoJSONEncoder,
        )

        self.fieldsets = self.fieldsets
        self.change_form_template = "admin/workflow/project/inference/tab_1_facts.html"
        return super().changeform_view(request, str(object_id), form_url="", extra_context=context)

    def tab_2_rag_view(self, request, object_id, extra_context=None):
        """
        [Tab 2] 预留视图 (Reserves)
        """
        context = extra_context or {}
        context.update({"show_save": False, "show_save_and_continue": False, "show_save_and_add_another": False})

        # 仅传递简单的占位信息，不执行重逻辑
        context["server_data_json"] = json.dumps({"message": "此模块已预留，等待后续规划。"}, cls=DjangoJSONEncoder)

        self.fieldsets = self.fieldsets
        self.change_form_template = "admin/workflow/project/inference/tab_2_rag.html"
        return super().changeform_view(request, str(object_id), form_url="", extra_context=context)

    # --- 辅助方法 ---
    @admin.display(description="操作")
    def view_current_project(self, obj):
        url = reverse("admin:workflow_inferenceproject_change", args=[obj.pk])
        return format_html('<a href="{}" class="button">进入项目</a>', url)

    @admin.display(description="关联标注项目")
    def go_to_annotation(self, obj):
        if obj.annotation_project:
            url = reverse("admin:workflow_annotationproject_change", args=[obj.annotation_project.pk])
            return format_html('<a href="{}" class="button">返回标注</a>', url)
        return "N/A"
