import React from 'react';

const DialogueInspector = ({ data, onChange }) => {
    return (
        <>
            <div className="form-group">
                <label className="form-label">角色 (Speaker)</label>
                <input
                    type="text"
                    className="form-input"
                    placeholder="Unknown"
                    value={data.speaker || ''}
                    onChange={(e) => onChange('speaker', e.target.value)}
                />
            </div>

            {/* [新增] 原始内容展示 (只读) */}
            {data.original_text && (
                <div className="bg-gray-100 p-2 rounded mb-4 border border-gray-200">
                    <div className="text-xs text-gray-500 mb-1">原始内容 / ASR识别:</div>
                    <Text type="secondary" className="text-sm font-mono break-all">
                        {data.original_text}
                    </Text>
                </div>
            )}

            <div className="form-group">
                <label className="form-label">字幕内容 (修订)</label>
                <textarea
                    className="form-textarea"
                    placeholder="输入对话内容..."
                    value={data.text || ''}
                    onChange={(e) => onChange('text', e.target.value)}
                    style={{ minHeight: '120px' }}
                />
            </div>
        </>
    );
};

export default DialogueInspector;