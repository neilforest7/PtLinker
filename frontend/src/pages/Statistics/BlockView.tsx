import React, { useEffect, useState } from 'react';
import { Spin, Empty, Radio, Space, Select } from 'antd';
import { Chart } from '@antv/g2';
import { siteConfigApi } from '../../api/siteConfig';
import { StatisticsHistoryResponse } from '../../types/api';
import styles from './Statistics.module.css';

const BlockView: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [statistics, setStatistics] = useState<StatisticsHistoryResponse | null>(null);
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
            const end = new Date();
            end.setHours(23, 59, 59, 999);
            const start = new Date(end);
            start.setDate(end.getDate() - 30); // 改为30天前
            start.setHours(0, 0, 0, 0);

            const params = {
                start_date: start.toISOString().split('T')[0],
                end_date: end.toISOString().split('T')[0]
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

        // 首先按日期和站点分组，合并同一天同一站点的签到结果
        const dailyCheckins = statistics.metrics.checkins.reduce((acc, curr) => {
            const key = `${curr.date}-${curr.site_id}`;
            if (!acc[key]) {
                acc[key] = {
                    date: curr.date,
                    site_id: curr.site_id,
                    success: false,
                    checkin_time: curr.checkin_time
                };
            }
            // 只要有一次成功就算成功
            if (curr.checkin_status === 'success') {
                acc[key].success = true;
                // 更新为最早的成功签到时间
                if (new Date(curr.checkin_time) < new Date(acc[key].checkin_time)) {
                    acc[key].checkin_time = curr.checkin_time;
                }
            }
            return acc;
        }, {} as Record<string, { date: string; site_id: string; success: boolean; checkin_time: string; }>);

        // 然后按日期汇总所有站点的签到情况
        const dateCheckins = Object.values(dailyCheckins).reduce((acc, curr) => {
            if (!acc[curr.date]) {
                acc[curr.date] = {
                    successSites: new Set<string>(),
                    totalSites: new Set<string>(),
                    earliestCheckinTime: curr.checkin_time
                };
            }
            acc[curr.date].totalSites.add(curr.site_id);
            if (curr.success) {
                acc[curr.date].successSites.add(curr.site_id);
                // 更新为最早的签到时间
                if (new Date(curr.checkin_time) < new Date(acc[curr.date].earliestCheckinTime)) {
                    acc[curr.date].earliestCheckinTime = curr.checkin_time;
                }
            }
            return acc;
        }, {} as Record<string, { 
            successSites: Set<string>; 
            totalSites: Set<string>; 
            earliestCheckinTime: string; 
        }>);

        // 转换为热力图数据
        const blockData = (() => {
            // 获取当前日期
            const today = new Date();
            // 获取30天前的日期
            const startDate = new Date(today);
            startDate.setDate(today.getDate() - 30);
            startDate.setHours(0, 0, 0, 0);
            
            // 创建一个包含30天所有日期的数组
            const allDates = [];
            const currentDate = new Date(startDate);
            
            while (currentDate <= today) {
                const dateStr = currentDate.toISOString().split('T')[0];
                const dayData = dateCheckins[dateStr];
                
                // 计算成功率作为 value
                const value = dayData ? 
                    (dayData.totalSites.size > 0 ? dayData.successSites.size / dayData.totalSites.size : 0) : 0;
                
                allDates.push({
                    date: dateStr,
                    day: currentDate.getDay(),
                    week: Math.floor((currentDate.getTime() - startDate.getTime()) / (7 * 24 * 60 * 60 * 1000)),
                    value: value,
                    successCount: dayData?.successSites.size || 0,
                    totalSites: dayData?.totalSites.size || 0,
                    failedCount: dayData ? (dayData.totalSites.size - dayData.successSites.size) : 0,
                    checkinTime: dayData?.earliestCheckinTime || null
                });
                
                currentDate.setDate(currentDate.getDate() + 1);
            }
            return allDates;
        })();

        // 创建热力图
        if (blockChart) {
            blockChart.destroy();
        }

        const checkinBlockChart = new Chart({
            container: 'blockChart',
            autoFit: true,
            height: 170,
            width: 140,
        });

        checkinBlockChart.data(blockData);

        checkinBlockChart
            .cell()
            .encode('x', 'week')
            .encode('y', 'day')
            .encode('color', 'value')
            .style('inset', 0.5)
            .scale('color', {
                type: 'linear',
                domain: [0, 1],
                range: ['#ebedf0', '#338836']
            })
            .legend(false)
            .axis('x', {
                label: null,
                line: null,
                grid: null,
            })
            .axis('y', {
                label: null,
                line: null,
                grid: null,
            })
            .tooltip({
                items: [
                    (d: any) => ({
                        name: '日期',
                        value: new Date(d.date).toLocaleDateString()
                    }),
                    (d: any) => ({
                        name: '签到状态',
                        value: d.value === 1 ? '全部成功' : (d.value === 0 ? '未签到' : '部分成功')
                    }),
                    (d: any) => ({
                        name: '成功/总数',
                        value: d.checkinTime ? `${d.successCount}/${d.totalSites}` : '无签到记录'
                    }),
                    (d: any) => ({
                        name: '签到时间',
                        value: d.checkinTime ? new Date(d.checkinTime).toLocaleTimeString() : '-'
                    }),
                    (d: any) => ({
                        name: '失败站点',
                        value: d.failedCount
                    })
                ]
            })
            .animate('enter', { type: 'fadeIn' });

        checkinBlockChart.render();
        setBlockChart(checkinBlockChart);

        return () => {
            if (blockChart) {
                blockChart.destroy();
            }
        };
    }, [statistics]);

    if (loading) {
        return <Spin size="large" />;
    }

    if (!statistics || !statistics.metrics.daily_results.length) {
        return <Empty description="暂无统计数据" />;
    }

    return (
        <div id="blockChart" className={styles.blockchartContent} />
    );
};

export default BlockView; 