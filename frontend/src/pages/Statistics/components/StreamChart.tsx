import React, { useEffect, useState } from 'react';
import { Chart } from '@antv/g2';
import { StatisticsHistoryResponse } from '../../../types/api';
import { TimeRange, MetricType, formatValue } from '../utils/chartUtils';
import { toUTC8DateString, parseUTC8Date, formatDate } from '../../../utils/dateUtils';
import styles from '../Statistics.module.css';

interface StreamChartProps {
    statistics: StatisticsHistoryResponse;
    timeRange: TimeRange;
    metric: MetricType;
    selectedSites: string[];
}

const StreamChart: React.FC<StreamChartProps> = ({ 
    statistics, 
    timeRange, 
    metric, 
    selectedSites 
}) => {
    const [chart, setChart] = useState<Chart | null>(null);

    useEffect(() => {
        if (!statistics || !statistics.metrics.daily_results.length) return;

        // 准备河流图数据，并确保站点顺序一致
        const streamData = (() => {
            // 获取所有日期
            const allDates = Array.from(new Set(statistics.metrics.daily_results.map(item => item.date))).sort();

            // 获取所有站点并排序
            const siteOrder = Array.from(new Set(statistics.metrics.daily_results.map(item => item.site_id)))
                .sort((a, b) => a.localeCompare(b))
                .filter(site => selectedSites.length === 0 || selectedSites.includes(site));

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

        // 清理旧图表
        if (chart) {
            chart.destroy();
        }

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

        // 配置 X 轴日期格式
        streamChart.axis('x', {
            label: {
                formatter: (val: string) => formatDate(parseUTC8Date(val))
            }
        });

        streamChart.render();
        setChart(streamChart);

        return () => {
            if (chart) {
                chart.destroy();
            }
        };
    }, [statistics, timeRange, metric, selectedSites]);

    return (
        <div id="streamChart" className={styles.chartContent} />
    );
};

export default StreamChart; 