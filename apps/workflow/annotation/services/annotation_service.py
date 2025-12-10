# apps/workflow/annotation/services/annotation_service.py

import json
import logging
import uuid
from datetime import datetime

from django.core.files.base import ContentFile

# 引入 Schema 定义
from ..schemas import DataOrigin, DialogueContent, DialogueItem, ItemContext, MediaAnnotation

# [核心集成] 使用您提供的 utils.py 中的解析函数
from .srt_parser import parse_srt_content

logger = logging.getLogger(__name__)


class AnnotationService:
    @staticmethod
    def load_annotation(job) -> MediaAnnotation:
        """
        [数据加载与冷启动注入]
        逻辑：
        1. 尝试加载已存在的 annotation_file (热数据)。
        2. 如果不存在，执行冷启动 (Cold Start)：
           - 初始化 MediaAnnotation
           - 注入 SRT 字幕 (如果 Media 有 source_subtitle)
           - 注入波形图 URL (如果 Media 有 waveform_data)
        """
        # --- A. 热数据加载 ---
        if job.annotation_file:
            try:
                job.annotation_file.open("r")
                content = job.annotation_file.read()
                job.annotation_file.close()

                # 兼容二进制读取
                if isinstance(content, bytes):
                    content = content.decode("utf-8")

                data = json.loads(content)
                return MediaAnnotation(**data)
            except Exception as e:
                logger.error(f"Job {job.id}: Failed to load existing annotation. Error: {e}")
                # 文件损坏或读取失败时，降级进入冷启动流程

        # --- B. 冷启动 (Cold Start) ---
        logger.info(f"Job {job.id}: Starting cold start initialization...")

        # 1. 确定视频源路径 (作为基础元数据引用)
        source_path = ""
        if job.media.source_video:
            source_path = job.media.source_video.url

        # 2. 初始化骨架
        media_anno = MediaAnnotation(
            media_id=str(job.media.id),
            file_name=job.media.title,
            source_path=source_path,
            duration=0.0,  # TODO: 理论上应该在media asset或transcoding的时候自动获取时长，现在还没有写这个代码，所以这里先赋值 0 跳过schemas的校验
            # [注入] 波形图数据 (FileField 自动生成的 URL)
            waveform_url=job.media.waveform_data.url if job.media.waveform_data else None,
        )

        # 3. [核心] SRT 字幕注入
        subtitle_file = job.media.source_subtitle

        if subtitle_file:
            try:
                logger.info(f"Job {job.id}: Injecting subtitles from {subtitle_file.name}")
                with subtitle_file.open("r") as f:
                    content = f.read()
                    if isinstance(content, bytes):
                        content = content.decode("utf-8")

                # 调用 utils.py 解析
                # 返回格式: [{'start': 1.0, 'end': 2.0, 'text': '...', 'speaker': '...', 'original_text': '...'}]
                raw_dialogues = parse_srt_content(content)

                # 转换为 Schema 对象
                validated_dialogues = []
                for d in raw_dialogues:
                    # 构造内容实体
                    content_obj = DialogueContent(
                        text=d.get("text", ""),
                        speaker=d.get("speaker", "Unknown"),
                        original_text=d.get("original_text"),
                    )

                    # 构造上下文 (标记为 AI_ASR，状态为未校验)
                    context_obj = ItemContext(
                        id=str(uuid.uuid4()), origin=DataOrigin.AI_ASR, is_verified=False  # 假设源文件来自 AI 识别或外部导入
                    )

                    # 构造轨道条目
                    item = DialogueItem(start=d["start"], end=d["end"], content=content_obj, context=context_obj)
                    validated_dialogues.append(item)

                media_anno.dialogues = validated_dialogues
                logger.info(f"Job {job.id}: Successfully injected {len(validated_dialogues)} dialogue items.")

            except Exception as e:
                logger.error(f"Job {job.id}: Failed to inject SRT. Error: {e}", exc_info=True)
        else:
            logger.info(f"Job {job.id}: No source subtitle found. Skipping injection.")

        return media_anno

    @staticmethod
    def save_annotation(job, payload: dict) -> MediaAnnotation:
        """
        [数据保存]
        前端提交 JSON -> Pydantic 校验 -> 覆盖保存
        """
        # 1. 校验
        try:
            annotation = MediaAnnotation(**payload)
        except Exception as e:
            logger.error(f"Validation Error: {e}")
            raise ValueError(f"Invalid Schema: {e}")

        # 2. 更新时间戳
        annotation.updated_at = datetime.now()

        # 3. 序列化
        json_content = annotation.model_dump_json(indent=2, exclude_none=True)

        # 4. 落盘
        # 使用固定文件名，确保每次保存覆盖同一个逻辑文件，或者您可以加上时间戳做版本控制
        file_name = f"annotation_{job.id}.json"

        # save=True 会触发 update 数据库字段
        job.annotation_file.save(file_name, ContentFile(json_content.encode("utf-8")), save=True)

        return annotation
