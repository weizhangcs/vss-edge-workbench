# 文件路径: apps/workflow/creative/tasks.py

import logging
import json
import os
from decimal import Decimal
from pathlib import Path
from celery import shared_task
from django.core.files.base import ContentFile
from django.conf import settings
from django.db.models import Q
from django_fsm import TransitionNotAllowed

from .projects import CreativeProject, get_creative_output_upload_path
from .jobs import CreativeJob
from apps.workflow.inference.services.cloud_api import CloudApiService
from apps.workflow.inference.tasks import poll_cloud_task_status # 重用轮询器
from apps.workflow.common.baseJob import BaseJob
from apps.workflow.inference.projects import InferenceJob
from .services.synthesis_service import SynthesisService

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. 生成解说词 (Narration V3) - 最终事实版 (v1.2.0-alpha.3+)
# ==============================================================================

@shared_task(name="apps.workflow.creative.tasks.start_narration_task")
def start_narration_task(project_id: str, config: dict = None, **kwargs):
    """
    (V3 Final) 启动解说词生成任务。
    严格对应 API 文档 payload 结构。
    """
    job = None
    project = None

    # 1. 默认配置兜底 (若 config 为空)
    if not config:
        config = {
            "narrative_focus": "romantic_progression",
            "scope_start": 1,
            "scope_end": 5,
            "style": "humorous",
            "perspective": "third_person",
            "target_duration_minutes": 3,
            "overflow_tolerance": 0.0,
            "speaking_rate": 4.2,
            "rag_top_k": 50
        }

    # [类型清洗] Decimal -> float (防止 JSON 序列化报错)
    if config:
        for k, v in config.items():
            if isinstance(v, Decimal):
                config[k] = float(v)

    try:
        # --- 资源准备 & 状态检查 ---
        project = CreativeProject.objects.get(id=project_id)
        inference_project = project.inference_project
        if not inference_project:
            raise ValueError("未找到关联的 InferenceProject")

        asset_id = str(project.asset.id)
        asset_name = project.asset.title

        # --- 蓝图上传/获取逻辑 ---
        service = CloudApiService()
        blueprint_path = None

        # 优先上传本地最新蓝图
        local_bp = inference_project.annotation_project.final_blueprint_file
        if local_bp and local_bp.path and Path(local_bp.path).exists():
            success, path = service.upload_file(Path(local_bp.path))
            if success:
                blueprint_path = path
            else:
                raise Exception(f"蓝图上传失败: {path}")
        else:
            # 备用：尝试查找旧的云端路径
            inference_job = inference_project.jobs.filter(
                cloud_blueprint_path__isnull=False
            ).order_by('-modified').first()
            if inference_job and inference_job.cloud_blueprint_path:
                blueprint_path = inference_job.cloud_blueprint_path
                logger.warning("[NarrationTask] 使用缓存的云端蓝图路径。")
            else:
                raise ValueError("无法获取蓝图文件 (本地缺失且无云端记录)")

        # --- 创建 Job ---
        job = CreativeJob.objects.create(
            project=project,
            job_type=CreativeJob.TYPE.GENERATE_NARRATION,
            status=BaseJob.STATUS.PENDING,
            input_params=config
        )
        job.start()
        job.save()
        project.status = CreativeProject.STATUS.NARRATION_RUNNING
        project.save()

    except Exception as e:
        logger.error(f"[NarrationTask] 初始化失败: {e}", exc_info=True)
        if job: job.fail(); job.save()
        if project: project.status = CreativeProject.STATUS.FAILED; project.save()
        return

    # --- 构造 V3 API Payload ---
    try:
        # 1. 提取基础参数
        narrative_focus = config.get('narrative_focus', 'general')
        style = config.get('style', 'objective')
        perspective = config.get('perspective', 'third_person')

        # 2. 构造 Custom Prompts (字典)
        custom_prompts = {}
        if narrative_focus == 'custom':
            txt = config.get('custom_narrative_prompt', '').strip()
            if txt: custom_prompts['narrative_focus'] = txt

        if style == 'custom':
            txt = config.get('custom_style_prompt', '').strip()
            if txt: custom_prompts['style'] = txt

        # 3. 构造 Character Focus
        char_str = config.get('character_focus', '')
        char_list = [c.strip() for c in char_str.split(',') if c.strip()]
        character_focus_struct = {
            "mode": "specific" if char_list else "all",
            "characters": char_list
        }

        # 4. 构造 Control Params
        control_params = {
            "narrative_focus": narrative_focus,
            "style": style,
            "perspective": perspective,
            "target_duration_minutes": int(config.get('target_duration_minutes', 3)),
            "scope": {
                "type": "episode_range",
                "value": [
                    int(config.get('scope_start', 1)),
                    int(config.get('scope_end', 5))
                ]
            },
            "character_focus": character_focus_struct
        }

        # 第一人称必须传 perspective_character
        if perspective == 'first_person':
            p_char = config.get('perspective_character', '').strip()
            if p_char:
                control_params['perspective_character'] = p_char
            else:
                logger.warning("[NarrationTask] 第一人称视角未指定角色名，可能导致生成错误。")

        if custom_prompts:
            control_params['custom_prompts'] = custom_prompts

        # 5. 构造 Service Params
        service_params = {
            "lang": "zh",
            "model": "gemini-2.5-pro",
            "debug": True,
            "rag_top_k": int(config.get('rag_top_k', 50)),
            "speaking_rate": float(config.get('speaking_rate', 4.2)),
            "overflow_tolerance": float(config.get('overflow_tolerance', 0.0)),
            "control_params": control_params
        }

        # 6. 最终 Payload (键名 blueprint_path)
        payload = {
            "asset_name": asset_name,
            "asset_id": asset_id,
            "blueprint_path": blueprint_path,  # [Confirm: Doc Section 2]
            "service_params": service_params
        }

        logger.info(f"[NarrationTask] Payload Preview:\n{json.dumps(payload, ensure_ascii=False, indent=2)}")

        # --- 发送请求 ---
        service = CloudApiService()
        success, task_data = service.create_task("GENERATE_NARRATION", payload)

        if not success:
            msg = task_data.get('message', 'API Error')
            raise Exception(f"Create Task Failed: {msg}")

        job.cloud_task_id = task_data['id']
        job.save()

        logger.info(f"[NarrationTask] Task Created: {job.cloud_task_id}")

        # 触发轮询
        poll_cloud_task_status.delay(
            job_id=job.id,
            cloud_task_id=task_data['id'],
            on_complete_task_name='apps.workflow.creative.tasks.finalize_narration_task',
            on_complete_kwargs={}
        )

    except Exception as e:
        logger.error(f"[NarrationTask] 执行异常: {e}", exc_info=True)
        job.fail()
        job.save()
        project.status = CreativeProject.STATUS.FAILED
        project.save()

