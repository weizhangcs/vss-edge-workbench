# 文件路径: apps/workflow/projects/views.py

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from .transcodingProject import TranscodingProject
from ..jobs.transcodingJob import TranscodingJob
from ..tasks.transcoding_tasks import run_transcoding_job
from .forms import StartTranscodingForm

def start_transcoding_jobs_view(request, project_id):
    project = get_object_or_404(TranscodingProject, pk=project_id)
    form = StartTranscodingForm(request.POST)

    if form.is_valid():
        profile = form.cleaned_data['profile']
        media_files = project.asset.medias.all()
        # ... (此处省略了创建和派发 Job 的完整逻辑) ...
        messages.success(request, "转码任务已成功派发。")
    else:
        messages.error(request, f"表单无效: {form.errors.as_text()}")

    return redirect('admin:workflow_transcodingproject_change', object_id=project_id)