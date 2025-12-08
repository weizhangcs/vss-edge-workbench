# apps/workflow/annotation/schemas.py

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

# ==========================================
# 1. 受控词表 (Controlled Vocabularies)
# 基于 v2.6 文档及最新业务需求定义
# ==========================================


class SceneType(str, Enum):
    """场景内容类型"""

    DIALOGUE_HEAVY = "Dialogue_Heavy"  # 对话驱动
    ACTION_DRIVEN = "Action_Driven"  # 动作驱动
    INTERNAL_MONOLOGUE = "Internal_Monologue"  # 内心独白
    VISUAL_STORYTELLING = "Visual_Storytelling"  # 视觉叙事


class SceneMood(str, Enum):
    """场景氛围"""

    ROMANTIC = "Romantic"  # 浪漫
    WARM = "Warm"  # 温馨
    JOYFUL = "Joyful"  # 喜悦
    CALM = "Calm"  # 平静
    TENSE = "Tense"  # 紧张
    SUSPENSEFUL = "Suspenseful"  # 悬疑
    SAD = "Sad"  # 悲伤
    ANGRY = "Angry"  # 愤怒
    CONFRONTATIONAL = "Confrontational"  # 冲突
    FEARFUL = "Fearful"  # 恐惧
    OPPRESSIVE = "Oppressive"  # 压抑
    EERIE = "Eerie"  # 诡异


class HighlightType(str, Enum):
    """高光类型"""

    ACTION = "Action"  # 动作片段
    EMOTIONAL = "Emotional"  # 情感片段
    DIALOGUE = "Dialogue"  # 对话片段
    SUSPENSE = "Suspense"  # 悬念片段
    INFORMATION = "Information"  # 信息片段
    HUMOR = "Humor"  # 幽默片段
    OTHER = "Other"  # [核心修复] 补回 "其他" 选项


class HighlightMood(str, Enum):
    """高光情绪 (新增)"""

    EXCITING = "Exciting"  # 燃
    SATISFYING = "Satisfying"  # 爽
    HEART_WRENCHING = "Heart-wrenching"  # 虐
    SWEET = "Sweet"  # 甜
    HILARIOUS = "Hilarious"  # 爆笑
    TERRIFYING = "Terrifying"  # 恐怖
    HEALING = "Healing"  # 治愈
    TOUCHING = "Touching"  # 感动
    TENSE = "Tense"  # 紧张


class DataOrigin(str, Enum):
    HUMAN = "human"
    AI_ASR = "ai_asr"
    AI_LLM = "ai_llm"
    AI_CV = "ai_cv"
    AI_OCR = "ai_ocr"


# ==========================================
# 2. 基础组件 (Timeline Items)
# ==========================================


# ==========================================
# 2. 基础组件 (Base Components)
# ==========================================


class AiMetadata(BaseModel):
    """
    [AI 元数据]
    作为组合对象嵌入到各个 Item 中，记录推理痕迹。
    """

    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="AI 置信度 (0.0-1.0)")
    reasoning: Optional[str] = Field(None, description="推理依据/思维链")
    model_version: Optional[str] = Field(None, description="模型版本标识")


class TimelineItemBase(BaseModel):
    """
    [时间轴对象基类]
    所有轨道上的数据块都必须包含这些通用字段。
    """

    id: str = Field(..., description="UUID")
    start: float = Field(..., description="开始时间 (秒)")
    end: float = Field(..., description="结束时间 (秒)")

    # 状态与来源
    is_verified: bool = Field(default=False, description="是否经过人工校验")
    origin: DataOrigin = Field(default=DataOrigin.HUMAN, description="数据来源")

    # AI 扩展槽 (组合模式)
    ai_meta: Optional[AiMetadata] = None


# ==========================================
# 3. 业务实体 (Track Items)
# ==========================================


class DialogueItem(TimelineItemBase):
    """
    [轨道 1: 对话/台词] (SubEditor 核心产物)
    听觉源数据。
    """

    text: str = Field(..., description="字幕文本内容")
    speaker: str = Field(default="Unknown", description="角色名 (关联 Project.character_list)")
    original_text: Optional[str] = Field(None, description="原文/翻译对照")


class CaptionItem(TimelineItemBase):
    """
    [轨道 2: 提词/花字] (OCR/人工标注)
    视觉源数据。出现在画面上的文字信息。
    """

    content: str = Field(..., description="画面上的文字内容")
    category: Optional[str] = Field(None, description="类别 (如: 人名介绍, 地点提示, 时间流逝)")


class HighlightItem(TimelineItemBase):
    """
    [轨道 3: 高光片段] (Layer 3 产物)
    评价性数据。用于剪辑二创。
    """

    class HighlightItem(TimelineItemBase):
        """
        [轨道 3: 高光片段] (Layer 3 产物)
        评价性数据。用于剪辑二创。
        """

        type: HighlightType = Field(default=HighlightType.OTHER, description="高光类型")

        # [核心修复] 将 SceneMood 改为 HighlightMood
        mood: Optional[HighlightMood] = None

        description: Optional[str] = Field(None, description="高光简要描述")


class SceneItem(TimelineItemBase):
    """
    [轨道 4: 叙事场景] (Layer 2 产物)
    结构化/语义化数据。
    """

    label: str = Field(..., description="场景简短标题")
    description: Optional[str] = Field(None, description="详细剧情描述")

    # 核心语义属性 (Optional 以适应 AI 预生成的不确定性)
    mood: Optional[SceneMood] = None
    scene_type: Optional[SceneType] = None
    location: Optional[str] = None
    character_dynamics: Optional[str] = None
    keyframe_url: Optional[str] = None


# ==========================================
# 4. 存储与交换模型 (Storage Models)
# ==========================================


class MediaAnnotation(BaseModel):
    """
    [原子单元]
    Workbench 直接加载和保存的对象。
    对应数据库中一个 Media 的标注产出物 (通常存为 JSON 文件)。
    """

    # 物理关联
    media_id: str = Field(..., description="关联的 Media UUID")
    file_name: str = Field(..., description="物理文件名 (如 ep01.mp4)")
    source_path: str = Field(..., description="物理文件相对路径")

    # 核心数据 (四条轨道)
    scenes: List[SceneItem] = []  # 场景轨
    dialogues: List[DialogueItem] = []  # 对话轨
    captions: List[CaptionItem] = []  # 提词轨 (新增)
    highlights: List[HighlightItem] = []  # 高光轨 (新增)

    # 元数据
    duration: float = 0.0
    updated_at: datetime = Field(default_factory=datetime.now)
    version: str = "1.1"


class ProjectBlueprint(BaseModel):
    """
    [聚合体]
    整个 Project 的最终蓝图，用于 Inference 流程。
    """

    project_id: str
    asset_id: str
    project_name: str

    # 全局上下文 (标签云来源)
    global_character_list: List[str] = Field(default_factory=list)

    # 单元集合 (Key 可以是 media_id)
    annotations: Dict[str, MediaAnnotation] = {}
