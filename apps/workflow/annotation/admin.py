# apps/workflow/annotation/admin.py

import logging

from django.contrib import admin
from django.db import transaction
from django.http import HttpRequest
from django.urls import path, reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .jobs import AnnotationJob
from .projects import AnnotationProject

logger = logging.getLogger(__name__)


# =============================================================================
# 1. Unfold 顶部导航定义
# =============================================================================


def get_project_tabs(request: HttpRequest) -> list[dict]:
    """
    (V5.2 Creative 模式)
    定义 Unfold 顶部 Tab，指向不同的 URL 视图。
    """
    resolver = request.resolver_match
    # 确保只在 annotationproject 的相关页面显示
    if not (resolver and resolver.view_name.startswith("admin:workflow_annotationproject_")):
        return []

    object_id = resolver.kwargs.get("object_id")
    if not object_id:
        return []

    current_view = resolver.view_name

    return [
        {
            "models": [{"name": "workflow.annotationproject", "detail": True}],
            "items": [
                {
                    "title": "🎬 标注任务列表 (Workbench)",
                    # Tab 1: 直接指向 Change View
                    "link": reverse("admin:workflow_annotationproject_change", args=[object_id]),
                    "active": current_view == "admin:workflow_annotationproject_change",
                },
                {
                    "title": "🧩 场景编排 (Ordering)",
                    # Tab 2: 指向自定义视图 URL
                    "link": reverse("admin:workflow_annotationproject_tab_ordering", args=[object_id]),
                    "active": current_view == "admin:workflow_annotationproject_tab_ordering",
                },
            ],
        }
    ]


# =============================================================================
# 2. Admin 定义
# =============================================================================


@admin.register(AnnotationProject)
class AnnotationProjectAdmin(ModelAdmin):
    # 基础列表页配置
    list_display = ("name", "asset", "status_badge", "created", "action_quick_entry")
    search_fields = ("name", "asset__title")
    list_filter = ("status",)
    readonly_fields = ("status", "created", "modified")

    actions = ["generate_blueprint_action", "export_project_action", "run_audit_action"]

    def status_badge(self, obj):
        return obj.get_status_display()

    status_badge.short_description = "状态"

    # --- URL 路由配置 (注册 Tab 2) ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<uuid:object_id>/change/tab-ordering/",
                self.admin_site.admin_view(self.render_ordering_tab),
                name="workflow_annotationproject_tab_ordering",
            ),
        ]
        return custom_urls + urls

    # --- 视图 1: Add View (创建项目) ---
    def add_view(self, request, form_url="", extra_context=None):
        """
        创建模式：使用 Unfold 默认模板，显示表单 (Project Name, Asset, Encoding...)
        """
        self.change_form_template = None
        return super().add_view(request, form_url, extra_context)

    # --- 视图 2: Change View (Tab 1 - 标注列表) ---
    def change_view(self, request, object_id, form_url="", extra_context=None):
        """
        详情模式：加载 Media List Table，作为进入 React Workbench 的入口。
        """
        extra_context = extra_context or {}

        project = self.get_object(request, object_id)
        if project:
            # 1. 幂等初始化 (关联 Media)
            self._ensure_jobs_exist(project)

            # 2. 注入 Job 列表数据
            # 这里直接注入 QuerySet，由 Django Template 渲染表格
            jobs = project.jobs.select_related("media").order_by("media__sequence_number")
            extra_context["annotation_jobs"] = jobs

            # [UI] 隐藏默认的 Save 按钮 (列表页通常不需要保存 Project 属性)
            # 如果您希望在列表页上方也能修改 Project Name，可以设为 True
            extra_context["show_save"] = False
            extra_context["show_save_and_add_another"] = False
            extra_context["show_save_and_continue"] = False

            # [模板] 指定 Tab 1 模板
            self.change_form_template = "admin/workflow/project/annotation/tab_workbench_list.html"

        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    # --- 视图 3: Ordering View (Tab 2 - 场景编排) ---
    def render_ordering_tab(self, request, object_id, extra_context=None):
        """
        编排模式：独立的视图，加载编排界面。
        """
        context = extra_context or {}
        project = self.get_object(request, object_id)

        # 注入 Blueprint 数据 (供后续 React 编排组件使用)
        context["project_blueprint"] = project.final_blueprint_file

        context["show_save"] = False
        context["show_save_and_continue"] = False

        # [模板] 指定 Tab 2 模板
        self.change_form_template = "admin/workflow/project/annotation/tab_ordering.html"

        return super().changeform_view(request, str(object_id), extra_context=context)

    # --- 辅助逻辑 ---

    def _ensure_jobs_exist(self, project):
        if not project.asset:
            return
        medias = project.asset.medias.all()
        existing_media_ids = set(project.jobs.values_list("media_id", flat=True))
        new_jobs = []
        for media in medias:
            if media.id not in existing_media_ids:
                new_jobs.append(AnnotationJob(project=project, media=media, status="PENDING"))
        if new_jobs:
            with transaction.atomic():
                AnnotationJob.objects.bulk_create(new_jobs)

    # --- Actions ---
    @admin.action(description="生成/更新 生产蓝图")
    def generate_blueprint_action(self, request, queryset):
        for p in queryset:
            p.generate_blueprint()
        self.message_user(request, "蓝图已生成")

    @admin.action(description="导出工程包")
    def export_project_action(self, request, queryset):
        for p in queryset:
            p.export_project_annotation()
        self.message_user(request, "工程包已导出")

    @admin.action(description="执行审计")
    def run_audit_action(self, request, queryset):
        for p in queryset:
            p.run_audit()
        self.message_user(request, "审计任务已触发")

    @admin.display(description="操作")
    def action_quick_entry(self, obj):
        url = reverse("admin:workflow_annotationproject_change", args=[obj.pk])
        return format_html('<a href="{}" class="button">任务列表</a>', url)
