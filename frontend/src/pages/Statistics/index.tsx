import React from 'react';
import { Card, Row, Col, Statistic } from 'antd';
import { 
    UploadOutlined, 
    DownloadOutlined, 
    UserOutlined, 
    CloudUploadOutlined 
} from '@ant-design/icons';

const Statistics: React.FC = () => {
    return (
        <div>
            <Row gutter={[16, 16]}>
                <Col span={6}>
                    <Card>
                        <Statistic
                            title="总上传量"
                            value={0}
                            prefix={<UploadOutlined />}
                            suffix="GB"
                        />
                    </Card>
                </Col>
                <Col span={6}>
                    <Card>
                        <Statistic
                            title="总下载量"
                            value={0}
                            prefix={<DownloadOutlined />}
                            suffix="GB"
                        />
                    </Card>
                </Col>
                <Col span={6}>
                    <Card>
                        <Statistic
                            title="做种数量"
                            value={0}
                            prefix={<CloudUploadOutlined />}
                        />
                    </Card>
                </Col>
                <Col span={6}>
                    <Card>
                        <Statistic
                            title="活跃用户"
                            value={0}
                            prefix={<UserOutlined />}
                        />
                    </Card>
                </Col>
            </Row>
        </div>
    );
};

export default Statistics; 