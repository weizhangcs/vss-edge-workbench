# 文件路径: apps/workflow/annotation/admin.py

import logging

from django.contrib import admin
from django.core.paginator import Paginator
from django.utils.html import format_html
from django.urls import reverse, path
from django import forms
from django.db import models
from django.http import HttpRequest

from unfold.admin import ModelAdmin
from unfold.decorators import display
from unfold.widgets import UnfoldAdminTextareaWidget

from ..common.baseJob import BaseJob
from ..models import AnnotationProject, AnnotationJob
from ..widgets import FileFieldWithActionButtonWidget
from . import views as annotation_views

logger = logging.getLogger(__name__)


def get_project_tabs(request: HttpRequest) -> list[dict]:
    """
    (V4.3 架构)
    为 UNFOLD["TABS"] 设置提供动态 Tab 配置。
    此函数在 settings.py 中被引用，用于构建 AnnotationProject 的顶部 Tab 导航。
    """
    object_id = None
    if request.resolver_match and "object_id" in request.resolver_match.kwargs:
        object_id = request.resolver_match.kwargs.get("object_id")

    # 获取当前请求的 view name，用于判断哪个 tab 应该 active
    current_view_name = request.resolver_match.view_name

    # 默认的 change_view name
    default_change_view_name = "admin:workflow_annotationproject_change"

    tab_items = []
    if object_id:
        tab_items = [
            {
                "title": "第一步：角色标注",
                "link": reverse("admin:workflow_annotationproject_tab_l1", args=[object_id]),
                # 当 view_name 是 tab_l1 或者是默认 change_view 时，高亮此 tab
                "active": current_view_name in [
                    "admin:workflow_annotationproject_tab_l1",
                    default_change_view_name
                ]
            },
            {
                "title": "第二步：场景标注",
                "link": reverse("admin:workflow_annotationproject_tab_l2", args=[object_id]),
                "active": current_view_name == "admin:workflow_annotationproject_tab_l2"
            },
            {
                "title": "第三步：推理建模",
                "link": reverse("admin:workflow_annotationproject_tab_l3", args=[object_id]),
                "active": current_view_name == "admin:workflow_annotationproject_tab_l3"
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
    主要用于动态地将 FileField 替换为带自定义动作按钮的 Widget。
    """

    class Meta:
        model = AnnotationProject
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 统一 description 字段的高度
        if 'description' in self.fields:
            self.fields['description'].widget = UnfoldAdminTextareaWidget(attrs={'rows': 3})

        project = self.instance
        if project and project.pk:  # 仅在 change_view 中执行

            # L2: 为 'label_studio_export_file' 字段添加 "导出/更新" 按钮
            if 'label_studio_export_file' in self.fields:
                export_button_url = None
                if project.label_studio_project_id:
                    # 按钮指向 'export_l2_output_view' 视图
                    export_button_url = reverse('workflow:annotation_project_export_l2', args=[project.pk])

                self.fields['label_studio_export_file'].widget = FileFieldWithActionButtonWidget(
                    button_url=export_button_url, button_text="导出/更新", button_variant="default"
                )

            # L3: 为 'final_blueprint_file' 字段添加 "生成" 和 "云端推理" 两个按钮
            if 'final_blueprint_file' in self.fields:
                blueprint_button_url = None
                if project.label_studio_export_file:
                    # "生成/重建" 按钮指向 'generate_blueprint_view'
                    blueprint_button_url = reverse('workflow:annotation_project_generate_blueprint', args=[project.pk])

                reasoning_page_url = None
                if project.final_blueprint_file:
                    # "云端推理" 按钮指向 'reasoning_workflow_view'
                    reasoning_page_url = reverse('workflow:annotation_project_reasoning_workflow', args=[project.pk])

                self.fields['final_blueprint_file'].widget = FileFieldWithActionButtonWidget(
                    button_url=blueprint_button_url,
                    button_text="生成/重建",
                    button_variant="primary",
                    secondary_button_url=reasoning_page_url,
                    secondary_button_text="[ ➔ ] 云端推理",
                    secondary_button_variant="default"
                )


@admin.register(AnnotationJob)
class AnnotationJobAdmin(ModelAdmin):
    """
    标注任务 (AnnotationJob) 的标准 Admin 注册。
    """
    list_display = ('__str__', 'status', 'created', 'modified')
    list_filter = ('status', 'job_type')


@admin.register(AnnotationProject)
class AnnotationProjectAdmin(ModelAdmin):
    """
    (V4.3 架构)
    标注项目 (AnnotationProject) 的 Admin。
    使用自定义 Tab 视图 (tab_l1_view, tab_l2_view, tab_l3_view)
    来构建一个复杂的多页面工作流。
    """
    form = AnnotationProjectForm
    list_display = ('name', 'asset', 'status', 'blueprint_status', 'cloud_reasoning_status', 'created', 'modified',
                    'view_project_details')
    list_display_links = ('name',)
    autocomplete_fields = ['asset']

    # --- Fieldset 定义 ---
    # base_fieldsets 定义了所有 Tab 共享的“项目信息”
    base_fieldsets = (
        ('项目信息', {'fields': (
            'name',
            'description',
            'asset',
            'source_encoding_profile'
        )}),
    )

    # fieldsets 供 'add_view'（添加视图）使用
    fieldsets = base_fieldsets

    # tab_l1_fieldsets 合并了 base 和 L1 独有的字段
    tab_l1_fieldsets = base_fieldsets + (
        ('角色标注产出物', {
            'fields': ('character_audit_report',)
        }),
    )

    # tab_l2_fieldsets 合并了 base 和 L2 独有的字段
    tab_l2_fieldsets = base_fieldsets + (
        ('场景标注产出物', {
            'fields': ('label_studio_project_id', 'label_studio_export_file',)
        }),
    )

    # tab_l3_fieldsets 合并了 base 和 L3 独有的字段
    tab_l3_fieldsets = base_fieldsets + (
        ('推理建模产出物', {
            'fields': (
                'final_blueprint_file',
                'blueprint_validation_report',
                'cloud_reasoning_status',
                'cloud_metrics_result_file',
                'cloud_facts_result_file',
                'cloud_rag_report_file',
                # 隐藏的字段，用于 JS 或后台逻辑
                'cloud_blueprint_path',
                'cloud_facts_path'
            )
        }),
    )

    # 统一 admin 中所有 TextField 的默认高度
    formfield_overrides = {
        models.TextField: {"widget": UnfoldAdminTextareaWidget(attrs={'rows': 2})},
    }

    # 定义所有在 Tab 视图中应为只读的字段
    readonly_fields = (
        'label_studio_project_id', 'character_audit_report', 'blueprint_validation_report',
        'cloud_reasoning_status', 'cloud_metrics_result_file',
        'cloud_facts_result_file', 'cloud_rag_report_file', 'cloud_blueprint_path', 'cloud_facts_path'
    )

    def get_urls(self):
        """
        注册我们的自定义 Tab 视图 URL 和 L3 工作流 URL。
        """
        urls = super().get_urls()
        custom_urls = [
            # L1 Tab 视图
            path(
                '<uuid:object_id>/change/tab-l1/',
                self.admin_site.admin_view(self.tab_l1_view),
                name='workflow_annotationproject_tab_l1'
            ),
            # L2 Tab 视图
            path(
                '<uuid:object_id>/change/tab-l2/',
                self.admin_site.admin_view(self.tab_l2_view),
                name='workflow_annotationproject_tab_l2'
            ),
            # L3 Tab 视图
            path(
                '<uuid:object_id>/change/tab-l3/',
                self.admin_site.admin_view(self.tab_l3_view),
                name='workflow_annotationproject_tab_l3'
            ),
            # L3 独立工作流页面
            path(
                '<uuid:object_id>/reasoning-workflow/',
                self.admin_site.admin_view(annotation_views.reasoning_workflow_view),
                name='annotation_project_reasoning_workflow'
            ),
        ]
        return custom_urls + urls

    def add_view(self, request, form_url="", extra_context=None):
        """
        (优化) 覆盖 add_view 以防止被 Tab 视图污染状态。
        这能确保 "Add" 页面总是显示正确的 fieldsets 和模板。
        """
        # 1. 强制重置为 'add' 视图该用的 fieldsets
        self.fieldsets = self.base_fieldsets
        # 2. 强制重置为 Unfold 默认的 change_form 模板
        self.change_form_template = None

        return super().add_view(
            request,
            form_url=form_url,
            extra_context=extra_context
        )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """
        (优化) 覆盖默认的 change_view。
        当用户访问 .../change/ URL 时，自动将他们定向到 L1 Tab 视图。
        """
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
        all_media = project.asset.medias.all().order_by('sequence_number')
        l1_status_filter = request.GET.get('l1_status')
        l1_page_number = request.GET.get('page', 1)
        l1_media_list = all_media
        if l1_status_filter:
            l1_media_list = l1_media_list.filter(
                annotation_jobs__job_type=AnnotationJob.TYPE.L1_SUBEDITING,
                annotation_jobs__status=l1_status_filter
            ).distinct()
        l1_paginator = Paginator(l1_media_list, 10)
        l1_page_obj = l1_paginator.get_page(l1_page_number)
        l1_items_with_status = []
        for media in l1_page_obj:
            l1_job = AnnotationJob.objects.filter(project=project, media=media,
                                                  job_type=AnnotationJob.TYPE.L1_SUBEDITING).first()
            l1_items_with_status.append({'media': media, 'l1_job': l1_job})
        # --- L1 业务逻辑结束 ---

        # 准备要注入模板的额外上下文
        context = extra_context or {}
        context.update({
            'l1_media_items_with_status': l1_items_with_status,
            'l1_page_obj': l1_page_obj,
            'l1_active_filter': l1_status_filter,
            'status_choices': BaseJob.STATUS,
            # 为 L2 分页器提供占位符 (确保 L1 模板中的分页链接能正确构建)
            'l2l3_page_obj': Paginator([], 10).get_page(request.GET.get('l2l3_page', 1)),
            'l2l3_active_filter': request.GET.get('l2l3_status')
        })

        # 1. 动态设置此次渲染要使用的 fieldsets
        self.fieldsets = self.tab_l1_fieldsets
        # 2. 显式设置 L1 模板 (防止被其他 Tab 污染)
        self.change_form_template = "admin/workflow/project/annotation/tab_l1.html"

        # 3. 调用 Unfold 原生渲染器，并传入 object_id 字符串
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
        all_media = project.asset.medias.all().order_by('sequence_number')
        l2l3_status_filter = request.GET.get('l2l3_status')
        l2l3_page_number = request.GET.get('l2l3_page', 1)
        l2l3_media_list = all_media
        if l2l3_status_filter:
            l2l3_media_list = l2l3_media_list.filter(
                annotation_jobs__job_type=AnnotationJob.TYPE.L2L3_SEMANTIC,
                annotation_jobs__status=l2l3_status_filter
            ).distinct()
        l2l3_paginator = Paginator(l2l3_media_list, 10)
        l2l3_page_obj = l2l3_paginator.get_page(l2l3_page_number)
        l2l3_items_with_status = []
        for media in l2l3_page_obj:
            l2l3_job = AnnotationJob.objects.filter(project=project, media=media,
                                                    job_type=AnnotationJob.TYPE.L2L3_SEMANTIC).first()
            l2l3_items_with_status.append({'media': media, 'l2l3_job': l2l3_job})
        # --- L2 业务逻辑结束 ---

        # 准备要注入模板的额外上下文
        context = extra_context or {}
        context.update({
            'l2l3_media_items_with_status': l2l3_items_with_status,
            'l2l3_page_obj': l2l3_page_obj,
            'l2l3_active_filter': l2l3_status_filter,
            'status_choices': BaseJob.STATUS,
            # 为 L1 分页器提供占位符 (确保 L2 模板中的分页链接能正确构建)
            'l1_page_obj': Paginator([], 10).get_page(request.GET.get('page', 1)),
            'l1_active_filter': request.GET.get('l1_status')
        })

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
        渲染 L3 Tab ("推理建模")。
        这个视图只负责渲染字段集；复杂的工作流在 'reasoning_workflow_view' 中。
        """
        context = extra_context or {}
        context.update({
            'object_id': object_id  # 传递 object_id 供模板中的 JS 使用
        })

        # 1. 动态设置 fieldsets
        self.fieldsets = self.tab_l3_fieldsets
        # 2. 显式设置 L3 模板
        self.change_form_template = "admin/workflow/project/annotation/tab_l3.html"

        # 3. 调用 Unfold 原生渲染器
        return super().changeform_view(
            request,
            str(object_id),
            form_url="",
            extra_context=context,
        )

    # --- 辅助方法 ---

    def changelist_view(self, request, extra_context=None):
        """
        (V4.3 新增)
        允许 changelist 视图通过 GET 参数 'asset_id' 进行过滤。
        """
        extra_context = extra_context or {}
        asset_id = request.GET.get('asset_id')
        if asset_id:
            extra_context['asset_id'] = asset_id
        return super().changelist_view(request, extra_context=extra_context)

    @display(description="操作")
    def view_project_details(self, obj):
        """
        在 changelist 视图中添加一个“进入项目”的快捷按钮。
        """
        # 注意：这里链接到 .../change/，它会被 change_view 自动重定向到 L1 Tab
        url = reverse('admin:workflow_annotationproject_change', args=[obj.pk])
        return format_html('<a href="{}" class="button">进入项目</a>', url)

    def get_queryset(self, request):
        """
        (V4.3 新增)
        如果 'asset_id' 出现在 GET 参数中，则自动过滤 queryset。
        """
        queryset = super().get_queryset(request)
        asset_id = request.GET.get('asset_id')
        if asset_id:
            return queryset.filter(asset_id=asset_id)
        return queryset