# 文件路径: apps/workflow/creative/tasks.py

import logging
import json
import os
from pathlib import Path
from celery import shared_task
from django.core.files.base import ContentFile
from django.conf import settings

from .projects import CreativeProject, get_creative_output_upload_path
from .jobs import CreativeJob
from apps.workflow.inference.services.cloud_api import CloudApiService
from apps.workflow.inference.tasks import poll_cloud_task_status # 重用轮询器
from apps.workflow.common.baseJob import BaseJob
from apps.workflow.inference.projects import InferenceJob

logger = logging.getLogger(__name__)


# --- 您的步骤 1: 生成解说词 ---

@shared_task(name="apps.workflow.creative.tasks.start_narration_task")
def start_narration_task(project_id: str, **kwargs):
    """
    (新 V2 - 遵从您的正确逻辑)
    由 Admin 视图触发，开始您的“步骤 1：生成解说词”。
    """
    job = None
    project = None
    try:
        project = CreativeProject.objects.get(id=project_id)

        # 0. 检查前置条件：必须有关联的推理项目
        inference_project = project.inference_project
        if not inference_project:
            raise ValueError("找不到关联的 InferenceProject")

        # [!!!] --- 核心修正：您是正确的 --- [!!!]
        # 我们不需要查找旧的 RAG Job。
        # RAG 部署时使用的 series_id 就是 str(inference_project.id)。
        # 我们在这里直接重用这个 ID 即可。

        # 1. 直接获取 series_id 和 series_name
        series_id_to_use = str(inference_project.id)
        series_name = project.asset.title  #

        # 2. 创建 Job
        job = CreativeJob.objects.create(
            project=project,
            job_type=CreativeJob.TYPE.GENERATE_NARRATION,
            status=BaseJob.STATUS.PENDING,
            # (为了调试方便，我们仍然可以把它保存到 input_params，但这已非必要)
            input_params={
                "series_id": series_id_to_use,
                "series_name": series_name,
                "service_params": {"temp": 0.2}  #
            }
        )
        job.start()  # PENDING -> PROCESSING

        project.status = CreativeProject.STATUS.NARRATION_RUNNING
        project.save()

    except Exception as e:
        logger.error(f"[CreativeTask 1] 无法启动解说词任务 (Project: {project_id}): {e}", exc_info=True)
        if job: job.fail(); job.save()
        if project: project.status = CreativeProject.STATUS.FAILED; project.save()
        return

    try:
        # 3. 调用云端 API
        service = CloudApiService()
        payload = {
            "series_name": series_name,
            "series_id": series_id_to_use,  # [!!!] 使用我们推导出的 ID
            "service_params": job.input_params.get("service_params", {})
        }

        # (API Doc: GENERATE_NARRATION)
        success, task_data = service.create_task("GENERATE_NARRATION", payload)
        if not success:
            raise Exception(task_data.get('message', 'Failed to create GENERATE_NARRATION task'))

        job.cloud_task_id = task_data['id']
        job.save()

        # 4. 触发轮询
        poll_cloud_task_status.delay(
            job_id=job.id,
            cloud_task_id=task_data['id'],
            on_complete_task_name='apps.workflow.creative.tasks.finalize_narration_task',
            on_complete_kwargs={}
        )
    except Exception as e:
        logger.error(f"[CreativeTask 1] API 调用失败 (Job: {job.id}): {e}", exc_info=True)
        job.fail();
        job.save()
        project.status = CreativeProject.STATUS.FAILED;
        project.save()


@shared_task(name="apps.workflow.creative.tasks.finalize_narration_task")
def finalize_narration_task(job_id: str, cloud_task_data: dict, **kwargs):
    """
    (新) 
    “步骤 1：生成解说词”成功后的回调。
    """
    job = None
    try:
        job = CreativeJob.objects.get(id=job_id)
        project = job.project
    except CreativeJob.DoesNotExist:
        logger.error(f"[CreativeFinal 1] 找不到 CreativeJob {job_id}，任务终止。")
        return

    try:
        service = CloudApiService()
        download_url = cloud_task_data.get("download_url")  # [cite: 25]

        if download_url:
            success, content = service.download_task_result(download_url)  # [cite: 26, 27]
            if success:
                # [cite: 122]
                project.narration_script_file.save(f"narration_script_{job.id}.json", ContentFile(content), save=False)
            else:
                raise Exception(f"下载解说词失败: {download_url}")
        else:
            raise Exception("云端任务完成，但未提供 download_url")

        job.complete();
        job.save()
        project.status = CreativeProject.STATUS.NARRATION_COMPLETED
        project.save()

        logger.info(f"[CreativeFinal 1] 步骤 1 (解说词) 已成功 (Project: {project.id})！")
    except Exception as e:
        logger.error(f"[CreativeFinal 1] Job {job_id} 最终化处理失败: {e}", exc_info=True)
        if job: job.fail(); job.save()
        if project: project.status = CreativeProject.STATUS.FAILED; project.save()


