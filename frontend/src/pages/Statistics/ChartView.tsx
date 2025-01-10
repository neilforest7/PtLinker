import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Spin, Empty, Space, Select, Segmented, Button, Affix, FloatButton, Divider } from 'antd';
import { siteConfigApi } from '../../api/siteConfig';
import { StatisticsHistoryResponse } from '../../types/api';
import { toUTC8DateString } from '../../utils/dateUtils';
import styles from './Statistics.module.css';
import { ReloadOutlined, FieldTimeOutlined, AppstoreOutlined, TeamOutlined } from '@ant-design/icons';
import { TimeRange, MetricType, metricLabels } from './utils/chartUtils';
import OverviewChart from './components/OverviewChart';
import StreamChart from './components/StreamChart';
import StatisticsLineChart from './components/StatisticsLineChart';
import { CacheEntry, CacheMap, CACHE_EXPIRY_TIME } from './utils/chartUtils';
const timeRangeOptions = [
    { value: '7', label: '近7天' },
    { value: '14', label: '近14天' },
    { value: '30', label: '近30天' },
    { value: '60', label: '近60天' },
    { value: '90', label: '近90天' },
    { value: '180', label: '近180天' },
    { value: 'all', label: '所有' },
];

const ChartView: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [statistics, setStatistics] = useState<StatisticsHistoryResponse | null>(null);
    const [timeRange, setTimeRange] = useState<TimeRange>('7');
    const [metric, setMetric] = useState<MetricType>('upload');
    const [selectedSites, setSelectedSites] = useState<string[]>([]);
    const [siteOptions, setSiteOptions] = useState<{ label: string; value: string; }[]>([]);
    const [activeControl, setActiveControl] = useState<'time' | 'metric' | 'sites' | null>(null);
    const cacheRef = useRef<CacheMap>({});
    const controlTimeoutRef = useRef<ReturnType<typeof setTimeout>>();

    // 检查缓存是否有效
    const isCacheValid = useCallback((cacheEntry: CacheEntry | undefined, start: string, end: string): boolean => {
        if (!cacheEntry) return false;
        
        const now = Date.now();
        return (
            now - cacheEntry.timestamp < CACHE_EXPIRY_TIME && // 缓存未过期
            cacheEntry.startDate === start && // 开始日期匹配
            cacheEntry.endDate === end // 结束日期匹配
        );
    }, []);

    // 清理过期缓存
    const cleanExpiredCache = useCallback(() => {
        const now = Date.now();
        Object.keys(cacheRef.current).forEach(key => {
            if (now - cacheRef.current[key].timestamp >= CACHE_EXPIRY_TIME) {
                delete cacheRef.current[key];
            }
        });
    }, []);

    const loadSiteConfigs = async () => {
        try {
            // 获取所有站点配置
            const configs = await siteConfigApi.getAllCrawlerConfigs();
            
            // 获取统计数据中实际存在的站点
            const existingSites = new Set(
                statistics?.metrics.daily_results.map(result => result.site_id) || []
            );

            // 只保留有统计数据的站点
            const options = configs
                .filter(config => existingSites.has(config.site_id))
                .map(config => ({
                    label: config.site_id,
                    value: config.site_id
                }));

            setSiteOptions(options);
            // 设置所有站点为选中状态
            setSelectedSites(options.map(option => option.value));
        } catch (error) {
            console.error('加载站点配置失败:', error);
        }
    };

    // 当统计数据加载完成后，重新加载站点配置
    useEffect(() => {
        if (statistics) {
            loadSiteConfigs();
        }
    }, [statistics]);

    const loadStatistics = async () => {
        try {
            setLoading(true);
            
            // 计算时间范围
            const end = new Date();
            end.setHours(23, 59, 59, 999);
            const start = new Date(end);
            
            if (timeRange !== 'all') {
                const days = parseInt(timeRange);
                start.setDate(end.getDate() - days + 1);
                start.setHours(0, 0, 0, 0);
            } else {
                start.setMonth(start.getMonth() - 12);
                start.setDate(1);
                start.setHours(0, 0, 0, 0);
            }

            const params = {
                start_date: toUTC8DateString(start),
                end_date: toUTC8DateString(end)
            };

            // 检查缓存
            const cacheKey = `${timeRange}`;
            const cachedData = cacheRef.current[cacheKey];

            if (isCacheValid(cachedData, params.start_date, params.end_date)) {
                console.log('使用缓存数据:', cacheKey);
                setStatistics(cachedData.data);
                return;
            }

            // 清理过期缓存
            cleanExpiredCache();

            console.log('请求新数据:', params);
            const data = await siteConfigApi.getStatisticsHistory(params);
            
            // 更新缓存
            cacheRef.current[cacheKey] = {
                data,
                timestamp: Date.now(),
                startDate: params.start_date,
                endDate: params.end_date
            };
            
            setStatistics(data);
        } catch (error) {
            console.error('加载统计数据失败:', error);
        } finally {
            setLoading(false);
        }
    };

    // 添加手动刷新功能
    const handleRefresh = useCallback(() => {
        // 清除当前时间范围的缓存
        const cacheKey = `${timeRange}`;
        delete cacheRef.current[cacheKey];
        loadStatistics();
    }, [timeRange]);

    // 添加滚动位置记忆功能
    const maintainScrollPosition = useCallback((callback: () => void) => {
        const scrollPosition = window.scrollY;
        callback();
        requestAnimationFrame(() => {
            window.scrollTo({
                top: scrollPosition,
                behavior: 'instant'
            });
        });
    }, []);

    const handleTimeRangeChange = (value: string | number) => {
        maintainScrollPosition(() => {
            setTimeRange(value as TimeRange);
        });
    };

    const handleMetricChange = (value: string | number) => {
        maintainScrollPosition(() => {
            setMetric(value as MetricType);
        });
    };

    const handleSitesChange = (value: string[]) => {
        maintainScrollPosition(() => {
            setSelectedSites(value);
        });
    };

    // 使用useEffect监听timeRange的变化
    useEffect(() => {
        if (timeRange) {
            loadStatistics();
        }
    }, [timeRange]); // 依赖于timeRange

    // 组件初始化时加载数据
    useEffect(() => {
        loadStatistics();
    }, []); // 只在组件挂载时执行一次

    // 处理鼠标进入控制按钮
    const handleMouseEnter = (control: 'time' | 'metric' | 'sites') => {
        if (controlTimeoutRef.current) {
            clearTimeout(controlTimeoutRef.current);
        }
        setActiveControl(control);
    };

    // 处理鼠标离开控制区域
    const handleMouseLeave = () => {
        controlTimeoutRef.current = setTimeout(() => {
            setActiveControl(null);
        }, 500); // 300ms延迟，避免面板闪烁
    };

    if (loading) {
        return <Spin size="large" />;
    }

    if (!statistics || !statistics.metrics.daily_results.length) {
        return <Empty description="暂无统计数据" />;
    }

    return (
        <div className={styles.chartContainer}>
            <Affix className={styles.controlButtonGroup}>
                <div 
                    className={styles.timeControl}
                    onMouseEnter={() => handleMouseEnter('time')}
                    onMouseLeave={handleMouseLeave}
                >
                    <FloatButton
                        icon={<FieldTimeOutlined />}
                        tooltip="时间范围"
                        type={activeControl === 'time' ? 'primary' : 'default'}
                    />
                    {activeControl === 'time' && (
                        <div 
                            className={styles.controlPanel} 
                            onClick={e => e.stopPropagation()}
                        >
                            <Segmented
                                value={timeRange}
                                onChange={handleTimeRangeChange}
                                options={timeRangeOptions}
                                block={true}
                                className={styles.segmentedControl}
                            />
                        </div>
                    )}
                </div>

                <div 
                    className={styles.metricControl}
                    onMouseEnter={() => handleMouseEnter('metric')}
                    onMouseLeave={handleMouseLeave}
                >
                    <FloatButton
                        icon={<AppstoreOutlined />}
                        tooltip="指标类型"
                        type={activeControl === 'metric' ? 'primary' : 'default'}
                    />
                    {activeControl === 'metric' && (
                        <div 
                            className={styles.controlPanel} 
                            onClick={e => e.stopPropagation()}
                        >
                            <Segmented
                                value={metric}
                                onChange={handleMetricChange}
                                options={Object.entries(metricLabels).map(([value, label]) => ({
                                    value,
                                    label
                                }))}
                                block={true}
                                className={styles.segmentedControl}
                            />
                        </div>
                    )}
                </div>

                <div 
                    className={styles.siteControl}
                    onMouseEnter={() => handleMouseEnter('sites')}
                    onMouseLeave={handleMouseLeave}
                >
                    <FloatButton
                        icon={<TeamOutlined />}
                        tooltip="站点选择"
                        type={activeControl === 'sites' ? 'primary' : 'default'}
                    />
                    {activeControl === 'sites' && (
                        <div 
                            className={styles.controlPanel} 
                            onClick={e => e.stopPropagation()}
                        >
                            <div>
                                <Space className={styles.siteButtons}>
                                    <Button
                                        type="primary"
                                        icon={<ReloadOutlined />}
                                        onClick={() => handleSitesChange(siteOptions.map(s => s.value))}
                                        size="small"
                                    >
                                        全选
                                    </Button>
                                    <Button
                                        icon={<ReloadOutlined />}
                                        onClick={() => handleSitesChange([])}
                                        size="small"
                                    >
                                        只显示统计
                                    </Button>
                                </Space>
                                <Divider />
                                <Select
                                    mode="multiple"
                                    allowClear
                                    placeholder="选择要对比的站点"
                                    value={selectedSites}
                                    onChange={handleSitesChange}
                                    maxTagCount={8}
                                    className={styles.siteSelect}
                                    options={siteOptions}
                                />
                            </div>
                        </div>
                    )}
                </div>

                <div className={styles.refreshControl}>
                    <FloatButton
                        icon={<ReloadOutlined />}
                        tooltip="刷新数据"
                        onClick={handleRefresh}
                    />
                </div>
            </Affix>
            
            <OverviewChart 
                statistics={statistics} 
                timeRange={timeRange} 
            />

            <div className={styles.chartsGrid}>
                <StreamChart 
                    statistics={statistics}
                    timeRange={timeRange}
                    metric={metric}
                    selectedSites={selectedSites}
                />

                <StatisticsLineChart 
                    statistics={statistics}
                    timeRange={timeRange}
                    metric={metric}
                    selectedSites={selectedSites}
                />
            </div>
        </div>
    );
};

export default ChartView; 