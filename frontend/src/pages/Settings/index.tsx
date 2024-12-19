import React from 'react';
import { Card, Form, Switch, InputNumber, Button, Space } from 'antd';

const Settings: React.FC = () => {
    const [form] = Form.useForm();

    const onFinish = (values: any) => {
        console.log('Success:', values);
    };

    return (
        <Card title="系统设置">
            <Form
                form={form}
                layout="vertical"
                onFinish={onFinish}
                initialValues={{
                    autoCheck: true,
                    checkInterval: 30,
                    maxRetries: 3,
                }}
            >
                <Form.Item
                    label="自动检查"
                    name="autoCheck"
                    valuePropName="checked"
                >
                    <Switch />
                </Form.Item>

                <Form.Item
                    label="检查间隔（分钟）"
                    name="checkInterval"
                    rules={[{ required: true, message: '请输入检查间隔时间' }]}
                >
                    <InputNumber min={1} max={1440} />
                </Form.Item>

                <Form.Item
                    label="最大重试次数"
                    name="maxRetries"
                    rules={[{ required: true, message: '请输入最大重试次数' }]}
                >
                    <InputNumber min={1} max={10} />
                </Form.Item>

                <Form.Item>
                    <Space>
                        <Button type="primary" htmlType="submit">
                            保存设置
                        </Button>
                        <Button onClick={() => form.resetFields()}>
                            重置
                        </Button>
                    </Space>
                </Form.Item>
            </Form>
        </Card>
    );
};

export default Settings;