# --- 您的步骤 2: 生成配音 (框架) ---

@shared_task(name="apps.workflow.creative.tasks.start_audio_task")
def start_audio_task(project_id: str, **kwargs):
    """
    (新 V2)
    由 Admin 视图触发，开始您的“步骤 2：生成配音”。
    """
    job = None
    project = None
    try:
        project = CreativeProject.objects.get(id=project_id)

        if project.status != CreativeProject.STATUS.NARRATION_COMPLETED:
            logger.warning(f"[CreativeTask 2] 项目状态不是 NARRATION_COMPLETED，任务中止。")
            return

        if not project.narration_script_file:
            raise ValueError("找不到已完成的 narration_script_file")

        # (从指南中获取，您可以将其变为参数) [cite: 280]
        template_name = "chinese_paieas_replication"

        # 2. 创建 Job
        job = CreativeJob.objects.create(
            project=project,
            job_type=CreativeJob.TYPE.GENERATE_AUDIO,
            status=BaseJob.STATUS.PENDING,
            input_params={"template_name": template_name}
        )
        job.start()

        project.status = CreativeProject.STATUS.AUDIO_RUNNING
        project.save()

    except Exception as e:
        logger.error(f"[CreativeTask 2] 无法启动配音任务 (Project: {project_id}): {e}", exc_info=True)
        if job: job.fail(); job.save()
        if project: project.status = CreativeProject.STATUS.FAILED; project.save()
        return

    try:
        service = CloudApiService()

        # 1. 上传解说词脚本 [cite: 166]
        success, narration_path = service.upload_file(Path(project.narration_script_file.path))
        if not success:
            raise Exception(f"上传 narration_script_file 失败: {narration_path}")

        # 2. 构建 Payload [cite: 282]
        payload = {
            "input_narration_path": narration_path,  # [cite: 279]
            "service_params": {
                "template_name": template_name  # [cite: 280]
            }
        }

        # 3. 创建云端任务
        success, task_data = service.create_task("GENERATE_DUBBING", payload)
        if not success:
            raise Exception(task_data.get('message', 'Failed to create GENERATE_DUBBING task'))

        job.cloud_task_id = task_data['id']
        # (顺便保存我们上传的路径，便于调试)
        job.input_params['uploaded_narration_path'] = narration_path
        job.save()

        # 4. 触发轮询
        poll_cloud_task_status.delay(
            job_id=job.id,
            cloud_task_id=task_data['id'],
            on_complete_task_name='apps.workflow.creative.tasks.finalize_audio_task',
            on_complete_kwargs={}
        )
    except Exception as e:
        logger.error(f"[CreativeTask 2] API 调用失败 (Job: {job.id}): {e}", exc_info=True)
        job.fail();
        job.save()
        project.status = CreativeProject.STATUS.FAILED;
        project.save()


