import React, { useEffect, useState } from 'react';
import { Spin, Empty, Radio, Space, Select, Segmented, Button, Divider } from 'antd';
import { Chart } from '@antv/g2';
import { siteConfigApi } from '../../api/siteConfig';
import { StatisticsHistoryResponse } from '../../types/api';
import { toUTC8DateString, parseUTC8Date, formatDate } from '../../utils/dateUtils';
import styles from './Statistics.module.css';
import BlockView from './BlockView';
import { ReloadOutlined } from '@ant-design/icons';

export type TimeRange = '7' | '30' | '60' | '90' | '180' | 'all';
export type MetricType = 'upload' | 'seeding_size' | 'seeding_count' | 'bonus' | 'download' | 'seeding_score' | 'bonus_per_hour';

export interface ChartDataItem {
    date: string;
    site?: string;
    upload?: number;
    download?: number;
    bonus?: number;
    bonus_per_hour?: number;
    seeding_score?: number;
    seeding_size?: number;
    seeding_count?: number;
    [key: string]: string | number | undefined;
}

export const metricLabels: Record<MetricType, string> = {
    upload: '上传量',
    download: '下载量',
    seeding_size: '做种体积',
    seeding_count: '做种数量',
    bonus: '魔力值',
    bonus_per_hour: '时魔',
    seeding_score: '保种积分',
};

const formatValue = (value: number | null | undefined, type: MetricType) => {
    if (value === null || value === undefined) {
        switch (type) {
            case 'upload':
            case 'download':
                return '0 GB';
            case 'seeding_size':
                return '0 TB';
            default:
                return '0';
        }
    }

    switch (type) {
        case 'upload':
        case 'download':
            return `${value.toFixed(1)} GB`;
        case 'seeding_size':
            return `${(value / 1024).toFixed(2)} TB`;  // 转换为 TB
        case 'seeding_count':
            return value.toString();
        case 'bonus':
        case 'bonus_per_hour':
        case 'seeding_score':
            return value.toFixed(1);
        default:
            return value.toString();
    }
};

