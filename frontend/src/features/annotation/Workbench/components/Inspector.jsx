import React, { useEffect } from 'react';
import { Form, Input, InputNumber, Button, Typography, Empty, Select, Divider } from 'antd';
import { ClockCircleOutlined, UserOutlined, FontSizeOutlined, TagOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;
const { TextArea } = Input;

const Inspector = ({ action, track, onUpdate, onDelete }) => {
    const [form] = Form.useForm();

    // 当选中的对象变化时，重置表单
    useEffect(() => {
        if (action) {
            form.setFieldsValue({
                start: action.start,
                end: action.end,
                // 兼容不同类型的数据字段
                text: action.data.text || action.data.label || '',
                speaker: action.data.speaker || '',
            });
        }
    }, [action, form]);

    if (!action || !track) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-gray-400 p-6 text-center">
                <Empty description="未选中任何片段" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                <span className="text-xs mt-2">点击时间轴上的色块进行编辑</span>
            </div>
        );
    }

    // 处理表单变更 -> 实时更新父组件 State
    const handleValuesChange = (changedValues, allValues) => {
        const newData = { ...action.data };

        // 根据轨道类型更新不同字段
        if (track.id === 'scenes') {
            newData.label = allValues.text;
        } else {
            newData.text = allValues.text;
            newData.speaker = allValues.speaker;
        }

        onUpdate({
            ...action,
            start: allValues.start,
            end: allValues.end,
            data: newData
        });
    };

    return (
        <div className="flex flex-col h-full">
            <div className="p-4 border-b border-gray-200 bg-gray-50">
                <Title level={5} style={{ margin: 0 }}>
                    {track.name === 'SCENES' ? '场景属性' : '字幕属性'}
                </Title>
                <Text type="secondary" className="text-xs">ID: {action.id}</Text>
            </div>

            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                <Form
                    form={form}
                    layout="vertical"
                    onValuesChange={handleValuesChange}
                    size="small"
                >
                    {/* 1. 时间控制 */}
                    <div className="grid grid-cols-2 gap-4 mb-4">
                        <Form.Item label="开始时间 (s)" name="start">
                            <InputNumber step={0.1} className="w-full" prefix={<ClockCircleOutlined className="text-gray-400"/>} />
                        </Form.Item>
                        <Form.Item label="结束时间 (s)" name="end">
                            <InputNumber step={0.1} className="w-full" prefix={<ClockCircleOutlined className="text-gray-400"/>} />
                        </Form.Item>
                    </div>

                    <Divider />

                    {/* 2. 字幕/角色特有字段 */}
                    {track.id !== 'scenes' && (
                        <Form.Item label="角色 (Speaker)" name="speaker">
                            <Input prefix={<UserOutlined />} placeholder="输入角色名..." />
                        </Form.Item>
                    )}

                    {/* 3. 核心内容 (文本或标签) */}
                    <Form.Item
                        label={track.id === 'scenes' ? "场景标签" : "字幕内容"}
                        name="text"
                    >
                        {track.id === 'scenes' ? (
                            <Input prefix={<TagOutlined />} />
                        ) : (
                            <TextArea rows={4} showCount maxLength={200} placeholder="输入字幕内容..." />
                        )}
                    </Form.Item>
                </Form>
            </div>

            <div className="p-4 border-t border-gray-200 bg-gray-50">
                <Button danger block onClick={() => onDelete(action.id)}>
                    删除此片段
                </Button>
            </div>
        </div>
    );
};

export default Inspector;