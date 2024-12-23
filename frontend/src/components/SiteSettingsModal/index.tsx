import React, { useEffect, useState } from 'react';
import { Modal, Form, Input, Switch, InputNumber, Select, Tabs, message } from 'antd';
import type { SiteData } from '../../types/site';
import styles from './SiteSettingsModal.module.css';
import { siteConfigApi } from '../../api/siteConfig';
import classNames from 'classnames';

const { TextArea } = Input;

type GlobalValues = Record<string, boolean>;

interface SiteSettingsModalProps {
    visible: boolean;
    site?: SiteData;
    onClose: () => void;
    onSave: (values: any, globalValues: GlobalValues) => void;
}

const SiteSettingsModal: React.FC<SiteSettingsModalProps> = ({
    visible,
    site,
    onClose,
    onSave
}) => {
    const [form] = Form.useForm();
    const [loading, setLoading] = useState(false);
    const [globalValues, setGlobalValues] = useState<GlobalValues>(() => ({
        fresh_login: false,
        login_max_retry: false,
        captcha_method: false,
        captcha_skip: false,
        timeout: false,
        headless: false
    }));

    // 加载站点配置数据
    const loadSiteConfigs = async () => {
        if (!site?.site_id) return;
        
        try {
            setLoading(true);
            const [siteConfigData, crawlerConfigData, globalSettings, credentialData] = await Promise.all([
                siteConfigApi.getSiteConfig(site.site_id),
                siteConfigApi.getCrawlerConfig(site.site_id),
                siteConfigApi.getGlobalSettings(),
                siteConfigApi.getCredential(site.site_id).catch(() => null) // 如果获取凭证失败，返回null
            ]);
            
            // 解析全局设置中的站点列表
            const captchaSkipSites = globalSettings.captcha_skip_sites.split(',').map(s => s.trim()).filter(Boolean);
            const checkinSites = globalSettings.checkin_sites.split(',').map(s => s.trim()).filter(Boolean);
            
            // 检查当前站点是否在列表中
            const isInCaptchaSkipSites = captchaSkipSites.includes(site.site_id);
            const isInCheckinSites = checkinSites.includes(site.site_id);
            
            // 处理爬虫配置，如果某些值为空则使用全局设置
            const crawlerValues = {
                enabled: crawlerConfigData.enabled,
                use_proxy: crawlerConfigData.use_proxy,
                proxy_url: crawlerConfigData.proxy_url,
                fresh_login: crawlerConfigData.fresh_login ?? globalSettings.fresh_login,
                captcha_skip: crawlerConfigData.captcha_skip ?? isInCaptchaSkipSites,
                captcha_method: crawlerConfigData.captcha_method ?? globalSettings.captcha_default_method,
                timeout: crawlerConfigData.timeout ?? globalSettings.page_timeout,
                headless: crawlerConfigData.headless ?? globalSettings.headless,
                login_max_retry: crawlerConfigData.login_max_retry ?? globalSettings.login_max_retry,
                checkin_enabled: siteConfigData.checkin_config?.enabled ?? isInCheckinSites
            };

            // 记录哪些值来自全局设置
            setGlobalValues({
                fresh_login: crawlerConfigData.fresh_login === undefined || crawlerConfigData.fresh_login === null,
                login_max_retry: crawlerConfigData.login_max_retry === undefined || crawlerConfigData.login_max_retry === null,
                captcha_method: crawlerConfigData.captcha_method === undefined || crawlerConfigData.captcha_method === null,
                captcha_skip: crawlerConfigData.captcha_skip === undefined || crawlerConfigData.captcha_skip === null,
                timeout: crawlerConfigData.timeout === undefined || crawlerConfigData.timeout === null,
                headless: crawlerConfigData.headless === undefined || crawlerConfigData.headless === null
            });
            
            // 设置表单初始值
            form.setFieldsValue({
                // SITE CONFIG
                site_url: siteConfigData.site_url,
                login_config: JSON.stringify(siteConfigData.login_config, null, 2),
                extract_rules: JSON.stringify(siteConfigData.extract_rules, null, 2),
                checkin_config: JSON.stringify({
                    ...siteConfigData.checkin_config,
                    enabled: crawlerValues.checkin_enabled
                }, null, 2),
                
                // CRAWLER CONFIG
                ...crawlerValues,

                // CREDENTIAL
                ...(credentialData && {
                    enable_manual_cookies: credentialData.enable_manual_cookies,
                    manual_cookies: credentialData.manual_cookies,
                    username: credentialData.username,
                    password: credentialData.password,
                    authorization: credentialData.authorization,
                    apikey: credentialData.apikey
                })
            });
        } catch (error) {
            message.error('加载站点配置失败');
            console.error('加载站点配置失败:', error);
        } finally {
            setLoading(false);
        }
    };

    // 当模态框打开时加载数据
    useEffect(() => {
        if (visible && site) {
            loadSiteConfigs();
        }
    }, [visible, site]);

    // 生成表单项的类名
    const getFormItemClassName = (field: keyof GlobalValues) => {
        return classNames({
            [styles.globalValue]: globalValues[field]
        });
    };

    const handleOk = async () => {
        try {
            const values = await form.validateFields();
            setLoading(true);

            if (site?.site_id) {
                await onSave(values, globalValues);
            }
        } catch (error) {
            if (error instanceof Error) {
                message.error(`保存失败: ${error.message}`);
            } else {
                message.error('保存失败');
            }
            console.error('保存失败:', error);
        } finally {
            setLoading(false);
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
            confirmLoading={loading}
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
                                <Form.Item
                                    label="启用手动Cookie"
                                    name="enable_manual_cookies"
                                    valuePropName="checked"
                                >
                                    <Switch />
                                </Form.Item>
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
                                        className={getFormItemClassName('fresh_login')}
                                    >
                                        <Switch />
                                    </Form.Item>
                                    <Form.Item
                                        label="最大重试次数"
                                        name="login_max_retry"
                                        className={getFormItemClassName('login_max_retry')}
                                    >
                                        <InputNumber min={1} max={10} placeholder="最大重试次数" />
                                    </Form.Item>
                                    <Form.Item
                                        label="超时时间(秒)"
                                        name="timeout"
                                        className={getFormItemClassName('timeout')}
                                    >
                                        <InputNumber min={1} max={300} placeholder="超时时间(秒)" />
                                    </Form.Item>
                                </div>
                                <div className={styles.captchaGroup}>
                                    <Form.Item
                                        label="跳过验证码"
                                        name="captcha_skip"
                                        valuePropName="checked"
                                        className={getFormItemClassName('captcha_skip')}
                                    >
                                        <Switch />
                                    </Form.Item>

                                    <Form.Item
                                        label="验证码处理方式"
                                        name="captcha_method"
                                        className={getFormItemClassName('captcha_method')}
                                    >
                                        <Select placeholder="验证码处理方式">
                                            <Select.Option value="manual">手动识别</Select.Option>
                                            <Select.Option value="api">API识别</Select.Option>
                                            <Select.Option value="ocr">OCR识别</Select.Option>
                                            <Select.Option value="skip">跳过</Select.Option>
                                        </Select>
                                    </Form.Item>
                                </div>

                                <Form.Item
                                    label="无头模式"
                                    name="headless"
                                    valuePropName="checked"
                                    className={getFormItemClassName('headless')}
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