@shared_task(name="apps.workflow.creative.tasks.finalize_narration_task")
def finalize_narration_task(job_id: str, cloud_task_data: dict, **kwargs):
    """
    (V3 适配) “步骤 1：生成解说词”成功后的回调。
    """
    job = None
    try:
        job = CreativeJob.objects.get(id=job_id)
        project = job.project

        if job.status == BaseJob.STATUS.COMPLETED:
            logger.warning(f"[CreativeFinal 1] Job {job_id} 状态已是 COMPLETED，跳过重复执行。")
            return
    except CreativeJob.DoesNotExist:
        logger.error(f"[CreativeFinal 1] 找不到 CreativeJob {job_id}，任务终止。")
        return

    try:
        service = CloudApiService()

        # [V3 适配] 尝试从 result 字段直接获取 JSON (如果 API 直接返回了结果)
        # 或者从 download_url 下载
        result_data = cloud_task_data.get("result", {})
        download_url = cloud_task_data.get("download_url")

        content_bytes = None

        if download_url:
            success, content_bytes = service.download_task_result(download_url)
            if not success:
                raise Exception(f"下载解说词失败: {download_url}")
        elif result_data and "narration_script" in result_data:
            # 如果 result 直接包含了数据，将其转为 bytes
            content_bytes = json.dumps(result_data, ensure_ascii=False, indent=2).encode('utf-8')
        else:
            raise Exception("云端任务完成，但未提供 download_url 或有效的 result 数据")

        # 保存文件
        project.narration_script_file.save(f"narration_script_{job.id}.json", ContentFile(content_bytes), save=False)

        job.complete()
        job.save()
        project.status = CreativeProject.STATUS.NARRATION_COMPLETED
        project.save()

        logger.info(f"[CreativeFinal 1] 步骤 1 (解说词) 已成功 (Project: {project.id})！")

        # 自动化链式触发 (如果配置了 auto_config)
        if project.auto_config:
            logger.info(f"[AutoPilot] 检测到自动化配置，正在自动启动步骤 2 (配音)...")
            audio_config = project.auto_config.get('audio', {})
            start_audio_task.delay(project_id=str(project.id), config=audio_config)

    except Exception as e:
        logger.error(f"[CreativeFinal 1] Job {job_id} 最终化处理失败: {e}", exc_info=True)
        if job: job.fail(); job.save()
        if project: project.status = CreativeProject.STATUS.FAILED; project.save()


