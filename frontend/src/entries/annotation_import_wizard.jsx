// frontend/src/entries/annotation_import.jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { AppProvider } from '@/shared/theme';
import ImportWizard from '../features/annotation/ImportWizard';

const context = window.SERVER_CONTEXT || { assets: [], urls: {} };

const rootNode = document.getElementById('react-root-import-wizard');
if (rootNode) {
    const root = ReactDOM.createRoot(rootNode);
    root.render(
        <AppProvider>
            <ImportWizard context={context} />
        </AppProvider>
    );
}