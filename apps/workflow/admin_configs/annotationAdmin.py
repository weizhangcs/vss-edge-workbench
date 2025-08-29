from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path

from unfold.admin import ModelAdmin
from unfold.decorators import display

from ..models import AnnotationProject, AnnotationJob
from apps.media_assets.models import Media
from ..views import annotation_views


@admin.register(AnnotationJob)
class AnnotationJobAdmin(ModelAdmin):
    list_display = ('__str__', 'status', 'created', 'modified')
    list_filter = ('status', 'job_type')


@admin.register(AnnotationProject)
class AnnotationProjectAdmin(ModelAdmin):
    list_display = ('name', 'asset', 'created', 'modified', 'view_project_details')
    list_display_links = ('name',)
    change_form_template = "admin/workflow/project/annotation/change_form.html"

    fieldsets = (
        ('项目信息', {'fields': ('name', 'description', 'asset')}),
        ('项目级产出物', {
            'fields': (
                'label_studio_project_id',
                'character_audit_report',
                'final_blueprint_file',
                'label_studio_export_file',
                'blueprint_validation_report'
            )
        }),
    )
    readonly_fields = ('label_studio_project_id', 'character_audit_report', 'final_blueprint_file',
                       'label_studio_export_file', 'blueprint_validation_report')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        project = self.get_object(request, object_id)

        if project and project.asset:
            media_items_with_status = []
            all_media = project.asset.medias.all().order_by('sequence_number')

            for media in all_media:
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

        return super().change_view(
            request, object_id, form_url, extra_context=extra_context,
        )

    @display(description="操作")
    def view_project_details(self, obj):
        url = reverse('admin:workflow_annotationproject_change', args=[obj.pk])
        return format_html('<a href="{}" class="button">进入项目</a>', url)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        asset_id = request.GET.get('asset_id')
        if asset_id:
            extra_context['asset_id'] = asset_id
        return super().changelist_view(request, extra_context=extra_context)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        asset_id = request.GET.get('asset_id')
        if asset_id:
            return queryset.filter(asset_id=asset_id)
        return queryset