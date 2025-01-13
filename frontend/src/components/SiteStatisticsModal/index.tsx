import React, { useEffect, useState } from 'react';
import { Modal, Descriptions, Spin, message, Divider} from 'antd';
import { siteConfigApi } from '../../api/siteConfig';
import { StatisticsHistoryResponse } from '../../types/api';
import BlockView from './components/BlockView';
import OverviewChart from './components/OverviewChart';
import { TimeRange } from '../../pages/Statistics/utils/chartUtils';
import styles from './index.module.css';

interface SiteStatisticsModalProps {
    visible: boolean;
    site: {
        site_id: string;
        name: string;
    } | undefined;
    onClose: () => void;
}

const SiteStatisticsModal: React.FC<SiteStatisticsModalProps> = ({
    visible,
    site,
    onClose
}) => {
    const [loading, setLoading] = useState(false);
    const [statistics, setStatistics] = useState<StatisticsHistoryResponse | null>(null);
    const [timeRange] = useState<TimeRange>('30');

    const loadStatistics = async () => {
        if (!site) return;
        
        try {
            setLoading(true);
            const end = new Date();
            const start = new Date(end);
            start.setDate(end.getDate() - 30); // 获取最近30天的数据
            
            const response = await siteConfigApi.getStatisticsHistory({
                site_id: site.site_id,
                metrics: ['daily_results', 'daily_increments', 'checkins'],
                time_unit: 'day',
                calculation: 'last',
                start_date: start.toISOString().split('T')[0],
                end_date: end.toISOString().split('T')[0]
            });
            setStatistics(response);
        } catch (error) {
            message.error('加载统计数据失败');
            console.error('加载统计数据失败:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (visible && site) {
            loadStatistics();
        }
    }, [visible, site]);

    const renderValueWithIncrement = (value: number | null | undefined, increment: number | null | undefined, unit: string = '') => {
        return (
            <span>
                {(value === null || value === undefined ? 'N/A' : value.toLocaleString())}{unit}
                {increment !== null && increment !== undefined ? (
                    <span style={{ color: increment >= 0 ? '#52c41a' : '#ff4d4f', marginLeft: 8 }}>
                        {increment >= 0 ? '+' : ''}{increment.toLocaleString()}{unit}
                    </span>
                ) : null}
            </span>
        );
    };

    const latestData = statistics?.metrics.daily_results?.[0];
    const incrementData = statistics?.metrics.daily_increments?.[0];

    return (
        <Modal
            title={`${site?.name || ''} - 站点数据 - ${latestData?.date || ''}`}
            open={visible}
            onCancel={onClose}
            footer={null}
            width={1200}
            // style={{ top: 20 }}
        >
            <Spin spinning={loading}>
                {latestData && (
                    <>
                        <div className={styles.descriptionsContainer}>
                            <Descriptions title="用户信息" column={4} bordered size='small'>
                                <Descriptions.Item label="用户等级">
                                    {latestData.user_class || 'N/A'}
                                </Descriptions.Item>
                                <Descriptions.Item label="最后更新">
                                    {latestData.date || 'N/A'}
                                </Descriptions.Item>
                            </Descriptions>

                            <Descriptions title="魔力数据" column={4} bordered style={{ marginTop: 16 }} size='small'>
                                <Descriptions.Item label="魔力值">
                                    {renderValueWithIncrement(
                                        latestData.bonus,
                                        incrementData?.bonus_increment
                                    )}
                                </Descriptions.Item>
                                <Descriptions.Item label="时魔">
                                    {latestData.bonus_per_hour?.toLocaleString() || 'N/A'}
                                </Descriptions.Item>
                                <Descriptions.Item label="做种积分">
                                    {renderValueWithIncrement(
                                        latestData.seeding_score,
                                        incrementData?.seeding_score_increment
                                    )}
                                </Descriptions.Item>
                            </Descriptions>

                            <Descriptions title="流量统计" column={4} bordered style={{ marginTop: 16 }} size='small'>
                                <Descriptions.Item label="总上传量">
                                    {renderValueWithIncrement(
                                        latestData.upload,
                                        incrementData?.upload_increment,
                                        ' GB'
                                    )}
                                </Descriptions.Item>
                                <Descriptions.Item label="总下载量">
                                    {renderValueWithIncrement(
                                        latestData.download,
                                        incrementData?.download_increment,
                                        ' GB'
                                    )}
                                </Descriptions.Item>
                                <Descriptions.Item label="分享率">
                                    {latestData.ratio?.toFixed(3) || 'N/A'}
                                </Descriptions.Item>
                            </Descriptions>

                            <Descriptions title="做种信息" column={4} bordered style={{ marginTop: 16 }} size='small'>
                                <Descriptions.Item label="做种数量">
                                    {renderValueWithIncrement(
                                        latestData.seeding_count,
                                        incrementData?.seeding_count_increment,
                                        ' 个'
                                    )}
                                </Descriptions.Item>
                                <Descriptions.Item label="做种体积">
                                    {renderValueWithIncrement(
                                        latestData.seeding_size ? (latestData.seeding_size / 1024) : undefined,
                                        incrementData?.seeding_size_increment ? (incrementData.seeding_size_increment / 1024) : undefined,
                                        ' TB'
                                    )}
                                </Descriptions.Item>
                            </Descriptions>
                            <Descriptions title="签到统计" column={1} bordered style={{ marginTop: 16 }} size='small'>
                                <Descriptions.Item>
                                    {statistics && site && <BlockView site_id={site.site_id} />}
                                </Descriptions.Item>
                            </Descriptions>
                            <Descriptions title="数据趋势" column={1} bordered style={{ marginTop: 16 }} size='small'>
                                <Descriptions.Item>
                                    {statistics && <OverviewChart statistics={statistics} timeRange={timeRange} />}
                                </Descriptions.Item>
                            </Descriptions>
                        </div>
                        {/* <div className={styles.chartsContainer}>
                            <Divider orientation="left">签到状况</Divider>
                            <div className={styles.blockViewContainer}>
                                <BlockView />
                            </div>
                            <Divider orientation="left">数据趋势</Divider>
                            <div className={styles.chartContainer}>
                                {statistics && <OverviewChart statistics={statistics} timeRange={timeRange} />}
                            </div>
                        </div> */}
                    </>
                )}
            </Spin>
        </Modal>
    );
};

export default SiteStatisticsModal; 