# apps/workflow/creative/tasks.py

import json
import logging
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile

from apps.workflow.inference.tasks import poll_cloud_task_status

from ..common.baseJob import BaseJob
from .jobs import CreativeJob
from .projects import CreativeProject
from .services.actions import CreativeTaskAction
from .services.payloads import PayloadBuilder
from .services.synthesis_service import SynthesisService

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. 生成解说词 (Narration - Step 1)
# ==============================================================================


@shared_task(name="apps.workflow.creative.tasks.start_narration_task")
def start_narration_task(project_id: str, config: dict = None, **kwargs):
    """
    [Task] 启动解说词生成。
    逻辑委派：
    1. Action: 准备蓝图、创建 Job
    2. Builder: 组装 V3 Payload
    3. Action: 发送请求、启动轮询
    """
    action = None
    job = None
    try:
        # 1. 初始化动作处理器
        action = CreativeTaskAction(project_id)

        # 2. 准备资源 (智能上传/获取蓝图)
        blueprint_path = action.ensure_blueprint_uploaded()

        # 3. 创建 Job 并更新项目状态
        job = action.create_job(CreativeJob.TYPE.GENERATE_NARRATION, config)
        action.update_project_status(CreativeProject.STATUS.NARRATION_RUNNING)

        # 4. 组装 Payload (V3)
        asset_name, asset_id = action.get_asset_info()
        payload = PayloadBuilder.build_narration_payload(
            asset_name=asset_name, asset_id=asset_id, blueprint_path=blueprint_path, raw_config=config
        )

        # [Debug] 预览 Payload
        logger.info(f"[NarrationTask] Payload: \n{json.dumps(payload, ensure_ascii=False)}")

        # 5. 调用云端
        success, task_data = action.cloud_service.create_task("GENERATE_NARRATION", payload)
        if not success:
            raise Exception(task_data.get("message"))

        # 6. 绑定 Task ID 并轮询
        job.cloud_task_id = task_data["id"]
        job.save()

        poll_cloud_task_status.delay(
            job_id=job.id,
            cloud_task_id=task_data["id"],
            on_complete_task_name="apps.workflow.creative.tasks.finalize_narration_task",
            on_complete_kwargs={},
        )

    except Exception as e:
        logger.error(f"[NarrationTask] Failed: {e}", exc_info=True)
        if job:
            job.fail()
            job.save()
        if action:
            action.update_project_status(CreativeProject.STATUS.FAILED)


@shared_task(name="apps.workflow.creative.tasks.finalize_narration_task")
def finalize_narration_task(job_id: str, cloud_task_data: dict, **kwargs):
    """
    [Callback] 解说词任务完成回调。
    """
    try:
        job = CreativeJob.objects.get(id=job_id)
        action = CreativeTaskAction(str(job.project.id))

        # 1. 通用处理：下载 -> 保存 -> 完成 Job
        action.handle_callback_download(
            job_id=job_id,
            cloud_data=cloud_task_data,
            target_file_field_name="narration_script_file",
            filename_prefix="narration_script",
        )

        # 2. 更新项目状态
        action.update_project_status(CreativeProject.STATUS.NARRATION_COMPLETED)

        # 3. 自动化链式触发 (Auto-Pilot)
        if action.project.auto_config:
            # 检查是否有本地化配置，如果有则触发本地化，否则触发配音
            # 这里简化为直接触发配音，视具体业务逻辑而定
            logger.info("[AutoPilot] 自动触发下一阶段...")
            # TODO: 实现更复杂的 AutoPilot 路由逻辑

    except Exception as e:
        logger.error(f"[NarrationFinal] Failed: {e}", exc_info=True)
        # 这里的异常处理视需求而定，通常记录日志即可


# ==============================================================================
# 2. 本地化 (Localization - Step 1.5)
# ==============================================================================


