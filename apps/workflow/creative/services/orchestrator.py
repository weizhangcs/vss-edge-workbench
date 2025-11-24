# 文件路径: apps/workflow/creative/services/orchestrator.py (新建)

import random
from django.db import transaction
from ..projects import CreativeBatch, CreativeProject
from apps.workflow.common.baseJob import BaseJob
from ..tasks import start_narration_task


class CreativeOrchestrator:
    """
    负责处理批量创作的参数组装和项目初始化。
    """

    # 参数池定义
    OPTIONS = {
        "narrative_focus": ['romantic_progression', 'career_growth', 'suspense_thriller', 'dramatic_conflict'],
        "style": ['humorous', 'emotional', 'suspense', 'straight'],
        "perspective": ['third_person', 'first_person'],
        # Scope 随机策略：随机选取 3-5 集的跨度，或者全集
        # Audio 语速随机范围: 0.8 - 1.3
    }

    def __init__(self, inference_project_id: str):
        self.inference_project_id = inference_project_id

    def _generate_random_config(self, fixed_params: dict) -> dict:
        """
        生成单次创作的全流程配置。
        fixed_params 中存在的键值保持不变，不存在的则随机生成。
        """
        # 1. Narration Config
        narrative_focus = fixed_params.get('narrative_focus') or random.choice(self.OPTIONS['narrative_focus'])
        style = fixed_params.get('style') or random.choice(self.OPTIONS['style'])
        perspective = fixed_params.get('perspective') or random.choice(self.OPTIONS['perspective'])
        target_duration = fixed_params.get('target_duration_minutes') or random.randint(3, 8)

        # Scope 处理 (如果用户没指定，这里简单处理为默认 1-5，实际可更复杂)
        scope_start = fixed_params.get('scope_start', 1)
        scope_end = fixed_params.get('scope_end', 5)

        narration_config = {
            "narrative_focus": narrative_focus,
            "style": style,
            "perspective": perspective,
            "target_duration_minutes": target_duration,
            "scope_start": scope_start,
            "scope_end": scope_end
        }

        # 2. Audio Config
        # [需求限制] 模板只开放一个
        audio_template = "chinese_paieas_replication"

        # 语速随机化 (0.9 ~ 1.2)
        audio_speed = fixed_params.get('speed') or round(random.uniform(0.9, 1.2), 1)

        audio_config = {
            "template_name": audio_template,
            "speed": audio_speed,
            "style": ""  # 默认继承 narration style
        }

        # 3. Edit Config (通常无太多参数)
        edit_config = {
            "lang": "zh"
        }

        return {
            "narration": narration_config,
            "audio": audio_config,
            "edit": edit_config
        }

    @transaction.atomic
    def create_batch(self, count: int, fixed_params: dict) -> CreativeBatch:
        """
        创建批次并初始化所有项目。
        """
        # 1. 创建 Batch 记录
        from apps.workflow.inference.projects import InferenceProject
        inf_proj = InferenceProject.objects.get(id=self.inference_project_id)

        batch = CreativeBatch.objects.create(
            inference_project=inf_proj,
            total_count=count,
            batch_strategy=fixed_params
        )

        # 2. 循环创建 Project 并启动第一步
        for i in range(count):
            # 生成该项目的独立配置
            full_config = self._generate_random_config(fixed_params)

            # 创建项目
            project = CreativeProject.objects.create(
                inference_project=inf_proj,
                batch=batch,
                name=f"{inf_proj.name} - Batch {batch.id} - #{i + 1}",
                description=f"Auto-generated via Orchestrator.\nFocus: {full_config['narration']['narrative_focus']}\nStyle: {full_config['narration']['style']}",
                auto_config=full_config  # [关键] 保存全流程配置
            )

            # 立即启动第一步 (Narration)
            # 注意：我们把配置传给 Task
            start_narration_task.delay(
                project_id=str(project.id),
                config=full_config['narration']
            )

        return batch