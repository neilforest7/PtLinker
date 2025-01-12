import React from 'react';
import { Modal, Form, Input, Switch, message } from 'antd';
import { siteConfigApi } from '../../api/siteConfig';

interface AddSiteModalProps {
    visible: boolean;
    onClose: () => void;
    onSuccess: () => void;
}

const AddSiteModal: React.FC<AddSiteModalProps> = ({
    visible,
    onClose,
    onSuccess
}) => {
    const [form] = Form.useForm();
    const [loading, setLoading] = React.useState(false);

    const handleSubmit = async () => {
        try {
            setLoading(true);
            const values = await form.validateFields();
            
            await siteConfigApi.createSiteConfig(
                values.site_id,
                values.site_url,
                values.enable_crawler,
                true // 默认保存到本地文件
            );

            message.success('添加站点成功');
            form.resetFields();
            onSuccess();
            onClose();
        } catch (error: any) {
            message.error(error.response?.data?.detail || '添加站点失败');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Modal
            title="添加站点"
            open={visible}
            onCancel={onClose}
            onOk={handleSubmit}
            confirmLoading={loading}
            maskClosable={false}
        >
            <Form
                form={form}
                layout="vertical"
                initialValues={{
                    enable_crawler: true
                }}
            >
                <Form.Item
                    name="site_id"
                    label="站点ID"
                    rules={[
                        { required: true, message: '请输入站点ID' },
                        { pattern: /^[a-zA-Z0-9_-]+$/, message: '站点ID只能包含字母、数字、下划线和连字符' }
                    ]}
                >
                    <Input placeholder="请输入站点ID，例如：hdchina" />
                </Form.Item>

                <Form.Item
                    name="site_url"
                    label="站点URL"
                    rules={[
                        { required: true, message: '请输入站点URL' },
                        { type: 'url', message: '请输入有效的URL' }
                    ]}
                >
                    <Input placeholder="请输入站点URL，例如：https://hdchina.com" />
                </Form.Item>

                <Form.Item
                    name="enable_crawler"
                    label="启用爬虫"
                    valuePropName="checked"
                >
                    <Switch />
                </Form.Item>
            </Form>
        </Modal>
    );
};

export default AddSiteModal; 