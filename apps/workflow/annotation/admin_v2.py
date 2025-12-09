import json
import logging
import uuid

from django.contrib import admin
from django.core.files.base import ContentFile
from django.http import HttpResponseNotFound, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.views.decorators.csrf import csrf_protect
from unfold.admin import ModelAdmin
from unfold.decorators import display

from apps.workflow.annotation.jobs import AnnotationJob

# 引用模型
from apps.workflow.annotation.projects import AnnotationProjectV2
from apps.workflow.annotation.services.srt_parser import parse_srt_content
from visify_ssw import settings

# 引用 Schema
from .schemas import DataOrigin, DialogueItem, MediaAnnotation

# 引用刚才创建的 SRT 解析工具

logger = logging.getLogger(__name__)


@admin.register(AnnotationProjectV2)
class AnnotationProjectAdminV2(ModelAdmin):
    """
    V2 Admin: 标注工作台集成测试环境
    """

    list_display = ("name", "status", "created", "open_workbench_link")
    search_fields = ("name",)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "workbench/<int:job_id>/",
                self.admin_site.admin_view(self.workbench_view),
                name="workflow_annotationprojectv2_workbench",
            ),
        ]
        return custom_urls + urls

    @display(description="操作", label="进入工作台")
    def open_workbench_link(self, obj):
        # 查找该项目下的第一个 L1 字幕标注任务
        job = obj.jobs.filter(job_type=AnnotationJob.TYPE.L1_SUBEDITING).first()

        if job:
            url = reverse("admin:workflow_annotationprojectv2_workbench", args=[job.id])
            return format_html('<a href="{}" class="button" target="_blank">打开工作台 (Job #{})</a>', url, job.id)
        else:
            return "无 L1 任务"

    @method_decorator(csrf_protect)
    def workbench_view(self, request, job_id):
        """
        标注工作台核心视图 (V2)
        负责数据的加载 (Load) 与 保存 (Save)
        """
        # 1. 获取任务与上下文对象
        job = get_object_or_404(AnnotationJob, pk=job_id)
        media = job.media
        project = job.project

        if not media:
            return HttpResponseNotFound("该任务未关联 Media 文件")

        # =========================================================
        # 处理保存请求 (POST)
        # =========================================================
        if request.method == "POST":
            try:
                # A. 获取并解析数据
                data = json.loads(request.body)

                # B. Pydantic 强校验 (验证前端数据结构是否符合 Schema)
                annotation = MediaAnnotation(**data)

                # C. 保存到 l1_output_file
                # 将 Pydantic 对象转回 JSON 字符串
                json_content = annotation.model_dump_json(indent=2)

                # 构造文件名 (保持与 job id 关联，方便追溯)
                file_name = f"annotation_output_job_{job.id}.json"

                # 使用 ContentFile 包装字符串，保存到 FileField
                # save=True 会立即触发数据库更新
                job.l1_output_file.save(file_name, ContentFile(json_content.encode("utf-8")), save=True)

                print("====== [V2 Admin] Data Saved to DB ======")
                print(f"Job ID: {job.id}")
                print(f"File Path: {job.l1_output_file.name}")

                return JsonResponse({"status": "success", "message": "保存成功"})
            except Exception as e:
                # 捕获所有异常（JSON解析错误、校验错误、IO错误等）
                import traceback

                traceback.print_exc()
                logger.error(f"Save Annotation Failed: {e}")
                return JsonResponse({"status": "error", "message": str(e)}, status=400)

        # =========================================================
        # 处理加载请求 (GET)
        # =========================================================

        annotation_data = None

        # 准备当前最新的媒体资源地址 (无论是否加载旧存档，这些都应是最新的)
        encoding_profile = project.source_encoding_profile if project else None

        # 1. 获取最佳播放地址 (绝对路径)
        current_video_url = media.get_best_playback_url(encoding_profile)
        # 双重保险：如果返回的是相对路径，尝试补全 (依赖 settings 配置)
        if current_video_url and not current_video_url.startswith(("http://", "https://")):
            base = getattr(settings, "LOCAL_MEDIA_URL_BASE", "").rstrip("/")
            path = current_video_url.lstrip("/")
            current_video_url = f"{base}/{path}"

        # 2. 获取波形数据地址
        current_waveform_url = media.waveform_data.url if media.waveform_data else None

        # ---------------------------------------------------------
        # 场景 A: 尝试加载已有进度 (Load from File)
        # ---------------------------------------------------------
        if job.l1_output_file:
            try:
                # 打开并读取文件内容
                job.l1_output_file.open("r")
                file_content = job.l1_output_file.read()
                # 兼容 bytes 和 str
                if isinstance(file_content, bytes):
                    file_content = file_content.decode("utf-8")

                # 反序列化为对象
                json_data = json.loads(file_content)
                annotation_data = MediaAnnotation(**json_data)

                print(f"====== [V2 Admin] Loaded from File: {job.l1_output_file.name} ======")

                # [关键逻辑] 动态更新资源路径
                # 即使加载了旧 JSON，也要用最新的视频/波形地址覆盖，防止 URL 签名过期或文件位置变更
                if current_video_url:
                    annotation_data.source_path = current_video_url

                if current_waveform_url:
                    annotation_data.waveform_url = current_waveform_url

            except Exception as e:
                logger.warning(f"Failed to load existing annotation file for Job {job.id}: {e}")
                # 如果读取失败（文件损坏或丢失），annotation_data 保持为 None，将回退到初始化逻辑
                annotation_data = None

        # ---------------------------------------------------------
        # 场景 B: 初始化新数据 (Initialize New)
        # ---------------------------------------------------------
        if not annotation_data:
            print("====== [V2 Admin] Generating Initial Data from Media Source ======")

            # 解析源字幕 (如果有)
            initial_dialogues = []
            if media.source_subtitle:
                try:
                    media.source_subtitle.open("r")
                    srt_content = media.source_subtitle.read()
                    if isinstance(srt_content, bytes):
                        srt_content = srt_content.decode("utf-8")

                    # 使用工具函数解析 SRT
                    parsed_list = parse_srt_content(srt_content)

                    # 转换为 Schema 对象
                    for item in parsed_list:
                        initial_dialogues.append(
                            DialogueItem(
                                id=str(uuid.uuid4()),
                                start=item["start"],
                                end=item["end"],
                                text=item["text"],
                                speaker=item["speaker"],
                                # [重要] 保留原文到 original_text 字段
                                original_text=item.get("original_text", item["text"]),
                                origin=DataOrigin.HUMAN,  # 源字幕默认视为人工数据
                            )
                        )
                    print(f"Parsed {len(initial_dialogues)} dialogues from source subtitle.")
                except Exception as e:
                    logger.error(f"Failed to parse source subtitle for Media {media.id}: {e}")

            # 构造全新的 Annotation 对象
            annotation_data = MediaAnnotation(
                media_id=str(media.id),
                file_name=media.title,
                # 使用刚才获取的最新视频地址
                source_path=current_video_url if current_video_url else "",
                # 使用刚才获取的最新波形地址
                waveform_url=current_waveform_url,
                duration=0.0,  # 前端播放器加载后会更新准确时长
                # 初始化轨道数据
                scenes=[],
                dialogues=initial_dialogues,  # 填入解析后的字幕
                captions=[],
                highlights=[],
            )

        # ---------------------------------------------------------
        # 4. 序列化并渲染
        # ---------------------------------------------------------
        # 将 Pydantic 对象转为 JSON 字符串注入前端
        server_data_json = annotation_data.model_dump_json()

        context = {
            **self.admin_site.each_context(request),
            "title": f"标注工作台 - {media.title}",
            "server_data_json": server_data_json,
            # 将当前对象信息传给模板 (如果需要显示返回按钮等)
            "original_object": job,
        }

        return render(request, "admin/workflow/project/annotation/workbench.html", context)
