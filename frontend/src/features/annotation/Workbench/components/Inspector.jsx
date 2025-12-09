import React, { useEffect } from 'react';
import { Form, InputNumber, Button, Typography, Empty, Space, Tag } from 'antd';
import { DeleteOutlined, ClockCircleOutlined, CheckCircleOutlined, RobotOutlined, UserOutlined } from '@ant-design/icons'; // [新增图标]
import './inspectors/inspector.css';

import SceneInspector from './inspectors/SceneInspector';
import HighlightInspector from './inspectors/HighlightInspector';
import DialogueInspector from './inspectors/DialogueInspector';
import CaptionInspector from './inspectors/CaptionInspector';

const { Title } = Typography;

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

    if (!action || !track) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-gray-400 p-6 text-center select-none bg-white">
                <Empty description="未选中任何片段" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                <span className="text-xs mt-2 text-gray-400">点击时间轴上的色块进行编辑</span>
            </div>
        );
    }

    // [新增] 状态标签渲染组件
    const renderStatusTag = () => {
        const { origin, is_verified, ai_meta } = action.data;

        // 1. 人工创建/修改
        if (origin === 'human' || origin === 'HUMAN') {
            return <Tag icon={<UserOutlined />} color="purple">人工修订</Tag>;
        }

        // 2. AI 生成且已确认
        if (is_verified) {
            return <Tag icon={<CheckCircleOutlined />} color="success">AI (已确认)</Tag>;
        }

        // 3. AI 生成 (待确认)
        // 根据置信度显示不同颜色
        const confidence = ai_meta?.confidence ?? 1.0;
        const color = confidence > 0.8 ? "cyan" : (confidence > 0.5 ? "orange" : "red");

        return (
            <Tag icon={<RobotOutlined />} color={color}>
                AI预想 ({Math.round(confidence * 100)}%)
            </Tag>
        );
    };

    // 通用更新函数
    const handleTimeChange = (e, field) => {
        const val = parseFloat(e.target.value);
        if (!isNaN(val)) {
            // 时间改变也视为“人工修订”
            handleDataUpdate({ [field]: val }, true);
        }
    };

    // [修改] 统一的数据更新入口
    // forceHuman: 是否强制标记为人工修改
    const handleDataUpdate = (updates, forceHuman = false) => {
        const newData = { ...action.data, ...updates };

        // [核心逻辑] 只要用户修改了数据，就更新状态
        // 策略：一旦修改，就被视为“人工介入”，is_verified 必为 true
        // 如果是大幅修改内容，origin 改为 human；如果是微调，origin 可保持 AI 但状态变 verified
        // 这里简化逻辑：只要动了，就是 Human Verified
        if (forceHuman || !newData.is_verified) {
            newData.is_verified = true;
            // 可选：如果希望保留 "这是AI底稿，但我改过了" 的状态，可以不改 origin，只改 is_verified
            // 这里按照您的要求 "更新成用户修改"，我们将 origin 设为 human
            newData.origin = 'human';
        }

        // 注意：onUpdate 接收的是完整的 action 对象
        // 如果 updates 里包含 start/end，需要提取出来传给 action 根属性
        const newStart = updates.start !== undefined ? updates.start : action.start;
        const newEnd = updates.end !== undefined ? updates.end : action.end;

        onUpdate({
            ...action,
            start: newStart,
            end: newEnd,
            data: newData
        });
    };

    // 子组件回调适配
    const onFormChange = (field, value) => {
        handleDataUpdate({ [field]: value });
    };

    const renderSpecificInspector = () => {
        const props = { data: action.data, onChange: onFormChange };
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
            {/* Header */}
            <div className="inspector-header">
                <div className="inspector-title">
                    <span>{track.name} 详情</span>
                    {/* [修改] 渲染动态状态标签 */}
                    {renderStatusTag()}
                </div>
            </div>

            {/* Body */}
            <div className="inspector-body custom-scrollbar">
                {/* 1. Time Controls */}
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

                {/* 2. Specific Form */}
                {renderSpecificInspector()}
            </div>

            {/* Footer */}
            <div className="inspector-footer">
                <div className="flex gap-2">
                    {/* [新增] 快速确认按钮 (如果只是想确认AI是对的，不改内容) */}
                    {!action.data.is_verified && (
                        <Button
                            block
                            icon={<CheckCircleOutlined />}
                            onClick={() => handleDataUpdate({}, true)}
                            style={{ color: '#10b981', borderColor: '#10b981' }}
                        >
                            确认无误
                        </Button>
                    )}
                    <Button danger block icon={<DeleteOutlined />} onClick={() => onDelete(action.id)}>
                        删除
                    </Button>
                </div>
            </div>
        </div>
    );
};

export default Inspector;