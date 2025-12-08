/**
 * 将秒数转换为 VTT 时间格式 (HH:MM:SS.mmm)
 */
const formatVTTTime = (seconds) => {
    const date = new Date(0);
    date.setMilliseconds(seconds * 1000);
    // 截取 ISOString 的 HH:MM:SS.mmm 部分
    return date.toISOString().substr(11, 12);
};

/**
 * 将轨道数据转换为 WebVTT Blob URL
 * @param {Array} tracks - 所有的轨道数据
 * @returns {string|null} - Blob URL
 */
export const generateVTT = (tracks) => {
    let cues = [];

    // 1. 提取 Dialogues (字幕)
    const dialogTrack = tracks.find(t => t.id === 'dialogues');
    if (dialogTrack) {
        cues = cues.concat(dialogTrack.actions.map(a => ({
            start: a.start,
            end: a.end,
            // 格式: "角色名: 台词内容"
            text: a.data.speaker && a.data.speaker !== 'Unknown'
                ? `${a.data.speaker}：${a.data.text}`
                : a.data.text
        })));
    }

    // 2. 提取 Captions (提词)
    const captionTrack = tracks.find(t => t.id === 'captions');
    if (captionTrack) {
        cues = cues.concat(captionTrack.actions.map(a => ({
            start: a.start,
            end: a.end,
            // 格式: "[提词] 内容" (用方括号区分，或者加个颜色样式)
            text: `[提词] ${a.data.text}`
        })));
    }

    // 3. 按时间排序
    cues.sort((a, b) => a.start - b.start);

    // 4. 拼接 VTT 内容
    let content = "WEBVTT\n\n";
    cues.forEach((cue, index) => {
        // VTT 块结构:
        // 1
        // 00:00:01.000 --> 00:00:04.000
        // 内容
        content += `${index + 1}\n`;
        content += `${formatVTTTime(cue.start)} --> ${formatVTTTime(cue.end)}\n`;
        content += `${cue.text}\n\n`;
    });

    // 5. 生成 Blob URL
    const blob = new Blob([content], { type: 'text/vtt' });
    return URL.createObjectURL(blob);
};