import React from 'react';
import ReactDOM from 'react-dom/client';
import { AppProvider } from '@/shared/theme';
import DirectorApp from '../features/creative/Director';

// 获取 Django 注入的数据
const context = window.SERVER_DATA || {};

const rootNode = document.getElementById('react-root');
if (rootNode) {
    const root = ReactDOM.createRoot(rootNode);
    root.render(
        <AppProvider>
            <DirectorApp context={context} />
        </AppProvider>
    );
}