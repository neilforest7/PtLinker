import React, { useState, useEffect } from 'react';
import { Card, Button, Space, Tag, Typography, Popconfirm, message, Spin } from 'antd';
import {
    SyncOutlined,
    ExperimentOutlined,
    BarChartOutlined,
    HolderOutlined,
    UploadOutlined,
    DownloadOutlined,
    PercentageOutlined,
    SettingOutlined
} from '@ant-design/icons';
import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    DragEndEvent
} from '@dnd-kit/core';
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    useSortable,
    rectSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import styles from './Sites.module.css';
import SiteSettingsModal from '../../components/SiteSettingsModal';
import AddSiteModal from '../../components/AddSiteModal';
import SiteStatisticsModal from '../../components/SiteStatisticsModal';
import { siteConfigApi } from '../../api/siteConfig';

const { Text, Link } = Typography;

interface SiteData {
    id: string;
    site_id: string;
    name: string;
    base_url: string;
    connect_status: 'online' | 'offline';
    favicon?: string;
    upload: number;
    download: number;
    ratio: number;
}

interface SortableSiteCardProps {
    site: SiteData;
    onSettingsClick: (site: SiteData) => void;
    onUpdateClick: (site: SiteData) => void;
    onStatisticsClick: (site: SiteData) => void;
}

const SortableSiteCard: React.FC<SortableSiteCardProps> = ({ 
    site, 
    onSettingsClick, 
    onUpdateClick,
    onStatisticsClick 
}) => {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging
    } = useSortable({ id: site.id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
    };

    const handleVisitSite = (e: React.MouseEvent) => {
        e.preventDefault();
    };

    return (
        <div ref={setNodeRef} style={style} className={styles.siteWrapper}>
            <Card
                className={styles.siteCard}
                // styles={{ padding: '12px' }}
                actions={[
                    <Popconfirm
                        key="update"
                        placement='topLeft'
                        title="确认更新"
                        description="确定要更新该站点吗？"
                        okText="确定"
                        cancelText="取消"
                        onConfirm={(e) => {
                            e?.stopPropagation();
                            onUpdateClick(site);
                        }}
                    >
                        <SyncOutlined title="更新" />
                    </Popconfirm>,
                    <ExperimentOutlined key="test" title="测试" />,
                    <BarChartOutlined 
                        key="stats" 
                        title="数据"
                        onClick={(e) => {
                            e.stopPropagation();
                            onStatisticsClick(site);
                        }}
                    />,
                    <SettingOutlined 
                        key="setting" 
                        title="设置"
                        onClick={(e) => {
                            e.stopPropagation();
                            onSettingsClick(site);
                        }}
                    />
                ]}
            >
                <div className={styles.cardHeader}>
                    <div
                        className={styles.dragHandle}
                        {...attributes}
                        {...listeners}
                    >
                        <HolderOutlined />
                    </div>
                    <div className={styles.siteInfo}>
                        {site.favicon && (
                            <img
                                src={site.favicon}
                                alt={site.name}
                                className={styles.favicon}
                            />
                        )}
                        <Text strong>{site.name}</Text>
                    </div>
                </div>
                <div className={styles.siteContent}>
                    <Popconfirm
                        placement='topLeft'
                        title="站点地址"
                        description="要访问该站点吗？"
                        okText="确定"
                        cancelText="取消"
                        onConfirm={() => window.open(site.base_url, '_blank')}
                    >
                        <Link 
                            href={site.base_url} 
                            onClick={handleVisitSite}
                        >
                            {site.base_url}
                        </Link>
                    </Popconfirm>
                    <Tag
                        color={site.connect_status === 'online' ? 'success' : 'error'}
                        className={styles.statusTag}
                    >
                        {site.connect_status === 'online' ? '在线' : '离线'}
                    </Tag>
                    <Space className={styles.stats}>
                        <span>
                            <UploadOutlined /> {site.upload} GB
                        </span>
                        <span>
                            <DownloadOutlined /> {site.download} GB
                        </span>
                        <span>
                            <PercentageOutlined /> {site.ratio}
                        </span>
                    </Space>
                </div>
            </Card>
        </div>
    );
};

