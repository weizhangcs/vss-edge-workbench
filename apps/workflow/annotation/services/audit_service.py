# 文件路径: apps/workflow/annotation/services/audit_service.py

import csv
import io
import logging
from collections import defaultdict
from datetime import datetime

from django.core.files.base import ContentFile

from ...common.baseJob import BaseJob
from ...models import AnnotationJob, AnnotationProject

# 初始化 logger
logger = logging.getLogger(__name__)


class L1AuditService:
    """
    (已重构)
    L1 审计服务
    一次性生成“摘要报告”(Code 1) 和“详情日志”(Code 1 - find_occurrences)。
    """

    def __init__(self, project_id: str):
        try:
            self.project = AnnotationProject.objects.get(id=project_id)
            self.project_id = project_id
            logger.info(f"L1AuditService initialized for project: {self.project.name}")
        except AnnotationProject.DoesNotExist:
            logger.error(f"L1AuditService: Project {project_id} not found.")
            raise

    def _parse_duration(self, start_str: str, end_str: str) -> float:
        """
        健壮的 .ass 时间戳解析器。
        """
        try:
            start = datetime.strptime(start_str.strip(), "%H:%M:%S.%f")
            end = datetime.strptime(end_str.strip(), "%H:%M:%S.%f")
            return (end - start).total_seconds()
        except ValueError:
            try:
                start = datetime.strptime(start_str.strip(), "%H:%M:%S")
                end = datetime.strptime(end_str.strip(), "%H:%M:%S")
                return (end - start).total_seconds()
            except Exception:
                return 0.0

    def _generate_summary_csv(self, stats: defaultdict, total_dialogues: int) -> str:
        """
        (来自 Code 1 - list_character_names)
        生成“摘要” CSV 字符串。
        """
        report_rows = []
        for name, data in stats.items():
            count = data.get("count", 0)
            percentage = f"{(count / total_dialogues) * 100:.2f}%" if total_dialogues > 0 else "0.00%"  # noqa: E231
            report_rows.append(
                {
                    "character_name": name,
                    "dialogue_count": count,
                    "percentage": percentage,
                    "total_duration_seconds": round(data.get("duration", 0.0), 2),
                    "total_length_chars": data.get("length", 0),
                }
            )
        report_rows.sort(key=lambda x: x["dialogue_count"], reverse=True)
        header = ["character_name", "dialogue_count", "percentage", "total_duration_seconds", "total_length_chars"]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=header)
        writer.writeheader()
        writer.writerows(report_rows)  # (已修复: 移除了 'rows=')
        return output.getvalue()

    def _generate_occurrence_csv(self, occurrences: list) -> str:
        """
        (来自 Code 1 - find_character_occurrences)
        生成“详情” CSV 字符串。
        """
        header = ["file_name", "line_number", "found_in", "line_content"]
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=header)
        writer.writeheader()
        writer.writerows(occurrences)  # (已修复: 移除了 'rows=')
        return output.getvalue()

    def generate_audit_report(self):
        """
        (主方法 - 已重构)
        在一次循环中同时执行“摘要”和“详情”分析。
        """
        logger.info(f"开始为项目 {self.project.name} (ID: {self.project_id}) 生成 L1 角色审计...")

        l1_jobs = AnnotationJob.objects.filter(
            project=self.project,
            job_type=AnnotationJob.TYPE.L1_SUBEDITING,
            status__in=[BaseJob.STATUS.COMPLETED, BaseJob.STATUS.REVISING],  # (已修复: 包含 REVISING)
            l1_output_file__isnull=False,
        ).exclude(l1_output_file="")

        if not l1_jobs:
            logger.warning(f"项目 {self.project.name} 中没有找到已完成或修订中的 L1 .ass 文件。")
            return

        # --- 初始化两个报告的数据容器 ---
        # 1. 摘要报告 (来自 Code 1 - list_names)
        stats = defaultdict(lambda: {"count": 0, "length": 0, "duration": 0.0})
        total_dialogues = 0
        functional_names = {"SCENE", "HIGHLIGHT", "CAPTION", "场景", "高光", "提词"}

        # 2. 详情报告 (来自 Code 1 - find_occurrences)
        occurrences = []

        # --- 一次遍历，同时处理两个报告 ---
        for job in l1_jobs:
            try:
                if not job.l1_output_file:
                    continue

                job.l1_output_file.open("rb")
                content_bytes = job.l1_output_file.read()
                content = content_bytes.decode("utf-8-sig")
                job.l1_output_file.close()

                in_events = False

                # (来自 Code 1 - find_occurrences) enumerate() 从 1 开始计数
                for i, line_content in enumerate(content.splitlines(), 1):
                    line_strip = line_content.strip()

                    if line_strip.lower() == "[events]":
                        in_events = True
                        continue
                    if not in_events or not line_strip.lower().startswith("dialogue:"):
                        continue

                    try:
                        parts = line_strip.split(",", 9)
                        if len(parts) < 10:
                            continue

                        start_str, end_str, actor_raw, text = parts[1], parts[2], parts[4], parts[9]
                        actor = actor_raw.split(",")[0].strip()

                        if not actor or actor.upper() in functional_names:
                            continue  # 忽略功能性角色

                        # --- 1. 填充“摘要”数据 ---
                        stats[actor]["count"] += 1
                        stats[actor]["length"] += len(text)
                        stats[actor]["duration"] += self._parse_duration(start_str, end_str)
                        total_dialogues += 1

                        # --- 2. 填充“详情”数据 (来自 Code 1 - find_occurrences) ---
                        # 我们将记录所有*非功能性*角色的出现
                        # "search_in: 'actor'" 逻辑
                        occurrences.append(
                            {
                                "file_name": job.l1_output_file.name.split("/")[-1],
                                "line_number": i,
                                "found_in": actor,  # (优化: 直接使用 actor 名字)
                                "line_content": text,  # (优化: 只保存文本)
                            }
                        )

                    except IndexError:
                        continue

            except Exception as e:
                logger.error(f"处理文件 {job.l1_output_file.name} 时出错: {e}", exc_info=True)
                continue

        if not stats:
            logger.warning(f"项目 {self.project.name} 的 .ass 文件中未发现任何有效角色。")
            return

        # --- 生成并保存两个 CSV ---

        # 1. 保存“摘要”报告
        summary_csv = self._generate_summary_csv(stats, total_dialogues)
        summary_filename = f"character_SUMMARY_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.project.character_audit_report.save(
            summary_filename, ContentFile(summary_csv.encode("utf-8-sig")), save=False  # (我们稍后一起保存)
        )
        logger.info("“摘要”报告已生成。")

        # 2. 保存“详情”报告
        occurrence_csv = self._generate_occurrence_csv(occurrences)
        occurrence_filename = f"character_OCCURRENCES_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.project.character_occurrence_report.save(
            occurrence_filename, ContentFile(occurrence_csv.encode("utf-8-sig")), save=False
        )
        logger.info("“详情”报告已生成。")

        # 3. 一次性保存对 project 实例的所有修改
        self.project.save()

        logger.info(f"所有 L1 审计报告已成功为项目 {self.project.name} 生成并保存。")
