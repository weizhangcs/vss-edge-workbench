import React from 'react';
import VOCAB from '../../config/vocabularies.json';

const SceneInspector = ({ data, onChange }) => {
    return (
        <>
            <div className="form-group">
                <label className="form-label required">场景标题</label>
                <input
                    type="text"
                    className="form-input"
                    placeholder="例如：初遇..."
                    value={data.label || ''}
                    onChange={(e) => onChange('label', e.target.value)}
                />
            </div>

            <div className="form-group">
                <label className="form-label">内容类型</label>
                <select
                    className="form-select"
                    value={data.scene_type || ''}
                    onChange={(e) => onChange('scene_type', e.target.value)}
                >
                    <option value="">-- 选择类型 --</option>
                    {VOCAB.scene_types.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                </select>
            </div>

            <div className="form-group">
                <label className="form-label">情绪氛围</label>
                <select
                    className="form-select"
                    value={data.mood || ''}
                    onChange={(e) => onChange('mood', e.target.value)}
                >
                    <option value="">-- 选择氛围 --</option>
                    {VOCAB.scene_moods.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                </select>
            </div>

            <div className="form-group">
                <label className="form-label">场景地点 (Location)</label>
                <input
                    type="text"
                    className="form-input"
                    placeholder="例如：咖啡馆、雨中街角、秘密基地..."
                    // 绑定到 Schema 字段 location
                    value={data.location || ''}
                    onChange={(e) => onChange('location', e.target.value)}
                />
            </div>

            <div className="form-group">
                <label className="form-label">剧情描述</label>
                <textarea
                    className="form-textarea"
                    placeholder="详细描述本场景发生的事件..."
                    value={data.description || ''}
                    onChange={(e) => onChange('description', e.target.value)}
                    style={{ minHeight: '80px' }}
                />
                <div className="char-count">{(data.description || '').length} / 200</div>
            </div>
        </>
    );
};

export default SceneInspector;