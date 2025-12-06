/**
 * 将 SRT 时间格式 (00:00:01,500) 转换为秒数 (1.5)
 */
const parseTime = (timeStr) => {
    if (!timeStr) return 0;
    const [time, ms] = timeStr.split(',');
    const [hours, minutes, seconds] = time.split(':').map(Number);
    return hours * 3600 + minutes * 60 + seconds + parseInt(ms, 10) / 1000;
};

/**
 * 解析 SRT 文件内容为 Timeline Actions
 * @param {string} srtContent - SRT 文件原始内容
 * @returns {Array} actions - 符合 SimpleTimeline 格式的数据块列表
 */
export const parseSRT = (srtContent) => {
    const actions = [];
    // 统一换行符并按空行分割字幕块
    const blocks = srtContent.replace(/\r\n/g, '\n').split('\n\n');

    blocks.forEach((block, index) => {
        const lines = block.trim().split('\n');
        if (lines.length < 3) return; // 忽略无效块

        // 第一行是序号，第二行是时间轴，第三行及以后是内容
        // 格式: 00:00:01,000 --> 00:00:04,000
        const timeLine = lines[1];
        const [startStr, endStr] = timeLine.split(' --> ');

        if (!startStr || !endStr) return;

        // 提取文本内容 (可能有多行)
        const text = lines.slice(2).join('\n');

        // 简单的角色提取逻辑 (假设格式为 "Speaker: Content")
        let speaker = 'Unknown';
        let content = text;

        if (text.includes('：') || text.includes(':')) {
            const splitIndex = Math.max(text.indexOf('：'), text.indexOf(':'));
            speaker = text.substring(0, splitIndex).trim();
            content = text.substring(splitIndex + 1).trim();
        }

        actions.push({
            id: `sub-${index}`, // 唯一 ID
            start: parseTime(startStr),
            end: parseTime(endStr),
            effectId: 'subtitle', // 标识为字幕类型
            data: {
                text: content,
                speaker: speaker,
                originalText: text // 保留原始文本备用
            }
        });
    });

    return actions;
};