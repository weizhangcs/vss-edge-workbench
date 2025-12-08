export const transformToTracks = (annotationData) => {
    // 1. 基础防御
    if (!annotationData) {
        console.warn("[Adapter] No data provided");
        return [];
    }

    // 2. 解构并给予默认值
    const {
        scenes = [],
        dialogues = [],
        captions = [],
        highlights = []
    } = annotationData;

    console.log(`[Adapter] Processing: ${scenes.length} scenes, ${dialogues.length} dialogues`);

    return [
        // 1. 场景轨
        {
            id: 'scenes',
            name: 'SCENES',
            color: '#d8b4fe',
            actions: Array.isArray(scenes) ? scenes.map(item => ({
                id: item.id,
                start: item.start,
                end: item.end,
                effectId: 'scene',
                data: {
                    label: item.label || '未命名',
                    ...item
                }
            })) : []
        },
        // 2. 字幕轨
        {
            id: 'dialogues',
            name: 'DIALOG',
            color: '#bae7ff',
            actions: Array.isArray(dialogues) ? dialogues.map(item => ({
                id: item.id,
                start: item.start,
                end: item.end,
                effectId: 'subtitle',
                data: {
                    text: item.text || '',
                    speaker: item.speaker || 'Unknown',
                    ...item
                }
            })) : []
        }
        // 暂时先不加 captions 和 highlights，确保核心轨道能出来
    ];
};

export const transformFromTracks = (tracks, originalMeta) => {
    // ... (保持之前的保存逻辑不变)
    const scenesTrack = tracks.find(t => t.id === 'scenes');
    const dialoguesTrack = tracks.find(t => t.id === 'dialogues');

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
        dialogues: dialoguesTrack ? dialoguesTrack.actions.map(a => ({
            ...extractData(a),
            text: a.data.text || '',
            speaker: a.data.speaker || 'Unknown'
        })) : []
    };
};