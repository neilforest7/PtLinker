import React, { useEffect, useState } from 'react';
import { Spin, Empty, Radio, Space, Select } from 'antd';
import { Chart } from '@antv/g2';
import { siteConfigApi } from '../../api/siteConfig';
import { StatisticsHistoryResponse } from '../../types/api';
import styles from './Statistics.module.css';
import { TimeRange, MetricType, ChartDataItem, metricLabels } from './ChartView';

const BlockView: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [statistics, setStatistics] = useState<StatisticsHistoryResponse | null>(null);
    const [metric, setMetric] = useState<MetricType>('upload');
    const [blockChart, setBlockChart] = useState<Chart | null>(null);
    const [selectedSites, setSelectedSites] = useState<string[]>([]);
    const [siteOptions, setSiteOptions] = useState<{ label: string; value: string; }[]>([]);

    const loadSiteConfigs = async () => {
        try {
            const configs = await siteConfigApi.getAllCrawlerConfigs();
            const existingSites = new Set(
                statistics?.metrics.daily_results.map(result => result.site_id) || []
            );

            const options = configs
                .filter(config => existingSites.has(config.site_id))
                .map(config => ({
                    label: config.site_id,
                    value: config.site_id
                }));

            setSiteOptions(options);
            if (options.length > 0) {
                setSelectedSites([options[0].value]); // 默认选择第一个站点
            }
        } catch (error) {
            console.error('加载站点配置失败:', error);
        }
    };

    useEffect(() => {
        if (statistics) {
            loadSiteConfigs();
        }
    }, [statistics]);

    const loadStatistics = async () => {
        try {
            setLoading(true);
            const data = await siteConfigApi.getStatisticsHistory();
            setStatistics(data);
        } catch (error) {
            console.error('加载统计数据失败:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadStatistics();
    }, []);

    useEffect(() => {
        if (!statistics || !statistics.metrics.daily_results.length || !selectedSites.length) return;

        // 过滤选中站点的数据
        const siteData = statistics.metrics.daily_results.filter(
            item => selectedSites.includes(item.site_id)
        );

        // 准备热力图数据
        const blockData = siteData.map(item => {
            const date = new Date(item.date);
            return {
                date: item.date,
                day: date.getDay(), // 0-6 表示周日到周六
                week: Math.floor((date.getTime() - new Date(date.getFullYear(), 0, 1).getTime()) / (7 * 24 * 60 * 60 * 1000)),
                value: item[metric] || 0
            };
        });

        // 创建热力图
        if (blockChart) {
            blockChart.destroy();
        }

        const chart = new Chart({
            container: 'blockChart',
            autoFit: true,
            height: 200,
            paddingLeft: 50,
            paddingRight: 50,
        });

        chart.data(blockData);

        chart.scale({
            week: {
                type: 'cat',
            },
            day: {
                type: 'cat',
            },
            value: {
                nice: true,
            },
        });

        chart.axis(false);

        chart.legend('value', {
            position: 'bottom',
        });

        chart
            .polygon()
            .encode('position', ['week', 'day'])
            .encode('color', 'value')
            .style('stroke', '#fff')
            .style('strokeWidth', 1)
            .style('lineWidth', 1)
            .scale('color', {
                palette: 'green',
                offset: (t) => t ** 2,
            })
            .tooltip({
                items: [
                    (d: any) => ({
                        name: '日期',
                        value: new Date(d.date).toLocaleDateString()
                    }),
                    (d: any) => ({
                        name: metricLabels[metric],
                        value: d.value.toFixed(2)
                    })
                ]
            });

        chart.render();
        setBlockChart(chart);

        return () => {
            if (blockChart) {
                blockChart.destroy();
            }
        };
    }, [statistics, metric, selectedSites]);

    if (loading) {
        return <Spin size="large" />;
    }

    if (!statistics || !statistics.metrics.daily_results.length) {
        return <Empty description="暂无统计数据" />;
    }

    return (
        <div className={styles.chartContainer}>
            <div className={styles.chartControls}>
                <Space size="middle">
                    <Select
                        value={metric}
                        onChange={setMetric}
                        className={styles.metricSelect}
                        options={Object.entries(metricLabels).map(([value, label]) => ({
                            value,
                            label
                        }))}
                    />
                    <Select
                        mode="multiple"
                        allowClear
                        placeholder="选择站点"
                        value={selectedSites}
                        onChange={setSelectedSites}
                        options={siteOptions}
                        className={styles.siteSelect}
                        style={{ minWidth: '200px' }}
                        maxTagCount={3}
                    />
                </Space>
            </div>
            <div id="blockChart" className={styles.chartContent} />
        </div>
    );
};

export default BlockView; 