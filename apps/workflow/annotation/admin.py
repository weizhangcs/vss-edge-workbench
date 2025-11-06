# 文件路径: apps/workflow/annotation/admin.py

import json
import logging
from django.contrib import admin
from django.core.paginator import Paginator
from django.utils.html import format_html
from django.urls import reverse, path
from django import forms
from django.db import models
from django.contrib import messages

from unfold.admin import ModelAdmin
from unfold.decorators import display
from unfold.widgets import UnfoldAdminTextareaWidget

from ..common.baseJob import BaseJob
from ..models import AnnotationProject, AnnotationJob, TranscodingProject
from ..widgets import FileFieldWithActionButtonWidget
from .forms import CharacterSelectionForm
#
from . import views as annotation_views

logger = logging.getLogger(__name__)


class AnnotationProjectForm(forms.ModelForm):
    class Meta:
        model = AnnotationProject
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['description'].widget = UnfoldAdminTextareaWidget(attrs={'rows': 3})

        project = self.instance
        if project and project.pk:
            #
            export_button_url = None
            if project.label_studio_project_id:
                export_button_url = reverse('workflow:annotation_project_export_l2', args=[project.pk])
            self.fields['label_studio_export_file'].widget = FileFieldWithActionButtonWidget(
                button_url=export_button_url, button_text="导出/更新", button_variant="default"
            )

            #
            blueprint_button_url = None
            if project.label_studio_export_file:
                blueprint_button_url = reverse('workflow:annotation_project_generate_blueprint', args=[project.pk])

            # ---
            #
            reasoning_page_url = None
            if project.final_blueprint_file:
                #
                reasoning_page_url = reverse('workflow:annotation_project_reasoning_workflow', args=[project.pk])
            # ---

            self.fields['final_blueprint_file'].widget = FileFieldWithActionButtonWidget(
                button_url=blueprint_button_url,
                button_text="生成/重建",
                button_variant="primary",
                #
                secondary_button_url=reasoning_page_url,
                secondary_button_text="[ ➔ ] 云端推理",
                secondary_button_variant="default"
            )


@admin.register(AnnotationJob)
class AnnotationJobAdmin(ModelAdmin):
    list_display = ('__str__', 'status', 'created', 'modified')
    list_filter = ('status', 'job_type')


@admin.register(AnnotationProject)
class AnnotationProjectAdmin(ModelAdmin):
    form = AnnotationProjectForm
    #
    list_display = ('name', 'asset', 'status', 'blueprint_status', 'cloud_reasoning_status', 'created', 'modified',
                    'view_project_details')
    list_display_links = ('name',)
    change_form_template = "admin/workflow/project/annotation/change_form.html"
    autocomplete_fields = ['asset']

    # ---
    fieldsets = (
        ('项目信息', {'fields': (
            'name',
            'description',
            'asset',
            'source_encoding_profile'
        )}),
        ('项目级产出物', {
            'fields': (
                'label_studio_project_id',
                'character_audit_report',
                'label_studio_export_file',
                'final_blueprint_file',
                'blueprint_validation_report',

                #
                'cloud_reasoning_status',
                'cloud_metrics_result_file',
                'cloud_facts_result_file',
                'cloud_rag_report_file',
            )
        }),
    )
    # ---

    formfield_overrides = {
        models.TextField: {"widget": UnfoldAdminTextareaWidget(attrs={'rows': 3})},
    }

    #
    readonly_fields = (
        'label_studio_project_id', 'character_audit_report', 'blueprint_validation_report',
        'cloud_reasoning_status', 'cloud_metrics_result_file',
        'cloud_facts_result_file', 'cloud_rag_report_file', 'cloud_blueprint_path', 'cloud_facts_path'
    )

    def get_urls(self):
        """

        """
        urls = super().get_urls()
        custom_urls = [
            #
            path(
                '<uuid:project_id>/reasoning-workflow/',
                self.admin_site.admin_view(annotation_views.reasoning_workflow_view),
                name='annotation_project_reasoning_workflow'
            ),
        ]
        return custom_urls + urls

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        project = self.get_object(request, object_id)

        #
        l1_status_filter = request.GET.get('l1_status')
        l2l3_status_filter = request.GET.get('l2l3_status')
        page_number = request.GET.get('page', 1)

        if project and hasattr(project, 'asset') and project.asset:
            media_items_with_status = []
            all_media = project.asset.medias.all().order_by('sequence_number')

            if l1_status_filter:
                all_media = all_media.filter(
                    annotation_jobs__job_type=AnnotationJob.TYPE.L1_SUBEDITING,
                    annotation_jobs__status=l1_status_filter
                ).distinct()

            if l2l3_status_filter:
                all_media = all_media.filter(
                    annotation_jobs__job_type=AnnotationJob.TYPE.L2L3_SEMANTIC,
                    annotation_jobs__status=l2l3_status_filter
                ).distinct()

            paginator = Paginator(all_media, 10)
            page_obj = paginator.get_page(page_number)

            for media in page_obj:
                l1_job = AnnotationJob.objects.filter(project=project, media=media,
                                                      job_type=AnnotationJob.TYPE.L1_SUBEDITING).first()
                l2l3_job = AnnotationJob.objects.filter(project=project, media=media,
                                                        job_type=AnnotationJob.TYPE.L2L3_SEMANTIC).first()

                media_items_with_status.append({
                    'media': media,
                    'l1_job': l1_job,
                    'l2l3_job': l2l3_job,
                })
            extra_context['media_items_with_status'] = media_items_with_status
            extra_context['page_obj'] = page_obj
            extra_context['active_filters'] = {
                'l1_status': l1_status_filter,
                'l2l3_status': l2l3_status_filter,
            }
            extra_context['status_choices'] = BaseJob.STATUS

        #
        #
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context,
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