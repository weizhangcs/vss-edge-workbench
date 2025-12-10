import React, { useEffect } from 'react';
import { Form, Button, Typography, Empty, Tag, Divider, Tooltip, message } from 'antd';
import {
    DeleteOutlined,
    CheckCircleOutlined,
    RobotOutlined,
    UserOutlined,
    SaveOutlined,
    ClockCircleOutlined,
    EditOutlined,
    AuditOutlined
} from '@ant-design/icons';
import dayjs from 'dayjs';
import './inspectors/inspector.css';

import SceneInspector from './inspectors/SceneInspector';
import HighlightInspector from './inspectors/HighlightInspector';
import DialogueInspector from './inspectors/DialogueInspector';
import CaptionInspector from './inspectors/CaptionInspector';

const Inspector = ({ action, track, onUpdate, onDelete }) => {
    const [form] = Form.useForm();

    // 1. 数据回填
    useEffect(() => {
        if (action) {
            const formData = {
                start: action.start,
                end: action.end,
                ...action.data
            };
            form.setFieldsValue(formData);
        }
    }, [action, form]);

    // [Clean] 样式完全移入 inspector.css
    if (!action || !track) {
        return (
            <div className="inspector-empty-state">
                <Empty description="未选中任何片段" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                <span className="inspector-empty-hint">点击时间轴上的色块进行编辑</span>
            </div>
        );
    }

    // --- 核心业务逻辑 (保持不变) ---

    const handleDataUpdate = (updates, isStaging = false) => {
        const currentData = action.data || {};
        const now = new Date().toISOString();

        const newData = {
            ...currentData,
            ...updates,
            modified_at: now
        };

        if (isStaging) {
            newData.is_verified = true;
            if (newData.origin !== 'human') {
                newData.origin = 'human';
            }
        } else {
            newData.is_verified = false;
            newData.origin = 'human';
        }

        const newStart = updates.start !== undefined ? updates.start : action.start;
        const newEnd = updates.end !== undefined ? updates.end : action.end;

        onUpdate({
            ...action,
            start: newStart,
            end: newEnd,
            data: newData
        });
    };

    const handleFieldChange = (field, value) => {
        handleDataUpdate({ [field]: value }, false);
    };

    const handleTimeChange = (e, field) => {
        const val = parseFloat(e.target.value);
        if (!isNaN(val)) {
            handleDataUpdate({ [field]: val }, false);
        }
    };

    const handleLocalStage = () => {
        handleDataUpdate({}, true);
        message.success("状态已更新");
    };

    const isAiOrigin = (origin) => {
        return ['ai_asr', 'ai_cv', 'ai_llm'].includes(origin);
    };

    // --- UI 渲染逻辑 ---

    const renderInspectorHeader = () => {
        const { origin, is_verified, ai_meta, modified_at } = action.data;

        let typeTag;
        if (isAiOrigin(origin)) {
            const confidence = ai_meta?.confidence ? Math.round(ai_meta.confidence * 100) : 100;
            typeTag = <Tag icon={<RobotOutlined />} color="blue">AI ({confidence}%)</Tag>;
        } else {
            typeTag = <Tag icon={<UserOutlined />} color="purple">人工修订</Tag>;
        }

        let statusTag;
        if (is_verified) {
            statusTag = <Tag icon={<CheckCircleOutlined />} color="success">已确认</Tag>;
        } else {
            statusTag = <Tag icon={<EditOutlined />} color="warning">待确认</Tag>;
        }

        const timeDisplay = modified_at ? dayjs(modified_at).format('YYYY-MM-DD HH:mm:ss') : 'N/A';

        return (
            <div className="inspector-header">
                <div className="inspector-title">
                    <span>{track.name}</span>
                    <Tooltip title={`最后修改: ${modified_at || '未修改'}`}>
                        <span style={{ fontSize: '12px', fontWeight: 'normal', color: 'var(--insp-text-secondary)' }}>
                            <ClockCircleOutlined /> {timeDisplay}
                        </span>
                    </Tooltip>
                </div>
                <div className="inspector-status-bar">
                    {typeTag}
                    {statusTag}
                </div>
            </div>
        );
    };

    const renderSpecificInspector = () => {
        const props = { data: action.data, onChange: handleFieldChange };
        switch (track.id) {
            case 'scenes': return <SceneInspector {...props} />;
            case 'highlights': return <HighlightInspector {...props} />;
            case 'captions': return <CaptionInspector {...props} />;
            case 'dialogues': return <DialogueInspector {...props} />;
            default: return null;
        }
    };

    const getActionButtonProps = () => {
        const { is_verified, origin } = action.data;
        const isAi = isAiOrigin(origin);

        if (is_verified) {
            return {
                text: isAi ? "审订通过" : "已暂存",
                icon: <CheckCircleOutlined />,
                type: "default",
                className: "text-green-600 border-green-600 font-semibold"
            };
        } else {
            return {
                text: isAi ? "确认审订" : "暂存修改",
                icon: isAi ? <AuditOutlined /> : <SaveOutlined />,
                type: "primary",
                className: ""
            };
        }
    };

    const btnProps = getActionButtonProps();

    return (
        <div className="inspector-form border-l border-gray-200">
            {/* 1. Header */}
            {renderInspectorHeader()}

            {/* 2. Scrollable Body */}
            <div className="inspector-body custom-scrollbar flex-1 overflow-y-auto">
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

                <Divider style={{ margin: '24px 0', borderColor: '#e2e8f0' }} />

                {renderSpecificInspector()}
            </div>

            {/* 3. Footer Action Area */}
            <div className="inspector-footer border-t border-gray-200">
                <div className="flex gap-3">
                    <Button
                        type={btnProps.type}
                        block
                        icon={btnProps.icon}
                        onClick={handleLocalStage}
                        className={btnProps.className}
                    >
                        {btnProps.text}
                    </Button>

                    {/* 修改后的删除按钮：结构一致，样式分离 */}
                    <Button
                        danger
                        block
                        icon={<DeleteOutlined />}
                        onClick={() => onDelete(action.id)}
                        className="inspector-btn-delete"
                    >
                        删除
                    </Button>
                </div>
            </div>
        </div>
    );
};

export default Inspector;