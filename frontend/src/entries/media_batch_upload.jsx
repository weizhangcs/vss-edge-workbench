// frontend/src/entries/media_batch_upload.jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { AppProvider } from '@/shared/theme';
import BatchUpload from '../features/media/BatchUpload';

// 1. 获取 Django 注入的全局数据
// @ts-ignore
const context = window.SERVER_CONTEXT || {};

// 2. 挂载 React 应用
const rootNode = document.getElementById('react-root');
if (rootNode) {
    const root = ReactDOM.createRoot(rootNode);
    root.render(
        <AppProvider>
            <BatchUpload context={context} />
        </AppProvider>
    );
} else {
    console.error("Failed to find #react-root element!");
}