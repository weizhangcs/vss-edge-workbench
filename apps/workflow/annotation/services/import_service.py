# apps/workflow/annotation/services/import_service.py

import json
import logging

from django.db import transaction

from apps.media_assets.models import Asset

from ..jobs import AnnotationJob
from ..projects import AnnotationProject
from ..services.annotation_service import AnnotationService

logger = logging.getLogger(__name__)


class ProjectImportService:
    """
    负责将外部导出的工程文件 (ProjectAnnotation JSON) 导入并关联到新的 Asset。
    核心职责：
    1. 校验资产匹配度 (Media 数量/顺序)。
    2. ID 映射 (Replace Old IDs with New Asset IDs)。
    3. 事务性创建 Project 和 Jobs。
    """

    @classmethod
    @transaction.atomic
    def execute_import(cls, json_file, target_asset_id, project_name_override=None):
        try:
            # 1. 加载数据
            data = json.load(json_file)
            target_asset = Asset.objects.get(id=target_asset_id)

            # 2. 基础校验
            imported_annotations = data.get("annotations", {})
            # 按照 sequence_number 排序 Asset 中的 Media
            target_medias = target_asset.medias.order_by("sequence_number")

            if not target_medias.exists():
                raise ValueError(f"目标资产 '{target_asset.title}' 下没有媒体文件，无法导入。")

            # 简单的数量校验 (也可以做更复杂的时长校验)
            # 注意：导入的数据可能少于 Asset 的媒体数（部分导入），但不应多于。
            # 这里我们假设是一一对应的全量恢复
            if len(imported_annotations) != target_medias.count():
                logger.warning(
                    f"导入警告: 导入的标注条数 ({len(imported_annotations)}) 与 资产媒体数 ({target_medias.count()}) 不一致。系统将尝试按顺序匹配。"
                )

            # 3. 创建新项目
            new_project = AnnotationProject.objects.create(
                name=project_name_override or f"{data.get('project_name', 'Imported')} (恢复)",
                asset=target_asset,
                status="PROCESSING",  # 导入后默认为进行中
                description=f"从文件导入。原项目ID: {data.get('project_id')}",
            )

            # 4. 核心：移花接木 (Mapping & Injection)
            # 将 imported_annotations (Dict) 转为 List，按原有的 media 顺序处理
            # 假设 export JSON 中 annotations 是以 media_id 为 key 的字典
            # 我们无法依赖字典 key 的顺序，必须依赖数据内部的某种顺序，或者假定 Asset 的 sequence 顺序与导出时的遍历顺序一致。
            # *最佳策略*: 现在的 Export 是按 sequence 遍历导出的，但 JSON key 是无序的。
            # *修正*: 我们应该信任 Export 中的列表顺序，或者让用户确认。
            # 这里简化处理：将 annotations values 转为列表，假定它是按顺序导出的 (export_project_annotation 代码中是按 sequence 遍历的)

            sorted_import_items = list(imported_annotations.values())

            # 按顺序一一匹配
            for i, media in enumerate(target_medias):
                if i >= len(sorted_import_items):
                    break  # 媒体比标注多，剩下的不做

                old_anno_data = sorted_import_items[i]

                # --- [关键步骤] 数据清洗与 ID 替换 ---
                # 1. 替换 media_id
                old_anno_data["media_id"] = str(media.id)
                # 2. 替换 file_name
                old_anno_data["file_name"] = media.title
                # 3. 替换 source_path (指向新 Asset 的物理文件)
                old_anno_data["source_path"] = media.source_video.name if media.source_video else ""
                # 4. 替换 duration (以新 Asset 为准，防止飘移)
                old_anno_data["duration"] = media.duration or old_anno_data.get("duration", 0)

                # 创建 Job
                job = AnnotationJob.objects.create(
                    project=new_project, media=media, status="COMPLETED"  # 导入的数据通常是完成态，或者 PROCESSING
                )

                # 调用 Service 保存 (会自动触发 A/B 备份和 rotate_and_save)
                # 注意：我们要把处理过的 old_anno_data 重新转回 MediaAnnotation 对象再存，或者直接存 dict
                # AnnotationService.save_annotation 接受 dict
                AnnotationService.save_annotation(job, old_anno_data)

                logger.info(f"成功恢复 Job {job.id} (Media: {media.title})")

            # 5. 收尾：生成新项目的 Audit 和 Blueprint
            new_project.run_audit()

            return new_project

        except Exception as e:
            # 事务会自动回滚
            logger.error(f"导入项目失败: {e}", exc_info=True)
            raise ValueError(f"导入过程中发生错误，已回滚: {str(e)}")
