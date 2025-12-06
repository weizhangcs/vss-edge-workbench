// frontend/src/features/annotation/components/TaskTable.jsx
import React from 'react';
import { Table, Tag, Button, Space, Select, Card, Typography } from 'antd';
import { PlayCircleOutlined, SyncOutlined } from '@ant-design/icons';

const { Text } = Typography;

const TaskTable = ({
                       title,
                       dataSource,
                       pagination,
                       filter,
                       onFilterChange,
                       onPageChange,
                       statusOptions
                   }) => {

    // 1. 定义表格列
    const columns = [
        {
            title: '序号',
            dataIndex: 'sequence',
            key: 'sequence',
            width: 80,
        },
        {
            title: '资产标题',
            dataIndex: 'title',
            key: 'title',
            render: (text) => <span className="font-medium">{text}</span>,
        },
        {
            title: '状态',
            dataIndex: 'status',
            key: 'status',
            render: (status, record) => {
                // 根据状态显示不同颜色的 Tag
                let color = 'default';
                if (status === 'COMPLETED') color = 'success';
                if (status.includes('RUNNING')) color = 'processing';
                if (status === 'FAILED') color = 'error';
                return <Tag color={color}>{record.statusDisplay}</Tag>;
            }
        },
        {
            title: '创建时间',
            dataIndex: 'created',
            key: 'created',
            width: 160,
            className: 'text-gray-500 text-sm'
        },
        {
            title: '更新时间',
            dataIndex: 'modified',
            key: 'modified',
            width: 160,
            className: 'text-gray-500 text-sm'
        },
        {
            title: '操作',
            key: 'action',
            width: 180,
            render: (_, record) => (
                <Space size="middle">
                    {record.actionUrl ? (
                        <Button
                            type={record.isRevision ? "default" : "primary"}
                            size="small"
                            icon={record.isRevision ? <SyncOutlined /> : <PlayCircleOutlined />}
                            href={record.actionUrl}
                            target="_blank"
                        >
                            {record.actionText}
                        </Button>
                    ) : (
                        <Text type="secondary" style={{fontSize: '12px'}}>等待前序任务</Text>
                    )}
                </Space>
            ),
        },
    ];

    return (
        <div className="mt-6">
            <Card
                title={<span className="text-xl font-semibold">{title}</span>}
                bordered={false}
                className="shadow-sm"
                bodyStyle={{ padding: '0 24px 24px' }}
            >
                {/* 过滤器区域 */}
                <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-100 flex items-center gap-4">
                    <span className="font-medium text-gray-700">按子任务状态过滤:</span>
                    <Select
                        defaultValue={filter.currentValue || 'ALL'}
                        style={{ width: 200 }}
                        onChange={onFilterChange}
                        options={[
                            { value: 'ALL', label: '全部状态' },
                            ...statusOptions.map(opt => ({ value: opt[0], label: opt[1] }))
                        ]}
                    />
                </div>

                {/* 表格区域 */}
                <Table
                    dataSource={dataSource}
                    columns={columns}
                    rowKey="id"
                    pagination={{
                        current: pagination.current,
                        total: pagination.total,
                        pageSize: pagination.pageSize,
                        onChange: onPageChange,
                        showSizeChanger: false, // 简化分页，因为后端固定了 size
                        showTotal: (total) => `共 ${total} 条`
                    }}
                />
            </Card>
        </div>
    );
};

export default TaskTable;