const Sites: React.FC = () => {
    const [sites, setSites] = useState<SiteData[]>([]);
    const [loading, setLoading] = useState(false);
    const [selectedSite, setSelectedSite] = useState<SiteData | undefined>();
    const [settingsVisible, setSettingsVisible] = useState(false);
    const [originalValues, setOriginalValues] = useState<any>(null);
    const [addSiteVisible, setAddSiteVisible] = useState(false);
    const [statisticsVisible, setStatisticsVisible] = useState(false);

    const sensors = useSensors(
        useSensor(PointerSensor),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

    const handleDragEnd = (event: DragEndEvent) => {
        const { active, over } = event;

        if (over && active.id !== over.id) {
            setSites((items) => {
                const oldIndex = items.findIndex(item => item.id === active.id);
                const newIndex = items.findIndex(item => item.id === over.id);
                return arrayMove(items, oldIndex, newIndex);
            });
        }
    };

    const handleSettingsClick = async (site: SiteData) => {
        try {
            setLoading(true);
            const [siteConfig, crawlerConfig, credential] = await Promise.all([
                siteConfigApi.getSiteConfig(site.site_id),
                siteConfigApi.getCrawlerConfig(site.site_id),
                siteConfigApi.getCredential(site.site_id).catch(() => null)
            ]);

            // 保存原始值
            setOriginalValues({
                site_url: siteConfig.site_url,
                login_config: JSON.stringify(siteConfig.login_config || {}, null, 2),
                extract_rules: JSON.stringify(siteConfig.extract_rules || {}, null, 2),
                checkin_config: JSON.stringify(siteConfig.checkin_config || {}, null, 2),
                ...crawlerConfig,
                ...(credential || {})
            });

            setSelectedSite(site);
            setSettingsVisible(true);
        } catch (error) {
            message.error('加载站点配置失败');
            console.error('加载站点配置失败:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleSettingsSave = async (values: any, globalValues?: Record<string, boolean>) => {
        try {
            setLoading(true);
            const updates = [];

            if (selectedSite?.site_id && originalValues) {
                // 处理站点配置更新
                const siteConfigChanges: Record<string, any> = {};
                let hasSiteConfigChanges = false;

                // 检查 site_url 变化
                if (values.site_url !== originalValues.site_url
                    && typeof values.site_url !== 'undefined'
                    && values.site_url !== null
                    && values.site_url !== ''
                    && values.site_url.startsWith('http')
                ) {
                    siteConfigChanges.site_url = values.site_url;
                    hasSiteConfigChanges = true;
                }

                // 检查 JSON 配置变化
                const jsonFields = ['login_config', 'extract_rules', 'checkin_config'];
                for (const field of jsonFields) {
                    try {
                        const newValue = JSON.parse(values[field] || '{}');
                        const oldValue = JSON.parse(originalValues[field] || '{}');
                        if (JSON.stringify(newValue) !== JSON.stringify(oldValue)) {
                            siteConfigChanges[field] = newValue;
                            hasSiteConfigChanges = true;
                        }
                    } catch (e) {
                        message.error(`${field} 格式错误`);
                        return;
                    }
                }

                // 处理爬虫配置更新
                const crawlerConfigChanges: Record<string, any> = {};
                let hasCrawlerConfigChanges = false;
                const crawlerFields = ['enabled', 'use_proxy', 'proxy_url', 'fresh_login', 
                                        'captcha_method', 'captcha_skip', 'timeout', 
                                        'headless', 'login_max_retry'];
                
                crawlerFields.forEach(field => {
                    const isGlobalValue = globalValues?.[field] || false;
                    
                    // 只有在值不是全局设置且确实发生变化时更新
                    if (!isGlobalValue && 
                        typeof values[field] !== 'undefined' &&
                        values[field] !== null &&
                        values[field] !== originalValues[field]) {
                        crawlerConfigChanges[field] = values[field];
                        hasCrawlerConfigChanges = true;
                    }
                });

                // 处理凭证更新
                const credentialChanges: Record<string, any> = {};
                let hasCredentialChanges = false;
                const credentialFields = ['enable_manual_cookies', 'manual_cookies', 
                                        'username', 'password', 'authorization', 'apikey'];
                
                credentialFields.forEach(field => {
                    if (typeof values[field] !== 'undefined' && 
                        values[field] !== null && 
                        values[field] !== originalValues[field]) {
                        credentialChanges[field] = values[field];
                        hasCredentialChanges = true;
                    }
                });

                // 只有有变更时才发送更新请求
                if (hasSiteConfigChanges) {
                    console.log('siteConfigChanges', siteConfigChanges);
                    updates.push(siteConfigApi.updateSiteConfig(selectedSite.site_id, siteConfigChanges));
                }

                if (hasCrawlerConfigChanges) {
                    console.log('crawlerConfigChanges', crawlerConfigChanges);
                    updates.push(siteConfigApi.updateCrawlerConfig(selectedSite.site_id, crawlerConfigChanges));
                }

                if (hasCredentialChanges) {
                    console.log('credentialChanges', credentialChanges);
                    updates.push(siteConfigApi.updateCredential(selectedSite.site_id, credentialChanges));
                }

                if (updates.length > 0) {
                    console.log('all updates', updates);
                    await Promise.all(updates);
                    message.success('保存成功');
                    loadSitesData();
                } else {
                    message.info('没有需要保存的更改');
                }
            }
            setSettingsVisible(false);
            setOriginalValues(null);
        } catch (error) {
            message.error('保存失败');
            console.error('保存失败:', error);
        } finally {
            setLoading(false);
        }
    };

    const loadSitesData = async () => {
        try {
            setLoading(true);
            const [siteConfigs, statistics, tasks] = await Promise.all([
                siteConfigApi.getAllSiteConfigs(),
                siteConfigApi.getSiteStatistics(),
                siteConfigApi.getAllSitesTasks()
            ]);

            // 处理统计数据
            const statsMap = new Map();
            if (statistics.metrics.daily_results) {
                statistics.metrics.daily_results.forEach((result: any) => {
                    statsMap.set(result.site_id, {
                        upload: result.upload || 0,
                        download: result.download || 0,
                        ratio: result.ratio || 0
                    });
                });
            }

            // 处理任务状态
            const tasksMap = new Map();
            tasks.forEach((task: any) => {
                const currentTask = tasksMap.get(task.site_id);
                // 如果是第一个任务或者比现有任务更新
                if (!currentTask || new Date(task.created_at) > new Date(currentTask.created_at)) {
                    tasksMap.set(task.site_id, task);
                }
            });

            // 判断任务状态是否为今天
            const isToday = (dateStr: string) => {
                const taskDate = new Date(dateStr);
                const today = new Date();
                return taskDate.getDate() === today.getDate() &&
                    taskDate.getMonth() === today.getMonth() &&
                    taskDate.getFullYear() === today.getFullYear();
            };

            // 组合数据
            const sitesData = siteConfigs.map(config => {
                const stats = statsMap.get(config.site_id) || {
                    upload: 0,
                    download: 0,
                    ratio: 0
                };

                // 获取该站点的最新任务
                const latestTask = tasksMap.get(config.site_id);
                
                // 判断该站点的连接状态
                let connect_status: 'online' | 'offline' = 'offline';
                if (latestTask) {
                    const isTaskToday = isToday(latestTask.created_at);
                    const isTaskSuccess = latestTask.status === 'success';
                    connect_status = (isTaskToday && isTaskSuccess) ? 'online' : 'offline';
                }
                
                return {
                    id: config.site_id,
                    site_id: config.site_id,
                    name: config.site_id,
                    base_url: config.site_url,
                    connect_status,
                    favicon: `${config.site_url}/favicon.ico`,
                    upload: stats.upload,
                    download: stats.download,
                    ratio: stats.ratio
                };
            });

            setSites(sitesData);
        } catch (error) {
            message.error('加载站点数据失败');
            console.error('加载站点数据失败:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleUpdateClick = async (site: SiteData) => {
        try {
            const tasks = await siteConfigApi.createTasks(false, site.site_id);
            if (tasks.length > 0) {
                message.success('成功创建更新任务');
            } else {
                message.warning('创建任务失败，请检查站点配置');
            }
        } catch (error) {
            message.error('创建更新任务失败');
            console.error('创建更新任务失败:', error);
        }
    };

    const handleStatisticsClick = (site: SiteData) => {
        setSelectedSite(site);
        setStatisticsVisible(true);
    };

    useEffect(() => {
        loadSitesData();
    }, []);

    return (
        <Spin spinning={loading}>
            <div className={styles.sitesContainer}>
                <div className={styles.header}>
                    <Space>
                        <Button 
                            type="primary"
                            onClick={() => setAddSiteVisible(true)}
                        >
                            添加站点
                        </Button>
                        <Popconfirm
                            placement='bottomLeft'
                            title="确认开始爬取"
                            description="确定要开始爬取所有站点吗？"
                            okText="确定"
                            cancelText="取消"
                            onConfirm={async () => {
                                try {
                                    const tasks = await siteConfigApi.createTasks(true);
                                    const successCount = tasks.length;
                                    if (successCount > 0) {
                                        message.success(`成功创建 ${successCount} 个任务`);
                                    } else {
                                        message.warning('没有创建任何任务，请检查站点配置');
                                    }
                                } catch (error) {
                                    message.error('创建任务失败');
                                    console.error('创建任务失败:', error);
                                }
                            }}
                        >
                            <Button icon={<SyncOutlined />}>开始爬取所有站点</Button>
                        </Popconfirm>
                        <Popconfirm
                            placement='bottomLeft'
                            title="确认重试"
                            description="确定要重试所有失败的站点吗？"
                            okText="确定"
                            cancelText="取消"
                            onConfirm={async () => {
                                try {
                                    const tasks = await siteConfigApi.retryFailedTasks();
                                    const successCount = tasks.length;
                                    if (successCount > 0) {
                                        message.success(`成功重试 ${successCount} 个失败任务`);
                                    } else {
                                        message.info('没有找到需要重试的失败任务');
                                    }
                                } catch (error) {
                                    message.error('重试失败任务失败');
                                    console.error('重试失败任务失败:', error);
                                }
                            }}
                        >
                            <Button icon={<SyncOutlined />}>重试失败站点</Button>
                        </Popconfirm>
                    </Space>
                </div>
                <DndContext
                    sensors={sensors}
                    collisionDetection={closestCenter}
                    onDragEnd={handleDragEnd}
                >
                    <SortableContext
                        items={sites.map(site => site.id)}
                        strategy={rectSortingStrategy}
                    >
                        <div className={styles.sitesGrid}>
                            {sites.map((site) => (
                                <SortableSiteCard
                                    key={site.id}
                                    site={site}
                                    onSettingsClick={handleSettingsClick}
                                    onUpdateClick={handleUpdateClick}
                                    onStatisticsClick={handleStatisticsClick}
                                />
                            ))}
                        </div>
                    </SortableContext>
                </DndContext>

                <SiteSettingsModal
                    visible={settingsVisible}
                    site={selectedSite}
                    onClose={() => setSettingsVisible(false)}
                    onSave={handleSettingsSave}
                />

                <AddSiteModal
                    visible={addSiteVisible}
                    onClose={() => setAddSiteVisible(false)}
                    onSuccess={loadSitesData}
                />

                <SiteStatisticsModal
                    visible={statisticsVisible}
                    site={selectedSite}
                    onClose={() => setStatisticsVisible(false)}
                />
            </div>
        </Spin>
    );
};

export default Sites;

