import React, { useEffect, useState } from 'react';
import { Spin, Empty, Radio, Space, Select } from 'antd';
import { Chart } from '@antv/g2';
import { siteConfigApi } from '../../api/siteConfig';
import { StatisticsHistoryResponse } from '../../types/api';
import styles from './Statistics.module.css';

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

const formatValue = (value: number, type: MetricType) => {
    switch (type) {
        case 'upload':
        case 'download':
            return `${value.toFixed(1)} GB`;
        case 'seeding_size':
            return `${(value / 1024).toFixed(2)} TB`;  // 转换为 TiB
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

    const filterDataByTimeRange = (data: ChartDataItem[]) => {
        if (timeRange === 'all') return data;

        const days = parseInt(timeRange);
        const end = new Date();
        end.setHours(23, 59, 59, 999);
        const start = new Date();
        start.setDate(end.getDate() - days + 1);
        start.setHours(0, 0, 0, 0);

        // 直接过滤时间范围内的数据
        return data.filter(item => {
            const itemDate = new Date(item.date + 'T00:00:00');
            return itemDate >= start && itemDate <= end;
        });
    };

    useEffect(() => {
        if (!statistics || !statistics.metrics.daily_results.length) return;

        // 处理数据
        const processedData = statistics.metrics.daily_results.reduce((acc, curr) => {
            const date = curr.date;
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

        // // 计算时间范围
        // const start = new Date(filteredData[0].date);
        // const end = new Date(filteredData[filteredData.length - 1].date);

        // 创建图表
        if (perStatChart) {
            perStatChart.destroy();
        }

        const perStatLineChart = new Chart({
            container: 'statisticsChart',
            autoFit: true,
        });
        console.log("filteredData", filteredData);
        perStatLineChart.data(filteredData);

        // 使用 Auto 自动配置图表 #00ff00
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

        perStatLineChart.render();

        setPerStatChart(perStatLineChart);

        return () => {
            if (perStatChart) {
                perStatChart.destroy();
            }
        };
    }, [statistics, timeRange, metric, selectedSites]);

    useEffect(() => {
        if (!statistics || !statistics.metrics.daily_results.length) return;
        
        // 按日期分组并汇总数据
        const dailyTotals = statistics.metrics.daily_results.reduce((acc, curr) => {
            const date = curr.date;
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
        console.log('dailyTotals dates:', Object.keys(dailyTotals));
        console.log('dailyIncrements dates:', Object.keys(dailyIncrements));
        // 转换为数组并按日期排序
        const filteredData = Object.values(dailyTotals)
            .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
            .map((item, index, array) => {
                // 如果是最后一天（今天），需要计算增量
                if (index === array.length - 1 && !dailyIncrements[item.date]) {
                    const previousDay = array[index - 1];
                    return {
                        date: item.date,
                        site: '总计',
                        // 计算今天的增量并保留一位小数
                        upload: Number((item.upload - previousDay.upload).toFixed(1)),
                        download: Number((item.download - previousDay.download).toFixed(1)),
                        bonus: Number(item.bonus.toFixed(1)),
                        seeding_score: Number(item.seeding_score.toFixed(1))
                    };
                }
                
                // 其他天使用 dailyIncrements 中的数据
                return {
                    date: item.date,
                    site: '总计',
                    upload: Number((dailyIncrements[item.date]?.upload_increment || 0).toFixed(1)),
                    download: Number((dailyIncrements[item.date]?.download_increment || 0).toFixed(1)),
                    bonus: Number(item.bonus.toFixed(1)),
                    seeding_score: Number(item.seeding_score.toFixed(1))
                };
            });
            
        // 准备河流图数据，并确保站点顺序一致
        const siteOrder = Array.from(new Set(statistics.metrics.daily_results.map(item => item.site_id)))
            .sort((a, b) => a.localeCompare(b));  // 按站点ID字母顺序排序

        const streamData = statistics.metrics.daily_results
            .map(item => ({
                date: item.date,
                site: item.site_id,
                value: item[metric as keyof typeof item] || 0,
                siteIndex: siteOrder.indexOf(item.site_id)  // 添加站点索引用于排序
            }))
            .sort((a, b) => {
                // 首先按日期排序，然后按站点顺序排序
                const dateCompare = new Date(a.date).getTime() - new Date(b.date).getTime();
                if (dateCompare !== 0) return dateCompare;
                return a.siteIndex - b.siteIndex;
            });

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
            .scale('y', {nice: true})
            .interaction('elementSelect', true)
            // .scale('color', {
            //     range: siteOrder  // 确保颜色映射顺序一致
            // })
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

        // 创建概览图表
        if (overviewChart) {
            overviewChart.destroy();
        }

        const overallChangeLineChart = new Chart({
            container: 'overviewChart',
            autoFit: true,
        });

        // 设置数据
        console.log(filteredData);
        overallChangeLineChart.data(filteredData);

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
                titleFill: '#EE6666',
            });


        overallChangeLineChart.line()
            .encode('x', 'date')
            .encode('y', 'upload')
            .encode('color', '#EE6666')
            .scale('y', {nice: true, key: '1'})
            .style('lineWidth', 2)
            .style('lineDash', [1, 3])
            .style('shape', 'smooth')
        
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
            .transform([{ type: 'diffY'}]) // Diff the 2 area shape.
            .encode('x', 'date')
            .encode('y', 'upload')
            .encode('color', 'type')
            .scale('y', {nice: true, key: '1'})
            .style('fillOpacity', 0.1)
            .style('shape', 'smooth')
            .style('strokeWidth', 2)
            .tooltip(false)
            .legend(false)

        overallChangeLineChart.line()
            .encode('x', 'date')
            .encode('y', 'bonus')
            .encode('color', '#91CC75')
            .scale('y', {nice: true, key: '2' })
            .style('lineWidth', 1.5)
            .style('lineDash', [6, 4])
            // .style('shape', 'smooth')
            .axis('y', {
                position: 'right',
                title: 'bonus',
                grid: true,
                titleFill: '#91CC75',
            });

        overallChangeLineChart.line()
            .encode('x', 'date')
            .encode('y', 'seeding_score')
            .encode('color', '#FF9900')
            .scale('y', {nice: true, key: '2'})
            .style('lineWidth', 1.5)
            .style('lineDash', [6, 4])

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
            },
            items: [
                (d: any) => ({
                    name: d.site,
                    value: formatValue(d[metric], metric),
                    color: d.color
                })
            ],
        });

        overallChangeLineChart.render();
        setOverviewChart(overallChangeLineChart);

        return () => {
            if (overviewChart) {
                overviewChart.destroy();
            }
            if (streamChart) {
                streamChart.destroy();
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
            <div id="overviewChart" className={styles.chartContent} />
            <div className={styles.chartControls}>
                <Space size="middle">
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
                        placeholder="选择站点（默认显示总计）"
                        value={selectedSites}
                        onChange={setSelectedSites}
                        options={siteOptions}
                        className={styles.siteSelect}
                        style={{ minWidth: '200px' }}
                        maxTagCount={10}
                    />
                </Space>
            </div>
            <div id="streamChart" className={styles.chartContent} />
            <div id="statisticsChart" className={styles.chartContent} />
        </div>
    );
};

export default ChartView; 