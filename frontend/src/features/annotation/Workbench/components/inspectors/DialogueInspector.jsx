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

            <div className="form-group">
                <label className="form-label">字幕内容</label>
                <textarea
                    className="form-textarea"
                    placeholder="输入对话内容..."
                    value={data.text || ''}
                    onChange={(e) => onChange('text', e.target.value)}
                />
            </div>
        </>
    );
};

export default DialogueInspector;