# ==============================================================================
# 2. 生成配音 (Dubbing V2) - 完整实现
# ==============================================================================

@shared_task(name="apps.workflow.creative.tasks.start_audio_task")
def start_audio_task(project_id: str, config: dict = None, **kwargs):
    """
    (V2 升级版)
    由 Admin 视图触发，开始“步骤 2：生成配音”。
    支持通过 config 参数传递 Dubbing V2 接口所需的模版、语速等控参。
    """
    job = None
    project = None

    # 1. 默认配置
    if not config:
        config = {
            "template_name": "chinese_paieas_replication",
            "speed": 1.0,
            "style": ""  # 默认为空，继承 Narration 风格
        }

    try:
        # 2. 获取项目并检查状态
        project = CreativeProject.objects.get(id=project_id)

        if project.status != CreativeProject.STATUS.NARRATION_COMPLETED:
            logger.warning(f"[AudioTask] 项目状态不是 NARRATION_COMPLETED，任务中止。")
            return

        # 必须有解说词文件才能配音
        if not project.narration_script_file:
            raise ValueError("找不到已完成的 narration_script_file")

        # 3. 创建 Job 记录
        job = CreativeJob.objects.create(
            project=project,
            job_type=CreativeJob.TYPE.GENERATE_AUDIO,
            status=BaseJob.STATUS.PENDING,
            input_params=config
        )
        job.start()
        job.save()

        project.status = CreativeProject.STATUS.AUDIO_RUNNING
        project.save()

    except Exception as e:
        logger.error(f"[AudioTask] 无法启动配音任务 (Project: {project_id}): {e}", exc_info=True)
        if job:
            job.fail()
            job.save()
        if project:
            project.status = CreativeProject.STATUS.FAILED
            project.save()
        return

    # 4. 上传解说词并调用 API
    try:
        service = CloudApiService()

        # 4.1 上传解说词脚本 (Narration Output -> Dubbing Input)
        # 即使上一步是从云端下载下来的，为了稳健性，我们重新上传本地这份最新的文件
        local_script_path = Path(project.narration_script_file.path)
        success, narration_path = service.upload_file(local_script_path)

        if not success:
            raise Exception(f"上传 narration_script_file 失败: {narration_path}")

        logger.info(f"[AudioTask] 解说词已上传至: {narration_path}")

        # 4.2 构造 V2 Service Params
        service_params = {
            "template_name": config.get('template_name', 'chinese_paieas_replication'),
            "speed": float(config.get('speed', 1.0))
        }

        # 可选参数：如果用户选择了特定的 style，则传递；否则留空以继承
        user_style = config.get('style')
        if user_style:
            service_params['style'] = user_style

        # 可选参数：高级指令
        user_instruct = config.get('instruct')
        if user_instruct:
            service_params['instruct'] = user_instruct

        # 4.3 构造完整 Payload
        cloud_output_path = f"outputs/dubbing/{project.id}/{job.id}_audio_meta.json"

        payload = {
            "input_narration_path": narration_path,
            #"output_path": cloud_output_path,
            "service_params": service_params
        }

        # 4.4 创建云端任务
        success, task_data = service.create_task("GENERATE_DUBBING", payload)
        if not success:
            raise Exception(task_data.get('message', 'Failed to create GENERATE_DUBBING task'))

        job.cloud_task_id = task_data['id']
        # 记录一些调试信息
        job.input_params['uploaded_narration_path'] = narration_path
        job.save()

        logger.info(f"[AudioTask] 成功提交配音任务 TaskID: {job.cloud_task_id}")

        # 5. 触发轮询
        poll_cloud_task_status.delay(
            job_id=job.id,
            cloud_task_id=task_data['id'],
            on_complete_task_name='apps.workflow.creative.tasks.finalize_audio_task',
            on_complete_kwargs={}
        )

    except Exception as e:
        logger.error(f"[AudioTask] API 调用失败 (Job: {job.id}): {e}", exc_info=True)
        job.fail()
        job.save()
        project.status = CreativeProject.STATUS.FAILED
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

        # [新增幂等性检查] 如果任务已完成，则直接安全退出
        if job.status == BaseJob.STATUS.COMPLETED:
            logger.warning(f"[CreativeFinal 2] Job {job_id} 状态已是 COMPLETED，跳过重复执行。")
            return
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

        job.complete()
        job.save()
        project.status = CreativeProject.STATUS.AUDIO_COMPLETED
        project.save()

        logger.info(f"[CreativeFinal 2] 步骤 2 (配音) 已成功 (Project: {project.id})！")

        # [新增] 自动化链式触发
        if project.auto_config:
            logger.info(f"[AutoPilot] 检测到自动化配置，正在自动启动步骤 3 (剪辑脚本)...")
            # Edit 步骤目前不需要复杂配置，或者从 auto_config 取
            # edit_config = project.auto_config.get('edit', {})
            start_edit_script_task.delay(project_id=str(project.id))

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

        # [新增幂等性检查] 如果任务已完成，则直接安全退出
        if job.status == BaseJob.STATUS.COMPLETED:
            logger.warning(f"[CreativeFinal 3] Job {job_id} 状态已是 COMPLETED，跳过重复执行。")
            return
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

        job.complete()
        job.save()

        # [修改] 更新项目状态为 EDIT_COMPLETED
        project.status = CreativeProject.STATUS.EDIT_COMPLETED
        project.save()

        logger.info(f"[CreativeFinal 3] 步骤 3 (剪辑脚本) 已成功 (Project: {project.id})！")

        # [新增] 自动化链式触发
        if project.auto_config:
            logger.info(f"[AutoPilot] 检测到自动化配置，正在自动启动步骤 4 (最终合成)...")
            start_synthesis_task.delay(project_id=str(project.id))

    except Exception as e:
        logger.error(f"[CreativeFinal 3] Job {job_id} 最终化处理失败: {e}", exc_info=True)
        if job: job.fail(); job.save()
        if project: project.status = CreativeProject.STATUS.FAILED; project.save()


