from django.contrib import admin
from django.urls import path, reverse

from unfold.admin import ModelAdmin

from ..models import TranscodingProject
from ..projects.forms import StartTranscodingForm
from ..projects.views import start_transcoding_jobs_view

@admin.register(TranscodingProject)
class TranscodingProjectAdmin(ModelAdmin):
    change_form_template = "admin/workflow/transcodingproject/change_form.html"
    list_display = ('name', 'asset', 'status', 'created', 'modified')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['transcoding_form'] = StartTranscodingForm()
        project = self.get_object(request, object_id)
        if project:
            extra_context['existing_jobs'] = project.transcoding_jobs.all().order_by('-created')
        extra_context['start_jobs_url'] = reverse('admin:workflow_transcodingproject_start_jobs', args=[object_id])
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        custom_urls = [
            path(
                '<path:project_id>/start-jobs/',
                self.admin_site.admin_view(start_transcoding_jobs_view),
                name='%s_%s_start_jobs' % info
            ),
        ]
        return custom_urls + urls