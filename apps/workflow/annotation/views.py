# 文件路径: apps/workflow/views/annotation_views.py

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.files.base import ContentFile
import logging

from ..models import AnnotationJob,AnnotationProject, TranscodingJob
from .tasks import generate_narrative_blueprint_task

logger = logging.getLogger(__name__)


def get_video_url_for_job(job: AnnotationJob) -> str:
    project = job.project
    media_item = job.media

    video_url = None
    if project.source_encoding_profile:
        transcoding_job = TranscodingJob.objects.filter(
            media=media_item,
            profile=project.source_encoding_profile,
            status=TranscodingJob.STATUS.COMPLETED
        ).order_by('-modified').first()

        if transcoding_job and transcoding_job.output_url:
            video_url = transcoding_job.output_url

    if not video_url:
        video_url = f"{settings.LOCAL_MEDIA_URL_BASE}{media_item.source_video.url}"

    return video_url

def start_l1_annotation_view(request, job_id):
    """
    处理“开始L1字幕标注”按钮点击的视图。
    1. 将任务状态变更为“处理中”。
    2. 重定向到 vss-subeditor 外部工具。
    """
    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L1_SUBEDITING)

    if job.status == 'PENDING':
        job.start()
        job.save()
        messages.success(request, f"字幕任务 '{job.media.title}' 状态已更新为“处理中”。")

    #video_url = f"{settings.LOCAL_MEDIA_URL_BASE}{job.media.source_video.url}"
    # --- 核心修改: 使用辅助函数获取 URL ---
    video_url = get_video_url_for_job(job)

    srt_url = ""
    if job.media.source_subtitle:
        srt_url = f"{settings.LOCAL_MEDIA_URL_BASE}{job.media.source_subtitle.url}"

    job_id_param = job.id
    return_url_param = request.build_absolute_uri(
        reverse('admin:workflow_annotationproject_change', args=[job.project.id]))

    subeditor_url = f"{settings.SUBEDITOR_PUBLIC_URL}?videoUrl={video_url}&srtUrl={srt_url}&jobId={job_id_param}&returnUrl={return_url_param}"

    return redirect(subeditor_url)

@csrf_exempt
def save_l1_output_view(request, job_id):
    """
    接收来自 vss-subeditor 的回调，保存L1产出物 (.ass 文件)。
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'}, status=405)

    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L1_SUBEDITING)

    try:
        ass_content = request.body.decode('utf-8')

        if not ass_content:
            return JsonResponse({'status': 'error', 'message': 'No content received'}, status=400)

        file_name = f"{job.media.title}_l1.ass"
        job.l1_output_file.save(file_name, ContentFile(ass_content.encode('utf-8')), save=False)

        job.complete()
        job.save()

        return JsonResponse({'status': 'success', 'message': 'L1 output saved and job marked as complete.'})

    except Exception as e:
        job.fail()
        job.save()
        logger.error(f"保存L1产出物时出错 (Job ID: {job.id}): {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def revise_l1_annotation_view(request, job_id):
    """
    处理“修订L1字幕”按钮点击的视图。
    1. 调用revise()方法，自动备份产出物并将状态变更为“修订中”。
    2. 重定向到 vss-subeditor 外部工具。
    """
    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L1_SUBEDITING)

    if job.status == 'COMPLETED':
        job.revise()
        job.save()
        messages.success(request, f"字幕任务 '{job.media.title}' 已重新打开进行修订。")

    #video_url = f"{settings.LOCAL_MEDIA_URL_BASE}{job.media.source_video.url}"
    # --- 核心修改: 使用辅助函数获取 URL ---
    video_url = get_video_url_for_job(job)

    srt_url = ""
    if job.l1_output_file:
        # 【核心修正】手动构建正确的URL，以匹配Nginx配置
        # job.l1_output_file.name 的值是类似: <project_id>/<job_id>_filename.ass
        correct_path = f"/media/annotation/{job.l1_output_file.name}"
        srt_url = f"{settings.LOCAL_MEDIA_URL_BASE}{correct_path}"

    job_id_param = job.id
    return_url_param = request.build_absolute_uri(
        reverse('admin:workflow_annotationproject_change', args=[job.project.id]))

    subeditor_url = f"{settings.SUBEDITOR_PUBLIC_URL}?videoUrl={video_url}&srtUrl={srt_url}&jobId={job_id_param}&returnUrl={return_url_param}"

    return redirect(subeditor_url)

def start_l2l3_annotation_view(request, job_id):
    """
    处理“开始L2/L3语义标注”按钮点击的视图。
    1. 将任务状态变更为“处理中”。
    2. 重定向到 Label Studio 的具体任务页面。
    """
    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L2L3_SEMANTIC)

    if job.status == 'PENDING':
        job.start()
        job.save()
        messages.success(request, f"语义标注任务 '{job.media.title}' 状态已更新为“处理中”。")

    if not job.project.label_studio_project_id or not job.label_studio_task_id:
        messages.error(request, "错误：项目或任务未成功在 Label Studio 中创建，无法跳转。")
        return redirect(reverse('admin:workflow_annotationproject_change', args=[job.project.id]))

    ls_project_id = job.project.label_studio_project_id
    ls_task_id = job.label_studio_task_id
    label_studio_task_url = f"{settings.LABEL_STUDIO_PUBLIC_URL}/projects/{ls_project_id}/data/?task={ls_task_id}"

    return redirect(label_studio_task_url)

def export_l2_output_view(request, project_id):
    """
    触发一个后台任务，从 Label Studio 导出 L2 产出物。
    """
    project = get_object_or_404(AnnotationProject, id=project_id)

    # 引入我们将在下一步创建的 Celery Task
    from .tasks import export_l2_output_task

    export_l2_output_task.delay(project_id=str(project.id))

    messages.success(request, f"已启动为项目《{project.name}》导出L2产出物的后台任务。请稍后刷新查看结果。")

    return redirect(reverse('admin:workflow_annotationproject_change', args=[project.id]))

def generate_blueprint_view(request, project_id):
    """
    触发一个后台任务，为项目生成最终的叙事蓝图。
    """
    project = get_object_or_404(AnnotationProject, id=project_id)

    if not project.label_studio_export_file:
        messages.error(request, "错误：缺少L2产出物，无法生成蓝图。请先导出L2产出物。")
    else:
        generate_narrative_blueprint_task.delay(project_id=str(project.id))
        messages.success(request, f"已启动为项目《{project.name}》生成叙事蓝图的后台任务。")

    return redirect(reverse('admin:workflow_annotationproject_change', args=[project.id]))