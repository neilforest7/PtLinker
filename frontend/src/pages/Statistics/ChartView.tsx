import React, { useEffect, useState } from 'react';
import { Spin, Empty, Radio, Space, Select, Segmented, Button, Divider } from 'antd';
import { siteConfigApi } from '../../api/siteConfig';
import { StatisticsHistoryResponse } from '../../types/api';
import { toUTC8DateString } from '../../utils/dateUtils';
import styles from './Statistics.module.css';
import { ReloadOutlined } from '@ant-design/icons';
import { TimeRange, MetricType, metricLabels } from './utils/chartUtils';
import OverviewChart from './components/OverviewChart';
import StreamChart from './components/StreamChart';
import StatisticsLineChart from './components/StatisticsLineChart';
import BlockView from './components/BlockView';

const ChartView: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [statistics, setStatistics] = useState<StatisticsHistoryResponse | null>(null);
    const [timeRange, setTimeRange] = useState<TimeRange>('7');
    const [metric, setMetric] = useState<MetricType>('upload');
    const [selectedSites, setSelectedSites] = useState<string[]>([]);
    const [siteOptions, setSiteOptions] = useState<{ label: string; value: string; }[]>([]);

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
            const end = new Date();
            const start = new Date();
            
            if (timeRange !== 'all') {
                const days = parseInt(timeRange);
                start.setDate(end.getDate() - days + 1);
            } else {
                start.setDate(end.getDate() - 365);
            }

            const params = {
                start_date: toUTC8DateString(start),
                end_date: toUTC8DateString(end)
            };

            const data = await siteConfigApi.getStatisticsHistory(params);
            setStatistics(data);
        } catch (error) {
            console.error('加载统计数据失败:', error);
        } finally {
            setLoading(false);
        }
    };

    // 修改 useEffect，在 timeRange 变化时重新加载数据
    useEffect(() => {
        loadStatistics();
    }, [timeRange]); // 添加 timeRange 作为依赖

    if (loading) {
        return <Spin size="large" />;
    }

    if (!statistics || !statistics.metrics.daily_results.length) {
        return <Empty description="暂无统计数据" />;
    }

    return (
        <div className={styles.chartContainer}>
            <Radio.Group 
                value={timeRange} 
                onChange={e => setTimeRange(e.target.value)}
                buttonStyle="solid"
                className={styles.timeRangeGroup}
            >
                <Radio.Button value="7">近7天</Radio.Button>
                <Radio.Button value="30">近30天</Radio.Button>
                <Radio.Button value="60">近60天</Radio.Button>
                <Radio.Button value="90">近90天</Radio.Button>
                <Radio.Button value="180">近180天</Radio.Button>
                <Radio.Button value="all">所有</Radio.Button>
            </Radio.Group>

            <OverviewChart 
                statistics={statistics} 
                timeRange={timeRange} 
            />

            <BlockView />

            <div className={styles.chartControls}>
                <Segmented
                    value={metric}
                    onChange={value => setMetric(value as MetricType)}
                    options={Object.entries(metricLabels).map(([value, label]) => ({
                        value,
                        label
                    }))}
                    className={styles.metricSelect}
                />

                <Space className={styles.siteSelectContainer}>
                    <Select
                        mode="multiple"
                        allowClear
                        placeholder="选择要对比的站点"
                        value={selectedSites}
                        onChange={setSelectedSites}
                        maxTagCount={6}
                        className={styles.siteSelect}
                        optionLabelProp="label"
                        options={siteOptions.map(site => ({
                            value: site.value,
                            label: site.label,
                            optionRender: (option: any) => (
                                <Space>
                                    <span>{site.label}</span>
                                </Space>
                            ),
                        }))}
                        dropdownRender={(menu) => (
                            <>
                                <Space style={{ padding: '0 8px 4px' }}>
                                    <Button
                                        type="text"
                                        icon={<ReloadOutlined />}
                                        size="small"
                                        onClick={() => setSelectedSites(siteOptions.map(s => s.value))}>
                                        全选
                                    </Button>
                                    <Button
                                        type="text"
                                        icon={<ReloadOutlined />}
                                        size="small"
                                        onClick={() => setSelectedSites([])}>
                                        只显示统计
                                    </Button>
                                </Space>
                                <Divider style={{ margin: '0' }} />
                                {menu}
                            </>
                        )}
                    />
                </Space>
            </div>

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
    );
};

export default ChartView; 