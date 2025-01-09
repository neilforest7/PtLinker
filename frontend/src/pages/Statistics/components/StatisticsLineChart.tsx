import React, { useEffect, useState } from 'react';
import { Chart } from '@antv/g2';
import { StatisticsHistoryResponse } from '../../../types/api';
import { TimeRange, MetricType, formatValue, filterDataByTimeRange } from '../utils/chartUtils';
import { parseUTC8Date, formatDate } from '../../../utils/dateUtils';
import styles from '../Statistics.module.css';

interface StatisticsLineChartProps {
    statistics: StatisticsHistoryResponse;
    timeRange: TimeRange;
    metric: MetricType;
    selectedSites: string[];
}

const StatisticsLineChart: React.FC<StatisticsLineChartProps> = ({
    statistics,
    timeRange,
    metric,
    selectedSites
}) => {
    const [chart, setChart] = useState<Chart | null>(null);

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

        const filteredData = filterDataByTimeRange(chartData, timeRange);

        // 清理旧图表
        if (chart) {
            chart.destroy();
        }

        // 创建新图表
        const statisticsChart = new Chart({
            container: 'statisticsChart',
            autoFit: true,
        });

        statisticsChart.data(filteredData);

        // 使用 Auto 自动配置图表
        statisticsChart.line()
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
            });

        statisticsChart.axis('x', {
            label: {
                formatter: (val: string) => formatDate(parseUTC8Date(val))
            }
        });

        statisticsChart.render();
        setChart(statisticsChart);

        return () => {
            if (chart) {
                chart.destroy();
            }
        };
    }, [statistics, timeRange, metric, selectedSites]);

    return (
        <div id="statisticsChart" className={styles.chartContent} />
    );
};

export default StatisticsLineChart; 