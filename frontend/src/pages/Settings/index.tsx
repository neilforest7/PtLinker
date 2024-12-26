import React, { useEffect, useState } from 'react';
import { Form, Input, Switch, InputNumber, Button, message, Card, Space, Row, Col, Select, Popconfirm } from 'antd';
import { UndoOutlined } from '@ant-design/icons';
import { siteConfigApi } from '../../api/siteConfig';
import { SettingsResponse, CrawlerConfigResponse } from '../../types/api';
import styles from './Settings.module.css';

const { Option } = Select;

// 日志级别选项
const LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];

// 验证码方法选项
const CAPTCHA_METHODS = ['api', 'ddddocr', 'manual'];

const Settings: React.FC = () => {
    const [form] = Form.useForm();
    const [loading, setLoading] = useState(false);
    const [initialValues, setInitialValues] = useState<SettingsResponse | null>(null);
    const [siteOptions, setSiteOptions] = useState<string[]>([]);

    // 加载站点列表
    const loadSiteOptions = async () => {
        try {
            const configs = await siteConfigApi.getAllCrawlerConfigs();
            const siteIds = configs.map((config: CrawlerConfigResponse) => config.site_id);
            setSiteOptions(siteIds);
        } catch (error) {
            console.error('加载站点列表失败:', error);
        }
    };

    // 加载设置
    const loadSettings = async () => {
        try {
            setLoading(true);
            const settings = await siteConfigApi.getSettings();
            // 将逗号分隔的字符串转换为数组
            const formattedSettings = {
                ...settings,
                captcha_skip_sites: settings.captcha_skip_sites?.split(',').filter(Boolean) || [],
                checkin_sites: settings.checkin_sites?.split(',').filter(Boolean) || []
            };
            setInitialValues(settings);
            form.setFieldsValue(formattedSettings);
        } catch (error) {
            message.error('加载设置失败');
            console.error('加载设置失败:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadSettings();
        loadSiteOptions();
    }, []);

    // 保存设置
    const handleSave = async (values: any) => {
        try {
            setLoading(true);
            // 将数组转换回逗号分隔的字符串
            const submitValues = {
                ...values,
                captcha_skip_sites: values.captcha_skip_sites?.join(',') || '',
                checkin_sites: values.checkin_sites?.join(',') || ''
            };

            const changedFields = Object.keys(submitValues).reduce<Partial<SettingsResponse>>((acc, key) => {
                const k = key as keyof SettingsResponse;
                const value = submitValues[k];
                const initialValue = initialValues?.[k];
                
                if (value !== initialValue && value !== undefined) {
                    (acc[k] as any) = value;
                }
                return acc;
            }, {});

            if (Object.keys(changedFields).length === 0) {
                message.info('设置未发生变化');
                return;
            }

            const updatedSettings = await siteConfigApi.updateSettings(changedFields);
            // 将返回的设置中的站点列表转换为数组
            const formattedSettings = {
                ...updatedSettings,
                captcha_skip_sites: updatedSettings.captcha_skip_sites?.split(',').filter(Boolean) || [],
                checkin_sites: updatedSettings.checkin_sites?.split(',').filter(Boolean) || []
            };
            setInitialValues(updatedSettings);
            form.setFieldsValue(formattedSettings);
            message.success('保存设置成功');
        } catch (error) {
            message.error('保存设置失败');
            console.error('保存设置失败:', error);
        } finally {
            setLoading(false);
        }
    };

    // 重置设置
    const handleReset = async () => {
        try {
            setLoading(true);
            await siteConfigApi.resetSettings();
            const settings = await siteConfigApi.getSettings();
            // 将逗号分隔的字符串转换为数组
            const formattedSettings = {
                ...settings,
                captcha_skip_sites: settings.captcha_skip_sites?.split(',').filter(Boolean) || [],
                checkin_sites: settings.checkin_sites?.split(',').filter(Boolean) || []
            };
            setInitialValues(settings);
            form.setFieldsValue(formattedSettings);
            message.success('重置设置成功');
        } catch (error) {
            message.error('重置设置失败');
            console.error('重置设置失败:', error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className={styles.settingsContainer}>
            <Form
                form={form}
                layout="vertical"
                initialValues={initialValues || undefined}
            >
                <Form.Item className={styles.formActions}>
                    <Space size="middle">
                        <Popconfirm
                            placement='bottomLeft'
                            title="确认保存设置"
                            description="确定要保存设置吗？"
                            onConfirm={() => handleSave(form.getFieldsValue())}
                            okText="确定"
                            cancelText="取消"
                        >
                            <Button type="primary" loading={loading}>
                                保存设置
                            </Button>
                        </Popconfirm>
                        <Popconfirm
                            placement='bottomLeft'
                            title="确认重置设置"
                            description="确定要重置设置吗？"
                            onConfirm={handleReset}
                            okText="确定"
                            cancelText="取消"
                        >
                            <Button icon={<UndoOutlined />} loading={loading}>
                                重置设置
                            </Button>
                        </Popconfirm>
                    </Space>
                </Form.Item>
                <Row gutter={[16, 16]}>
                    <Col xs={24} lg={12}>
                        <Card title="爬虫设置" size="small" className={styles.settingSection} loading={loading}>
                            <Form.Item label="配置文件路径" name="crawler_config_path">
                                <Input placeholder="services/sites/implementations" />
                            </Form.Item>
                            <Form.Item label="凭证文件路径" name="crawler_credential_path">
                                <Input placeholder="services/sites/credentials" />
                            </Form.Item>
                            <Form.Item label="存储路径" name="crawler_storage_path">
                                <Input placeholder="storage" />
                            </Form.Item>
                            <Form.Item label="最大并发数" name="crawler_max_concurrency">
                                <InputNumber min={1} style={{ width: '100%' }} />
                            </Form.Item>
                            <Form.Item label="每次强制登录" name="fresh_login" valuePropName="checked">
                                <Switch />
                            </Form.Item>
                            <Form.Item label="最大重试次数" name="login_max_retry">
                                <InputNumber min={1} style={{ width: '100%' }} />
                            </Form.Item>
                        </Card>

                        <Card title="验证码设置" size="small" className={styles.settingSection} loading={loading}>
                            <Form.Item label="验证码方法" name="captcha_default_method">
                                <Select>
                                    {CAPTCHA_METHODS.map(method => (
                                        <Option key={method} value={method}>
                                            {method === 'api' ? '2Captcha API' : 
                                            method === 'ddddocr' ? 'DDDD OCR' : 
                                            '手动输入'}
                                        </Option>
                                    ))}
                                </Select>
                            </Form.Item>
                            <Form.Item label="跳过验证码站点" name="captcha_skip_sites">
                                <Select
                                    mode="multiple"
                                    placeholder="选择跳过验证码的站点"
                                    style={{ width: '100%' }}
                                    allowClear
                                >
                                    {siteOptions.map(site => (
                                        <Option key={site} value={site}>{site}</Option>
                                    ))}
                                </Select>
                            </Form.Item>
                            <Form.Item label="API Key" name="captcha_api_key">
                                <Input placeholder="9d0f7571f4fb9f8b78f19bb4c542d5f4" />
                            </Form.Item>
                            <Form.Item label="API URL" name="captcha_api_url">
                                <Input placeholder="http://api.2captcha.com" />
                            </Form.Item>
                            <Form.Item label="最大重试次数" name="captcha_max_retries">
                                <InputNumber min={1} style={{ width: '100%' }} />
                            </Form.Item>
                            <Form.Item label="轮询间隔(秒)" name="captcha_poll_interval">
                                <InputNumber min={1} style={{ width: '100%' }} />
                            </Form.Item>
                            <Form.Item label="超时时间(秒)" name="captcha_timeout">
                                <InputNumber min={1} style={{ width: '100%' }} />
                            </Form.Item>
                        </Card>

                        <Card title="签到设置" size="small" className={styles.settingSection} loading={loading}>
                            <Form.Item label="启用签到" name="enable_checkin" valuePropName="checked">
                                <Switch />
                            </Form.Item>
                            <Form.Item label="签到站点" name="checkin_sites">
                                <Select
                                    mode="multiple"
                                    placeholder="选择需要签到的站点"
                                    style={{ width: '100%' }}
                                    allowClear
                                >
                                    {siteOptions.map(site => (
                                        <Option key={site} value={site}>{site}</Option>
                                    ))}
                                </Select>
                            </Form.Item>
                        </Card>

                    </Col>

                    <Col xs={24} lg={12}>
                        <Card title="浏览器设置" size="small" className={styles.settingSection} loading={loading}>
                            <Form.Item label="视窗宽度" name="browser_viewport_width">
                                <InputNumber min={1} style={{ width: '100%' }} />
                            </Form.Item>
                            <Form.Item label="视窗高度" name="browser_viewport_height">
                                <InputNumber min={1} style={{ width: '100%' }} />
                            </Form.Item>
                            <Form.Item label="Chrome路径" name="chrome_path">
                                <Input placeholder="C:/Users/Lukee/AppData/Local/pyppeteer/pyppeteer/local-chromium/1263111/chrome-win/chrome.exe" />
                            </Form.Item>
                            <Form.Item label="Driver路径" name="driver_path">
                                <Input placeholder="留空" />
                            </Form.Item>
                            <Form.Item label="无头模式" name="headless" valuePropName="checked">
                                <Switch />
                            </Form.Item>
                            <Form.Item label="页面超时(秒)" name="page_timeout">
                                <InputNumber min={1} style={{ width: '100%' }} />
                            </Form.Item>
                            <Form.Item label="导航超时(秒)" name="navigation_timeout">
                                <InputNumber min={1} style={{ width: '100%' }} />
                            </Form.Item>
                            <Form.Item label="请求超时(秒)" name="request_timeout">
                                <InputNumber min={1} style={{ width: '100%' }} />
                            </Form.Item>
                            <Form.Item label="验证SSL" name="verify_ssl" valuePropName="checked">
                                <Switch />
                            </Form.Item>
                            <Form.Item label="重试次数" name="retry_times">
                                <InputNumber min={1} style={{ width: '100%' }} />
                            </Form.Item>
                        </Card>

                        <Card title="日志设置" size="small" className={styles.settingSection} loading={loading}>
                            <Form.Item label="日志级别" name="log_level">
                                <Select>
                                    {LOG_LEVELS.map(level => (
                                        <Option key={level} value={level}>{level}</Option>
                                    ))}
                                </Select>
                            </Form.Item>
                            <Form.Item label="控制台日志级别" name="console_log_level">
                                <Select>
                                    {LOG_LEVELS.map(level => (
                                        <Option key={level} value={level}>{level}</Option>
                                    ))}
                                </Select>
                            </Form.Item>
                            <Form.Item label="文件日志级别" name="file_log_level">
                                <Select>
                                    {LOG_LEVELS.map(level => (
                                        <Option key={level} value={level}>{level}</Option>
                                    ))}
                                </Select>
                            </Form.Item>
                            <Form.Item label="错误日志级别" name="error_log_level">
                                <Select>
                                    {LOG_LEVELS.map(level => (
                                        <Option key={level} value={level}>{level}</Option>
                                    ))}
                                </Select>
                            </Form.Item>
                            <Form.Item label="日志文件" name="log_file">
                                <Input placeholder="task_{time:YYMMDD-HHMM}.log" />
                            </Form.Item>
                            <Form.Item label="错误日志文件" name="error_log_file">
                                <Input placeholder="task_error_{time:YYMMDD-HHMM}.log" />
                            </Form.Item>
                            <Form.Item label="存储路径" name="storage_path">
                                <Input placeholder="storage" />
                            </Form.Item>
                            <Form.Item label="验证码存储路径" name="captcha_storage_path">
                                <Input placeholder="storage/captcha" />
                            </Form.Item>
                        </Card>
                    </Col>
                </Row>
            </Form>
        </div>
    );
};

export default Settings;

