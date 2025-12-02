import io
import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import transaction

from apps.media_assets.models import Asset
from apps.workflow.annotation.services.label_studio import LabelStudioService
from apps.workflow.models import AnnotationJob, AnnotationProject

logger = logging.getLogger(__name__)


class ProjectPortableService:
    """
    负责项目的导出（序列化为ZIP）和导入（从ZIP反序列化）。
    """

    @staticmethod
    def export_annotation_project(project_id: str) -> bytes:
        """
        导出 AnnotationProject 及其关联 Jobs 和文件。
        返回 ZIP 文件的二进制内容。
        """
        try:
            project = AnnotationProject.objects.get(id=project_id)
        except AnnotationProject.DoesNotExist:
            raise ValueError("Project not found")

        # 1. 准备元数据 (Manifest)
        manifest = {
            "type": "AnnotationProject",
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "project": {
                "name": f"{project.name} (Imported)",  # 导入后默认改个名
                "description": project.description,
                "status": "COMPLETED",  # 强制设为完成状态，以便直接使用
                "asset_id": str(project.asset.id),  # 记录关联资产ID，导入时尝试关联
                "label_studio_project_id": project.label_studio_project_id,
                # 其他配置字段
                "source_encoding_profile_id": project.source_encoding_profile_id,
            },
            "jobs": [],
            "files_map": {},  # 记录 字段名 -> ZIP内路径 的映射
        }

        # 准备 ZIP 内存流
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # --- 辅助函数：处理文件字段 ---
            def _archive_file(model_instance, field_name, zip_path_prefix):
                file_field = getattr(model_instance, field_name)
                if file_field and file_field.name:
                    # 物理文件存在性检查
                    try:
                        # 读取文件内容
                        with file_field.open("rb") as f:
                            file_content = f.read()

                        # 生成 ZIP 内的路径
                        file_name = Path(file_field.name).name
                        zip_path = f"{zip_path_prefix}/{file_name}"

                        # 写入 ZIP
                        zf.writestr(zip_path, file_content)
                        return zip_path
                    except Exception as e:
                        logger.warning(f"Export: File {file_field.name} could not be read: {e}")
                return None

            # 2. 处理项目级文件
            project_file_fields = [
                "label_studio_export_file",
                "character_audit_report",
                "character_occurrence_report",
                "final_blueprint_file",
                "local_metrics_result_file",
            ]

            for field in project_file_fields:
                zip_path = _archive_file(project, field, "project_files")
                if zip_path:
                    manifest["files_map"][field] = zip_path

            # 3. 处理 Jobs
            jobs = AnnotationJob.objects.filter(project=project)
            for job in jobs:
                job_data = {
                    "job_type": job.job_type,
                    "status": "COMPLETED",  # 强制完成
                    "label_studio_task_id": job.label_studio_task_id,
                    "media_sequence": job.media.sequence_number if job.media else 0,  # 通过序号关联 Media
                    "files_map": {},
                }

                # 处理 Job 的产出文件 (.ass)
                job_file_fields = ["l1_output_file"]
                for field in job_file_fields:
                    # job files 放在 jobs/{sequence}/ 下
                    zip_path = _archive_file(job, field, f"job_files/{job_data['media_sequence']}")
                    if zip_path:
                        job_data["files_map"][field] = zip_path

                manifest["jobs"].append(job_data)

            # 4. 写入 Manifest
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        return zip_buffer.getvalue()

    @staticmethod
    @transaction.atomic
    def import_annotation_project(zip_bytes: bytes, target_asset: Asset):
        """
        [V5.0 修复版] 从 ZIP 导入项目，并同步恢复 Label Studio 的工程状态。
        """
        zip_buffer = io.BytesIO(zip_bytes)

        with zipfile.ZipFile(zip_buffer, "r") as zf:
            if "manifest.json" not in zf.namelist():
                raise ValueError("Invalid package: manifest.json missing")

            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            proj_data = manifest["project"]

            logger.info(
                f"Importing project '{proj_data['name']}' into Asset: {target_asset.title} (ID: {target_asset.id})"
            )

            # 1. 创建 Django 项目骨架
            new_project = AnnotationProject.objects.create(
                name=f"{proj_data['name']} (Restored)",
                description=proj_data.get("description", ""),
                asset=target_asset,
                status="COMPLETED",
                # 先留空 LS ID，稍后创建
                label_studio_project_id=None,
                source_encoding_profile_id=proj_data.get("source_encoding_profile_id"),
            )

            # 2. 恢复文件 (包括 label_studio_export_file)
            files_map = manifest.get("files_map", {})
            for field_name, zip_path in files_map.items():
                if zip_path in zf.namelist():
                    try:
                        file_content = zf.read(zip_path)
                        original_name = Path(zip_path).name
                        getattr(new_project, field_name).save(original_name, ContentFile(file_content), save=False)
                    except Exception as e:
                        logger.warning(f"Failed to restore project file {field_name}: {e}")

            new_project.save()

            # 3. [关键步骤] 在 Label Studio 中重建项目
            # 这一步会创建 LS Project，并为 Asset 下的所有 Media 创建 Tasks
            ls_service = LabelStudioService()
            success, msg, ls_proj_id, task_mapping = ls_service.create_project_for_asset(new_project)

            if success:
                logger.info(f"Label Studio Project restored: ID {ls_proj_id}")
                new_project.label_studio_project_id = ls_proj_id
                new_project.save()
            else:
                logger.error(f"Failed to restore Label Studio project: {msg}")
                # 即使失败也继续，至少保留 Django 记录

            # 4. 恢复 Jobs 并关联新的 Task ID
            media_map = {m.sequence_number: m for m in target_asset.medias.all()}
            # 建立 Media ID -> Job 的临时映射，用于后续注入注记
            media_id_to_job_map = {}

            for job_data in manifest["jobs"]:
                seq = job_data["media_sequence"]
                target_media = media_map.get(seq)

                if not target_media:
                    continue

                # 尝试从 task_mapping 中找到新创建的 Task ID
                new_task_id = task_mapping.get(target_media.id) if success else None

                new_job = AnnotationJob.objects.create(
                    project=new_project,
                    media=target_media,
                    job_type=job_data["job_type"],
                    status="COMPLETED",
                    label_studio_task_id=new_task_id,  # 关联新 ID
                )

                media_id_to_job_map[target_media.id] = new_job

                # 恢复 Job 文件
                job_files_map = job_data.get("files_map", {})
                for field_name, zip_path in job_files_map.items():
                    if zip_path in zf.namelist():
                        file_content = zf.read(zip_path)
                        original_name = Path(zip_path).name
                        getattr(new_job, field_name).save(original_name, ContentFile(file_content), save=False)
                new_job.save()

            # 5. [关键修复] 回灌历史标注数据 (Annotations)
            # 放弃文件名匹配，改用 "旧ID -> 序号 -> 新ID" 的可靠映射
            if success and new_project.label_studio_export_file:
                try:
                    logger.info("Restoring annotations from export file...")
                    new_project.label_studio_export_file.open("r")
                    export_json = json.load(new_project.label_studio_export_file)

                    # 5.1 构建映射表：旧 LS Task ID -> Media Sequence
                    # 数据来源：manifest['jobs']
                    old_task_id_to_seq = {}
                    for j in manifest["jobs"]:
                        if j.get("label_studio_task_id"):
                            old_task_id_to_seq[j["label_studio_task_id"]] = j["media_sequence"]

                    # 5.2 构建映射表：Media Sequence -> 新 LS Task ID
                    # 数据来源：target_asset (Media) + task_mapping (API返回)
                    seq_to_new_task_id = {}
                    for m in target_asset.medias.all():
                        if m.id in task_mapping:
                            seq_to_new_task_id[m.sequence_number] = task_mapping[m.id]

                    # 5.3 遍历导出文件，通过“序号”这座桥梁进行匹配
                    restore_count = 0
                    for item in export_json:
                        # item['id'] 是旧环境的 LS Task ID
                        old_id = item.get("id")

                        # 1. 找序号
                        sequence = old_task_id_to_seq.get(old_id)
                        if sequence is None:
                            # 尝试兼容性回退：有些版本的 LS 导出可能不包含 ID，或者 ID 变了
                            # 此时才不得已使用 filenames 匹配 (作为兜底，虽然不一定准)
                            logger.warning(f"Annotation Record {old_id}: No matching sequence in manifest. Skipping.")
                            continue

                        # 2. 找新任务 ID
                        new_task_id = seq_to_new_task_id.get(sequence)
                        if not new_task_id:
                            logger.warning(
                                f"Annotation Record {old_id} (Seq {sequence}): No new task created. Skipping."
                            )
                            continue

                        # 3. 注入数据
                        annotations = item.get("annotations", [])
                        if not annotations:
                            # 有些导出可能是 'predictions' 或者根级别就是 result
                            # 这里假设是标准的 LS JSON 格式
                            continue

                        for annotation in annotations:
                            if ls_service.import_annotation_to_task(new_task_id, annotation):
                                restore_count += 1

                    logger.info(f"Successfully restored {restore_count} annotation records.")

                except Exception as e:
                    logger.warning(f"Failed to restore annotations content: {e}", exc_info=True)

            return new_project
