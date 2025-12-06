# 文件路径: apps/workflow/annotation/admin.py
import logging
from datetime import datetime

from django import forms
from django.contrib import admin, messages
from django.core.paginator import Paginator
from django.db import models
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import action, display
from unfold.widgets import UnfoldAdminTextareaWidget

from apps.media_assets.models import Asset

from ..common.baseJob import BaseJob
from ..models import AnnotationJob, AnnotationProject
from ..services.portable import ProjectPortableService  # 导入新服务
from ..widgets import FileFieldWithActionButtonWidget

logger = logging.getLogger(__name__)


# --- 定义一个简单的上传表单 ---
class ImportProjectForm(forms.Form):
    zip_file = forms.FileField(
        label="1. 上传项目导出包 (.zip)",
        widget=forms.FileInput(
            attrs={
                # 使用 Tailwind 样式美化文件输入框
                "class": (
                    "block w-full text-sm text-gray-900 border border-gray-300 "
                    "rounded-lg cursor-pointer bg-gray-50 focus:outline-none "
                    "dark:bg-gray-700 dark:border-gray-600 "
                    "dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500"
                ),
                "accept": ".zip",  # 限制只能选 zip
            }
        ),
    )

    target_asset = forms.ModelChoiceField(
        queryset=Asset.objects.all().order_by("-created"),
        label="2. 选择挂载目标资产 (Target Asset)",
        required=True,
        empty_label="-- 请选择要关联的媒资 --",
        # 将 help_text 留空，我们会在模板中使用专门的 Alert 组件来展示指引
        help_text="",
        widget=forms.Select(
            attrs={
                # 使用 Tailwind 样式美化下拉框
                "class": (
                    "bg-gray-50 border border-gray-300 text-gray-900 text-sm "
                    "rounded-lg focus:ring-blue-500 focus:border-blue-500 "
                    "block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 "
                    "dark:placeholder-gray-400 dark:text-white "
                    "dark:focus:ring-blue-500 dark:focus:border-blue-500"
                ),
            }
        ),
    )


def get_project_tabs(request: HttpRequest) -> list[dict]:
    """
    (V4.3 架构)
    为 UNFOLD["TABS"] 设置提供动态 Tab 配置。
    此函数在 settings.py 中被引用，用于构建 AnnotationProject 的顶部 Tab 导航。
    """
    resolver = request.resolver_match

    # [关键修复] 1. 防御性检查：确保视图匹配正确的模型
    # 检查 view_name 是否以 AnnotationProject 的 admin URL 前缀开头
    if not (resolver and resolver.view_name.startswith("admin:workflow_annotationproject_")):
        return []

    # 2. 检查是否有 object_id (确认是 detail view)
    object_id = resolver.kwargs.get("object_id")
    if not object_id:
        return []

    # 此时 object_id 保证为 UUID 字符串，且视图匹配 AnnotationProject
    current_view_name = resolver.view_name
    default_change_view_name = "admin:workflow_annotationproject_change"

    tab_items = []
    if object_id:
        tab_items = [
            {
                "title": "第一步：角色标注",
                "link": reverse("admin:workflow_annotationproject_tab_l1", args=[object_id]),
                # 当 view_name 是 tab_l1 或者是默认 change_view 时，高亮此 tab
                "active": current_view_name in ["admin:workflow_annotationproject_tab_l1", default_change_view_name],
            },
            {
                "title": "第二步：场景标注",
                "link": reverse("admin:workflow_annotationproject_tab_l2", args=[object_id]),
                "active": current_view_name == "admin:workflow_annotationproject_tab_l2",
            },
            {
                "title": "第三步：建模产出",
                "link": reverse("admin:workflow_annotationproject_tab_l3", args=[object_id]),
                "active": current_view_name == "admin:workflow_annotationproject_tab_l3",
            },
        ]

    return [
        {
            # 指定此 Tab 导航仅在 workflow.annotationproject 模型的
            # change_form 页面 (detail=True) 上显示。
            "models": [
                {
                    "name": "workflow.annotationproject",
                    "detail": True,
                }
            ],
            "items": tab_items,
        }
    ]


