// frontend/src/shared/theme/index.jsx
import React from 'react';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';

// 定义统一的紫色主题
export const AppProvider = ({ children }) => (
    <ConfigProvider
        locale={zhCN}
        theme={{
            token: {
                colorPrimary: '#9333ea', // Purple-600
                colorLink: '#9333ea',
                borderRadius: 6,
            },
        }}
    >
        {children}
    </ConfigProvider>
);