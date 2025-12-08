import React from 'react';

const CaptionInspector = ({ data, onChange }) => {
    return (
        <>
            <div className="form-group">
                <label className="form-label">提词分类</label>
                <input
                    type="text"
                    className="form-input"
                    placeholder="例如：地点、时间..."
                    value={data.category || ''}
                    onChange={(e) => onChange('category', e.target.value)}
                />
            </div>

            <div className="form-group">
                <label className="form-label">OCR 内容</label>
                <textarea
                    className="form-textarea"
                    placeholder="画面上的文字..."
                    value={data.text || ''}
                    onChange={(e) => onChange('text', e.target.value)}
                />
            </div>
        </>
    );
};

export default CaptionInspector;