@shared_task(name="apps.workflow.creative.tasks.start_synthesis_task")
def start_synthesis_task(project_id: str, **kwargs):
    """
    (新 V3 - 修复版)
    由 finalize_edit_script_task 触发，开始您的“步骤 4：视频合成”。
    这是一个本地任务，不调用云端 API。
    """
    job = None
    project = None
    try:
        project = CreativeProject.objects.get(id=project_id)

        if project.status != CreativeProject.STATUS.EDIT_COMPLETED:
            logger.warning(f"[CreativeTask 4] 项目状态不是 EDIT_COMPLETED，任务中止。")
            return

        # 1. 检查所有必需的本地输入文件 (略)

        # 2. 创建 Job
        job = CreativeJob.objects.create(
            project=project,
            job_type=CreativeJob.TYPE.SYNTHESIS,
            status=BaseJob.STATUS.PENDING
        )
        job.start()
        job.save() # <--- [关键修复] 必须保存，将状态从 PENDING 切换为 PROCESSING

        # 3. 设置项目状态
        project.status = CreativeProject.STATUS.SYNTHESIS_RUNNING
        project.save()

        # 4. 准备 SynthesisService 的输入路径 (略)
        editing_script_path = Path(project.edit_script_file.path)
        blueprint_path = Path(project.inference_project.annotation_project.final_blueprint_file.path)

        # 5. 确定本地音频和视频的基目录 (略)
        audio_job = CreativeJob.objects.filter(
            Q(project=project) & Q(job_type=CreativeJob.TYPE.GENERATE_AUDIO) & Q(status=BaseJob.STATUS.COMPLETED)
        ).order_by('-modified').first()
        if not audio_job:
            raise RuntimeError("找不到已完成的 GENERATE_AUDIO 任务来确定音频基目录。")
        local_audio_base_dir = Path(settings.MEDIA_ROOT) / get_creative_output_upload_path(project,
                                                                                           f"audio_{audio_job.id}")
        source_videos_dir = Path(settings.MEDIA_ROOT) / 'source_files' / str(project.asset.id) / 'media'

        # 6. 实例化并执行 SynthesisService
        service = SynthesisService(project_id=str(project.id))

        final_output_path = service.execute(
            editing_script_path=editing_script_path,
            blueprint_path=blueprint_path,
            local_audio_base_dir=local_audio_base_dir,
            source_videos_dir=source_videos_dir,
            asset_id=str(project.asset.id)
        )

        # 任务成功，立即调用回调函数 (不使用 Celery 链式调用，因为这是同步操作)
        finalize_synthesis_task(job_id=str(job.id), final_output_path=str(final_output_path))

    except Exception as e:
        logger.error(f"[CreativeTask 4] 无法启动/执行合成任务 (Project: {project_id}): {e}", exc_info=True)
        if job: job.fail(); job.save()
        if project: project.status = CreativeProject.STATUS.FAILED; project.save()
        return


