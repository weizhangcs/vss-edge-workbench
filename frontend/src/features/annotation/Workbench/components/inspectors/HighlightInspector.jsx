import React from 'react';
import VOCAB from '../../config/vocabularies.json';

const HighlightInspector = ({ data, onChange }) => {
    return (
        <>
            <div className="form-group">
                <label className="form-label required">高光类型</label>
                <select
                    className="form-select"
                    value={data.type || ''}
                    onChange={(e) => {
                        onChange('type', e.target.value);
                        // 自动同步 label，方便时间轴显示
                        onChange('label', e.target.value);
                    }}
                >
                    {VOCAB.highlight_types.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                </select>
            </div>

            <div className="form-group">
                <label className="form-label">情绪体验</label>
                <select
                    className="form-select"
                    value={data.mood || ''}
                    onChange={(e) => onChange('mood', e.target.value)}
                >
                    <option value="">-- 选择情绪 --</option>
                    {VOCAB.highlight_moods.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                </select>
            </div>

            <div className="form-group">
                <label className="form-label">高光描述</label>
                <textarea
                    className="form-textarea"
                    placeholder="描述高光内容..."
                    value={data.description || ''}
                    onChange={(e) => onChange('description', e.target.value)}
                    style={{ minHeight: '80px' }}
                />
            </div>
        </>
    );
};

export default HighlightInspector;