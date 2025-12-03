// apps/workflow/static/creative/js/director/config.js

(function() {
    window.DirectorConfig = window.DirectorConfig || {};

    const TYPES = {
        VALUE: 'value', // 导演模式只许单选
        CONST: 'const'
    };
    window.DirectorConfig.TYPES = TYPES;

    // 复用语速知识库
    const SPEAKING_RATES = {
        zh: { unit: "字/秒", options: [{ label: "慢 (3.5)", value: 3.5 }, { label: "标准 (4.2)", value: 4.2 }, { label: "快 (5.0)", value: 5.0 }], default: 4.2 },
        en: { unit: "词/秒", options: [{ label: "慢 (2.2)", value: 2.2 }, { label: "标准 (2.5)", value: 2.5 }, { label: "快 (3.0)", value: 3.0 }], default: 2.5 },
        fr: { unit: "词/秒", options: [{ label: "慢 (2.2)", value: 2.2 }, { label: "标准 (2.6)", value: 2.6 }, { label: "快 (3.1)", value: 3.1 }], default: 2.6 }
    };

    window.DirectorConfig.SCHEMA = {
        narration: {
            narrative_focus: {
                label: "叙事焦点", group: "content", widget: "segmented", // 改为分段器
                type: TYPES.VALUE, // 单选
                options: [
                    { label: "情感递进", value: "romantic_progression" },
                    { label: "商业成功", value: "business_success" },
                    { label: "悬疑揭秘", value: "suspense_reveal" },
                    { label: "人物成长", value: "character_growth" },
                    { label: "复仇爽文", value: "revenge_plot" }
                ],
                desc: "决定故事的核心走向"
            },
            style: {
                label: "解说风格", group: "content", widget: "segmented",
                type: TYPES.VALUE, // 单选
                options: [
                    { label: "幽默", value: "humorous" },
                    { label: "严肃", value: "serious" },
                    { label: "悬疑", value: "suspense" },
                    { label: "毒舌", value: "sarcastic" },
                    { label: "深情", value: "emotional" },
                    { label: "治愈", value: "healing" }
                ],
                desc: "决定文案的情感基调"
            },
            perspective: {
                label: "叙述视角", group: "content", widget: "segmented",
                type: TYPES.VALUE,
                options: [
                    { label: "上帝视角 (默认)", value: "third_person" },
                    { label: "第一人称", value: "first_person" }
                ]
            },

            perspective_character: {
                label: "角色名称", group: "content", widget: "input",
                type: TYPES.VALUE,
                desc: "指定第一人称的角色（如：车小小）"
            },

            scope: {
                label: "剧情范围", group: "content", widget: "segmented",
                type: TYPES.VALUE,
                options: [
                    { label: "全剧模式", value: "full" },
                    { label: "选集模式", value: "episode_range" }
                ]
            },
            // [新增] 起始集
            scope_start: {
                label: "起始集数", group: "content", widget: "number",
                type: TYPES.VALUE,
                min: 1, max: 100, step: 1,
                desc: "开始集数 (包含)"
            },
            // [新增] 结束集
            scope_end: {
                label: "结束集数", group: "content", widget: "number",
                type: TYPES.VALUE,
                min: 1, max: 100, step: 1,
                desc: "结束集数 (包含)"
            },
            target_duration_minutes: {
                label: "目标时长", group: "constraints", widget: "slider",
                type: TYPES.VALUE,
                min: 1, max: 20, step: 1, unit: "分",
                desc: "用户期望的视频物理时长"
            },
            speaking_rate: {
                label: "基准语速", group: "constraints", widget: "speed_preset",
                type: TYPES.VALUE,
                options_map: SPEAKING_RATES
            },
            rag_top_k: {
                label: "RAG 检索量", group: "constraints", widget: "slider",
                type: TYPES.VALUE, // 降级为单值滑块
                min: 10, max: 100, step: 10, unit: "条",
                desc: "上下文检索数量"
            },
            overflow_tolerance: {
                label: "时长容忍度", group: "constraints", widget: "segmented",
                type: TYPES.VALUE,
                options: [
                    { label: "严格 (-15%)", value: -0.15 },
                    { label: "精准 (0%)", value: 0.0 },
                    { label: "宽松 (+15%)", value: 0.15 }
                ]
            }
        },
        localize: {
            target_lang: {
                label: "目标语言", group: "content", widget: "segmented", // 改为单选
                type: TYPES.VALUE,
                options: [
                    { label: "英语", value: "en" },
                    { label: "法语", value: "fr" }
                ],
                desc: "目标市场"
            },
            speaking_rate: {
                label: "目标语速", group: "constraints", widget: "speed_preset",
                type: TYPES.VALUE,
                options_map: SPEAKING_RATES
            },
            overflow_tolerance: {
                label: "译文时长容忍", group: "constraints", widget: "segmented",
                type: TYPES.VALUE,
                options: [{ label: "严格 (-15%)", value: -0.15 }, { label: "精准 (0%)", value: 0.0 }]
            }
        },
        audio: {
            template_name: {
                label: "配音引擎", group: "content", widget: "const_display",
                type: TYPES.VALUE,
                options: [{ label: "Gemini Emotional TTS", value: "chinese_gemini_emotional" }]
            },
            voice_name: {
                label: "音色选择", group: "content", widget: "segmented", // 改为单选
                type: TYPES.VALUE,
                options: [
                    { label: "Puck (男 | 活泼幽默)", value: "Puck" },
                    { label: "Charon (男 | 深沉磁性)", value: "Charon" },
                    { label: "Kore (女 | 温柔治愈)", value: "Kore" },
                    { label: "Fenrir (男 | 激昂有力)", value: "Fenrir" },
                    { label: "Aoede (女 | 明亮自信)", value: "Aoede" },
                    { label: "Zephyr (女 | 平和知性)", value: "Zephyr" },
                    { label: "Orus (男 | 稳重叙述)", value: "Orus" },
                    { label: "Leda (女 | 亲切自然)", value: "Leda" }
                ]
            },
            speed: {
                label: "朗读倍速", group: "constraints", widget: "slider",
                type: TYPES.VALUE,
                min: 0.8, max: 1.5, step: 0.1, unit: "x"
            }
        },
        edit: {
            lang: {
                label: "剪辑字幕语言", group: "content", widget: "const_display",
                type: TYPES.VALUE,
                options: [{ label: "中文 (默认)", value: "zh" }]
            }
        }
    };

    // 默认值也只保留单值
    window.DirectorConfig.DEFAULTS = {
        narration: {
            narrative_focus: { type: TYPES.VALUE, value: 'romantic_progression' },
            style: { type: TYPES.VALUE, value: 'humorous' },
            perspective: { type: TYPES.VALUE, value: 'third_person' },
            perspective_character: { type: TYPES.VALUE, value: '' }, // 默认为空
            scope: { type: TYPES.VALUE, value: 'full' },
            scope_start: { type: TYPES.VALUE, value: 1 },
            scope_end: { type: TYPES.VALUE, value: 10 },
            target_duration_minutes: { type: TYPES.VALUE, value: 5 },
            speaking_rate: { type: TYPES.VALUE, value: 4.2 },
            rag_top_k: { type: TYPES.VALUE, value: 50 },
            overflow_tolerance: { type: TYPES.VALUE, value: 0.0 }
        },
        localize: {
            target_lang: { type: TYPES.VALUE, value: 'en' },
            speaking_rate: { type: TYPES.VALUE, value: 2.5 },
            overflow_tolerance: { type: TYPES.VALUE, value: 0.0 }
        },
        audio: {
            template_name: { type: TYPES.VALUE, value: 'chinese_gemini_emotional' },
            voice_name: { type: TYPES.VALUE, value: 'Puck' },
            speed: { type: TYPES.VALUE, value: 1.0 }
        },
        edit: {
            lang: { type: TYPES.VALUE, value: 'zh' }
        }
    };
})();