@shared_task(name="apps.workflow.creative.tasks.finalize_synthesis_task")
def finalize_synthesis_task(job_id: str, final_output_path: str, **kwargs):
    """
    (新 V3 - FSM健壮性修复)
    “步骤 4：视频合成”成功后的回调。
    保存最终视频文件并完成项目。
    """
    job = None
    project = None
    try:
        job = CreativeJob.objects.get(id=job_id)
        project = job.project

        # [新增幂等性检查] 如果任务已完成，则直接安全退出
        if job.status == BaseJob.STATUS.COMPLETED:
            logger.warning(f"[CreativeFinal 4] Job {job_id} 状态已是 COMPLETED，跳过重复执行。")
            return

        # 1. 保存最终产出物
        output_path = Path(final_output_path)
        if not output_path.is_file():
            raise FileNotFoundError(f"最终合成文件未找到: {final_output_path}")

        with output_path.open('rb') as f:
            project.final_video_file.save(output_path.name, ContentFile(f.read()), save=False)

        # 2. 标记任务和项目为完成
        try:
            job.complete() # <-- 如果状态是 PENDING，会抛出 TransitionNotAllowed
            job.save()
        except TransitionNotAllowed as e:
            # [关键修复] 捕获 FSM 转换错误，强制更新状态
            logger.warning(f"[CreativeFinal 4] FSM 转换失败 ({job.status})。强制标记为 COMPLETED。")
            job.status = BaseJob.STATUS.COMPLETED
            job.save(update_fields=['status'])

        project.status = CreativeProject.STATUS.COMPLETED
        project.save()

        logger.info(f"[CreativeFinal 4] 步骤 4 (合成) 已成功 (Project: {project.id})！")
        logger.info(f"--- [Creative Workflow COMPLETE] (Project: {project.id}) ---")

    except Exception as e:
        logger.error(f"[CreativeFinal 4] Job {job_id} 最终化处理失败: {e}", exc_info=True)
        if job: job.fail(); job.save()
        if project: project.status = CreativeProject.STATUS.FAILED; project.save()