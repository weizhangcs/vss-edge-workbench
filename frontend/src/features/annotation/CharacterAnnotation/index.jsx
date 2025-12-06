// frontend/src/features/annotation/CharacterAnnotationTab/index.jsx
import React from 'react';
import TaskTable from '../components/TaskTable';

const CharacterAnnotationTab = ({ context }) => {
    const { items, pagination, filter, statusOptions } = context;

    // 辅助函数：更新 URL 参数并跳转 (MPA 模式)
    const updateUrl = (params) => {
        const searchParams = new URLSearchParams(window.location.search);
        Object.keys(params).forEach(key => {
            if (params[key] === 'ALL' || !params[key]) {
                searchParams.delete(key);
            } else {
                searchParams.set(key, params[key]);
            }
        });
        window.location.search = searchParams.toString();
    };

    const handleFilterChange = (value) => {
        // 切换筛选时，通常重置回第 1 页
        updateUrl({ l1_status: value, page: 1 });
    };

    const handlePageChange = (page) => {
        updateUrl({ page: page });
    };

    return (
        <TaskTable
            title="子任务列表：角色标注"
            dataSource={items}
            pagination={pagination}
            filter={{ currentValue: filter.active }}
            statusOptions={statusOptions}
            onFilterChange={handleFilterChange}
            onPageChange={handlePageChange}
        />
    );
};

export default CharacterAnnotationTab;