# 文件路径: apps/workflow/annotation/admin.py

import json
import logging
import re
from django.contrib import admin
from django.core.paginator import Paginator
from django.utils.html import format_html
from django.urls import reverse_lazy, reverse, path
from django import forms
from django.db import models
from django.contrib import messages
from django.shortcuts import render
from django.http import Http404, HttpRequest, HttpResponseRedirect

from unfold.admin import ModelAdmin
from unfold.decorators import display
# [!!! 优化 3.1: 导入标准文件小部件 !!!]
from unfold.widgets import UnfoldAdminTextareaWidget, UnfoldAdminFileFieldWidget

from ..common.baseJob import BaseJob
from ..models import AnnotationProject, AnnotationJob, TranscodingProject
from ..widgets import FileFieldWithActionButtonWidget
from .forms import CharacterSelectionForm
from . import views as annotation_views

logger = logging.getLogger(__name__)


def get_project_tabs(request: HttpRequest) -> list[dict]:
    # ... (此函数保持不变) ...
    object_id = None
    if request.resolver_match and "object_id" in request.resolver_match.kwargs:
        object_id = request.resolver_match.kwargs.get("object_id")
    current_view_name = request.resolver_match.view_name
    default_change_view_name = "admin:workflow_annotationproject_change"
    tab_items = []
    if object_id:
        tab_items = [
            {
                "title": "第一步：角色标注",
                "link": reverse("admin:workflow_annotationproject_tab_l1", args=[object_id]),
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
                "title": "第三步：建模产出",
                "link": reverse("admin:workflow_annotationproject_tab_l3", args=[object_id]),
                "active": current_view_name == "admin:workflow_annotationproject_tab_l3"
            },
        ]
    return [
        {
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
    """

    class Meta:
        model = AnnotationProject
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'description' in self.fields:
            self.fields['description'].widget = UnfoldAdminTextareaWidget(attrs={'rows': 2})

        project = self.instance
        if project and project.pk:

            # [!!! 优化 3.2: 更新 L1 按钮逻辑 !!!]
            if 'character_audit_report' in self.fields:
                audit_button_url = reverse('workflow:annotation_project_trigger_character_audit', args=[project.pk])

                # 1. 只为“摘要”字段添加按钮
                self.fields['character_audit_report'].widget = FileFieldWithActionButtonWidget(
                    button_url=audit_button_url,
                    button_text="生成/更新审计报告",
                    button_variant="primary"
                )

                # 2. 为“详情”字段应用标准小部件 (无按钮)
                if 'character_occurrence_report' in self.fields:
                    self.fields['character_occurrence_report'].widget = FileFieldWithActionButtonWidget(
                        button_url=audit_button_url,
                        button_text="生成/更新审计报告",
                        button_variant="primary"
                    )

            # L2 按钮 (保持不变)
            if 'label_studio_export_file' in self.fields:
                export_button_url = None
                if project.label_studio_project_id:
                    export_button_url = reverse('workflow:annotation_project_export_l2', args=[project.pk])
                self.fields['label_studio_export_file'].widget = FileFieldWithActionButtonWidget(
                    button_url=export_button_url, button_text="导出/更新", button_variant="default"
                )

            # L3 按钮 (保持不变)
            if 'final_blueprint_file' in self.fields:
                blueprint_button_url = None
                if project.label_studio_export_file:
                    blueprint_button_url = reverse('workflow:annotation_project_generate_blueprint', args=[project.pk])


                self.fields['final_blueprint_file'].widget = FileFieldWithActionButtonWidget(
                    button_url=blueprint_button_url,
                    button_text="生成/重建",
                    button_variant="primary",
                )

            # L3 按钮 2: "计算矩阵" (本地)
            if 'local_metrics_result_file' in self.fields:
                metrics_button_url = None
                if project.final_blueprint_file:  # 仅当蓝图存在时才显示按钮
                    metrics_button_url = reverse('workflow:annotation_project_trigger_local_metrics',
                                                 args=[project.pk])

                self.fields['local_metrics_result_file'].widget = FileFieldWithActionButtonWidget(
                    button_url=metrics_button_url,
                    button_text="计算/更新 (矩阵)",
                    button_variant="primary"
                )
                self.fields['local_metrics_result_file'].disabled = True


@admin.register(AnnotationJob)
class AnnotationJobAdmin(ModelAdmin):
    # ... (保持不变) ...
    list_display = ('__str__', 'status', 'created', 'modified')
    list_filter = ('status', 'job_type')


@admin.register(AnnotationProject)
class AnnotationProjectAdmin(ModelAdmin):
    form = AnnotationProjectForm
    list_display = ('name', 'asset', 'status', 'blueprint_status', 'created', 'modified',
                    'view_project_details')
    list_display_links = ('name',)
    autocomplete_fields = ['asset']

    # [!!! 优化 1: 更新 base_fieldsets !!!]
    base_fieldsets = (
        ('项目信息', {'fields': (
            'name',
            'description',
            # (优化) 将这两个字段放在一个元组中，使它们 1:1 布局
            ('asset', 'source_encoding_profile'),
        )}),
    )

    # fieldsets 供 'add_view' 使用 (保持不变)
    fieldsets = base_fieldsets

    # [!!! 优化 2: 更新 tab_l1_fieldsets !!!]
    tab_l1_fieldsets = base_fieldsets + (
        ('角色标注产出物', {
            'fields': (
                # (优化) 将这两个字段放在一个元组中，使它们 1:1 布局
                ('character_audit_report', 'character_occurrence_report'),
            )
        }),
    )

    # L2 fieldsets (保持不变)
    tab_l2_fieldsets = base_fieldsets + (
        ('场景标注产出物', {
            'fields': ('label_studio_project_id', 'label_studio_export_file',)
        }),
    )

    # L3 fieldsets (保持不变)
    tab_l3_fieldsets = base_fieldsets + (
        ('建模产出物', {
            'fields': (
                # 第 1 行 (1:1): 角色矩阵产出 | 最终叙事蓝图
                ('blueprint_status','final_blueprint_file', 'local_metrics_result_file'),
                # 'blueprint_validation_report' 已被隐藏 (移除)
            )
        }),
    )

    formfield_overrides = {
        models.TextField: {"widget": UnfoldAdminTextareaWidget(attrs={'rows': 2})},
    }

    # readonly_fields 保持不变 (我们在上一轮已修复)
    readonly_fields = (
        'label_studio_project_id',
    )

    # ... (所有 get_urls, add_view, change_view, tab_..._view, changelist_view,
    #      view_project_details, get_queryset 函数都保持不变) ...

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<uuid:object_id>/change/tab-l1/',
                self.admin_site.admin_view(self.tab_l1_view),
                name='workflow_annotationproject_tab_l1'
            ),
            path(
                '<uuid:object_id>/change/tab-l2/',
                self.admin_site.admin_view(self.tab_l2_view),
                name='workflow_annotationproject_tab_l2'
            ),
            path(
                '<uuid:object_id>/change/tab-l3/',
                self.admin_site.admin_view(self.tab_l3_view),
                name='workflow_annotationproject_tab_l3'
            ),
        ]
        return custom_urls + urls

    def add_view(self, request, form_url="", extra_context=None):
        self.fieldsets = self.base_fieldsets
        self.change_form_template = None
        return super().add_view(
            request,
            form_url=form_url,
            extra_context=extra_context
        )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        return self.tab_l1_view(request, object_id, extra_context)

    def tab_l1_view(self, request, object_id, extra_context=None):
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

        context = extra_context or {}
        context.update({
            'l1_media_items_with_status': l1_items_with_status,
            'l1_page_obj': l1_page_obj,
            'l1_active_filter': l1_status_filter,
            'status_choices': BaseJob.STATUS,
            'l2l3_page_obj': Paginator([], 10).get_page(request.GET.get('l2l3_page', 1)),
            'l2l3_active_filter': request.GET.get('l2l3_status')
        })

        self.fieldsets = self.tab_l1_fieldsets
        self.change_form_template = "admin/workflow/project/annotation/tab_l1.html"

        return super().changeform_view(
            request,
            str(object_id),
            form_url="",
            extra_context=context,
        )

    def tab_l2_view(self, request, object_id, extra_context=None):
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

        context = extra_context or {}
        context.update({
            'l2l3_media_items_with_status': l2l3_items_with_status,
            'l2l3_page_obj': l2l3_page_obj,
            'l2l3_active_filter': l2l3_status_filter,
            'status_choices': BaseJob.STATUS,
            'l1_page_obj': Paginator([], 10).get_page(request.GET.get('page', 1)),
            'l1_active_filter': request.GET.get('l1_status')
        })

        self.fieldsets = self.tab_l2_fieldsets
        self.change_form_template = "admin/workflow/project/annotation/tab_l2.html"

        return super().changeform_view(
            request,
            str(object_id),
            form_url="",
            extra_context=context,
        )

    def tab_l3_view(self, request, object_id, extra_context=None):
        """
        渲染 L3 Tab ("建模产出")。
        (不再需要 'object_id' 注入)
        """
        context = extra_context or {}
        self.fieldsets = self.tab_l3_fieldsets
        self.change_form_template = "admin/workflow/project/annotation/tab_l3.html"

        return super().changeform_view(
            request,
            str(object_id),
            form_url="",
            extra_context=context,
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        asset_id = request.GET.get('asset_id')
        if asset_id:
            extra_context['asset_id'] = asset_id
        return super().changelist_view(request, extra_context=extra_context)

    @display(description="操作")
    def view_project_details(self, obj):
        url = reverse('admin:workflow_annotationproject_change', args=[obj.pk])
        return format_html('<a href="{}" class="button">进入项目</a>', url)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        asset_id = request.GET.get('asset_id')
        if asset_id:
            return queryset.filter(asset_id=asset_id)
        return queryset

    # [!!! 步骤 2.8: 添加一个链接到新项目的快捷方式 !!!]
    @admin.display(description="L3 推理")
    def go_to_inference(self, obj):
        try:
            # (假设你已有名为 'inference_project' 的 related_name)
            inference_proj = obj.inference_project
            url = reverse('admin:inference_inferenceproject_change', args=[inference_proj.pk])
            return format_html('<a href="{}" class="button">进入推理</a>', url)
        except Exception:
            # (你可以在这里添加一个 "创建推理项目" 的按钮)
            # (这需要一个新的视图，暂时先不实现)
            return "尚未创建"