const ChartView: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [statistics, setStatistics] = useState<StatisticsHistoryResponse | null>(null);
    const [timeRange, setTimeRange] = useState<TimeRange>('7');
    const [metric, setMetric] = useState<MetricType>('upload');
    const [perStatChart, setPerStatChart] = useState<Chart | null>(null);
    const [selectedSites, setSelectedSites] = useState<string[]>([]);
    const [siteOptions, setSiteOptions] = useState<{ label: string; value: string; }[]>([]);
    const [overviewChart, setOverviewChart] = useState<Chart | null>(null);

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

    const filterDataByTimeRange = (data: ChartDataItem[]) => {
        if (timeRange === 'all') return data;

        const days = parseInt(timeRange);
        const end = new Date();
        const start = new Date();
        start.setDate(end.getDate() - days + 1);

        return data.filter(item => {
            const itemDate = parseUTC8Date(item.date);
            return itemDate >= start && itemDate <= end;
        });
    };

    useEffect(() => {
        if (!statistics || !statistics.metrics.daily_results.length) return;

        // 处理数据
        const processedData = statistics.metrics.daily_results.reduce((acc, curr) => {
            const date = curr.date;  // 这里的 date 已经是 UTC+8 的日期字符串
            if (!acc[date]) {
                acc[date] = {
                    date,
                    sites: {}
                };
            }
            acc[date].sites[curr.site_id] = {
                upload: curr.upload,
                download: curr.download,
                bonus: curr.bonus,
                bonus_per_hour: curr.bonus_per_hour,
                seeding_score: curr.seeding_score,
                seeding_size: curr.seeding_size,
                seeding_count: curr.seeding_count,
            };
            return acc;
        }, {} as Record<string, any>);

        let chartData = Object.values(processedData).map(day => {
            const siteData = Object.entries(day.sites).map(([siteId, data]: [string, any]) => ({
                date: day.date,
                site: siteId,
                [metric]: data[metric]
            }));
            return siteData;
        }).flat();

        // 如果没有选择站点，计算所有站点的总和
        if (selectedSites.length === 0) {
            chartData = Object.values(processedData).map(day => {
                const totalValue = Object.values(day.sites).reduce((sum: number, data: any) => {
                    return sum + data[metric];
                }, 0);
                return {
                    date: day.date,
                    site: '总计',
                    [metric]: totalValue
                };
            });
        } else {
            // 只保留选中的站点数据
            chartData = chartData.filter(item => selectedSites.includes(item.site));
        }

        const filteredData = filterDataByTimeRange(chartData);

        // ------------------------------------------
        // 每日分站点、数据类型概览图
        // 总量数据: 魔力值、保种积分、上传、下载、做种体积、做种数量、时魔、保种积分
        // 被站点选项控制，被时间范围控制
        // ------------------------------------------
        if (perStatChart) {
            perStatChart.destroy();
        }
        const perStatLineChart = new Chart({
            container: 'statisticsChart',
            autoFit: true,
        });
        perStatLineChart.data(filteredData);
        setPerStatChart(perStatLineChart);

        // 使用 Auto 自动配置图表
        perStatLineChart.line()
            .encode('x', 'date')
            .encode('y', metric)
            .encode('color', 'site')
            .encode('shape', 'smooth')
            .scale('x', {nice: true})
            .scale("y", {nice: true, min: 0,})
            .tooltip({
                items: [
                    (d: any) => ({
                        name: d.site,
                        value: formatValue(d[metric], metric),
                        color: d.color
                    })
                ],
                shared: true,
                showCrosshairs: true,
            })
        perStatLineChart.axis('x', {
            label: {
                formatter: (val: string) => formatDate(parseUTC8Date(val))
            }
        });
        perStatLineChart.render();

        // ------------------------------------------
        // 每日重要数据河流图
        // 总量数据: 魔力值、保种积分、上传、下载、做种体积、做种数量、时魔、保种积分
        // 被站点选项控制，被时间范围控制
        // ------------------------------------------
        // 准备河流图数据，并确保站点顺序一致
        const streamData = (() => {
            // 获取所有日期
            const allDates = Array.from(new Set(statistics.metrics.daily_results.map(item => item.date))).sort();

            // 获取所有站点并排序
            const siteOrder = Array.from(new Set(statistics.metrics.daily_results.map(item => item.site_id)))
                .sort((a, b) => a.localeCompare(b));

            // 为每个站点维护最后一次的有效数据
            const lastValidData: Record<string, number> = {};

            // 生成完整的数据集
            return allDates.flatMap(date => {
                // 获取当天的所有数据
                const dayData = statistics.metrics.daily_results.filter(item => item.date === date);

                return siteOrder.map((siteId, siteIndex) => {
                    // 查找当天该站点的数据
                    const siteData = dayData.find(item => item.site_id === siteId);

                    if (siteData) {
                        // 更新最后一次有效数据
                        lastValidData[siteId] = siteData[metric as keyof typeof siteData] as number || 0;
                    }

                    return {
                        date,
                        site: siteId,
                        value: lastValidData[siteId] || 0,
                        siteIndex
                    };
                });
            }).sort((a, b) => {
                // 首先按日期排序，然后按站点顺序排序
                const dateCompare = new Date(a.date).getTime() - new Date(b.date).getTime();
                if (dateCompare !== 0) return dateCompare;
                return a.siteIndex - b.siteIndex;
            });
        })();

        // 创建河流图
        const streamChart = new Chart({
            container: 'streamChart',
            autoFit: true,
        });

        streamChart.data(streamData);

        streamChart
            .area()
            .transform({ type: 'stackY' })
            .transform({ type: 'symmetryY' })
            .encode('x', 'date')
            .encode('y', 'value')
            .encode('color', 'site')
            .style('shape', 'smooth')
            .scale('y', { nice: true })
            .interaction('elementSelect', true)
            .tooltip({
                shared: false,
                items: [
                    (d: any) => ({
                        name: d.site,
                        value: formatValue(d.value, metric as MetricType),
                        color: d.color
                    })
                ]
            });

        streamChart.legend({
            position: 'top',
            flipPage: false
        });

        streamChart.render();

    }, [statistics, timeRange, metric, selectedSites]);

    useEffect(() => {
        // ------------------------------------------
        // 每日重要数据概览图
        // 增量数据: 上传、下载
        // 总量数据: 魔力值、保种积分
        // 不被站点选项控制，被时间范围控制
        // ------------------------------------------
        if (!statistics || !statistics.metrics.daily_results.length) return;
        
        // 按日期分组并汇总
        const dailyTotals = statistics.metrics.daily_results.reduce((acc, curr) => {
            const date = curr.date;  // 这里的 date 已经是 UTC+8 的日期字符串
            if (!acc[date]) {
                acc[date] = {
                    date,
                    site: '总计',
                    upload: 0,
                    download: 0,
                    bonus: 0,
                    bonus_per_hour: 0,
                    seeding_score: 0,
                    seeding_size: 0,
                    seeding_count: 0
                };
            }
            acc[date].upload += curr.upload || 0;
            acc[date].download += curr.download || 0;
            acc[date].bonus += curr.bonus || 0;
            acc[date].bonus_per_hour += curr.bonus_per_hour || 0;
            acc[date].seeding_score += curr.seeding_score || 0;
            acc[date].seeding_size += curr.seeding_size || 0;
            acc[date].seeding_count += curr.seeding_count || 0;
            return acc;
        }, {} as Record<string, any>);

        const dailyIncrements = statistics.metrics.daily_increments.reduce((acc, curr) => {
            const date = curr.date;
            if (!acc[date]) {
                acc[date] = {
                    date,
                    upload_increment: 0,
                    download_increment: 0,
                    bonus_increment: 0,
                    seeding_score_increment: 0,
                    seeding_size_increment: 0,
                    seeding_count_increment: 0
                };
            }
            acc[date].upload_increment += curr.upload_increment || 0;
            acc[date].download_increment += curr.download_increment || 0;
            acc[date].bonus_increment += curr.bonus_increment || 0;
            acc[date].seeding_score_increment += curr.seeding_score_increment || 0;
            acc[date].seeding_size_increment += curr.seeding_size_increment || 0;
            acc[date].seeding_count_increment += curr.seeding_count_increment || 0;
            return acc;
        }, {} as Record<string, any>);

        // 生成日期范围内的所有日期
        const startDate = new Date(statistics.time_range.start);
        const endDate = new Date(statistics.time_range.end);
        const allDates: string[] = [];
        const currentDate = new Date(startDate);

        while (currentDate <= endDate) {
            allDates.push(toUTC8DateString(currentDate));
            currentDate.setDate(currentDate.getDate() + 1);
        }

        // 记录上一个有效的总量数据
        let lastValidBonus = 0;
        let lastValidSeedingScore = 0;

        // 转换为数组并处理每一天的数据
        const filteredData = allDates
            .sort((a, b) => new Date(a).getTime() - new Date(b).getTime())
            .map(date => {
                const dayTotal = dailyTotals[date];
                const increment = dailyIncrements[date] || {
                    upload_increment: 0,
                    download_increment: 0,
                    bonus_increment: 0,
                    seeding_score_increment: 0
                };

                // 如果有当天的数据，更新最后的有效值
                if (dayTotal) {
                    lastValidBonus = dayTotal.bonus;
                    lastValidSeedingScore = dayTotal.seeding_score;
                }

                return {
                    date,
                    site: '总计',
                    upload: increment.upload_increment,
                    download: increment.download_increment,
                    bonus: lastValidBonus,  // 使用最后的有效值
                    seeding_score: lastValidSeedingScore  // 使用最后的有效值
                };
            });

        // 创建概览图表
        if (overviewChart) {
            overviewChart.destroy();
        }

        const overallChangeLineChart = new Chart({
            container: 'overviewChart',
            autoFit: true,
        });

        // 设置数据
        // console.log(filteredData);
        overallChangeLineChart.data(filteredData);

        // 下载量线条
        overallChangeLineChart.line()
            .encode('x', 'date')
            .encode('y', 'download')
            .encode('color', '#5470C6')
            .scale('y', {nice: true, key: '1'})
            .style('lineWidth', 2)
            .style('lineDash', [1, 3])
            .style('shape', 'smooth')
            .axis('y', {
                title: 'GB',
                grid: true,
                titleFill: '#5470C6',
            })
            .tooltip({
                items: [
                    (d: any) => ({
                        name: '当日下载量',
                        value: formatValue(d.download, 'download'),
                        color: '#5470C6'
                    })
                ]
            });

        // 上传量线条
        overallChangeLineChart.line()
            .encode('x', 'date')
            .encode('y', 'upload')
            .encode('color', '#EE6666')
            .scale('y', {nice: true, key: '1'})
            .style('lineWidth', 2)
            .style('lineDash', [1, 3])
            .style('shape', 'smooth')
            .tooltip({
                items: [
                    (d: any) => ({
                        name: '当日上传量',
                        value: formatValue(d.upload, 'upload'),
                        color: '#EE6666'
                    })
                ]
            });

        // 上传下载量区域图
        overallChangeLineChart.area()
            .data({
                transform: [
                    {
                        type: 'fold',
                        fields: ['upload', 'download'],
                        key: 'type',
                        value: 'upload',
                    },
                ],
            })
            .transform([{ type: 'diffY'}])
            .encode('x', 'date')
            .encode('y', 'upload')
            .encode('color', 'type')
            .scale('y', {nice: true, key: '1'})
            .style('fillOpacity', 0.1)
            .style('shape', 'smooth')
            .style('strokeWidth', 2)
            .tooltip(false)
            .legend(false);

        // 魔力值线条
        overallChangeLineChart.line()
            .encode('x', 'date')
            .encode('y', 'bonus')
            .encode('color', '#91CC75')
            .scale('y', {nice: true, key: '2'})
            .style('lineWidth', 1.5)
            .style('lineDash', [6, 4])
            // .style('shape', 'smooth')
            .axis('y', {
                position: 'right',
                title: '魔力值',
                grid: true,
                titleFill: '#91CC75',
            })
            .tooltip({
                items: [
                    (d: any) => ({
                        name: '魔力值',
                        value: formatValue(d.bonus, 'bonus'),
                        color: '#91CC75'
                    })
                ]
            });

        // 保种积分线条
        overallChangeLineChart.line()
            .encode('x', 'date')
            .encode('y', 'seeding_score')
            .encode('color', '#FF9900')
            .scale('y', {nice: true, key: '2'})
            .style('lineWidth', 1.5)
            .style('lineDash', [6, 4])
            .tooltip({
                items: [
                    (d: any) => ({
                        name: '保种积分',
                        value: formatValue(d.seeding_score, 'seeding_score'),
                        color: '#FF9900'
                    })
                ]
            });

        // 配置图例
        overallChangeLineChart.legend({
            position: 'bottom',
            flipPage: false
        });

        // 配置提示框
        overallChangeLineChart.interaction('tooltip', {
            shared: true,
            crosshairs: {
                type: 'x',
            }
        });

        // 配置 X 轴日期格式
        overallChangeLineChart.axis('x', {
            label: {
                formatter: (val: string) => formatDate(parseUTC8Date(val))
            }
        });

        overallChangeLineChart.render();
        setOverviewChart(overallChangeLineChart);

        return () => {
            if (overviewChart) {
                overviewChart.destroy();
            }
        };
    }, [statistics, timeRange, metric]);

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
            <div id="overviewChart" className={styles.chartContent} />
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
                        // maxTagTextLength={3}
                        className={styles.siteSelect}
                        optionLabelProp="label"
                        options={siteOptions.map(site => ({
                            value: site.value,
                            label: site.label,
                            optionRender: (option: any) => (
                                <Space>
                                    {/* {site.icon && (
                                        <img 
                                            src={site.icon} 
                                            alt={site.label} 
                                            style={{ width: 16, height: 16 }}
                                        />
                                    )} */}
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
            <div id="streamChart" className={styles.chartContent} />
            <div id="statisticsChart" className={styles.chartContent} />
        </div>
    );
};

export default ChartView; 