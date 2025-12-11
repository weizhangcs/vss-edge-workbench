// frontend/src/entries/annotation_dashboard.jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { AppProvider } from '@/shared/theme';
import Dashboard from "../features/annotation/Dashboard";

// 这里的 ID 必须与 Django 模板中的 div ID 一致
// 模板中是: <div id="react-root-annotation" ...>
const rootNode = document.getElementById('react-root-annotation');

const context = window.SERVER_CONTEXT || { assets: [], urls: {} };

if (rootNode) {
    const root = ReactDOM.createRoot(rootNode);
    root.render(
        <AppProvider>
            <Dashboard context={context} />
        </AppProvider>
    );
} else {
    console.error("React root node 'react-root-annotation' not found!");
}