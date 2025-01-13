import React, { useEffect, useState } from 'react';
import { Chart } from '@antv/g2';
import { StatisticsHistoryResponse } from '../../../types/api';
import { TimeRange, formatValue } from '../../../pages/Statistics/utils/chartUtils';
import { toUTC8DateString, parseUTC8Date, formatDate } from '../../../utils/dateUtils';
import styles from '../index.module.css';

interface OverviewChartProps {
    statistics: StatisticsHistoryResponse;
    timeRange: TimeRange;
}

const OverviewChart: React.FC<OverviewChartProps> = ({ statistics, timeRange }) => {
    const [chart, setChart] = useState<Chart | null>(null);

    useEffect(() => {
        if (!statistics || !statistics.metrics.daily_results.length) return;
        
        // 按日期分组并汇总
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
                    bonus: lastValidBonus,
                    seeding_score: lastValidSeedingScore
                };
            });

        // 清理旧图表
        if (chart) {
            chart.destroy();
        }

        // 创建新图表
        const overallChangeLineChart = new Chart({
            container: 'overviewChart',
            autoFit: true,
        });

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
            .animate('enter', { type: 'pathIn', duration: 1200 })
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
            .animate('enter', { type: 'pathIn', duration: 1000 })
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
            .axis('y', {
                position: 'right',
                title: '魔力值',
                grid: true,
                titleFill: '#91CC75',
            })
            .animate('enter', { duration: 500 })
            .tooltip({
                items: [
                    (d: any) => ({
                        name: '魔力值',
                        value: formatValue(d.bonus, 'bonus'),
                        color: '#91CC75'
                    })
                ]
            })
            .style('connect', true)
            .style('connectStroke', '#aaa');

        // 保种积分线条
        overallChangeLineChart.line()
            .encode('x', 'date')
            .encode('y', 'seeding_score')
            .encode('color', '#FF9900')
            .scale('y', {nice: true, key: '2'})
            .style('lineWidth', 1.5)
            .style('lineDash', [6, 4])
            .animate('enter', {duration: 500})
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
        setChart(overallChangeLineChart);

        return () => {
            if (chart) {
                chart.destroy();
            }
        };
    }, [statistics, timeRange]);

    return (
        <div id="overviewChart" className={styles.chartContent} />
    );
};

export default React.memo(OverviewChart); 