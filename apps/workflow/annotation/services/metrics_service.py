# 文件路径: apps/workflow/annotation/services/metrics_service.py

import logging
from typing import Dict
from datetime import datetime
from collections import defaultdict

# 在模块顶部初始化一次 logger
logger = logging.getLogger(__name__)

class CharacterMetricsCalculator:
    """
    角色量化指标计算器 (Character Metrics Calculator)。

    这是一个纯粹的“计算引擎”，其唯一职责是从结构化的剧本数据 (blueprint.json) 中，
    为每个角色计算出一系列量化指标（如出场次数、对话量）和重要度得分。

    它被设计为无状态的，以便 Celery 任务可以安全地实例化和调用它。
    """

    def __init__(self):
        """
        初始化计算器。
        (设计为无状态，不接受 logger 依赖注入)
        """
        pass

    def execute(self, blueprint_data: Dict, **kwargs) -> Dict:
        """
        执行角色量化指标计算的核心方法。

        此方法编排了整个计算流程：
        1. 预处理 (Preprocessing)
        2. 计算重要度 (Importance Scores)
        3. 格式化并返回最终报告。

        Args:
            blueprint_data (Dict): 包含完整剧本场景数据的Python字典 (来自 blueprint.json)。
            **kwargs: 其他可选的配置参数，例如:
                - exclude_patterns (List[str]): 在预处理中需要排除的角色名模式列表。
                - importance_weights (Dict): 用于计算重要度得分的权重配置。

        Returns:
            Dict: 一个包含所有计算结果的字典报告。
        """
        logger.info("开始执行角色量化指标计算...")
        try:
            # 为了快速查找，将场景字典的键从字符串转换为整数。
            scenes_map = {int(k): v for k, v in blueprint_data.get('scenes', {}).items()}

            # --- 步骤 1: 预处理 ---
            logger.info("正在进行本地预处理...")
            character_metrics, all_characters = self._local_preprocessing(scenes_map, **kwargs)

            # --- 步骤 2: 计算重要度 ---
            logger.info("正在计算角色重要度...")
            weights = kwargs.get('importance_weights', {'presence': 0.7, 'interaction': 0.3})
            total_dialogues = sum(d.get('dialogue_count', 0) for d in character_metrics.values())
            importance_scores = self._calculate_importance_scores(character_metrics, total_dialogues, weights)

            # 按重要度得分从高到低排序。
            sorted_by_importance = sorted(importance_scores.items(), key=lambda item: item[1], reverse=True)

            # --- 步骤 3: 构建最终报告 ---
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
        """
        对剧本数据进行预处理，提取每个角色的原始量化指标。

        Args:
            scenes_map (Dict): 以场景ID为键的场景数据字典。
            **kwargs: 其他可选参数，主要用于获取 'exclude_patterns'。

        Returns:
            tuple: 一个元组，包含两个元素:
                - (Dict) final_metrics: 每个角色的详细量化指标。
                - (List) all_characters: 在剧中出现的所有（未被排除的）角色名称列表。
        """
        metrics = defaultdict(lambda: {
            "scene_count": 0, "dialogue_count": 0, "dialogue_total_length": 0,
            "dialogue_total_duration": 0.0, "co_occurrence": defaultdict(int),
            "scene_ids": set()
        })
        all_characters = set()
        exclude_patterns = kwargs.get('exclude_patterns', ["Minor", "路人"])

        # 遍历每一个场景以收集数据。
        for scene_id, scene_obj in scenes_map.items():
            dialogues_in_scene = scene_obj.get('dialogues', [])

            # 识别当前场景中所有发言的角色，并根据排除模式进行过滤。
            present_characters = {
                d.get('speaker') for d in dialogues_in_scene
                if d.get('speaker') and not any(d.get('speaker').startswith(p) for p in exclude_patterns)
            }
            all_characters.update(present_characters)

            # 记录角色出现的场景ID。
            for char_name in present_characters:
                metrics[char_name]["scene_ids"].add(scene_id)

            # 计算角色共现次数（co-occurrence），用于衡量角色间的互动强度。
            for char1 in present_characters:
                for char2 in present_characters:
                    if char1 != char2:
                        metrics[char1]['co_occurrence'][char2] += 1

            # 累加每个角色的对话相关指标。
            for dialogue in dialogues_in_scene:
                speaker = dialogue.get('speaker')
                if speaker in present_characters:
                    metrics[speaker]['dialogue_count'] += 1
                    metrics[speaker]['dialogue_total_length'] += len(dialogue.get('content', ''))
                    # 安全地计算对话时长，忽略格式错误的时间戳。
                    try:
                        start = datetime.strptime(dialogue['start_time'], '%H:%M:%S.%f')
                        end = datetime.strptime(dialogue['end_time'], '%H:%M:%S.%f')
                        metrics[speaker]['dialogue_total_duration'] += (end - start).total_seconds()
                    except (ValueError, KeyError):
                        continue

        # 将临时的 set 和 defaultdict 转换为最终的字典和列表格式。
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
        """
        根据量化指标，计算每个角色的综合重要度得分。

        得分是基于“出场度” (presence) 和“互动度” (interaction) 的加权平均。

        Args:
            metrics (Dict): 由 _local_preprocessing 方法生成的角色指标字典。
            total_dialogues (int): (当前未使用) 剧本中的总对话数。
            weights (Dict): 包含 'presence' 和 'interaction' 权重的字典。

        Returns:
            Dict: 一个 {角色名: 重要度得分} 的字典。
        """
        scores = {}
        if not metrics: return scores

        target_characters = metrics.keys()

        # --- 归一化处理 ---
        # 找到各项指标的最大值，用于后续的归一化计算，以消除量纲影响。
        # `or 1` 用于防止除以零的错误。
        max_vals = {
            'scene': max(metrics[c]['scene_count'] for c in target_characters) or 1,
            'dialogue': max(metrics[c]['dialogue_count'] for c in target_characters) or 1,
            'length': max(metrics[c]['dialogue_total_length'] for c in target_characters) or 1,
            'duration': max(metrics[c]['dialogue_total_duration'] for c in target_characters) or 1,
            'interaction': max(len(metrics[c]['co_occurrence']) for c in target_characters) or 1
        }

        # 为每个角色计算得分。
        for name in target_characters:
            data = metrics[name]

            # “出场度”得分是多个指标归一化后的总和。
            presence_score = (data['scene_count'] / max_vals['scene'] +
                              data['dialogue_count'] / max_vals['dialogue'] +
                              data['dialogue_total_length'] / max_vals['length'] +
                              data['dialogue_total_duration'] / max_vals['duration'])

            # “互动度”得分基于与多少个其他角色有过共现。
            interaction_score = len(data['co_occurrence']) / max_vals['interaction']

            # 最终得分为“出场度”和“互动度”的加权平均。
            scores[name] = (presence_score * weights.get('presence', 0.7)) + \
                           (interaction_score * weights.get('interaction', 0.3))

        return scores