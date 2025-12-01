# apps/workflow/creative/services/payloads.py

import logging
from decimal import Decimal
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


# ==============================================================================
# Part A: VSS-Cloud Contract (Strict Schemas)
# 这一部分是云端 schemas.py 的 Edge 端镜像，用于确保发送的数据 100% 符合契约。
# ==============================================================================


class CustomPrompts(BaseModel):
    """[Cloud Mirror] 自定义提示词容器"""

    narrative_focus: Optional[str] = Field(None, description="自定义 RAG 检索意图")
    style: Optional[str] = Field(None, description="自定义 LLM 生成风格")


class ScopeParams(BaseModel):
    """[Cloud Mirror] 剧情范围"""

    type: Literal["full", "episode_range", "scene_selection"] = "full"
    value: Optional[List[int]] = None


class CharacterFocusParams(BaseModel):
    """[Cloud Mirror] 角色聚焦"""

    mode: Literal["all", "specific"] = "all"
    characters: List[str] = Field(default_factory=list)


class ControlParams(BaseModel):
    """[Cloud Mirror] 创作控制参数"""

    narrative_focus: str = "general"
    scope: ScopeParams = Field(default_factory=ScopeParams)
    character_focus: CharacterFocusParams = Field(default_factory=CharacterFocusParams)
    style: str = "objective"
    perspective: Literal["third_person", "first_person"] = "third_person"
    perspective_character: Optional[str] = None
    target_duration_minutes: Optional[int] = None
    custom_prompts: Optional[CustomPrompts] = None

    @model_validator(mode="after")
    def validate_custom_usage(self):
        """
        [复用云端逻辑] 核心校验：如果选了 custom，必须传对应的文本。
        这能防止 Edge 端发出的空 Prompt 请求被 Cloud 端拒绝。
        """
        focus = self.narrative_focus
        style = self.style
        prompts = self.custom_prompts

        # 检查 narrative_focus
        if focus == "custom":
            if not prompts or not prompts.narrative_focus:
                raise ValueError("叙事焦点选择了 'custom'，但未填写 '自定义焦点 Prompt'")

        # 检查 style
        if style == "custom":
            if not prompts or not prompts.style:
                raise ValueError("解说风格选择了 'custom'，但未填写 '自定义风格 Prompt'")

        # 检查 perspective (第一人称必填角色)
        if self.perspective == "first_person" and not self.perspective_character:
            raise ValueError("选择了 '角色第一人称' 视角，但未填写 '视角角色名'")

        return self


class NarrationServiceConfig(BaseModel):
    """[Cloud Mirror] 完整的服务配置契约"""

    lang: Literal["zh", "en"] = "zh"
    model: str = "gemini-2.5-pro"
    rag_top_k: int = Field(default=50, ge=1, le=200)
    speaking_rate: float = 4.2
    overflow_tolerance: float = Field(default=0.0)
    debug: bool = True
    control_params: ControlParams


# ==============================================================================
# Part B: Form Input Adapter (Flat Schemas)
# 这一部分负责接收 Django Admin 的扁平化输入，并清洗数据（类型转换）。
# ==============================================================================


class BaseFormInput(BaseModel):
    """表单输入基类：处理 Django 特有的数据清洗"""

    class Config:
        arbitrary_types_allowed = True

    @field_validator("*", mode="before")
    @classmethod
    def convert_decimal(cls, v):
        """[核心治理] 自动将 Django 表单传来的 Decimal 转为 float"""
        if isinstance(v, Decimal):
            return float(v)
        return v


