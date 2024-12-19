import React from 'react';
import { Modal, Form, Input, Switch, InputNumber, Select, Tabs } from 'antd';
import type { SiteData } from '../../types/site';
import styles from './SiteSettingsModal.module.css';

const { TextArea } = Input;

interface SiteSettingsModalProps {
    visible: boolean;
    site?: SiteData;
    onClose: () => void;
    onSave: (values: any) => void;
}

const SiteSettingsModal: React.FC<SiteSettingsModalProps> = ({
    visible,
    site,
    onClose,
    onSave
}) => {
    const [form] = Form.useForm();

    const handleOk = async () => {
        try {
            const values = await form.validateFields();
            onSave(values);
        } catch (error) {
            console.error('Validation failed:', error);
        }
    };

    return (
        <Modal
            title="站点设置"
            open={visible}
            onOk={handleOk}
            onCancel={onClose}
            width={800}
            destroyOnClose
        >
            <Form
                form={form}
                layout="horizontal"
                labelCol={{ flex: '120px' }}
                labelAlign="left"
                wrapperCol={{ flex: 1 }}
                initialValues={site}
                className={styles.settingsForm}
            >
                {/* 基本设置 */}
                <div className={styles.basicSettings}>
                    <Form.Item
                        label="站点地址"
                        name="site_url"
                        rules={[{ required: true, message: '请输入站点地址' }]}
                    >
                        <Input placeholder="站点地址" />
                    </Form.Item>

                    <div className={styles.switchGroup}>
                        <Form.Item
                            label="启用"
                            name="enabled"
                            valuePropName="checked"
                        >
                            <Switch />
                        </Form.Item>

                        <Form.Item
                            label="使用代理"
                            name="use_proxy"
                            valuePropName="checked"
                        >
                            <Switch />
                        </Form.Item>

                        <Form.Item
                            label="代理地址"
                            name="proxy_url"
                        >
                            <Input placeholder="代理地址" />
                        </Form.Item>
                    </div>
                </div>

                <Tabs items={[
                    {
                        key: 'site_config',
                        label: 'SITE CONFIG',
                        children: (
                            <div className={styles.tabContent}>
                                <Form.Item label="登录配置" name="login_config">
                                    <TextArea placeholder="登录配置" rows={4} />
                                </Form.Item>

                                <Form.Item label="数据提取规则" name="extract_rules">
                                    <TextArea placeholder="数据提取规则" rows={4} />
                                </Form.Item>

                                <Form.Item label="签到配置" name="checkin_config">
                                    <TextArea placeholder="签到配置" rows={4} />
                                </Form.Item>
                            </div>
                        ),
                    },
                    {
                        key: 'credential',
                        label: 'CREDENTIAL',
                        children: (
                            <div className={styles.tabContent}>
                                <Form.Item label="Cookies" name="manual_cookies">
                                    <TextArea placeholder="Cookies" autoSize={{ minRows: 1 }} />
                                </Form.Item>

                                <Form.Item label="用户名" name="username">
                                    <Input placeholder="用户名" />
                                </Form.Item>

                                <Form.Item label="密码" name="password">
                                    <Input.Password placeholder="密码" />
                                </Form.Item>

                                <Form.Item label="Authorization" name="authorization">
                                    <Input placeholder="Authorization" />
                                </Form.Item>

                                <Form.Item label="API Key" name="apikey">
                                    <Input placeholder="API Key" />
                                </Form.Item>
                            </div>
                        ),
                    },
                    {
                        key: 'crawler_config',
                        label: 'CRAWLER CONFIG',
                        children: (
                            <div className={styles.tabContent}>
                                <div className={styles.captchaGroup}>
                                    <Form.Item
                                        label="每次刷新登录"
                                        name="fresh_login"
                                        valuePropName="checked"
                                    >
                                        <Switch />
                                    </Form.Item>
                                    <Form.Item
                                        label="最大重试次数"
                                        name="login_max_retry"
                                    >
                                        <InputNumber min={1} max={10} placeholder="最大重试次数" />
                                    </Form.Item>
                                    <Form.Item
                                        label="超时时间(秒)"
                                        name="timeout"
                                    >
                                        <InputNumber min={1} max={300} placeholder="超时时间(秒)" />
                                    </Form.Item>
                                </div>
                                <div className={styles.captchaGroup}>
                                    <Form.Item
                                        label="跳过验证码"
                                        name="captcha_skip"
                                        valuePropName="checked"
                                    >
                                        <Switch />
                                    </Form.Item>

                                    <Form.Item
                                        label="验证码处理方式"
                                        name="captcha_method"
                                    >
                                        <Select placeholder="验证码处理方式">
                                            <Select.Option value="ddddocr">本地识别(ddddocr)</Select.Option>
                                            <Select.Option value="2captcha">在线识别(2captcha)</Select.Option>
                                            <Select.Option value="manual">手动识别</Select.Option>
                                        </Select>
                                    </Form.Item>
                                </div>

                                <Form.Item
                                    label="无头模式"
                                    name="headless"
                                    valuePropName="checked"
                                >
                                    <Switch />
                                </Form.Item>
                            </div>
                        ),
                    },
                ]} />
            </Form>
        </Modal>
    );
};

export default SiteSettingsModal; 