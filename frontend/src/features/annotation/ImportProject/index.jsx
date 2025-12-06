// frontend/src/features/annotation/ImportProject/index.jsx
import React, { useState, useMemo } from 'react';
import { Steps, Upload, Select, Alert, Button, Typography, Card, message } from 'antd';
import {
    FolderOpenOutlined,
    InboxOutlined,
    InfoCircleOutlined
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { Dragger } = Upload;

// 样式定义
const styles = {
    dragger: {
        padding: '40px 0',
        backgroundColor: '#faf5ff', // Purple-50
        border: '1px dashed #d8b4fe', // Purple-300
    },
    iconPrimary: {
        color: '#9333ea',
        fontSize: '48px'
    },
    headerIcon: {
        fontSize: '36px',
        color: '#9333ea',
        marginRight: '20px',
        marginTop: '4px'
    }
};

const ImportProject = ({ context }) => {
    // 从后端注入的 Context 中解构数据
    const { assets, urls } = context;
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

    const [fileList, setFileList] = useState([]);
    const [targetAssetId, setTargetAssetId] = useState(null);
    const [submitting, setSubmitting] = useState(false);

    const uploadProps = {
        name: 'zip_file',
        multiple: false,
        fileList: fileList,
        accept: '.zip',
        beforeUpload: (file) => {
            setFileList([file]);
            return false; // 阻止自动上传，改为手动提交
        },
        onRemove: () => {
            setFileList([]);
        }
    };

    const handleSubmit = async () => {
        if (fileList.length === 0) {
            message.error('请先上传项目压缩包！');
            return;
        }
        if (!targetAssetId) {
            message.error('请选择关联的媒体资产！');
            return;
        }

        setSubmitting(true);
        const formData = new FormData();
        formData.append('zip_file', fileList[0]);
        formData.append('target_asset', targetAssetId);
        formData.append('csrfmiddlewaretoken', csrfToken);

        try {
            // 提交到当前页面 URL (Django View 处理 POST)
            const response = await fetch(urls.submit, {
                method: 'POST',
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });

            if (response.redirected) {
                message.success('导入成功！正在跳转...', 1.5, () => {
                    window.location.href = response.url;
                });
            } else if (!response.ok) {
                message.error('导入失败，请检查文件格式或重试。');
                setSubmitting(false);
            } else {
                message.success('导入处理完成', 1.5, () => {
                    window.location.href = urls.changelist;
                });
            }
        } catch (error) {
            console.error(error);
            message.error('网络请求错误');
            setSubmitting(false);
        }
    };

    const stepItems = [
        { title: '上传文件', status: fileList.length > 0 ? 'finish' : 'process' },
        { title: '关联资产', status: targetAssetId ? 'finish' : 'wait' },
        { title: '开始恢复', status: 'wait' },
    ];

    return (
        <div className="flex justify-center items-start pt-4">
            <Card bordered={false} className="w-full max-w-[900px] shadow-none" bodyStyle={{ padding: 0 }}>
                {/* Header */}
                <div style={{ padding: '32px 0', backgroundColor: '#fff' }}>
                    <div className="flex items-start" style={{ marginBottom: '32px' }}>
                        <FolderOpenOutlined style={styles.headerIcon} />
                        <div>
                            <Title level={3} style={{ margin: 0, fontWeight: 'bold' }}>导入标注项目</Title>
                            <Text type="secondary">上传 ZIP 文件以恢复标注数据，并自动关联到媒体资产库。</Text>
                        </div>
                    </div>
                    <div style={{ padding: '0 10px' }}>
                        <Steps current={fileList.length > 0 ? (targetAssetId ? 2 : 1) : 0} items={stepItems} size="small" />
                    </div>
                </div>

                {/* Body */}
                <div style={{ padding: '0', backgroundColor: '#fff' }}>
                    <section style={{ marginBottom: '40px' }}>
                        <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px', color: '#374151' }}>
                            步骤 1：上传项目数据包
                        </h3>
                        <Dragger {...uploadProps} style={styles.dragger}>
                            <p className="ant-upload-drag-icon">
                                <InboxOutlined style={styles.iconPrimary} />
                            </p>
                            <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
                            <p className="ant-upload-hint">支持格式: .zip (需包含 manifest.json)</p>
                        </Dragger>
                    </section>

                    <section>
                        <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px', color: '#374151' }}>
                            步骤 2：选择目标媒体资产
                        </h3>
                        <Select
                            showSearch
                            placeholder="请选择或搜索要关联的媒体资产..."
                            optionFilterProp="children"
                            size="large"
                            style={{ width: '100%' }}
                            onChange={(value) => setTargetAssetId(value)}
                            filterOption={(input, option) =>
                                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                            }
                            options={assets}
                        />

                        <Alert
                            style={{ marginTop: '24px', borderRadius: '8px' }}
                            message={<span style={{ fontWeight: 600 }}>关联匹配逻辑说明</span>}
                            description="系统将根据媒体文件序号 (Sequence) 自动匹配并导入数据。请确保所选资产包含对应的媒体文件。"
                            type="info"
                            showIcon
                            icon={<InfoCircleOutlined />}
                        />
                    </section>
                </div>

                {/* Footer */}
                <div style={{ padding: '40px 0', marginTop: '20px', display: 'flex', gap: '12px' }}>
                    <Button
                        type="primary"
                        size="large"
                        onClick={handleSubmit}
                        loading={submitting}
                        disabled={!fileList.length || !targetAssetId}
                        style={{ minWidth: '160px' }}
                    >
                        {submitting ? '正在恢复数据...' : '确认并开始导入'}
                    </Button>
                    <Button size="large" onClick={() => window.history.back()}>
                        取消
                    </Button>
                </div>
            </Card>
        </div>
    );
};

export default ImportProject;