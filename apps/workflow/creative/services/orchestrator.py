# apps/workflow/creative/services/orchestrator.py


import logging
import random

from django.db import transaction

from ..projects import CreativeBatch, CreativeProject
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
        [Debug V4] 模拟批量生成，支持 Lock/Skip/New 模式识别。
        """
        from apps.workflow.inference.projects import InferenceProject

        results = []
        logger.info(f"========== [Factory Debug Start] Planning {count} Items ==========")

        try:
            inf_proj = InferenceProject.objects.get(id=self.inference_project_id)
            asset_name = inf_proj.asset.title if inf_proj.asset else "Unknown Asset"
            asset_id = str(inf_proj.asset.id) if inf_proj.asset else "unknown-id"

            # 模拟蓝图路径
            blueprint_path = "debug/mock_blueprint.json"
            if inf_proj.annotation_project.final_blueprint_file:
                blueprint_path = inf_proj.annotation_project.final_blueprint_file.name

        except Exception as e:
            logger.error(f"Debug Prep Failed: {e}")
            return [{"error": str(e)}]

        for i in range(count):
            # --- 1. 解析配置 (适配 V2 嵌套结构) ---
            pure_config_map = {}
            modes_map = {}

            # 预处理：分离 mode 和 config
            for domain, data in strategy.items():
                if domain == "_meta":
                    continue
                # 兼容旧结构（防守性编程）：如果 data 里没有 mode，假设是旧扁平结构
                if isinstance(data, dict) and "mode" in data:
                    modes_map[domain] = data.get("mode", "NEW")
                    pure_config_map[domain] = data.get("config") or {}
                else:
                    modes_map[domain] = "NEW"
                    pure_config_map[domain] = data or {}

            # 参数抽样 (Random/Enum/Range)
            instance_config = self._flatten_strategy(pure_config_map)

            # --- 2. Cloud Payloads: 模拟全链路转换 ---
            cloud_payloads = {}

            # === Step 1: Narration ===
            mode_narration = modes_map.get("narration", "NEW")

            if mode_narration == "LOCKED":
                cloud_payloads["step_1_narration"] = {
                    "status": "LOCKED (Asset Reuse)",
                    "info": "Will copy narration_script_file from source.",
                }
            elif mode_narration == "SKIP":
                cloud_payloads["step_1_narration"] = {"status": "SKIPPED"}
            else:
                # NEW / RECREATE
                try:
                    cloud_payloads["step_1_narration"] = PayloadBuilder.build_narration_payload(
                        asset_name=asset_name,
                        asset_id=asset_id,
                        blueprint_path=blueprint_path,
                        raw_config=instance_config.get("narration", {}),
                    )
                except Exception as e:
                    cloud_payloads["step_1_narration"] = {"error": f"Narration Error: {str(e)}"}

            # === Step 1.5: Localize ===
            mode_loc = modes_map.get("localize", "SKIP")

            if mode_loc == "LOCKED":
                cloud_payloads["step_1.5_localize"] = {"status": "LOCKED (Asset Reuse)"}
            elif mode_loc == "SKIP":
                # Debug 模式下如果不显示 SKIP 也可以，看你喜好，这里显式展示
                cloud_payloads["step_1.5_localize"] = {"status": "SKIPPED"}
            else:
                try:
                    mock_master_path = "debug/mock_narration_script.json"
                    cloud_payloads["step_1.5_localize"] = PayloadBuilder.build_localize_payload(
                        master_path=mock_master_path,
                        blueprint_path=blueprint_path,
                        raw_config=instance_config.get("localize", {}),
                    )
                except Exception as e:
                    cloud_payloads["step_1.5_localize"] = {"error": f"Localize Error: {str(e)}"}

            # === Step 2: Audio ===
            mode_audio = modes_map.get("audio", "NEW")

            if mode_audio == "LOCKED":
                cloud_payloads["step_2_audio"] = {
                    "status": "LOCKED (Asset Reuse)",
                    "info": "Will copy dubbing_script_file & assets from source.",
                }
            elif mode_audio == "SKIP":
                cloud_payloads["step_2_audio"] = {"status": "SKIPPED"}
            else:
                try:
                    audio_config = instance_config.get("audio", {}).copy()

                    # [Debug逻辑复用] 智能推断语言代码
                    # 注意：在 Debug 模式下，如果 Localize 是 NEW，我们可以拿到 target_lang
                    # 如果 Localize 是 LOCKED，我们可能拿不到，这里做个简单的 Mock 处理

                    target_lang = None
                    if mode_loc == "NEW" or mode_loc == "RECREATE":
                        target_lang = instance_config.get("localize", {}).get("target_lang")

                    if target_lang:
                        audio_config["source_script_type"] = "localized"
                        if "language_code" not in audio_config:
                            audio_config["language_code"] = self._map_lang_code(target_lang)
                    else:
                        # 默认为 master
                        if "source_script_type" not in audio_config:
                            audio_config["source_script_type"] = "master"
                        if "language_code" not in audio_config:
                            audio_config["language_code"] = "cmn-CN"

                    # Mock Path
                    if audio_config.get("source_script_type") == "localized":
                        mock_input_path = "debug/mock_localized_script.json"
                    else:
                        mock_input_path = "debug/mock_narration_script.json"

                    cloud_payloads["step_2_audio"] = PayloadBuilder.build_dubbing_payload(
                        input_path=mock_input_path, raw_config=audio_config
                    )
                except Exception as e:
                    cloud_payloads["step_2_audio"] = {"error": f"Audio Error: {str(e)}"}

            # 3. 组装结果
            debug_item = {
                "batch_index": i + 1,
                "factory_output": {
                    # 方便调试查看，把解析后的纯参数放这里
                    "modes": modes_map,
                    "configs": instance_config,
                },
                "cloud_payloads": cloud_payloads,
            }

            results.append(debug_item)

        logger.info("========== [Factory Debug End] ==========")
        return results

    # [新增 Helper] 资产复用逻辑
    def _replicate_asset(self, source_proj: CreativeProject, target_proj: CreativeProject, field_name: str):
        """
        将源项目的产出物（FileField）“指针复制”到目标项目。
        注意：这里进行的是引用复制，不会物理复制文件，节省空间。
        """
        source_file = getattr(source_proj, field_name)
        if source_file:
            # 直接赋值 FileField，Django 会处理引用
            setattr(target_proj, field_name, source_file)
            target_proj.save(update_fields=[field_name])
            logger.info(f"Asset Reused: {field_name} from {source_proj.id} to {target_proj.id}")
        else:
            logger.warning(f"Source project {source_proj.id} missing asset {field_name}, cannot lock.")

    @transaction.atomic
    def create_batch_from_strategy(self, count: int, strategy: dict, source_creative_project_id: str) -> CreativeBatch:
        from apps.workflow.creative.projects import CreativeProject
        from apps.workflow.inference.projects import InferenceProject

        from ..tasks import start_audio_task, start_localize_task, start_narration_task

        # 0. 上下文准备
        inf_proj = InferenceProject.objects.get(id=self.inference_project_id)
        source_proj = CreativeProject.objects.get(id=source_creative_project_id)

        # 1. Batch
        batch = CreativeBatch.objects.create(inference_project=inf_proj, total_count=count, batch_strategy=strategy)
        logger.info(f"Starting Batch {batch.id}...")

        for i in range(count):
            # --- 解析配置 ---
            pure_config_map = {}
            modes_map = {}
            for domain, data in strategy.items():
                if domain == "_meta":
                    continue
                modes_map[domain] = data.get("mode", "NEW")
                pure_config_map[domain] = data.get("config") or {}

            instance_config = self._flatten_strategy(pure_config_map)

            # --- 创建项目 ---
            target_proj = CreativeProject.objects.create(
                inference_project=inf_proj,
                batch=batch,
                name=f"{inf_proj.name} - Batch {batch.id} - #{i + 1}",
                description=f"Auto Generated. Narration: {modes_map.get('narration')}",
                auto_config=instance_config,
            )

            # =========================================================
            # 核心流水线控制器 (Pipeline Controller)
            # =========================================================

            # --- Step 1: Narration ---
            mode_narration = modes_map.get("narration", "NEW")
            step_1_done = False

            if mode_narration == "LOCKED":
                self._replicate_asset(source_proj, target_proj, "narration_script_file")
                target_proj.status = CreativeProject.STATUS.NARRATION_COMPLETED
                step_1_done = True
            elif mode_narration == "SKIP":
                step_1_done = True  # 视为已过
            else:
                # 启动任务，链条到此暂时交给 Celery，后续由 Task Callback 接管
                start_narration_task.delay(project_id=str(target_proj.id), config=instance_config.get("narration"))
                continue  # 【重要】直接跳出当前循环，等待异步回调触发下一步

            if not step_1_done:
                continue

            # --- Step 1.5: Localize ---
            mode_loc = modes_map.get("localize", "SKIP")
            step_1_5_done = False

            if mode_loc == "LOCKED":
                self._replicate_asset(source_proj, target_proj, "localized_script_file")
                target_proj.status = CreativeProject.STATUS.LOCALIZATION_COMPLETED
                step_1_5_done = True
            elif mode_loc == "SKIP":
                step_1_5_done = True
            else:
                start_localize_task.delay(project_id=str(target_proj.id), config=instance_config.get("localize"))
                continue

            if not step_1_5_done:
                continue

            # --- Step 2: Audio ---
            mode_audio = modes_map.get("audio", "NEW")
            # step_2_done = False

            if mode_audio == "LOCKED":
                self._replicate_asset(source_proj, target_proj, "dubbing_script_file")
                # 注意：Audio 还有大量音频文件，不仅是脚本。
                # 简单的 FileField 复制是不够的。但 MVP 阶段先只复制脚本。
                # TODO: 复制实际音频文件目录
                target_proj.status = CreativeProject.STATUS.AUDIO_COMPLETED
                # step_2_done = True
            elif mode_audio == "SKIP":
                pass
                # step_2_done = True
            else:
                # 智能修正：如果前一步是 Localize，且已完成，确保 Audio 使用 Localized 源
                audio_conf = instance_config.get("audio", {})
                # ... (此处可加入之前的语言代码修正逻辑) ...
                start_audio_task.delay(project_id=str(target_proj.id), config=audio_conf)
                continue

            # ... 后续 Step 3 (Edit) 和 Step 4 (Synthesis) 逻辑类似 ...
            # 如果到了 Audio 还是 Locked，说明用户只想跑最后一步，或者只是复制项目

            target_proj.save()

        return batch
