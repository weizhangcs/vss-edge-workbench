import React from 'react';
import { Empty, Card } from 'antd';
import { BulbOutlined } from '@ant-design/icons';

const InferenceRag = () => {
    return (
        <div className="mt-6">
            <Card bordered={false} className="shadow-sm min-h-[400px] flex items-center justify-center">
                <Empty
                    image={<BulbOutlined style={{ fontSize: 60, color: '#d8b4fe' }} />}
                    description={
                        <span className="text-gray-500 text-lg">
                    第二步：高级功能 (预留位)
                    <br />
                    <span className="text-sm text-gray-400">此模块等待进一步规划...</span>
                </span>
                    }
                />
            </Card>
        </div>
    );
};

export default InferenceRag;