@shared_task(name="apps.workflow.creative.tasks.start_localize_task")
def start_localize_task(project_id: str, config: dict = None, **kwargs):
    action = None
    job = None
    try:
        action = CreativeTaskAction(project_id)

        # 1. 准备资源
        if not action.project.narration_script_file:
            raise ValueError("母本解说词不存在")

        blueprint_path = action.ensure_blueprint_uploaded()
        master_script_path = action.upload_file_field(action.project.narration_script_file)

        # 2. 创建 Job
        job = action.create_job(CreativeJob.TYPE.LOCALIZE_NARRATION, config)
        action.update_project_status(CreativeProject.STATUS.LOCALIZATION_RUNNING)

        # 3. Payload
        payload = PayloadBuilder.build_localize_payload(
            master_path=master_script_path, blueprint_path=blueprint_path, raw_config=config
        )
        logger.info(f"[LocalizeTask] Payload: \n{json.dumps(payload, ensure_ascii=False)}")

        # 4. API Call
        success, task_data = action.cloud_service.create_task("LOCALIZE_NARRATION", payload)
        if not success:
            raise Exception(task_data.get("message"))

        job.cloud_task_id = task_data["id"]
        job.save()

        # 5. Poll
        poll_cloud_task_status.delay(
            job_id=job.id,
            cloud_task_id=task_data["id"],
            on_complete_task_name="apps.workflow.creative.tasks.finalize_localize_task",
            on_complete_kwargs={},
        )

    except Exception as e:
        logger.error(f"[LocalizeTask] Failed: {e}", exc_info=True)
        if job:
            job.fail()
            job.save()
        if action:
            action.update_project_status(CreativeProject.STATUS.FAILED)


@shared_task(name="apps.workflow.creative.tasks.finalize_localize_task")
def finalize_localize_task(job_id: str, cloud_task_data: dict, **kwargs):
    try:
        job = CreativeJob.objects.get(id=job_id)
        action = CreativeTaskAction(str(job.project.id))

        action.handle_callback_download(
            job_id=job_id,
            cloud_data=cloud_task_data,
            target_file_field_name="localized_script_file",
            filename_prefix="localized_script",
        )

        action.update_project_status(CreativeProject.STATUS.LOCALIZATION_COMPLETED)

    except Exception as e:
        logger.error(f"[LocalizeFinal] Failed: {e}", exc_info=True)


# ==============================================================================
# 3. 配音 (Dubbing - Step 2)
# ==============================================================================


@shared_task(name="apps.workflow.creative.tasks.start_audio_task")
def start_audio_task(project_id: str, config: dict = None, **kwargs):
    action = None
    job = None
    try:
        action = CreativeTaskAction(project_id)
        if not config:
            config = {}

        # 1. 确定输入源 (Master vs Localized)
        source_type = config.get("source_script_type", "master")
        source_field = (
            action.project.localized_script_file if source_type == "localized" else action.project.narration_script_file
        )

        if not source_field:
            raise ValueError(f"选定的配音脚本源 ({source_type}) 文件不存在")

        # 2. 上传脚本
        input_path = action.upload_file_field(source_field)

        # 3. 创建 Job
        job = action.create_job(CreativeJob.TYPE.GENERATE_AUDIO, config)
        action.update_project_status(CreativeProject.STATUS.AUDIO_RUNNING)

        # 4. Payload
        payload = PayloadBuilder.build_dubbing_payload(input_path=input_path, raw_config=config)
        logger.info(f"[AudioTask] Payload: \n{json.dumps(payload, ensure_ascii=False)}")

        # 5. API Call
        success, task_data = action.cloud_service.create_task("GENERATE_DUBBING", payload)
        if not success:
            raise Exception(task_data.get("message"))

        job.cloud_task_id = task_data["id"]
        job.save()

        # 6. Poll
        poll_cloud_task_status.delay(
            job_id=job.id,
            cloud_task_id=task_data["id"],
            on_complete_task_name="apps.workflow.creative.tasks.finalize_audio_task",
            on_complete_kwargs={},
        )

    except Exception as e:
        logger.error(f"[AudioTask] Failed: {e}", exc_info=True)
        if job:
            job.fail()
            job.save()
        if action:
            action.update_project_status(CreativeProject.STATUS.FAILED)


@shared_task(name="apps.workflow.creative.tasks.finalize_audio_task")
def finalize_audio_task(job_id: str, cloud_task_data: dict, **kwargs):
    """
    [Callback] 配音回调 (完整版)。
    """
    try:
        job = CreativeJob.objects.get(id=job_id)
        action = CreativeTaskAction(str(job.project.id))

        # 1. 下载主 JSON (dubbing_script.json)
        action.handle_callback_download(
            job_id=job_id,
            cloud_data=cloud_task_data,
            target_file_field_name="dubbing_script_file",
            filename_prefix="dubbing_script",
        )

        # 2. [新增] 下载音频资源并回写路径
        action.download_assets_from_dubbing_script(job_id)

        # 3. 更新状态
        action.update_project_status(CreativeProject.STATUS.AUDIO_COMPLETED)

        # 4. 自动化触发 (Auto-Pilot)
        if action.project.auto_config:
            logger.info("[AutoPilot] 自动启动步骤 3 (剪辑脚本)...")
            # 注意：需要导入 start_edit_script_task
            from .tasks import start_edit_script_task

            start_edit_script_task.delay(project_id=str(action.project.id))

    except Exception as e:
        logger.error(f"[AudioFinal] Failed: {e}", exc_info=True)
        # 这里可以考虑增加 action.update_project_status(CreativeProject.STATUS.FAILED)


