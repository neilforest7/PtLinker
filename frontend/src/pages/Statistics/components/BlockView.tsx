import React, { useEffect, useState } from 'react';
import { Spin, Empty } from 'antd';
import CalendarHeatmap from 'react-calendar-heatmap';
import 'react-calendar-heatmap/dist/styles.css';
import { siteConfigApi } from '../../../api/siteConfig';
import { StatisticsHistoryResponse } from '../../../types/api';
import { toUTC8DateString, parseUTC8Date, formatDate } from '../../../utils/dateUtils';
import styles from './Statistics.module.css';

interface HeatmapValue {
    date: Date;
    count: number;
    details?: {
        success: number;
        total: number;
        successRate: number;
        failedSites: string[];
    }
}

const BlockView: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [statistics, setStatistics] = useState<StatisticsHistoryResponse | null>(null);
    const [heatmapData, setHeatmapData] = useState<HeatmapValue[]>([]);

    const loadStatistics = async () => {
        try {
            setLoading(true);
            const end = new Date();
            const start = new Date(end);
            start.setDate(end.getDate() - 200);

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

    useEffect(() => {
        loadStatistics();
    }, []);

    useEffect(() => {
        if (!statistics || !statistics.metrics.checkins.length) return;

        // 按日期分组，计算每日签到成功率和失败站点
        const dailyCheckins = statistics.metrics.checkins.reduce((acc, curr) => {
            const dateKey = curr.date;
            if (!acc[dateKey]) {
                acc[dateKey] = {
                    success: 0,
                    total: 0,
                    failedSites: [] as string[]
                };
            }
            acc[dateKey].total++;
            if (curr.checkin_status === 'success') {
                acc[dateKey].success++;
            } else {
                acc[dateKey].failedSites.push(curr.site_id);
            }
            return acc;
        }, {} as Record<string, { 
            success: number; 
            total: number; 
            failedSites: string[];
        }>);

        // 转换为热力图数据
        const today = new Date();
        const startDate = new Date(today);
        startDate.setDate(today.getDate() - 200);

        const heatmapValues: HeatmapValue[] = [];
        const currentDate = new Date(startDate);

        while (currentDate <= today) {
            const dateStr = toUTC8DateString(currentDate);
            const dayData = dailyCheckins[dateStr];

            // 计算成功率并转换为0-4的等级
            let count = 0;
            let details = undefined;

            if (dayData) {
                const successRate = dayData.success / dayData.total;
                if (successRate === 1) count = 4;
                else if (successRate >= 0.75) count = 3;
                else if (successRate >= 0.5) count = 2;
                else if (successRate > 0) count = 1;

                details = {
                    success: dayData.success,
                    total: dayData.total,
                    successRate: successRate * 100,
                    failedSites: dayData.failedSites
                };
            }

            heatmapValues.push({
                date: parseUTC8Date(dateStr),
                count,
                details
            });
            currentDate.setDate(currentDate.getDate() + 1);
        }

        setHeatmapData(heatmapValues);
    }, [statistics]);

    if (loading) {
        return <Spin size="large" />;
    }

    if (!statistics || !statistics.metrics.daily_results.length) {
        return <Empty description="暂无统计数据" />;
    }

    return (
        <div className={styles.blockchartContent}>
            <CalendarHeatmap
                startDate={parseUTC8Date(toUTC8DateString(new Date(Date.now() - 200 * 24 * 60 * 60 * 1000)))}
                endDate={parseUTC8Date(toUTC8DateString(new Date()))}
                values={heatmapData}
                classForValue={(value) => {
                    if (!value || value.count === 0) {
                        return 'color-empty';
                    }
                    return `color-github-${value.count}`;
                }}
                titleForValue={(value: any) => {
                    if (!value) return '无数据';
                    if (!value.details) {
                        return `${formatDate(value.date)}\n无签到数据`;
                    }
                    const { details } = value;
                    let tooltip = `${formatDate(value.date)}\n签到情况: ${details.success}/${details.total}`;
                    if (details.failedSites.length > 0) {
                        tooltip += `\n签到失败站点: ${details.failedSites.join(', ')}`;
                    }
                    return tooltip;
                }}
                horizontal={true}
                gutterSize={2}
                
            />
        </div>
    );
};

export default BlockView; 