class AnnotationProjectForm(forms.ModelForm):
    """
    自定义 AnnotationProject 的 Admin 表单。
    主要用于动态地将 FileField 替换为带自定义动作按钮的 Widget，
    并将这些字段设为 'disabled'，以防止手动更改，同时保留按钮功能。
    """

    class Meta:
        model = AnnotationProject
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "description" in self.fields:
            self.fields["description"].widget = UnfoldAdminTextareaWidget(attrs={"rows": 2})

        project = self.instance
        if project and project.pk:  # 仅在 change_view 中执行
            # --- L1 审计按钮 ---
            if "character_audit_report" in self.fields:
                audit_button_url = reverse("workflow:annotation_project_trigger_character_audit", args=[project.pk])

                self.fields["character_audit_report"].widget = FileFieldWithActionButtonWidget(
                    button_url=audit_button_url, button_text="生成/更新审计报告", button_variant="primary"
                )
                self.fields["character_audit_report"].disabled = True

                if "character_occurrence_report" in self.fields:
                    self.fields["character_occurrence_report"].widget = FileFieldWithActionButtonWidget(
                        button_url=audit_button_url, button_text="生成/更新审计报告", button_variant="primary"
                    )
                    self.fields["character_occurrence_report"].disabled = True

            # --- L2 导出按钮 ---
            if "label_studio_export_file" in self.fields:
                export_button_url = None
                if project.label_studio_project_id:
                    export_button_url = reverse("workflow:annotation_project_export_l2", args=[project.pk])
                self.fields["label_studio_export_file"].widget = FileFieldWithActionButtonWidget(
                    button_url=export_button_url, button_text="导出/更新", button_variant="primary"
                )
                self.fields["label_studio_export_file"].disabled = True

            # --- L3 蓝图按钮 ---
            if "final_blueprint_file" in self.fields:
                blueprint_button_url = None
                if project.label_studio_export_file:
                    blueprint_button_url = reverse("workflow:annotation_project_generate_blueprint", args=[project.pk])

                self.fields["final_blueprint_file"].widget = FileFieldWithActionButtonWidget(
                    button_url=blueprint_button_url,
                    button_text="生成/重建 (蓝图)",
                    button_variant="primary",
                )
                self.fields["final_blueprint_file"].disabled = True

            # --- L3 矩阵按钮 ---
            if "local_metrics_result_file" in self.fields:
                metrics_button_url = None
                if project.final_blueprint_file:
                    metrics_button_url = reverse("workflow:annotation_project_trigger_local_metrics", args=[project.pk])

                self.fields["local_metrics_result_file"].widget = FileFieldWithActionButtonWidget(
                    button_url=metrics_button_url, button_text="计算/更新 (矩阵)", button_variant="primary"
                )
                self.fields["local_metrics_result_file"].disabled = True


@admin.register(AnnotationJob)
class AnnotationJobAdmin(ModelAdmin):
    """
    标注任务 (AnnotationJob) 的标准 Admin 注册。
    """

    list_display = ("__str__", "status", "created", "modified")
    list_filter = ("status", "job_type")


