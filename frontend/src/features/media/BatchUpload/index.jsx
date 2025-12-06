// frontend/src/features/media/BatchUpload/index.jsx
import React, { useState, useMemo } from 'react';
import { Steps, Upload, Button, Typography, Card, message, Alert } from 'antd';
import {
    CloudUploadOutlined,
    InboxOutlined,
    CheckCircleOutlined,
    InfoCircleOutlined,
    RollbackOutlined
} from '@ant-design/icons';

// 简单的内联样式，你也可以选择创建同级 css 文件引入
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

const { Title, Text } = Typography;
const { Dragger } = Upload;

const BatchUpload = ({ context }) => {
    const { mediaTitle, urls } = context;
    // 获取 CSRF Token (Django 默认会在 Cookie 或 DOM 中埋)
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

    const [fileList, setFileList] = useState([]);
    const [isProcessing, setIsProcessing] = useState(false);

    // 计算属性
    const isUploading = useMemo(() => {
        return fileList.some(file => file.status === 'uploading');
    }, [fileList]);

    const canStartIngest = useMemo(() => {
        return fileList.length > 0 &&
            fileList.every(file => file.status === 'done') &&
            !isUploading;
    }, [fileList, isUploading]);

    // Upload 组件配置
    const uploadProps = {
        name: 'file',
        multiple: true,
        action: urls.uploadApi,
        headers: { 'X-CSRFToken': csrfToken },
        accept: '.mp4,.mov,.srt',
        onChange(info) {
            const { status } = info.file;
            if (status === 'done') {
                message.success(`${info.file.name} 上传成功`);
            } else if (status === 'error') {
                message.error(`${info.file.name} 上传失败`);
            }
            setFileList([...info.fileList]);
        },
        showUploadList: {
            showRemoveIcon: true,
            showDownloadIcon: false,
        },
    };

    const handleStartProcessing = () => {
        setIsProcessing(true);
        message.loading({ content: '正在启动后台处理任务...', key: 'process_msg' });
        // 简单跳转触发
        setTimeout(() => {
            window.location.href = urls.triggerIngest;
        }, 800);
    };

    const stepItems = [
        { title: '上传文件', status: fileList.length > 0 ? (isUploading ? 'process' : 'finish') : 'process' },
        { title: '文件校验', status: canStartIngest ? 'finish' : 'wait' },
        { title: '后台处理', status: 'wait' },
    ];

    return (
        <div className="flex justify-center items-start pt-4">
            <Card bordered={false} className="w-full max-w-[900px] shadow-none" bodyStyle={{ padding: 0 }}>
                {/* Header */}
                <div style={{ padding: '32px 0', backgroundColor: '#fff' }}>
                    <div className="flex items-start" style={{ marginBottom: '32px' }}>
                        <CloudUploadOutlined style={styles.headerIcon} />
                        <div>
                            <Title level={3} style={{ margin: 0, fontWeight: 'bold' }}>批量上传资源</Title>
                            <Text type="secondary">为资产 <b>{mediaTitle}</b> 上传视频与字幕文件。</Text>
                        </div>
                    </div>
                    <div style={{ padding: '0 10px' }}>
                        <Steps current={canStartIngest ? 1 : 0} items={stepItems} size="small" />
                    </div>
                </div>

                {/* Body */}
                <div style={{ padding: '0', backgroundColor: '#fff' }}>
                    <Alert
                        style={{ marginBottom: '24px', borderRadius: '8px' }}
                        message="文件名匹配规则"
                        description="视频和字幕的文件名主干必须保持一致（例如 ep01.mp4 和 ep01.srt），否则无法自动关联。"
                        type="info"
                        showIcon
                        icon={<InfoCircleOutlined />}
                    />

                    <Dragger {...uploadProps} fileList={fileList} style={styles.dragger}>
                        <p className="ant-upload-drag-icon">
                            <InboxOutlined style={styles.iconPrimary} />
                        </p>
                        <p className="ant-upload-text">点击或拖拽文件到此处</p>
                        <p className="ant-upload-hint">支持批量上传 .mp4, .mov, .srt 文件</p>
                    </Dragger>

                    {fileList.length > 0 && (
                        <div style={{ marginTop: '16px', textAlign: 'right', color: '#6b7280', fontSize: '12px' }}>
                            已选择 {fileList.length} 个文件
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div style={{ padding: '40px 0', marginTop: '20px', display: 'flex', gap: '12px' }}>
                    <Button
                        type="primary"
                        size="large"
                        onClick={handleStartProcessing}
                        loading={isProcessing}
                        disabled={!canStartIngest}
                        icon={<CheckCircleOutlined />}
                        style={{ minWidth: '180px' }}
                    >
                        {isUploading ? '正在上传...' : '确认并开始处理'}
                    </Button>
                    <Button
                        size="large"
                        icon={<RollbackOutlined />}
                        onClick={() => window.location.href = urls.backToChange}
                    >
                        返回编辑页
                    </Button>
                </div>
            </Card>
        </div>
    );
};

export default BatchUpload;