@shared_task(name="apps.workflow.creative.tasks.finalize_audio_task")
def finalize_audio_task(job_id: str, cloud_task_data: dict, **kwargs):
    """
    (新 V2)
    “步骤 2：生成配音”成功后的回调。
    这是最复杂的一步，因为它需要下载*多个*文件。
    """
    job = None
    try:
        job = CreativeJob.objects.get(id=job_id)
        project = job.project
    except CreativeJob.DoesNotExist:
        logger.error(f"[CreativeFinal 2] 找不到 CreativeJob {job_id}，任务终止。")
        return

    try:
        service = CloudApiService()

        # 1. 下载主结果文件 (dubbing_script.json) [cite: 283]
        download_url = cloud_task_data.get("download_url")
        if not download_url:
            raise Exception("云端任务完成，但未提供 download_url (for dubbing_script.json)")

        success, content = service.download_task_result(download_url)
        if not success:
            raise Exception(f"下载 dubbing_script.json 失败: {download_url}")

        dubbing_script_data = json.loads(content.decode('utf-8'))
        dubbing_list = dubbing_script_data.get("dubbing_script", [])

        # 2. 准备本地存储
        # 定义一个此任务专用的音频文件夹
        local_audio_dir_rel = os.path.join(
            get_creative_output_upload_path(project, ''),  # creative/{id}/outputs/
            f"audio_{job.id}"
        )
        local_audio_dir_abs = Path(settings.MEDIA_ROOT) / local_audio_dir_rel
        local_audio_dir_abs.mkdir(parents=True, exist_ok=True)

        logger.info(f"[CreativeFinal 2] 准备下载 {len(dubbing_list)} 个音频文件到 {local_audio_dir_abs}")

        # 3. 遍历 JSON，逐个下载音频文件 [cite: 288]
        modified_dubbing_list = []
        for item in dubbing_list:
            cloud_audio_path = item.get("audio_file_path")  # e.g., "tmp/.../narration_000.wav"
            if not cloud_audio_path:
                continue

            # 3a. 使用“通用下载接口”下载 [cite: 216]
            success_wav, content_wav = service.download_general_file(cloud_audio_path)

            if success_wav:
                # 3b. 保存 .wav 文件到本地
                wav_filename = os.path.basename(cloud_audio_path)  # "narration_000.wav"
                local_wav_path_rel = os.path.join(local_audio_dir_rel, wav_filename)
                local_wav_path_abs = Path(settings.MEDIA_ROOT) / local_wav_path_rel

                with open(local_wav_path_abs, 'wb') as f:
                    f.write(content_wav)

                # 3c. (关键) 更新 JSON 对象，将云端路径替换为本地相对路径
                item["local_audio_path"] = local_wav_path_rel
                modified_dubbing_list.append(item)
            else:
                logger.error(f"[CreativeFinal 2] 成功下载 dubbing_script.json，但下载 {cloud_audio_path} 失败。")
                # (根据业务逻辑，您可以选择是中止还是继续)
                modified_dubbing_list.append(item)  # 仍然添加，但缺少 local_audio_path

        # 4. 保存被修改过的 (包含 local_audio_path) dubbing_script.json
        dubbing_script_data["dubbing_script"] = modified_dubbing_list
        modified_content_str = json.dumps(dubbing_script_data, indent=2, ensure_ascii=False)

        project.dubbing_script_file.save(
            f"dubbing_script_{job.id}.json",
            ContentFile(modified_content_str.encode('utf-8')),
            save=False
        )

        job.complete();
        job.save()
        project.status = CreativeProject.STATUS.AUDIO_COMPLETED
        project.save()

        logger.info(f"[CreativeFinal 2] 步骤 2 (配音) 已成功 (Project: {project.id})！")
    except Exception as e:
        logger.error(f"[CreativeFinal 2] Job {job_id} 最终化处理失败: {e}", exc_info=True)
        if job: job.fail(); job.save()
        if project: project.status = CreativeProject.STATUS.FAILED; project.save()


# --- 您的步骤 3: 生成剪辑脚本 (已实现) ---

