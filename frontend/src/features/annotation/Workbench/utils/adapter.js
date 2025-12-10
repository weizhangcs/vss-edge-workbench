import { TRACK_DEFINITIONS } from '../config/tracks';

// 定义工程字段集合 (属于 Context 的字段)
const CONTEXT_FIELDS = ['id', 'is_verified', 'origin', 'ai_meta'];

/**
 * [前端适配器] Backend Schema <-> Timeline Tracks
 */
export const transformToTracks = (annotationData) => {
    if (!annotationData) return [];

    const {
        scenes = [],
        dialogues = [],
        captions = [],
        highlights = []
    } = annotationData;

    // 通用转换函数
    const createTrack = (key, dataItems, effectId) => {
        const config = TRACK_DEFINITIONS[key];
        if (!config) return null;

        return {
            id: config.id,
            name: config.label,
            color: config.color,
            actions: dataItems.map(item => {
                // 1. 尝试提取嵌套结构
                const content = item.content || {};
                const context = item.context || {};

                // 2. 兼容扁平结构
                const isNested = !!item.content;
                const flatData = isNested ? { ...content, ...context } : { ...item };

                // 3. 映射显示标签 (Timeline 上显示的文字)
                let displayLabel = flatData.label || flatData.type;
                let displayText = flatData.text || flatData.content; // 读的时候 content -> text

                return {
                    id: item.id || context.id,
                    start: item.start,
                    end: item.end,
                    effectId: effectId,
                    data: {
                        label: displayLabel,
                        text: displayText, // 统一转为 text 供前端使用
                        ...flatData
                    }
                };
            })
        };
    };

    return [
        createTrack('scenes', scenes, 'scene'),
        createTrack('highlights', highlights, 'highlight'),
        createTrack('dialogues', dialogues, 'subtitle'),
        createTrack('captions', captions, 'caption')
    ].filter(Boolean);
};

/**
 * 反向转换器：Timeline Tracks -> Backend JSON (用于保存)
 */
export const transformFromTracks = (tracks, originalMeta) => {
    const scenesTrack = tracks.find(t => t.id === 'scenes');
    const dialoguesTrack = tracks.find(t => t.id === 'dialogues');
    const captionsTrack = tracks.find(t => t.id === 'captions');
    const highlightsTrack = tracks.find(t => t.id === 'highlights');

    // 辅助函数：将扁平 data 拆分为 content 和 context
    // [修改] 增加 type 参数，用于特殊字段映射
    const reconstructItem = (action, trackType) => {
        const flatData = action.data;
        const content = {};
        const context = {};

        context.id = action.id;

        Object.keys(flatData).forEach(key => {
            if (CONTEXT_FIELDS.includes(key)) {
                context[key] = flatData[key];
            } else {
                content[key] = flatData[key];
            }
        });

        // --- 特殊字段映射 (Fix Validation Error) ---

        // 1. Captions: text -> content
        if (trackType === 'captions') {
            if (content.text) {
                content.content = content.text;
                delete content.text; // 移除前端专用字段
            }
        }

        // 2. Dialogues: 确保 text 存在
        if (trackType === 'dialogues') {
            if (!content.text) content.text = "";
        }

        // 3. Highlights: 确保 type 存在
        if (trackType === 'highlights') {
            // 前端可能用 label 显示类型，保存时确保 type 字段正确
            if (!content.type && content.label) {
                content.type = content.label;
            }
        }

        return {
            id: action.id,
            start: action.start,
            end: action.end,
            content: content,
            context: context
        };
    };

    return {
        ...originalMeta,
        updated_at: new Date().toISOString(),

        scenes: scenesTrack ? scenesTrack.actions.map(a => reconstructItem(a, 'scenes')) : [],
        dialogues: dialoguesTrack ? dialoguesTrack.actions.map(a => reconstructItem(a, 'dialogues')) : [],

        // [关键] 传入 'captions' 类型标记，触发 text->content 映射
        captions: captionsTrack ? captionsTrack.actions.map(a => reconstructItem(a, 'captions')) : [],

        highlights: highlightsTrack ? highlightsTrack.actions.map(a => reconstructItem(a, 'highlights')) : []
    };
};