class NarrationFormInput(BaseFormInput):
    """接收来自 NarrationConfigurationForm 的扁平数据"""

    # Core
    narrative_focus: str
    custom_narrative_prompt: Optional[str] = None
    style: str
    custom_style_prompt: Optional[str] = None
    perspective: str
    perspective_character: Optional[str] = None

    # Scope
    # [FIX 1] 增加 scope 类型字段，接收 Factory 的 "full" / "episode_range"
    scope: Literal["full", "episode_range", "scene_selection"] = "full"
    scope_start: int = 1
    scope_end: int = 5

    # Characters
    character_focus: str = ""  # 逗号分隔字符串

    # Service
    target_duration_minutes: int = 3
    overflow_tolerance: float = 0.0
    speaking_rate: float = 4.2
    rag_top_k: int = 50

    def to_cloud_contract(self) -> NarrationServiceConfig:
        """
        [核心转换] 将扁平的表单数据 -> 转换为符合云端契约的嵌套对象
        在此过程中完成逻辑映射。
        """
        # 1. 组装 Scope [FIX 2] 动态逻辑
        scope_value = None
        if self.scope == "episode_range":
            scope_value = [self.scope_start, self.scope_end]
        elif self.scope == "scene_selection":
            # 预留逻辑，目前 Factory 可能还没传具体的 scene IDs
            pass

        scope = ScopeParams(type=self.scope, value=scope_value)

        # 2. 组装 Character Focus
        char_list = [c.strip() for c in self.character_focus.split(",") if c.strip()]
        char_params = CharacterFocusParams(mode="specific" if char_list else "all", characters=char_list)

        # 3. 组装 Custom Prompts
        custom_prompts = CustomPrompts()
        has_custom = False
        if self.narrative_focus == "custom" and self.custom_narrative_prompt:
            custom_prompts.narrative_focus = self.custom_narrative_prompt.strip()
            has_custom = True
        if self.style == "custom" and self.custom_style_prompt:
            custom_prompts.style = self.custom_style_prompt.strip()
            has_custom = True

        # 4. 组装 Control Params
        control = ControlParams(
            narrative_focus=self.narrative_focus,
            scope=scope,
            character_focus=char_params,
            style=self.style,
            perspective=self.perspective,  # type: ignore (Pydantic will validate literal)
            perspective_character=self.perspective_character,
            target_duration_minutes=self.target_duration_minutes,
            custom_prompts=custom_prompts if has_custom else None,
        )

        # 5. 组装 Service Config
        return NarrationServiceConfig(
            speaking_rate=self.speaking_rate,
            overflow_tolerance=self.overflow_tolerance,
            rag_top_k=self.rag_top_k,
            control_params=control,
        )


class LocalizeFormInput(BaseFormInput):
    target_lang: str = "en"
    speaking_rate: float = 2.5
    overflow_tolerance: float = -0.15


class DubbingFormInput(BaseFormInput):
    source_script_type: str = "master"
    template_name: str = "chinese_gemini_emotional"
    voice_name: str = "Puck"
    # [FIX 3] 默认值设为 None，以便在上层没传时使用默认逻辑，传了时使用传入值
    # 但为了兼容旧表单，这里保留默认值，但在 Builder 里做处理
    language_code: str = "cmn-CN"
    speed: float = 1.0


# ==============================================================================
# Part C: Payload Builder (Public API)
# ==============================================================================


class PayloadBuilder:
    @staticmethod
    def build_narration_payload(asset_name: str, asset_id: str, blueprint_path: str, raw_config: Dict) -> Dict:
        """
        构建 GENERATE_NARRATION Payload (V3 Strict)
        """
        # 1. 清洗输入 (Flat -> Typed Object)
        form_input = NarrationFormInput(**raw_config)

        # 2. 转换为云端契约对象 (在此处会触发 validate_custom_usage 等核心校验)
        cloud_config = form_input.to_cloud_contract()

        # 3. 输出最终 Payload 字典
        return {
            "asset_name": asset_name,
            "asset_id": asset_id,
            "blueprint_path": blueprint_path,
            "service_params": cloud_config.model_dump(exclude_none=True),
        }

    @staticmethod
    def build_localize_payload(master_path: str, blueprint_path: str, raw_config: Dict) -> Dict:
        cfg = LocalizeFormInput(**raw_config)
        return {
            "master_script_path": master_path,
            "blueprint_path": blueprint_path,
            "service_params": {
                "lang": "zh",
                "target_lang": cfg.target_lang,
                "model": "gemini-2.5-pro",
                "speaking_rate": cfg.speaking_rate,
                "overflow_tolerance": cfg.overflow_tolerance,
            },
        }

    @staticmethod
    def build_dubbing_payload(input_path: str, raw_config: Dict) -> Dict:
        """
        构建配音任务 Payload
        """
        cfg = DubbingFormInput(**raw_config)
        service_params = {"template_name": cfg.template_name}

        if "gemini" in cfg.template_name:
            service_params.update(
                {
                    "voice_name": cfg.voice_name,
                    "language_code": cfg.language_code,  # 这里直接使用 Config 中的值
                    "speaking_rate": cfg.speed,
                    "model_name": "gemini-2.5-pro-tts",
                }
            )
        else:
            service_params.update({"speed": cfg.speed})

        return {"input_narration_path": input_path, "service_params": service_params}
