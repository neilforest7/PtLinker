import React, { useEffect, useState } from 'react';
import { Chart } from '@antv/g2';
import { StatisticsHistoryResponse } from '../../../types/api';
import { TimeRange, MetricType, formatValue, filterDataByTimeRange } from '../utils/chartUtils';
import { toUTC8DateString, parseUTC8Date, formatDate } from '../../../utils/dateUtils';
import styles from '../Statistics.module.css';
import { Auto } from '@antv/g2-extension-ava';
import { Label } from '@antv/g2/lib/shape/label/label';

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

        // 如果没有选择站点，添加"总计"到站点列表
        if (selectedSites.length === 0) {
            siteOrder.push('总计');
        }

        // 生成完整的数据集
        const chartData = allDates.flatMap(date => {
            // 获取当天的所有数据
            const dayData = statistics.metrics.daily_results.filter(item => item.date === date);

            // 如果是"总计"模式，计算总和
            if (selectedSites.length === 0) {
                const totalValue = dayData.reduce((sum, item) => {
                    return sum + (item[metric as keyof typeof item] as number || 0);
                }, 0);

                if (totalValue !== 0) {
                    lastValidData['总计'] = totalValue;
                }

                return [{
                    date,
                    site: '总计',
                    [metric]: lastValidData['总计'] || 0
                }];
            }

            // 否则处理每个选中的站点
            return siteOrder.map(siteId => {
                const siteData = dayData.find(item => item.site_id === siteId);

                if (siteData && siteData[metric as keyof typeof siteData] !== undefined) {
                    lastValidData[siteId] = siteData[metric as keyof typeof siteData] as number || 0;
                }

                return {
                    date,
                    site: siteId,
                    [metric]: lastValidData[siteId] || 0
                };
            });
        });

        const filteredData = filterDataByTimeRange(chartData, timeRange);

        // 清理旧图表
        if (chart) {
            chart.destroy();
        }

        // 创建新图表
        const statisticsChart = new Chart({
            container: 'statisticsChart',
            autoFit: true,
            // height: 800,
            // paddingLeft: 16,
            // paddingRight: 16,
            // paddingTop: 16,
            // paddingBottom: 16,
        });

        statisticsChart.data(filteredData);

        statisticsChart.line()
            .encode('x', 'date')
            .encode('y', metric)
            .encode('color', 'site')
            .encode('shape', 'smooth')
            .scale('x', {nice: true})
            .scale("y", {nice: true, min: 0,})
            .style('lineWidth', 1.5)
            .label({
                text: 'site',
                position: 'right', // `area` type positon used here.
                selector: 'last',
                transform: [{ type: 'overlapDodgeY' }, { type: 'exceedAdjust' }],
                fontSize: 8,
            })
            .tooltip({ series: false, shared: false, disableNative: true, items: [
                (d: any) => ({
                    name: d.site,
                    value: formatValue(d[metric as keyof typeof d], metric as MetricType),
                    color: d.color
                })
            ] })
            .animate('enter', { type: 'pathIn', duration: 1000 })
            .animate('exit', { type: 'fadeOut', duration: 200 })
            .state('inactive', { opacity: 0.1 })
            .legend('color', {
                state: { inactive: { labelOpacity: 0.1, markerOpacity: 0.1 } },
                itemLabelFill: (d: any) => d.color,
                layout: 'flex',
                cols: 8,
                colPadding: 12,
                itemSpacing: 2,
            })
        statisticsChart.interaction('legendHighlight', true);
        statisticsChart.interaction('legendFilter', false);
        statisticsChart.interaction('elementSelect', true);
        // statisticsChart.emit('element:highlight', {
        //     data: { data: { site: '总计' } },
        // });

        // statisticsChart.emit('element:unhighlight', {});
        // statisticsChart.on('element:highlight', (event) => {
        //     const { data, nativeEvent } = event;
        //     if (nativeEvent) console.log('element:highlight', data);
        // });
        // statisticsChart.on('element:unhighlight', (event) => {
        //     const { nativeEvent } = event;
        //     if (nativeEvent) console.log('reset');
        // });


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