# ==============================================================================
# 4. 生成剪辑脚本 (Edit Script - Step 3)
# ==============================================================================


@shared_task(name="apps.workflow.creative.tasks.start_edit_script_task")
def start_edit_script_task(project_id: str, **kwargs):
    """
    [Task] 启动剪辑脚本生成。
    依赖：
    1. Dubbing Script (配音脚本，含音频时长信息)
    2. Blueprint (蓝图，含画面结构信息)
    """
    action = None
    job = None
    try:
        action = CreativeTaskAction(project_id)

        # 1. 检查前置依赖
        # 必须有配音脚本 (无论是母本配音还是译本配音，都在 dubbing_script_file 中)
        if not action.project.dubbing_script_file:
            raise ValueError("配音脚本 (Dubbing Script) 不存在，无法生成剪辑脚本。请先完成步骤 2。")

        # 2. 准备资源
        # 智能上传蓝图
        blueprint_path = action.ensure_blueprint_uploaded()
        # 上传配音脚本
        dubbing_script_path = action.upload_file_field(action.project.dubbing_script_file)

        # 3. 创建 Job
        job = action.create_job(CreativeJob.TYPE.GENERATE_EDIT_SCRIPT, {})
        action.update_project_status(CreativeProject.STATUS.EDIT_RUNNING)

        # 4. 组装 Payload
        # (此 Payload 结构较简单，直接在此组装，也可以扩展 PayloadBuilder)
        payload = {
            "dubbing_script_path": dubbing_script_path,
            "blueprint_path": blueprint_path,
            "service_params": {"lang": "zh"},  # 剪辑脚本生成通常不需要复杂的语言参数，主要依赖时间戳
        }
        logger.info(f"[EditTask] Payload: {json.dumps(payload, ensure_ascii=False)}")

        # 5. 调用云端 API
        success, task_data = action.cloud_service.create_task("GENERATE_EDITING_SCRIPT", payload)
        if not success:
            raise Exception(task_data.get("message"))

        job.cloud_task_id = task_data["id"]
        job.save()

        # 6. 轮询
        poll_cloud_task_status.delay(
            job_id=job.id,
            cloud_task_id=task_data["id"],
            on_complete_task_name="apps.workflow.creative.tasks.finalize_edit_script_task",
            on_complete_kwargs={},
        )

    except Exception as e:
        logger.error(f"[EditTask] Failed: {e}", exc_info=True)
        if job:
            job.fail()
            job.save()
        if action:
            action.update_project_status(CreativeProject.STATUS.FAILED)


@shared_task(name="apps.workflow.creative.tasks.finalize_edit_script_task")
def finalize_edit_script_task(job_id: str, cloud_task_data: dict, **kwargs):
    """
    [Callback] 剪辑脚本完成回调。
    """
    try:
        job = CreativeJob.objects.get(id=job_id)
        action = CreativeTaskAction(str(job.project.id))

        # 1. 下载并保存 editing_script.json
        action.handle_callback_download(
            job_id=job_id,
            cloud_data=cloud_task_data,
            target_file_field_name="edit_script_file",
            filename_prefix="editing_script",
        )

        action.update_project_status(CreativeProject.STATUS.EDIT_COMPLETED)

        # 2. 自动化链式触发 (如果配置了 Auto-Pilot)
        if action.project.auto_config:
            logger.info("[AutoPilot] 检测到自动化配置，正在自动启动步骤 4 (最终合成)...")
            start_synthesis_task.delay(project_id=str(action.project.id))

    except Exception as e:
        logger.error(f"[EditFinal] Failed: {e}", exc_info=True)
        # Job 状态更新在 handle_callback_download 中已处理了一部分，这里可补充 Fail 逻辑


# ==============================================================================
# 5. 视频合成 (Synthesis - Step 4)
# ==============================================================================


