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

            {/* ASR 原始内容展示 (只读区域) */}
            {data.original_text && (
                <div style={{
                    backgroundColor: '#f8fafc', // 接近 var(--insp-bg-body)
                    padding: '12px',
                    borderRadius: 'var(--insp-input-radius)',
                    marginBottom: '24px',
                    border: '1px solid var(--insp-border-color)'
                }}>
                    <div style={{
                        fontSize: '12px',
                        color: 'var(--insp-text-secondary)',
                        marginBottom: '6px',
                        fontWeight: 600
                    }}>
                        原始内容 / ASR识别:
                    </div>
                    <div style={{
                        fontSize: '13px',
                        fontFamily: 'SF Mono, Menlo, monospace',
                        color: 'var(--insp-text-primary)',
                        lineHeight: 1.5,
                        wordBreak: 'break-all'
                    }}>
                        {data.original_text}
                    </div>
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