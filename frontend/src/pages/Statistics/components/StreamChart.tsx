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

        // 生成日期范围内的所有日期
        const startDate = new Date(statistics.time_range.start);
        const endDate = new Date(statistics.time_range.end);
        const allDates: string[] = [];
        const currentDate = new Date(startDate);

        while (currentDate <= endDate) {
            allDates.push(toUTC8DateString(currentDate));
            currentDate.setDate(currentDate.getDate() + 1);
        }

        // 获取所有站点并排序
        const siteOrder = Array.from(new Set(statistics.metrics.daily_results.map(item => item.site_id)))
            .sort((a, b) => a.localeCompare(b))
            .filter(site => selectedSites.length === 0 || selectedSites.includes(site));

        // 为每个站点维护最后一次的有效数据
        const lastValidData: Record<string, number> = {};

        // 生成完整的数据集
        const streamData = allDates.flatMap(date => {
            // 获取当天的所有数据
            const dayData = statistics.metrics.daily_results.filter(item => item.date === date);

            return siteOrder.map((siteId, siteIndex) => {
                // 查找当天该站点的数据
                const siteData = dayData.find(item => item.site_id === siteId);

                if (siteData && siteData[metric as keyof typeof siteData] !== undefined) {
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
            .transform({ type: 'stackEnter', groupBy: 'color', duration: 1000 })
            .encode('x', 'date')
            .encode('y', 'value')
            .encode('color', 'site')
            .style('shape', 'smooth')
            .scale('y', { nice: true })
            .animate('enter', { type: 'growInX', duration: 500 })
            .label({
                text: 'site',
                position: 'area', // `area` type positon used here.
                selector: 'first',
                transform: [{ type: 'overlapHide' }],
                fontSize: 8,
            })
            .tooltip({
                position: 'right',
                shared: false,
                items: [
                    (d: any) => ({
                        name: d.site,
                        value: formatValue(d.value, metric as MetricType),
                        color: d.color
                    })
                ]
            })
            .state('inactive', { opacity: 0.2 })
            .state('selected', { fill: 'blue' })
            .state('unselected', { opacity: 0.3 })
            .legend('color', {
                state: { inactive: { labelOpacity: 0.2, markerOpacity: 0.2 } },
                itemLabelFill: (d: any) => d.color,
                layout: 'flex',
                cols: 8,
                colPadding: 12,
                itemSpacing: 2,
            })

        streamChart.interaction('legendHighlight', true);
        streamChart.interaction('legendFilter', false);
        streamChart.interaction('elementSelect', {
            single: true,
            multiple: false,
        })
        // 配置 X 轴日期格式
        streamChart.axis('x', {
            title: null,
            label: {
                formatter: (val: string) => formatDate(parseUTC8Date(val))
            }
        });

        streamChart.axis('y', {
            title: null
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

export default React.memo(StreamChart, (prevProps, nextProps) => {
    // 只有当相关的 props 改变时才重新渲染
    return (
        prevProps.timeRange === nextProps.timeRange &&
        prevProps.metric === nextProps.metric &&
        prevProps.selectedSites === nextProps.selectedSites
    );
}); 