import React, { useState } from 'react';
import {
    Card,
    Table,
    Tag,
    Button,
    Statistic,
    Row,
    Col,
    Progress,
    Alert,
    Space,
    Typography,
    Tabs,
    Empty,
    message
} from 'antd';
import {
    PlayCircleOutlined,
    BarChartOutlined,
    CheckCircleOutlined,
    SyncOutlined,
    FileTextOutlined,
    UserOutlined,
    ClockCircleOutlined,
    MessageOutlined,
    PictureOutlined,
    ExportOutlined,
    StarOutlined,
    TeamOutlined,
    AppstoreOutlined,
    BuildOutlined
} from '@ant-design/icons';

const { Title, Text } = Typography;

const Dashboard = ({ context }) => {
    const { meta, dashboard, jobs, urls } = context;
    const [auditLoading, setAuditLoading] = useState(false);

    // --- 逻辑部分 ---
    const handleTriggerAudit = async () => {
        if (!urls?.trigger_audit) {
            message.error("未配置审计 API 地址");
            return;
        }

        setAuditLoading(true);
        try {
            const response = await fetch(urls.trigger_audit);
            if (response.ok) {
                message.success("审计指令已发送，正在重新计算...");
                setTimeout(() => window.location.reload(), 1000);
            } else {
                message.error("审计触发失败");
            }
        } catch (e) {
            console.error(e);
            message.error("网络请求错误");
        } finally {
            setAuditLoading(false);
        }
    };

    // --- 表格定义 1: 角色权重表 ---
    const rosterColumns = [
        {
            title: '角色 (Key)',
            dataIndex: 'name',
            key: 'name',
            render: (text, record) => (
                <div className="flex flex-col">
                    <span className="font-medium text-gray-800">{text}</span>
                    <span className="text-xs text-gray-400 font-mono">{record.key}</span>
                </div>
            )
        },
        {
            title: '综合权重',
            key: 'weight',
            width: 140,
            render: (_, record) => (
                <div className="w-full">
                    <div className="flex justify-between text-xs mb-1">
                        <span className="text-blue-600 font-bold">{record.weight_score?.toFixed(4)}</span>
                    </div>
                    <Progress
                        percent={parseFloat(record.weight_percent)}
                        showInfo={false}
                        size="small"
                        strokeColor="#3b82f6"
                        trailColor="#f3f4f6"
                    />
                </div>
            )
        },
        {
            title: '台词',
            dataIndex: ['stats', 'lines'],
            key: 'lines',
            align: 'center',
            className: 'text-gray-600',
            width: 70
        },
        // [新增] 场景数量 (需求 4)
        {
            title: '场景',
            dataIndex: ['stats', 'scene_count'],
            key: 'scene_count',
            align: 'center',
            className: 'text-gray-600 font-medium',
            width: 70
        },
    ];

    // --- 表格定义 2: 任务列表 ---
    const jobColumns = [
        {
            title: '媒体资源',
            dataIndex: 'media_title',
            key: 'title',
            render: (text) => <span className="font-medium text-gray-700">{text}</span>
        },
        {
            title: '状态',
            dataIndex: 'status',
            key: 'status',
            width: 100,
            render: (status, record) => {
                let color = 'default';
                let label = record.status_display || status;
                if (status === 'COMPLETED') color = 'success';
                if (status === 'PROCESSING') color = 'processing';
                if (status === 'ERROR') color = 'error';
                return <Tag color={color}>{label}</Tag>;
            }
        },
        // [新增] 创建时间 (需求 3: 项目管理逻辑)
        {
            title: '创建时间',
            dataIndex: 'created_at',
            key: 'created_at',
            width: 140,
            className: 'text-gray-500 text-xs font-mono'
        },
        {
            title: '最后更新',
            dataIndex: 'updated_at',
            key: 'updated_at',
            width: 140,
            className: 'text-gray-400 text-xs font-mono'
        },
        {
            title: '操作',
            key: 'action',
            width: 160,
            render: (_, record) => (
                <Space size="small">
                    <Button
                        type="primary"
                        ghost
                        size="small"
                        icon={<PlayCircleOutlined />}
                        href={record.workbench_url}
                        target="_blank"
                    >
                        标注
                    </Button>
                    {record.download_url && (
                        <Button
                            type="text"
                            size="small"
                            icon={<FileTextOutlined />}
                            href={record.download_url}
                            target="_blank"
                            title="下载 JSON"
                        />
                    )}
                </Space>
            )
        }
    ];

    // --- 数据准备 ---
    const engStats = dashboard?.engineering || {};
    const semStats = dashboard?.semantic || {};
    const issues = semStats.name_issues || [];
    const roster = semStats.character_roster || [];

    // --- 组件样式 ---
    const StatCard = ({ title, value, icon, colorClass, suffix }) => (
        <Card
            bordered={false}
            className="shadow-sm hover:shadow-lg transition-all duration-300 h-full rounded-xl"
            bodyStyle={{ padding: '24px' }}
            style={{ borderTop: `3px solid ${colorClass}` }}
        >
            <div className="flex items-center justify-between">
                <div>
                    <div className="text-gray-500 text-sm mb-2 font-medium">{title}</div>
                    <div className="text-3xl font-bold text-gray-800 tracking-tight">
                        {value} <span className="text-sm font-normal text-gray-400 ml-1">{suffix}</span>
                    </div>
                </div>
                <div className={`p-4 rounded-full bg-opacity-10`} style={{ backgroundColor: `${colorClass}1A` }}>
                    {React.cloneElement(icon, { style: { fontSize: '28px', color: colorClass } })}
                </div>
            </div>
        </Card>
    );

    const cardHeadStyle = {
        backgroundColor: '#fff',
        borderBottom: '1px solid #f0f0f0',
        padding: '16px 24px',
        minHeight: '56px',
        fontWeight: 600,
        color: '#1f2937',
        fontSize: '16px'
    };

    // --- Tab 内容渲染 ---
    const OverviewContent = () => (
        <div className="space-y-8">
            {/* Header Area */}
            <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm flex justify-between items-center">
                <div className="flex items-center gap-3">
                    <Title level={4} style={{ margin: 0 }} className="text-gray-800">{meta.name}</Title>
                    <Tag color={meta.status === 'COMPLETED' ? 'green' : 'blue'} className="px-2 py-0.5 rounded text-xs font-semibold">
                        {meta.status}
                    </Tag>
                </div>

                <Space size="middle">
                    {urls.export_project && urls.export_project !== '#' && (
                        <Button icon={<ExportOutlined />} size="large" href={urls.export_project}>导出工程</Button>
                    )}
                    <Button
                        type="primary"
                        icon={auditLoading ? <SyncOutlined spin /> : <BarChartOutlined />}
                        onClick={handleTriggerAudit}
                        loading={auditLoading}
                        size="large"
                        className="bg-blue-600 hover:bg-blue-500 border-none shadow-md px-6"
                    >
                        生成交付物并审计
                    </Button>
                </Space>
            </div>

            {meta.has_report ? (
                <>
                    {/* Stats Grid */}
                    <Row gutter={[24, 24]}>
                        <Col xs={24} sm={12} lg={6}>
                            <StatCard
                                title="有效任务"
                                value={meta.valid_job_count || jobs.length}
                                icon={<CheckCircleOutlined />}
                                colorClass="#10b981"
                            />
                        </Col>
                        <Col xs={24} sm={12} lg={6}>
                            <StatCard
                                title="角色总数"
                                value={roster.length}
                                icon={<TeamOutlined />}
                                colorClass="#3b82f6"
                            />
                        </Col>
                        <Col xs={24} sm={12} lg={6}>
                            <StatCard
                                title="场景总数"
                                value={engStats.track_counts?.scenes || 0}
                                icon={<PictureOutlined />}
                                colorClass="#f59e0b"
                            />
                        </Col>
                        <Col xs={24} sm={12} lg={6}>
                            <StatCard
                                title="高光时刻"
                                value={engStats.track_counts?.highlights || 0}
                                icon={<StarOutlined />}
                                colorClass="#8b5cf6"
                            />
                        </Col>
                    </Row>

                    {/* Alerts */}
                    {issues.length > 0 && (
                        <Alert
                            message={<span className="font-bold text-orange-800">数据一致性警告</span>}
                            description={
                                <ul className="list-disc pl-4 text-xs text-orange-700 mt-1">
                                    {issues.map((i, idx) => (
                                        <li key={idx}>
                                            {i.msg}
                                            <span className="opacity-75 ml-1">
                                                ({i.details?.join(', ')})
                                            </span>
                                        </li>
                                    ))}
                                </ul>
                            }
                            type="warning"
                            showIcon
                            className="rounded-xl border-orange-200 bg-orange-50 shadow-sm"
                        />
                    )}

                    {/* Main Content Area */}
                    <Row gutter={[24, 24]} className="mt-4">
                        <Col xs={24} lg={14}>
                            <Card
                                title="标注任务列表"
                                bordered={false}
                                className="shadow-md rounded-xl overflow-hidden h-full border border-gray-100"
                                headStyle={cardHeadStyle}
                                bodyStyle={{ padding: 0 }}
                            >
                                <Table
                                    dataSource={jobs}
                                    columns={jobColumns}
                                    rowKey="id"
                                    pagination={{ pageSize: 8, size: 'small', position: ['bottomCenter'] }}
                                    size="middle"
                                    className="ant-table-striped"
                                />
                            </Card>
                        </Col>
                        <Col xs={24} lg={10}>
                            <Card
                                title={<Space><UserOutlined className="text-blue-500"/><span>角色权重分析</span></Space>}
                                bordered={false}
                                className="shadow-md rounded-xl overflow-hidden h-full border border-gray-100"
                                headStyle={cardHeadStyle}
                                bodyStyle={{ padding: 0 }}
                            >
                                <Table
                                    dataSource={roster}
                                    columns={rosterColumns}
                                    rowKey="key"
                                    pagination={{ pageSize: 6, size: 'small', position: ['bottomCenter'] }}
                                    size="middle"
                                />
                            </Card>
                        </Col>
                    </Row>
                </>
            ) : (
                <div className="bg-white border-2 border-dashed border-gray-200 rounded-2xl p-20 text-center shadow-sm">
                    <div className="bg-gray-50 w-24 h-24 rounded-full flex items-center justify-center mx-auto mb-6">
                        <BarChartOutlined style={{ fontSize: 40, color: '#9ca3af' }} />
                    </div>
                    <Title level={4} type="secondary" className="mb-2">暂无审计数据</Title>
                    <Text type="secondary" className="block mb-8 max-w-md mx-auto">
                        项目尚未生成分析报告。请点击上方的按钮来初始化项目数据，这将生成生产蓝图并执行完整审计。
                    </Text>
                    <Button
                        type="primary"
                        icon={<PlayCircleOutlined />}
                        onClick={handleTriggerAudit}
                        loading={auditLoading}
                        size="large"
                        className="h-12 px-8 text-lg"
                    >
                        初始化项目数据
                    </Button>
                </div>
            )}
        </div>
    );

    // --- Tabs 配置 ---
    const items = [
        {
            key: 'overview',
            label: (
                <span className="flex items-center gap-2 px-2">
                    <AppstoreOutlined />
                    项目概览
                </span>
            ),
            children: <OverviewContent />,
        },
        {
            key: 'orchestration',
            label: (
                <span className="flex items-center gap-2 px-2">
                    <BuildOutlined />
                    场景编排
                </span>
            ),
            children: (
                <div className="bg-white p-12 text-center rounded-xl border border-dashed border-gray-200">
                    <BuildOutlined style={{ fontSize: 48, color: '#e5e7eb', marginBottom: 16 }} />
                    <Title level={5} type="secondary">功能开发中</Title>
                    <Text type="secondary">场景编排与分镜管理模块即将上线，敬请期待。</Text>
                </div>
            ),
        },
    ];

    return (
        // [需求 1: 增加顶部间距] mt-4 甚至可以更大，让 Tab 和上方 Django Header 分离
        <div className="bg-gray-50 min-h-screen p-8 -m-6 mt-2">
            <div className="max-w-7xl mx-auto">
                {/* [需求 2: Tabs 导航] */}
                <Tabs
                    defaultActiveKey="overview"
                    items={items}
                    type="card"
                    className="custom-tabs"
                    size="large"
                />
            </div>
        </div>
    );
};

export default Dashboard;