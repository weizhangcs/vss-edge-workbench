import React from 'react';
import ReactDOM from 'react-dom/client';
import { AppProvider } from '@/shared/theme';
import AnnotationWorkbench from '../features/annotation/Workbench';

// 全屏模式，直接挂载到 body 或者一个全屏 div，不依赖 Django 的 base_site 布局
// 但为了保持 Unfold 风格一致，我们依然用 AppProvider 包裹
const rootNode = document.getElementById('react-root');
if (rootNode) {
    const root = ReactDOM.createRoot(rootNode);
    root.render(
        <AppProvider>
            <AnnotationWorkbench />
        </AppProvider>
    );
}