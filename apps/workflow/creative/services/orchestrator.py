# apps/workflow/creative/services/orchestrator.py

import logging
import random

from django.db import transaction

from ..models import CreativeProject
from ..tasks import start_audio_task, start_localize_task, start_narration_task
from .payloads import PayloadBuilder

logger = logging.getLogger(__name__)


class CreativeOrchestrator:
    def __init__(self, inference_project_id: str):
        self.inference_project_id = inference_project_id

    def _resolve_value(self, field_config: dict):
        if not isinstance(field_config, dict):
            return field_config

        c_type = field_config.get("type")

        # 显式支持 value (Director 模式核心)
        if c_type in ["single", "text", "fixed", "custom", "value"]:
            return field_config.get("value")

        if c_type == "enum":
            val_str = field_config.get("values_str", "")
            val_str = str(val_str).replace("，", ",")
            options = [x.strip() for x in val_str.split(",") if x.strip()]
            if not options:
                return None
            return random.choice(options)

        if c_type == "range":
            try:
                mn = float(field_config.get("min", 0))
                mx = float(field_config.get("max", 0))
                step = float(field_config.get("step", 1))
                if step <= 0:
                    step = 1
                options = []
                curr = mn
                while curr <= mx + 0.00001:
                    options.append(curr)
                    curr += step
                val = random.choice(options) if options else mn
                if step == int(step) and mn == int(mn):
                    return int(val)
                return round(val, 2)
            except Exception as e:
                logger.warning(f"Error resolving range: {e}")
                return 0

        return field_config.get("value")

    def _flatten_strategy(self, strategy_tree: dict) -> dict:
        flat_config = {}
        for domain, fields in strategy_tree.items():
            if domain.startswith("_"):
                continue
            domain_conf = {}
            for key, conf_obj in fields.items():
                domain_conf[key] = self._resolve_value(conf_obj)
            flat_config[domain] = domain_conf
        return flat_config

    def _map_lang_code(self, simple_lang: str) -> str:
        MAPPING = {
            "en": "en-US",
            "fr": "fr-FR",
            "de": "de-DE",
            "ja": "ja-JP",
            "ko": "ko-KR",
            "zh": "cmn-CN",
            "es": "es-ES",
        }
        return MAPPING.get(simple_lang, "cmn-CN")

    def _replicate_asset(self, source_proj: CreativeProject, target_proj: CreativeProject, field_name: str):
        source_file = getattr(source_proj, field_name)
        if source_file:
            setattr(target_proj, field_name, source_file)
            target_proj.save(update_fields=[field_name])
            logger.info(f"Asset Reused: {field_name} from {source_proj.id} to {target_proj.id}")
        else:
            logger.warning(f"Source project {source_proj.id} missing asset {field_name}, cannot lock.")

    # [Renamed] preview_batch_creation -> preview_pipeline_creation
    def preview_pipeline_creation(self, count: int, strategy: dict) -> list:
        """
        [Debug V4] 模拟 Pipeline 生成
        """
        from apps.workflow.inference.projects import InferenceProject

        results = []
        logger.info(f"========== [Pipeline Debug Start] Planning {count} Items ==========")

        try:
            inf_proj = InferenceProject.objects.get(id=self.inference_project_id)
            asset_name = inf_proj.asset.title if inf_proj.asset else "Unknown Asset"
            asset_id = str(inf_proj.asset.id) if inf_proj.asset else "unknown-id"

            blueprint_path = "debug/mock_blueprint.json"
            if inf_proj.annotation_project.final_blueprint_file:
                blueprint_path = inf_proj.annotation_project.final_blueprint_file.name

        except Exception as e:
            logger.error(f"Debug Prep Failed: {e}")
            return [{"error": str(e)}]

        for i in range(count):
            pure_config_map = {}
            modes_map = {}
            for domain, data in strategy.items():
                if domain == "_meta":
                    continue
                if isinstance(data, dict) and "mode" in data:
                    modes_map[domain] = data.get("mode", "NEW")
                    pure_config_map[domain] = data.get("config") or {}
                else:
                    modes_map[domain] = "NEW"
                    pure_config_map[domain] = data or {}

            instance_config = self._flatten_strategy(pure_config_map)
            cloud_payloads = {}

            # === Step 1: Narration ===
            mode_narration = modes_map.get("narration", "NEW")

            if mode_narration == "LOCKED":
                cloud_payloads["step_1_narration"] = {"status": "LOCKED (Asset Reuse)"}
            elif mode_narration == "SKIP":
                cloud_payloads["step_1_narration"] = {"status": "SKIPPED"}
            else:
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
                cloud_payloads["step_2_audio"] = {"status": "LOCKED (Asset Reuse)"}
            elif mode_audio == "SKIP":
                cloud_payloads["step_2_audio"] = {"status": "SKIPPED"}
            else:
                try:
                    audio_config = instance_config.get("audio", {}).copy()
                    target_lang = None
                    if mode_loc == "NEW" or mode_loc == "RECREATE":
                        target_lang = instance_config.get("localize", {}).get("target_lang")

                    if target_lang:
                        audio_config["source_script_type"] = "localized"
                        if "language_code" not in audio_config:
                            audio_config["language_code"] = self._map_lang_code(target_lang)
                    else:
                        if "source_script_type" not in audio_config:
                            audio_config["source_script_type"] = "master"
                        if "language_code" not in audio_config:
                            audio_config["language_code"] = "cmn-CN"

                    mock_input_path = (
                        "debug/mock_localized_script.json"
                        if audio_config.get("source_script_type") == "localized"
                        else "debug/mock_narration_script.json"
                    )

                    cloud_payloads["step_2_audio"] = PayloadBuilder.build_dubbing_payload(
                        input_path=mock_input_path, raw_config=audio_config
                    )
                except Exception as e:
                    cloud_payloads["step_2_audio"] = {"error": f"Audio Error: {str(e)}"}

            debug_item = {
                "batch_index": i + 1,
                "factory_output": {"modes": modes_map, "configs": instance_config},
                "cloud_payloads": cloud_payloads,
            }
            results.append(debug_item)

        logger.info("========== [Pipeline Debug End] ==========")
        return results

    @transaction.atomic
    def create_pipeline_from_strategy(self, count: int, strategy: dict, source_creative_project_id: str):
        """
        [V4 Refactor] 导演模式：原地执行 (In-place Execution)
        直接在源项目上更新配置并启动任务，不再创建新项目。
        """
        from apps.workflow.creative.models import CreativeProject

        # 1. 获取当前项目 (这就是我们的操作对象)
        target_proj = CreativeProject.objects.get(id=source_creative_project_id)

        # 确保关联了正确的推理项目 (通常已经关联，这里是防御性检查或更新)
        # inf_proj = InferenceProject.objects.get(id=self.inference_project_id)
        # target_proj.inference_project = inf_proj # 如果需要强制同步

        # 2. 解析配置
        pure_config_map = {}
        modes_map = {}
        for domain, data in strategy.items():
            if domain == "_meta":
                continue
            modes_map[domain] = data.get("mode", "NEW")
            pure_config_map[domain] = data.get("config") or {}

        instance_config = self._flatten_strategy(pure_config_map)

        # 3. [核心修改] 原地更新项目信息
        target_proj.auto_config = instance_config
        target_proj.description = f"Director Execution. Modes: {modes_map}"
        # 如果是首次运行，状态可能是 CREATED；如果是重跑，状态可能是 COMPLETED
        # 我们不在这里强制重置状态为 CREATED，而是让具体的 Task 去更新状态 (e.g. NARRATION_RUNNING)
        target_proj.save()

        logger.info(f"Starting Pipeline Execution IN-PLACE for Project {target_proj.id}...")

        # =========================================================
        # 流水线控制器 (Pipeline Controller)
        # =========================================================

        # --- Step 1: Narration ---
        mode_narration = modes_map.get("narration", "NEW")
        step_1_done = False

        if mode_narration == "LOCKED":
            # In-place 模式下，LOCKED 意味着“保留原样”
            # 如果文件本来就在这里，不需要 replicate。
            # 但为了逻辑统一，如果用户是从别的项目 Fork 来的（未来场景），replicate 也是安全的（self copy）
            if target_proj.narration_script_file:
                logger.info(f"[{target_proj.id}] Narration Locked (Preserved).")
                # 状态如果是 FAILED 或其他，可能需要修正为 COMPLETED？
                # 暂时假设 LOCKED 意味着用户确认它是好的。
                target_proj.status = CreativeProject.Status.NARRATION_COMPLETED
                target_proj.save()
                step_1_done = True
            else:
                # 异常：选了 LOCKED 但没文件
                logger.warning(f"[{target_proj.id}] Narration Locked but no file found! Fallback to NEW.")
                mode_narration = "NEW"  # 强制降级为 NEW

        if mode_narration == "SKIP":
            step_1_done = True

        if mode_narration == "NEW":  # 注意：这里不能用 elif，因为上面可能降级
            logger.info(f"[{target_proj.id}] Triggering Narration Pipeline Task...")
            start_narration_task.delay(project_id=str(target_proj.id), config=instance_config.get("narration"))
            return target_proj

        if not step_1_done:
            return target_proj

        # --- Step 1.5: Localize ---
        mode_loc = modes_map.get("localize", "SKIP")
        step_1_5_done = False

        if mode_loc == "LOCKED":
            if target_proj.localized_script_file:
                target_proj.status = CreativeProject.Status.LOCALIZATION_COMPLETED
                target_proj.save()
                step_1_5_done = True
            else:
                mode_loc = "NEW"  # Fallback

        if mode_loc == "SKIP":
            step_1_5_done = True

        if mode_loc == "NEW" or mode_loc == "RECREATE":
            start_localize_task.delay(project_id=str(target_proj.id), config=instance_config.get("localize"))
            return target_proj

        if not step_1_5_done:
            return target_proj

        # --- Step 2: Audio ---
        mode_audio = modes_map.get("audio", "NEW")

        if mode_audio == "LOCKED":
            if target_proj.dubbing_script_file:
                target_proj.status = CreativeProject.Status.AUDIO_COMPLETED
                target_proj.save()
            else:
                mode_audio = "NEW"  # Fallback

        if mode_audio == "SKIP":
            pass

        if mode_audio == "NEW" or mode_audio == "RECREATE":
            audio_conf = instance_config.get("audio", {}).copy()
            # 语言推断逻辑
            target_lang = None
            if mode_loc == "NEW" or mode_loc == "RECREATE":
                target_lang = instance_config.get("localize", {}).get("target_lang")
            elif mode_loc == "LOCKED":
                # 尝试从已存在的 localize 脚本或配置中读取？比较复杂，暂时由前端传递或默认
                # 简单做法：如果 Localize 是 Locked，且有 target_lang 配置，沿用
                pass

            if target_lang:
                audio_conf["source_script_type"] = "localized"
                if "language_code" not in audio_conf:
                    audio_conf["language_code"] = self._map_lang_code(target_lang)
            else:
                if "source_script_type" not in audio_conf:
                    audio_conf["source_script_type"] = "master"
                if "language_code" not in audio_conf:
                    audio_conf["language_code"] = "cmn-CN"

            start_audio_task.delay(project_id=str(target_proj.id), config=audio_conf)
            return target_proj

        # 保存最终状态
        target_proj.save()
        return target_proj