@admin.register(AnnotationProject)
class AnnotationProjectAdmin(ModelAdmin):
    """
    (V4.3 架构)
    标注项目 (AnnotationProject) 的 Admin。
    使用自定义 Tab 视图 (tab_l1_view, tab_l2_view, tab_l3_view)
    来构建一个复杂的多页面工作流。
    """

    form = AnnotationProjectForm
    list_display = ("name", "asset", "status", "created", "modified", "view_project_details", "go_to_inference")
    list_display_links = ("name",)
    autocomplete_fields = ["asset"]

    # --- 搜索与过滤 ---
    search_fields = ("name", "asset__title")  # 允许按项目名称和关联的资产标题搜索
    list_filter = ("status",)  # 允许按项目状态过滤

    # [核心修复] 增加分页
    list_per_page = 20

    # --- Fieldset 定义 ---
    # base_fieldsets 定义了所有 Tab 共享的“项目信息”
    base_fieldsets = (
        (
            "项目信息",
            {
                "fields": (
                    "name",
                    "description",
                    ("asset", "source_encoding_profile"),  # 使用元组创建 1:1 左右布局
                )
            },
        ),
    )

    # fieldsets 供 'add_view'（添加视图）使用
    fieldsets = base_fieldsets

    # tab_l1_fieldsets 合并了 base 和 L1 独有的字段
    tab_l1_fieldsets = base_fieldsets + (
        ("角色标注产出物", {"fields": (("character_audit_report", "character_occurrence_report"),)}),  # 1:1 布局
    )

    # tab_l2_fieldsets 合并了 base 和 L2 独有的字段
    tab_l2_fieldsets = base_fieldsets + (
        ("场景标注产出物", {"fields": (("label_studio_project_id", "label_studio_export_file"),)}),  # 1:1 布局
    )

    # tab_l3_fieldsets 合并了 base 和 L3 独有的字段
    tab_l3_fieldsets = base_fieldsets + (
        (
            "建模产出物",
            {
                "fields": (
                    "status",  # (已合并 blueprint_status)
                    ("final_blueprint_file", "local_metrics_result_file"),  # 1:1 布局
                )
            },
        ),
    )

    # 统一 admin 中所有 TextField 的默认高度
    formfield_overrides = {
        models.TextField: {"widget": UnfoldAdminTextareaWidget(attrs={"rows": 2})},
    }

    # (基础 readonly_fields 列表，get_readonly_fields 会在此基础上动态添加)
    readonly_fields = ("status",)  # 状态字段总是只读，由后台任务更新

    actions = ["export_project_action"]

    # --- 1. 导出功能 (Action) ---
    @admin.action(description="📦 导出项目包 (用于测试/迁移)")
    def export_project_action(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "一次只能导出一个项目。", level=messages.WARNING)
            return

        project = queryset.first()
        try:
            zip_data = ProjectPortableService.export_annotation_project(str(project.id))

            # 返回文件下载响应
            filename = f"annotation_project_{project.name}_{datetime.now().strftime('%Y%m%d')}.zip"
            response = HttpResponse(zip_data, content_type="application/zip")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'  # noqa: E702
            return response

        except Exception as e:
            self.message_user(request, f"导出失败: {e}", level=messages.ERROR)

    # --- 按钮具体实现 ---
    @action(description="导入项目 (ZIP)", url_path="import-wizard", icon="file_upload")
    def open_import_wizard(self, request: HttpRequest):
        """
        列表页按钮点击后的回调：直接重定向到现有的导入视图 URL
        """
        return redirect("admin:workflow_annotationproject_import")

    # --- 2. 导入功能 (Custom View) ---
    def get_urls(self):
        """
        [已合并] 注册自定义 URL：包含 导入功能 和 Tab页切换
        """
        urls = super().get_urls()
        custom_urls = [
            # --- 1. 导入项目功能的 URL ---
            path(
                "import-project/",
                self.admin_site.admin_view(self.import_project_view),
                name="workflow_annotationproject_import",
            ),
            # --- 2. Tab 页切换的 URLs ---
            path(
                "<uuid:object_id>/change/tab-l1/",
                self.admin_site.admin_view(self.tab_l1_view),
                name="workflow_annotationproject_tab_l1",
            ),
            path(
                "<uuid:object_id>/change/tab-l2/",
                self.admin_site.admin_view(self.tab_l2_view),
                name="workflow_annotationproject_tab_l2",
            ),
            path(
                "<uuid:object_id>/change/tab-l3/",
                self.admin_site.admin_view(self.tab_l3_view),
                name="workflow_annotationproject_tab_l3",
            ),
        ]
        return custom_urls + urls

    def import_project_view(self, request):
        if request.method == "POST":
            form = ImportProjectForm(request.POST, request.FILES)
            if form.is_valid():
                zip_file = request.FILES["zip_file"]
                target_asset = form.cleaned_data["target_asset"]  # 获取用户选择的 Asset 对象

                try:
                    # [修改] 将 target_asset 传递给服务层
                    new_project = ProjectPortableService.import_annotation_project(
                        zip_bytes=zip_file.read(), target_asset=target_asset
                    )
                    self.message_user(
                        request, f"项目 '{new_project.name}' 已成功导入并挂载到《{target_asset.title}》！", level=messages.SUCCESS
                    )
                    return redirect("admin:workflow_annotationproject_changelist")
                except Exception as e:
                    self.message_user(request, f"导入失败: {e}", level=messages.ERROR)
        else:
            form = ImportProjectForm()

        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "title": "导入标注项目包",
            "opts": self.model._meta,
        }
        return render(request, "admin/workflow/project/annotation/import_form.html", context)

    def get_readonly_fields(self, request, obj=None):
        """
        动态设置只读字段。
        - 'add' 视图 (obj is None): 只读 'status'
        - 'change' 视图 (obj is not None): 所有产出物字段也变为只读
        """
        if obj:  # 这是一个 'change' 视图
            # 返回所有基础只读字段，并动态添加所有产出物字段
            return self.readonly_fields + ("label_studio_project_id",)

        # 这是一个 'add' 视图
        return self.readonly_fields

    def add_view(self, request, form_url="", extra_context=None):
        # self.fieldsets = self.base_fieldsets
        # 指定我们即将创建的新模板
        self.add_form_template = "admin/workflow/project/annotation/add_form.html"
        return super().add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """
        覆盖默认的 change_view。
        当用户访问 .../change/ URL 时，自动将他们定向到 L1 Tab 视图。
        [UX 优化] 在修改页面隐藏所有 "保存" 系列按钮。
        原因：此页面的业务流转完全由 Tab 内部的 Action 按钮驱动，原生保存按钮会误导用户。
        保留：删除按钮 (由 has_delete_permission 控制)。
        """
        extra_context = extra_context or {}

        # 核心：隐藏三个保存相关按钮
        extra_context["show_save"] = False
        extra_context["show_save_and_continue"] = False
        extra_context["show_save_and_add_another"] = False

        return self.tab_l1_view(request, object_id, extra_context)

    # --- 自定义 Tab 视图 (V4.3 架构) ---
    # 这一组视图重用了 Unfold 原生的 'changeform_view'，
    # 以确保 Unfold 样式 (如 Widget) 被正确加载，解决了 UI 不统一的问题。

    def tab_l1_view(self, request, object_id, extra_context=None):
        """
        渲染 L1 Tab ("角色标注")。
        """
        # --- L1 业务逻辑: 获取 L1 任务和分页数据 ---
        project = self.get_object(request, object_id)
        all_media = project.asset.medias.all().order_by("sequence_number")
        l1_status_filter = request.GET.get("l1_status")
        l1_page_number = request.GET.get("page", 1)
        l1_media_list = all_media
        if l1_status_filter:
            l1_media_list = l1_media_list.filter(
                annotation_jobs__job_type=AnnotationJob.TYPE.L1_SUBEDITING, annotation_jobs__status=l1_status_filter
            ).distinct()
        l1_paginator = Paginator(l1_media_list, 10)
        l1_page_obj = l1_paginator.get_page(l1_page_number)
        l1_items_with_status = []
        for media in l1_page_obj:
            l1_job = AnnotationJob.objects.filter(
                project=project, media=media, job_type=AnnotationJob.TYPE.L1_SUBEDITING
            ).first()
            l1_items_with_status.append({"media": media, "l1_job": l1_job})
        # --- L1 业务逻辑结束 ---

        # 准备要注入模板的额外上下文
        context = extra_context or {}
        context.update(
            {
                "l1_media_items_with_status": l1_items_with_status,
                "l1_page_obj": l1_page_obj,
                "l1_active_filter": l1_status_filter,
                "status_choices": BaseJob.STATUS,
                # 为 L2 分页器提供占位符 (确保 L1 模板中的分页链接能正确构建)
                "l2l3_page_obj": Paginator([], 10).get_page(request.GET.get("l2l3_page", 1)),
                "l2l3_active_filter": request.GET.get("l2l3_status"),
                "show_save": False,
                "show_save_and_continue": False,
                "show_save_and_add_another": False,
            }
        )

        # 1. 动态设置此次渲染要使用的 fieldsets
        self.fieldsets = self.tab_l1_fieldsets
        # 2. 显式设置 L1 模板 (防止被其他 Tab 污染)
        self.change_form_template = "admin/workflow/project/annotation/tab_l1.html"

        # 3. 调用 Unfold 原生渲染器 (将 UUID 转为 str)
        return super().changeform_view(
            request,
            str(object_id),
            form_url="",
            extra_context=context,
        )

    def tab_l2_view(self, request, object_id, extra_context=None):
        """
        渲染 L2 Tab ("场景标注")。
        """
        # --- L2 业务逻辑: 获取 L2 任务和分页数据 ---
        project = self.get_object(request, object_id)
        all_media = project.asset.medias.all().order_by("sequence_number")
        l2l3_status_filter = request.GET.get("l2l3_status")
        l2l3_page_number = request.GET.get("l2l3_page", 1)
        l2l3_media_list = all_media
        if l2l3_status_filter:
            l2l3_media_list = l2l3_media_list.filter(
                annotation_jobs__job_type=AnnotationJob.TYPE.L2L3_SEMANTIC, annotation_jobs__status=l2l3_status_filter
            ).distinct()
        l2l3_paginator = Paginator(l2l3_media_list, 10)
        l2l3_page_obj = l2l3_paginator.get_page(l2l3_page_number)
        l2l3_items_with_status = []
        for media in l2l3_page_obj:
            l2l3_job = AnnotationJob.objects.filter(
                project=project, media=media, job_type=AnnotationJob.TYPE.L2L3_SEMANTIC
            ).first()
            l2l3_items_with_status.append({"media": media, "l2l3_job": l2l3_job})
        # --- L2 业务逻辑结束 ---

        # 准备要注入模板的额外上下文
        context = extra_context or {}
        context.update(
            {
                "l2l3_media_items_with_status": l2l3_items_with_status,
                "l2l3_page_obj": l2l3_page_obj,
                "l2l3_active_filter": l2l3_status_filter,
                "status_choices": BaseJob.STATUS,
                # 为 L1 分页器提供占位符 (确保 L2 模板中的分页链接能正确构建)
                "l1_page_obj": Paginator([], 10).get_page(request.GET.get("page", 1)),
                "l1_active_filter": request.GET.get("l1_status"),
                "show_save": False,
                "show_save_and_continue": False,
                "show_save_and_add_another": False,
            }
        )

        # 1. 动态设置 fieldsets
        self.fieldsets = self.tab_l2_fieldsets
        # 2. 显式设置 L2 模板
        self.change_form_template = "admin/workflow/project/annotation/tab_l2.html"

        # 3. 调用 Unfold 原生渲染器
        return super().changeform_view(
            request,
            str(object_id),
            form_url="",
            extra_context=context,
        )

    def tab_l3_view(self, request, object_id, extra_context=None):
        """
        渲染 L3 Tab ("建模产出")。
        (已重构：不再需要自定义模板)
        """
        context = extra_context or {}
        context["show_save"] = False
        context["show_save_and_continue"] = False
        context["show_save_and_add_another"] = False

        # 1. 动态设置 fieldsets
        self.fieldsets = self.tab_l3_fieldsets
        # 2. 使用 Unfold 默认模板
        self.change_form_template = None

        # 3. 调用 Unfold 原生渲染器
        return super().changeform_view(
            request,
            str(object_id),
            form_url="",
            extra_context=context,
        )

    def changelist_view(self, request, extra_context=None):
        """
        允许 changelist 视图通过 GET 参数 'asset_id' 进行过滤。
        """
        extra_context = extra_context or {}
        asset_id = request.GET.get("asset_id")
        if asset_id:
            extra_context["asset_id"] = asset_id
        return super().changelist_view(request, extra_context=extra_context)

    @display(description="操作")
    def view_project_details(self, obj):
        """
        在 changelist 视图中添加一个“进入项目”的快捷按钮。
        """
        url = reverse("admin:workflow_annotationproject_change", args=[obj.pk])
        return format_html('<a href="{}" class="button">进入项目</a>', url)

    def get_queryset(self, request):
        """
        如果 'asset_id' 出现在 GET 参数中，则自动过滤 queryset。
        """
        queryset = super().get_queryset(request)
        asset_id = request.GET.get("asset_id")
        if asset_id:
            return queryset.filter(asset_id=asset_id)
        return queryset

    @display(description="关联推理项目")
    def go_to_inference(self, obj):
        """
        在 changelist 视图中添加一个快捷方式，
        用于跳转到此项目关联的 InferenceProject。
        """
        try:
            inference_proj = obj.inference_project
            # [!!! 修复: 使用 'workflow' app_label !!!]
            url = reverse("admin:workflow_inferenceproject_change", args=[inference_proj.pk])
            return format_html('<a href="{}" class="button">进入推理</a>', url)
        except Exception:
            # (未来可在此处添加一个 "创建推理项目" 的按钮)
            return "尚未创建"
