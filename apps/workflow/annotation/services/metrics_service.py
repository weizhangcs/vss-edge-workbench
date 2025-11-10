# 文件路径: apps/workflow/annotation/services/metrics_service.py

import json
import logging
from typing import Dict
from datetime import datetime
from collections import defaultdict
from ...models import AnnotationProject


# (这是你提供的 Code 2)
# (我只做了一个小小的修改：移除了 __init__ 中的 logger，
#  并在每个方法中直接获取 logger，使其更易于被 Celery 任务调用)

class CharacterMetricsCalculator:
    """
    (来自 Code 2) 角色量化指标计算器。
    """

    def __init__(self):
        # 移除了 logger 依赖注入，使其无状态
        pass

    def execute(self, blueprint_data: Dict, **kwargs) -> Dict:
        logger = logging.getLogger(__name__)
        logger.info("开始执行角色量化指标计算...")
        try:
            scenes_map = {int(k): v for k, v in blueprint_data.get('scenes', {}).items()}
            logger.info("正在进行本地预处理...")
            character_metrics, all_characters = self._local_preprocessing(scenes_map, **kwargs)
            logger.info("正在计算角色重要度...")
            weights = kwargs.get('importance_weights', {'presence': 0.7, 'interaction': 0.3})
            total_dialogues = sum(d.get('dialogue_count', 0) for d in character_metrics.values())
            importance_scores = self._calculate_importance_scores(character_metrics, total_dialogues, weights)
            sorted_by_importance = sorted(importance_scores.items(), key=lambda item: item[1], reverse=True)

            final_report = {
                "calculation_date": datetime.now().isoformat(),
                "all_characters_found": all_characters,
                "importance_scores": dict(sorted_by_importance),
                "ranked_characters": [{"name": name, "score": score} for name, score in sorted_by_importance],
                "quantitative_metrics": dict(
                    sorted(character_metrics.items(), key=lambda item: item[1].get('scene_count', 0), reverse=True)),
            }
            logger.info("角色量化指标计算成功完成。")
            return final_report
        except Exception as e:
            logger.error(f"在计算角色指标时发生错误: {e}", exc_info=True)
            raise

    def _local_preprocessing(self, scenes_map: Dict, **kwargs) -> tuple:
        logger = logging.getLogger(__name__)
        metrics = defaultdict(lambda: {
            "scene_count": 0, "dialogue_count": 0, "dialogue_total_length": 0,
            "dialogue_total_duration": 0.0, "co_occurrence": defaultdict(int),
            "scene_ids": set()
        })
        all_characters = set()
        exclude_patterns = kwargs.get('exclude_patterns', ["Minor", "路人"])

        for scene_id, scene_obj in scenes_map.items():
            dialogues_in_scene = scene_obj.get('dialogues', [])
            present_characters = {
                d.get('speaker') for d in dialogues_in_scene
                if d.get('speaker') and not any(d.get('speaker').startswith(p) for p in exclude_patterns)
            }
            all_characters.update(present_characters)
            for char_name in present_characters:
                metrics[char_name]["scene_ids"].add(scene_id)
            for char1 in present_characters:
                for char2 in present_characters:
                    if char1 != char2:
                        metrics[char1]['co_occurrence'][char2] += 1
            for dialogue in dialogues_in_scene:
                speaker = dialogue.get('speaker')
                if speaker in present_characters:
                    metrics[speaker]['dialogue_count'] += 1
                    metrics[speaker]['dialogue_total_length'] += len(dialogue.get('content', ''))
                    try:
                        start = datetime.strptime(dialogue['start_time'], '%H:%M:%S.%f')
                        end = datetime.strptime(dialogue['end_time'], '%H:%M:%S.%f')
                        metrics[speaker]['dialogue_total_duration'] += (end - start).total_seconds()
                    except (ValueError, KeyError):
                        continue

        final_metrics = {}
        for name, data in metrics.items():
            final_metrics[name] = {
                "scene_count": len(data['scene_ids']),
                "dialogue_count": data['dialogue_count'],
                "dialogue_total_length": data['dialogue_total_length'],
                "dialogue_total_duration": data['dialogue_total_duration'],
                "co_occurrence": dict(data['co_occurrence'])
            }
        logger.info(f"预处理完成，已过滤掉匹配模式的角色，剩余 {len(all_characters)} 个角色进入分析。")
        return final_metrics, sorted(list(all_characters))

    def _calculate_importance_scores(self, metrics: Dict, total_dialogues: int, weights: Dict) -> Dict:
        # ... (此方法保持与 Code 2 完全一致) ...
        scores = {}
        if not metrics: return scores
        target_characters = metrics.keys()
        max_vals = {
            'scene': max(metrics[c]['scene_count'] for c in target_characters) or 1,
            'dialogue': max(metrics[c]['dialogue_count'] for c in target_characters) or 1,
            'length': max(metrics[c]['dialogue_total_length'] for c in target_characters) or 1,
            'duration': max(metrics[c]['dialogue_total_duration'] for c in target_characters) or 1,
            'interaction': max(len(metrics[c]['co_occurrence']) for c in target_characters) or 1
        }
        for name in target_characters:
            data = metrics[name]
            presence_score = (data['scene_count'] / max_vals['scene'] +
                              data['dialogue_count'] / max_vals['dialogue'] +
                              data['dialogue_total_length'] / max_vals['length'] +
                              data['dialogue_total_duration'] / max_vals['duration'])
            interaction_score = len(data['co_occurrence']) / max_vals['interaction']
            scores[name] = (presence_score * weights.get('presence', 0.7)) + \
                           (interaction_score * weights.get('interaction', 0.3))
        return scores