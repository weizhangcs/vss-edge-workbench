# apps/workflow/creative/services/orchestrator.py

import json  # [新增引用]
import logging
import random

from django.db import transaction

from ..projects import CreativeBatch, CreativeProject
from ..tasks import start_narration_task
from .payloads import PayloadBuilder

logger = logging.getLogger(__name__)


class CreativeOrchestrator:
    # ... (__init__, _resolve_value, _flatten_strategy 保持不变) ...
    def __init__(self, inference_project_id: str):
        self.inference_project_id = inference_project_id

    def _resolve_value(self, field_config: dict):
        """
        [核心逻辑] 解析单个配置项的值。
        将 {type: 'range', min: 1, max: 5} 解析为具体的数值 (如 3)。
        """
        if not isinstance(field_config, dict):
            return field_config

        c_type = field_config.get("type")

        # 1. 固定值 / 文本输入 / 单选
        if c_type in ["single", "text", "fixed", "custom"]:
            return field_config.get("value")

        # 2. 枚举多选 (Enum) -> 随机选一个
        if c_type == "enum":
            val_str = field_config.get("values_str", "")
            val_str = val_str.replace("，", ",")  # 兼容中文逗号
            options = [x.strip() for x in val_str.split(",") if x.strip()]
            if not options:
                return None
            return random.choice(options)

        # 3. 范围 (Range) -> 随机取值
        if c_type == "range":
            try:
                mn = float(field_config.get("min", 0))
                mx = float(field_config.get("max", 0))
                step = float(field_config.get("step", 1))
                if step <= 0:
                    step = 1

                # 生成步进序列
                options = []
                curr = mn
                while curr <= mx + 0.00001:
                    options.append(curr)
                    curr += step

                val = random.choice(options) if options else mn

                # 如果是整数步进，转为int，否则保留2位小数
                if step == int(step) and mn == int(mn):
                    return int(val)
                return round(val, 2)
            except Exception as e:
                logger.warning(f"Error resolving range: {e}")
                return 0

        # 容错：如果有 value 字段直接返回
        return field_config.get("value")

    def _flatten_strategy(self, strategy_tree: dict) -> dict:
        """
        将前端的策略树压扁为简单的 Key-Value 配置。
        """
        flat_config = {}

        for domain, fields in strategy_tree.items():
            if domain.startswith("_"):
                continue

            domain_conf = {}
            for key, conf_obj in fields.items():
                domain_conf[key] = self._resolve_value(conf_obj)

            flat_config[domain] = domain_conf

        return flat_config

    def preview_batch_creation(self, count: int, strategy: dict) -> list:
        """
        [Debug V2] 模拟批量生成，并生成 Cloud Payload 预览。
        Returns: List of { factory_config, cloud_payload }
        """
        from apps.workflow.inference.projects import InferenceProject

        results = []
        logger.info(f"========== [Factory Debug Start] Planning {count} Items ==========")

        try:
            inf_proj = InferenceProject.objects.get(id=self.inference_project_id)
            # 获取 Asset 信息 (模拟 Action 的行为)
            asset_name = inf_proj.asset.title if inf_proj.asset else "Unknown Asset"
            asset_id = str(inf_proj.asset.id) if inf_proj.asset else "unknown-id"
            # 模拟蓝图路径 (Debug 模式下可能文件不存在，给个占位符)
            blueprint_path = "debug/mock_blueprint.json"
            if inf_proj.annotation_project.final_blueprint_file:
                blueprint_path = inf_proj.annotation_project.final_blueprint_file.name

        except Exception as e:
            logger.error(f"Debug Prep Failed: {e}")
            return [{"error": str(e)}]

        for i in range(count):
            # 1. Factory Output: 策略抽样
            instance_config = self._flatten_strategy(strategy)

            # 2. Cloud Payload: 模拟转换
            cloud_payload = {}
            narration_config = instance_config.get("narration", {})

            try:
                # 调用 PayloadBuilder 生成真实 Payload
                # 注意：这会触发 Pydantic 的校验逻辑 (如 validate_custom_usage)
                cloud_payload = PayloadBuilder.build_narration_payload(
                    asset_name=asset_name, asset_id=asset_id, blueprint_path=blueprint_path, raw_config=narration_config
                )
            except Exception as e:
                cloud_payload = {"error": f"Payload Builder Failed: {str(e)}"}

            # 3. 组装结果
            debug_item = {
                "batch_index": i + 1,
                "factory_output": instance_config,  # 参数工厂的产出
                "cloud_payload": cloud_payload,  # 发给 Cloud 的产出
            }

            # 打印日志 (可选，因为会生成文件)
            logger.info(f"[Factory Debug] Item #{i + 1}: \n{json.dumps(debug_item, ensure_ascii=False)}")

            results.append(debug_item)

        logger.info("========== [Factory Debug End] ==========")
        return results

    @transaction.atomic
    def create_batch_from_strategy(self, count: int, strategy: dict) -> CreativeBatch:
        # ... (保持原有的 create_batch_from_strategy 逻辑不变) ...
        from apps.workflow.inference.projects import InferenceProject

        try:
            inf_proj = InferenceProject.objects.get(id=self.inference_project_id)
        except InferenceProject.DoesNotExist:
            logger.error(f"InferenceProject {self.inference_project_id} not found.")
            raise

        # 1. 创建 Batch
        batch = CreativeBatch.objects.create(inference_project=inf_proj, total_count=count, batch_strategy=strategy)

        logger.info(f"Starting Batch {batch.id} creation with count {count}")

        # 2. 循环创建 Project
        for i in range(count):
            # A. 解析参数
            instance_config = self._flatten_strategy(strategy)

            # B. 构造名称
            project_name = f"{inf_proj.name} - Batch {batch.id} - #{i + 1}"

            # 构造描述
            focus = instance_config.get("narration", {}).get("narrative_focus", "N/A")
            style = instance_config.get("narration", {}).get("style", "N/A")
            desc = f"Generated via Factory.\nFocus: {focus}\nStyle: {style}"

            # C. 创建 Project
            project = CreativeProject.objects.create(
                inference_project=inf_proj,
                batch=batch,
                name=project_name,
                description=desc,
                auto_config=instance_config,
            )

            # D. 启动任务 (Narration)
            if "narration" in instance_config:
                narration_config = instance_config["narration"]
                if narration_config:
                    start_narration_task.delay(project_id=str(project.id), config=narration_config)

        return batch
