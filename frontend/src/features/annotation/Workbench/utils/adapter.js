import { TRACK_DEFINITIONS } from '../config/tracks';

/**
 * [前端适配器] Backend Schema <-> Timeline Tracks
 */
export const transformToTracks = (annotationData) => {
    if (!annotationData) return [];

    const { scenes = [], dialogues = [], captions = [], highlights = [] } = annotationData;

    // 通用转换函数：根据配置生成轨道
    const createTrack = (key, dataItems, effectId) => {
        const config = TRACK_DEFINITIONS[key];
        if (!config) return null;

        return {
            id: config.id,
            name: config.label,
            color: config.color,
            actions: dataItems.map(item => ({
                id: item.id,
                start: item.start,
                end: item.end,
                effectId: effectId,
                data: {
                    // 动态映射显示标签
                    label: item.label || item.type, // scene/highlight 用 label/type
                    text: item.text || item.content, // dialogue/caption 用 text/content
                    ...item
                }
            }))
        };
    };

    return [
        createTrack('scenes', scenes, 'scene'),
        createTrack('highlights', highlights, 'highlight'),
        createTrack('dialogues', dialogues, 'subtitle'),
        createTrack('captions', captions, 'caption')
    ].filter(Boolean); // 过滤掉无效配置
};

// ... transformFromTracks 保持不变 (因为它主要处理反向的数据提取逻辑，暂时无需高度抽象) ...
export const transformFromTracks = (tracks, originalMeta) => {
    // ... (保持原样)
    const scenesTrack = tracks.find(t => t.id === 'scenes');
    const dialoguesTrack = tracks.find(t => t.id === 'dialogues');
    const captionsTrack = tracks.find(t => t.id === 'captions');
    const highlightsTrack = tracks.find(t => t.id === 'highlights');

    const extractData = (action) => {
        const { label, text, ...rest } = action.data;
        return {
            ...rest,
            id: action.id,
            start: action.start,
            end: action.end
        };
    };

    return {
        ...originalMeta,
        updated_at: new Date().toISOString(),

        scenes: scenesTrack ? scenesTrack.actions.map(a => ({
            ...extractData(a),
            label: a.data.label || 'New Scene'
        })) : [],

        highlights: highlightsTrack ? highlightsTrack.actions.map(a => ({
            ...extractData(a),
            type: a.data.label || a.data.type || 'Other'
        })) : [],

        dialogues: dialoguesTrack ? dialoguesTrack.actions.map(a => ({
            ...extractData(a),
            text: a.data.text || '',
            speaker: a.data.speaker || 'Unknown'
        })) : [],

        captions: captionsTrack ? captionsTrack.actions.map(a => ({
            ...extractData(a),
            content: a.data.text || ''
        })) : []
    };
};