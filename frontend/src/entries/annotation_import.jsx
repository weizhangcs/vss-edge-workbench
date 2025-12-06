// frontend/src/entries/annotation_import.jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { AppProvider } from '@/shared/theme';
import ImportProject from '../features/annotation/ImportProject';

const context = window.SERVER_CONTEXT || { assets: [], urls: {} };

const rootNode = document.getElementById('react-root');
if (rootNode) {
    const root = ReactDOM.createRoot(rootNode);
    root.render(
        <AppProvider>
            <ImportProject context={context} />
        </AppProvider>
    );
}