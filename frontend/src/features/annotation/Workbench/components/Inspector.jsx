import React from 'react';
import { Empty } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
// [核心] 引入独立样式文件
import './inspectors/inspector.css';

import SceneInspector from './inspectors/SceneInspector';
import HighlightInspector from './inspectors/HighlightInspector';
import DialogueInspector from './inspectors/DialogueInspector';
import CaptionInspector from './inspectors/CaptionInspector';

const Inspector = ({ action, track, onUpdate, onDelete }) => {
    if (!action || !track) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-gray-400 p-6 text-center select-none bg-white">
                <Empty description="未选中任何片段" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                <span className="text-xs mt-2 text-gray-400">点击时间轴上的色块进行编辑</span>
            </div>
        );
    }

    const handleTimeChange = (e, field) => {
        const val = parseFloat(e.target.value);
        if (!isNaN(val)) {
            onUpdate({ ...action, [field]: val });
        }
    };

    const handleDataChange = (field, value) => {
        onUpdate({
            ...action,
            data: { ...action.data, [field]: value }
        });
    };

    const renderSpecificInspector = () => {
        const props = { data: action.data, onChange: handleDataChange };
        switch (track.id) {
            case 'scenes': return <SceneInspector {...props} />;
            case 'highlights': return <HighlightInspector {...props} />;
            case 'captions': return <CaptionInspector {...props} />;
            case 'dialogues': return <DialogueInspector {...props} />;
            default: return null;
        }
    };

    return (
        <div className="inspector-form bg-white border-l border-gray-200">
            {/* 顶部 */}
            <div className="inspector-header">
                <div className="inspector-title">
                    <span>{track.name} 详情</span>
                    <span className="inspector-id-tag">{action.id.split('-').pop()}</span>
                </div>
            </div>

            {/* 内容区 */}
            <div className="inspector-body custom-scrollbar">
                {/* 1. 通用时间控制 */}
                <div className="form-row">
                    <div className="form-group">
                        <label className="form-label">开始 (s)</label>
                        <input
                            type="number"
                            className="form-input"
                            step="0.1"
                            value={Number(action.start).toFixed(2)}
                            onChange={(e) => handleTimeChange(e, 'start')}
                        />
                    </div>
                    <div className="form-group">
                        <label className="form-label">结束 (s)</label>
                        <input
                            type="number"
                            className="form-input"
                            step="0.1"
                            value={Number(action.end).toFixed(2)}
                            onChange={(e) => handleTimeChange(e, 'end')}
                        />
                    </div>
                </div>

                {/* 2. 专用表单 */}
                {renderSpecificInspector()}
            </div>

            {/* 底部 */}
            <div className="inspector-footer">
                <button className="btn-delete" onClick={() => onDelete(action.id)}>
                    <DeleteOutlined style={{ marginRight: 8 }} /> 删除此片段
                </button>
            </div>
        </div>
    );
};

export default Inspector;