@shared_task(name="apps.workflow.creative.tasks.start_edit_script_task")
def start_edit_script_task(project_id: str, **kwargs):
    """
    (新 V2)
    由 Admin 视图触发，开始您的“步骤 3：生成剪辑脚本”。
    """
    job = None
    project = None
    try:
        project = CreativeProject.objects.get(id=project_id)

        if project.status != CreativeProject.STATUS.AUDIO_COMPLETED:
            logger.warning(f"[CreativeTask 3] 项目状态不是 AUDIO_COMPLETED，任务中止。")
            return

        if not project.dubbing_script_file:
            raise ValueError("找不到已完成的 dubbing_script_file")

        if not project.inference_project.annotation_project.final_blueprint_file:
            raise ValueError("找不到关联的 final_blueprint_file")

        # 2. 创建 Job
        job = CreativeJob.objects.create(
            project=project,
            job_type=CreativeJob.TYPE.GENERATE_EDIT_SCRIPT,
            status=BaseJob.STATUS.PENDING,
            input_params={"lang": "zh"}  # [cite: 297]
        )
        job.start()

        project.status = CreativeProject.STATUS.EDIT_RUNNING
        project.save()

    except Exception as e:
        logger.error(f"[CreativeTask 3] 无法启动剪辑脚本任务 (Project: {project_id}): {e}", exc_info=True)
        if job: job.fail(); job.save()
        if project: project.status = CreativeProject.STATUS.FAILED; project.save()
        return

    try:
        service = CloudApiService()

        # 1. 上传 dubbing_script.json [cite: 292]
        success, dubbing_path = service.upload_file(Path(project.dubbing_script_file.path))
        if not success:
            raise Exception(f"上传 dubbing_script_file 失败: {dubbing_path}")

        # 2. (高效) 重用已上传的 blueprint 路径 [cite: 293]
        # 我们从 inference 工作流中找到它
        inference_job = project.inference_project.jobs.filter(
            cloud_blueprint_path__isnull=False
        ).order_by('-modified').first()

        if not inference_job or not inference_job.cloud_blueprint_path:
            # (备用方案：如果找不到，就重新上传)
            logger.warning(f"[CreativeTask 3] 找不到已上传的蓝图路径，将重新上传。")
            bp_file_path = project.inference_project.annotation_project.final_blueprint_file.path
            success_bp, blueprint_path = service.upload_file(Path(bp_file_path))
            if not success_bp:
                raise Exception(f"备用方案：上传 blueprint 失败: {blueprint_path}")
        else:
            blueprint_path = inference_job.cloud_blueprint_path
            logger.info(f"[CreativeTask 3] 成功重用蓝图路径: {blueprint_path}")

        # 3. 构建 Payload [cite: 297]
        payload = {
            "dubbing_script_path": dubbing_path,
            "blueprint_path": blueprint_path,
            "service_params": job.input_params
        }

        # 4. 创建云端任务
        success, task_data = service.create_task("GENERATE_EDITING_SCRIPT", payload)
        if not success:
            raise Exception(task_data.get('message', 'Failed to create GENERATE_EDITING_SCRIPT task'))

        job.cloud_task_id = task_data['id']
        job.save()

        # 5. 触发轮询
        poll_cloud_task_status.delay(
            job_id=job.id,
            cloud_task_id=task_data['id'],
            on_complete_task_name='apps.workflow.creative.tasks.finalize_edit_script_task',
            on_complete_kwargs={}
        )
    except Exception as e:
        logger.error(f"[CreativeTask 3] API 调用失败 (Job: {job.id}): {e}", exc_info=True)
        job.fail();
        job.save()
        project.status = CreativeProject.STATUS.FAILED;
        project.save()


@shared_task(name="apps.workflow.creative.tasks.finalize_edit_script_task")
def finalize_edit_script_task(job_id: str, cloud_task_data: dict, **kwargs):
    """
    (新 V2)
    “步骤 3：生成剪辑脚本”成功后的回调。
    """
    job = None
    try:
        job = CreativeJob.objects.get(id=job_id)
        project = job.project
    except CreativeJob.DoesNotExist:
        logger.error(f"[CreativeFinal 3] 找不到 CreativeJob {job_id}，任务终止。")
        return

    try:
        service = CloudApiService()

        # 1. 下载主结果文件 (editing_script.json) [cite: 298]
        download_url = cloud_task_data.get("download_url")
        if not download_url:
            raise Exception("云端任务完成，但未提供 download_url (for editing_script.json)")

        success, content = service.download_task_result(download_url)
        if not success:
            raise Exception(f"下载 editing_script.json 失败: {download_url}")

        # 2. 保存到步骤 3 的产出物字段
        project.edit_script_file.save(f"editing_script_{job.id}.json", ContentFile(content), save=False)

        job.complete();
        job.save()
        project.status = CreativeProject.STATUS.COMPLETED  # [!!!] 整个工作流完成
        project.save()

        logger.info(f"[CreativeFinal 3] 步骤 3 (剪辑脚本) 已成功 (Project: {project.id})！")
        logger.info(f"--- [Creative Workflow COMPLETE] (Project: {project.id}) ---")

    except Exception as e:
        logger.error(f"[CreativeFinal 3] Job {job_id} 最终化处理失败: {e}", exc_info=True)
        if job: job.fail(); job.save()
        if project: project.status = CreativeProject.STATUS.FAILED; project.save()