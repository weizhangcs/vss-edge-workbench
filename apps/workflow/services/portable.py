import io
import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import transaction

from apps.media_assets.models import Asset
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
        从 ZIP 导入项目并挂载到指定的 Asset。
        :param zip_bytes: ZIP 文件二进制流
        :param target_asset: 用户明确指定的 Asset 对象 (覆盖 manifest 中的记录)
        """
        zip_buffer = io.BytesIO(zip_bytes)

        with zipfile.ZipFile(zip_buffer, "r") as zf:
            if "manifest.json" not in zf.namelist():
                raise ValueError("Invalid package: manifest.json missing")

            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            proj_data = manifest["project"]

            # [核心修改] 不再从 manifest 查找 Asset，直接使用传入的 target_asset
            # (旧逻辑已删除：try Asset.objects.get(id=proj_data.get("asset_id"))...)

            logger.info(
                f"Importing project '{proj_data['name']}' into Asset: {target_asset.title} (ID: {target_asset.id})"
            )

            # 1. 创建项目骨架
            new_project = AnnotationProject.objects.create(
                name=f"{proj_data['name']} (Restored)",
                description=proj_data.get("description", ""),
                asset=target_asset,  # 使用用户选择的 Asset
                status="COMPLETED",  # 直接完成，跳过流程状态
                label_studio_project_id=proj_data.get("label_studio_project_id"),
                source_encoding_profile_id=proj_data.get("source_encoding_profile_id"),
            )

            # 2. 恢复项目级文件 (Blueprints, Reports)
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

            # 3. 恢复 Jobs (标注子任务)
            # 建立目标 Asset 下的 Media 映射表: sequence_number -> media_object
            media_map = {m.sequence_number: m for m in target_asset.medias.all()}

            restored_jobs_count = 0
            for job_data in manifest["jobs"]:
                seq = job_data["media_sequence"]
                target_media = media_map.get(seq)

                # [宽松容错] 如果目标 Asset 下找不到对应的 ep01/ep02，则跳过该 Job，不报错
                if not target_media:
                    logger.warning(f"Import Skipped: Media sequence {seq} not in target Asset '{target_asset.title}'.")
                    continue

                new_job = AnnotationJob.objects.create(
                    project=new_project,
                    media=target_media,
                    job_type=job_data["job_type"],
                    status="COMPLETED",
                    label_studio_task_id=job_data.get("label_studio_task_id"),
                )

                # 恢复 Job 文件 (.ass)
                job_files_map = job_data.get("files_map", {})
                for field_name, zip_path in job_files_map.items():
                    if zip_path in zf.namelist():
                        file_content = zf.read(zip_path)
                        original_name = Path(zip_path).name
                        getattr(new_job, field_name).save(original_name, ContentFile(file_content), save=False)

                new_job.save()
                restored_jobs_count += 1

            logger.info(f"Project imported successfully with {restored_jobs_count} jobs restored.")
            return new_project
