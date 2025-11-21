# 文件路径: apps/workflow/transcoding/views.py

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from ..models import TranscodingProject, TranscodingJob
from .tasks import run_transcoding_job
from .forms import StartTranscodingForm

def trigger_transcoding_view(request, project_id):
    """
    一个新的、专门用于从列表页触发转码的视图。
    """
    project = get_object_or_404(TranscodingProject, pk=project_id)

    if not project.encoding_profile:
        messages.error(request, f"项目《{project.name}》未选择编码配置，无法启动。")
        return redirect('admin:workflow_transcodingproject_changelist')

    media_files = project.asset.medias.all()
    jobs_created_count = 0
    for media in media_files:
        job, created = TranscodingJob.objects.get_or_create(
            project=project,
            media=media,
            profile=project.encoding_profile, # 使用项目预设的 profile
            defaults={'status': 'PENDING'}
        )
        run_transcoding_job.delay(job.id)
        jobs_created_count += 1

    if jobs_created_count > 0:
        messages.success(request, f"已成功为《{project.name}》派发 {jobs_created_count} 个转码任务。")
        project.status = TranscodingProject.STATUS.PROCESSING
        project.save()
    else:
        messages.warning(request, f"项目《{project.name}》下没有找到可用于转码的媒体文件。")

    return redirect('admin:workflow_transcodingproject_changelist')

def start_transcoding_jobs_view(request, project_id):
    print("--- [DEBUG] 'start_transcoding_jobs_view' 被调用 ---") # 诊断点 1

    project = get_object_or_404(TranscodingProject, pk=project_id)

    # 确保只处理 POST 请求
    if request.method != 'POST':
        messages.error(request, "错误：无效的请求方法。")
        return redirect('admin:workflow_transcodingproject_change', object_id=project_id)

    form = StartTranscodingForm(request.POST)

    if form.is_valid():
        print("--- [DEBUG] 表单有效 (Form is valid) ---") # 诊断点 2
        profile = form.cleaned_data['profile']
        media_files = project.asset.medias.all()

        jobs_created_count = 0
        for media in media_files:
            job, created = TranscodingJob.objects.get_or_create(
                project=project,
                media=media,
                profile=profile,
                defaults={'status': 'PENDING'}
            )
            print(f"--- [DEBUG] 准备派发 Job ID: {job.id} ---") # 诊断点 3
            run_transcoding_job.delay(job.id)
            jobs_created_count += 1

        if jobs_created_count > 0:
            messages.success(request, f"已成功为 {jobs_created_count} 个媒体文件派发转码任务。")
            project.status = TranscodingProject.STATUS.PROCESSING
            project.save()
        else:
            messages.warning(request, "此项目下没有找到可用于转码的媒体文件。")
    else:
        # --- ↓↓↓ 这是最关键的诊断点 ↓↓↓ ---
        print("--- [DEBUG] 表单无效 (Form is invalid) ---")
        print(f"--- [DEBUG] 表单错误详情: {form.errors.as_json()} ---") # 诊断点 4

        messages.error(request, f"表单无效: {form.errors.as_text()}")

    return redirect('admin:workflow_transcodingproject_change', object_id=project_id)