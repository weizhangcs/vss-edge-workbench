import io
import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path

from celery import chain  # [新增] 用于构建任务链
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
                "name": f"{project.name} (Imported)",
                "description": project.description,
                "status": "COMPLETED",
                "asset_id": str(project.asset.id),
                "label_studio_project_id": project.label_studio_project_id,
                "source_encoding_profile_id": project.source_encoding_profile_id,
            },
            "jobs": [],
            "files_map": {},
        }

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:

            def _archive_file(model_instance, field_name, zip_path_prefix):
                file_field = getattr(model_instance, field_name)
                if file_field and file_field.name:
                    try:
                        with file_field.open("rb") as f:
                            file_content = f.read()
                        file_name = Path(file_field.name).name
                        zip_path = f"{zip_path_prefix}/{file_name}"
                        zf.writestr(zip_path, file_content)
                        return zip_path
                    except Exception as e:
                        logger.warning(f"Export: File {file_field.name} could not be read: {e}")
                return None

            # 2. 处理项目级文件
            # 注意：虽然我们在导入时会重新生成蓝图和矩阵，但导出时依然保留它们作为参考快照
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
                    "status": "COMPLETED",
                    "label_studio_task_id": job.label_studio_task_id,
                    "media_sequence": job.media.sequence_number if job.media else 0,
                    "files_map": {},
                }
                job_file_fields = ["l1_output_file"]
                for field in job_file_fields:
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
        [V5.2 重构版]
        1. 从 ZIP 恢复项目骨架和源文件。
        2. 重建 Label Studio 项目并回灌标注数据。
        3. [核心变更] 丢弃 ZIP 中的衍生数据，触发 Celery Chain 全链路重新生成。
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
                label_studio_project_id=None,
                source_encoding_profile_id=proj_data.get("source_encoding_profile_id"),
            )

            # [关键修改] 定义衍生字段列表，导入时强制跳过，防止旧数据污染
            DERIVED_FIELDS = ["final_blueprint_file", "local_metrics_result_file"]

            # 2. 恢复文件
            files_map = manifest.get("files_map", {})
            for field_name, zip_path in files_map.items():
                # 如果是衍生数据，直接跳过，保持字段为 None/Empty
                if field_name in DERIVED_FIELDS:
                    logger.info(f"Skipping derived file: {field_name} (will be re-generated)")
                    continue

                if zip_path in zf.namelist():
                    try:
                        file_content = zf.read(zip_path)
                        original_name = Path(zip_path).name
                        getattr(new_project, field_name).save(original_name, ContentFile(file_content), save=False)
                    except Exception as e:
                        logger.warning(f"Failed to restore project file {field_name}: {e}")

            new_project.save()

            # 3. 在 Label Studio 中重建项目
            ls_service = LabelStudioService()
            success, msg, ls_proj_id, task_mapping = ls_service.create_project_for_asset(new_project)

            if success:
                new_project.label_studio_project_id = ls_proj_id
                new_project.save()
            else:
                logger.error(f"Failed to restore Label Studio project: {msg}")

            # 4. 恢复 Jobs 并关联新的 Task ID
            media_map = {m.sequence_number: m for m in target_asset.medias.all()}

            for job_data in manifest["jobs"]:
                seq = job_data["media_sequence"]
                target_media = media_map.get(seq)

                if not target_media:
                    continue

                new_task_id = task_mapping.get(target_media.id) if success else None

                new_job = AnnotationJob.objects.create(
                    project=new_project,
                    media=target_media,
                    job_type=job_data["job_type"],
                    status="COMPLETED",
                    label_studio_task_id=new_task_id,
                )

                job_files_map = job_data.get("files_map", {})
                for field_name, zip_path in job_files_map.items():
                    if zip_path in zf.namelist():
                        file_content = zf.read(zip_path)
                        original_name = Path(zip_path).name
                        getattr(new_job, field_name).save(original_name, ContentFile(file_content), save=False)
                new_job.save()

            # 5. 回灌历史标注数据 (Annotations)
            has_annotations = False
            if success and new_project.label_studio_export_file:
                try:
                    logger.info("Restoring annotations to Label Studio tasks...")
                    new_project.label_studio_export_file.open("r")
                    export_json = json.load(new_project.label_studio_export_file)

                    # 构建映射表：旧 LS Task ID -> Media Sequence
                    old_task_id_to_seq = {}
                    for j in manifest["jobs"]:
                        if j.get("label_studio_task_id"):
                            old_task_id_to_seq[j["label_studio_task_id"]] = j["media_sequence"]

                    # 构建映射表：Media Sequence -> 新 LS Task ID
                    seq_to_new_task_id = {}
                    for m in target_asset.medias.all():
                        if m.id in task_mapping:
                            seq_to_new_task_id[m.sequence_number] = task_mapping[m.id]

                    restore_count = 0
                    for item in export_json:
                        old_id = item.get("id")
                        sequence = old_task_id_to_seq.get(old_id)
                        if sequence is None:
                            continue

                        new_task_id = seq_to_new_task_id.get(sequence)
                        if not new_task_id:
                            continue

                        annotations = item.get("annotations", [])
                        for annotation in annotations:
                            if ls_service.import_annotation_to_task(new_task_id, annotation):
                                restore_count += 1
                                has_annotations = True

                    logger.info(f"Successfully restored {restore_count} annotation records.")

                except Exception as e:
                    logger.warning(f"Failed to restore annotations content: {e}", exc_info=True)

            # 6. [核心修正] 触发全链路重建任务 (Chain)
            # 只有当标注数据成功回灌后，后续的生成才有意义
            if success and has_annotations:
                # 局部引入避免循环依赖
                from apps.workflow.annotation.tasks import (
                    calculate_local_metrics_task,
                    export_l2_output_task,
                    generate_narrative_blueprint_task,
                )

                project_id_str = str(new_project.id)

                # 定义任务链：
                # 1. Export L2: 从 LS 拉取含有新 TaskID 的 JSON，覆盖旧文件
                # 2. Blueprint: 基于新 JSON 生成蓝图
                # 3. Metrics: 基于新蓝图计算矩阵
                rehydration_chain = chain(
                    export_l2_output_task.s(project_id=project_id_str),
                    generate_narrative_blueprint_task.s(project_id=project_id_str),
                    calculate_local_metrics_task.s(project_id=project_id_str),
                )

                # 在事务提交后执行，确保 Celery Worker 能读到新创建的 Project
                transaction.on_commit(lambda: rehydration_chain.apply_async())
                logger.info("Triggered rehydration chain: Export L2 -> Blueprint -> Metrics")

            return new_project