@shared_task(name="apps.workflow.creative.tasks.start_synthesis_task")
def start_synthesis_task(project_id: str, **kwargs):
    """
    [Task] 本地合成任务。
    不调用云端 API，而是调用本地的 SynthesisService 操作 FFmpeg。
    """
    action = None
    job = None
    try:
        action = CreativeTaskAction(project_id)

        # 1. 简单状态检查 (允许重试)
        if action.project.status == CreativeProject.STATUS.SYNTHESIS_RUNNING:
            logger.warning(f"项目 {project_id} 正在合成中，跳过重复触发。")
            return

        # 2. 创建本地任务
        job = action.create_job(CreativeJob.TYPE.SYNTHESIS, {})
        action.update_project_status(CreativeProject.STATUS.SYNTHESIS_RUNNING)

        # 3. 准备必要的文件路径
        # (1) 剪辑脚本
        if not action.project.edit_script_file:
            raise ValueError("缺少剪辑脚本 (edit_script_file)")
        editing_script_path = Path(action.project.edit_script_file.path)

        # (2) 蓝图 (从推理项目获取)
        inf_proj = action.project.inference_project
        if not inf_proj.annotation_project.final_blueprint_file:
            raise ValueError("缺少叙事蓝图 (final_blueprint_file)")
        blueprint_path = Path(inf_proj.annotation_project.final_blueprint_file.path)

        # (3) 原始视频目录 (Source Videos)
        # 假设存储结构: media_root/source_files/{asset_id}/media/
        source_videos_dir = Path(settings.MEDIA_ROOT) / "source_files" / str(action.project.asset.id) / "media"

        # (4) 本地音频基目录 (Audio Base Dir)
        # 这是一个难点：我们需要找到之前配音任务下载音频的那个目录。
        # 假设逻辑：找到最近一个成功的配音任务，其产出目录即为基目录。
        # 注意：这依赖于 finalize_audio_task 是否真的把音频下载到了这个固定结构的目录中。
        last_audio_job = (
            CreativeJob.objects.filter(
                project=action.project, job_type=CreativeJob.TYPE.GENERATE_AUDIO, status=BaseJob.STATUS.COMPLETED
            )
            .order_by("-modified")
            .first()
        )

        if not last_audio_job:
            raise ValueError("找不到已完成的配音任务，无法定位音频文件。")

        # 构建路径: media_root/creative/{id}/outputs/audio_{job_id}/
        # 这里的命名规则必须与 finalize_audio_task 中的下载逻辑保持一致
        # from .projects import get_creative_output_upload_path

        # 注意：get_creative_output_upload_path 返回的是相对路径，我们需要绝对路径
        # 这里的 audio_{job_id} 是我们约定的子目录名
        relative_audio_dir = f"creative/{action.project.id}/outputs/audio_{last_audio_job.id}"
        local_audio_base_dir = Path(settings.MEDIA_ROOT) / relative_audio_dir

        if not local_audio_base_dir.exists():
            raise FileNotFoundError(f"音频目录不存在: {local_audio_base_dir}")

        logger.info(f"[Synthesis] 准备就绪。AudioDir: {local_audio_base_dir}")

        # 4. 执行本地合成服务 (同步阻塞操作)
        service = SynthesisService(project_id)

        final_output_path = service.execute(
            editing_script_path=editing_script_path,
            blueprint_path=blueprint_path,
            local_audio_base_dir=local_audio_base_dir,
            source_videos_dir=source_videos_dir,
            asset_id=str(action.project.asset.id),
        )

        # 5. 任务完成，直接调用回调 (因为是本地同步执行)
        finalize_synthesis_task(job_id=str(job.id), final_output_path=str(final_output_path))

    except Exception as e:
        logger.error(f"[Synthesis] Failed: {e}", exc_info=True)
        if job:
            job.fail()
            job.save()
        if action:
            action.update_project_status(CreativeProject.STATUS.FAILED)


@shared_task(name="apps.workflow.creative.tasks.finalize_synthesis_task")
def finalize_synthesis_task(job_id: str, final_output_path: str, **kwargs):
    """
    [Callback] 本地合成完成回调。
    """
    try:
        job = CreativeJob.objects.get(id=job_id)
        # 这里不需要 Action 去处理下载，因为文件已经在本地了
        project = job.project

        output_path_obj = Path(final_output_path)
        if not output_path_obj.exists():
            raise FileNotFoundError(f"合成产物未找到: {final_output_path}")

        # 将生成的视频文件挂载到 Project 字段
        # 使用 File 对象读取本地文件并保存
        with output_path_obj.open("rb") as f:
            project.final_video_file.save(output_path_obj.name, ContentFile(f.read()), save=False)

        project.status = CreativeProject.STATUS.COMPLETED
        project.save()

        job.complete()
        job.save()

        logger.info(f"[SynthesisFinal] 视频合成全流程结束！Project: {project.id}")

    except Exception as e:
        logger.error(f"[SynthesisFinal] Failed: {e}", exc_info=True)
        # 更新状态失败
