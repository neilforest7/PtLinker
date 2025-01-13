import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Spin, Empty, Segmented, Table } from 'antd';
import { 
    UploadOutlined, 
    DownloadOutlined,
    GiftOutlined,
    CloudUploadOutlined,
    PercentageOutlined,
    AppstoreOutlined,
    BarsOutlined,
    LineChartOutlined
} from '@ant-design/icons';
import { siteConfigApi } from '../../api/siteConfig';
import { StatisticsResponse, SiteStatistics } from '../../types/api';
import styles from './Statistics.module.css';
import ChartView from './ChartView';
import BlockView from './components/BlockView';

type ViewMode = 'grid' | 'list' | 'chart';

interface TotalStats {
    upload: number;
    download: number;
    seeding_count: number;
    seeding_size: number;
    bonus: number;
}

const Statistics: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [statistics, setStatistics] = useState<StatisticsResponse>({});
    const [viewMode, setViewMode] = useState<ViewMode>('grid');

    const loadStatistics = async () => {
        try {
            setLoading(true);
            const data = await siteConfigApi.getLastSuccessStatistics();
            setStatistics(data);
            console.log(data);
        } catch (error) {
            console.error('加载统计数据失败:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadStatistics();
    }, []);

    if (loading) {
        return <Spin size="large" />;
    }

    if (Object.keys(statistics).length === 0) {
        return <Empty description="暂无统计数据" />;
    }

    const formatSize = (size: number) => {
        if (size === 0) return '0 GB';
        return `${size.toFixed(2)} GB`;
    };

    const formatSizeToTB = (size: number) => {
        if (size === 0) return '0 TB';
        return `${(size / 1024).toFixed(2)} TB`;
    };

    // 计算总计数据
    const totals = Object.values(statistics).reduce<TotalStats>((acc, site: SiteStatistics) => {
        const { daily_results } = site;
        return {
            upload: acc.upload + (daily_results.upload || 0),
            download: acc.download + (daily_results.download || 0),
            seeding_count: acc.seeding_count + (daily_results.seeding_count || 0),
            seeding_size: acc.seeding_size + (daily_results.seeding_size || 0),
            bonus: acc.bonus + (daily_results.bonus || 0)
        };
    }, { upload: 0, download: 0, seeding_count: 0, seeding_size: 0, bonus: 0 });

    // 表格列定义
    const columns = [
        {
            title: '站点',
            dataIndex: 'siteId',
            key: 'siteId',
            render: (siteId: string, record: any) => `${siteId} (${record.username})`,
        },
        {
            title: '上传量',
            dataIndex: 'upload',
            key: 'upload',
            render: (upload: number | null) => formatSize(upload ?? 0),
            sorter: (a: any, b: any) => (a.upload ?? 0) - (b.upload ?? 0),
        },
        {
            title: '下载量',
            dataIndex: 'download',
            key: 'download',
            render: (download: number | null) => formatSize(download ?? 0),
            sorter: (a: any, b: any) => (a.download ?? 0) - (b.download ?? 0),
        },
        {
            title: '魔力值',
            dataIndex: 'bonus',
            key: 'bonus',
            render: (bonus: number | null) => (bonus ?? 0).toFixed(2),
            sorter: (a: any, b: any) => (a.bonus ?? 0) - (b.bonus ?? 0),
        },
        {
            title: '分享率',
            dataIndex: 'ratio',
            key: 'ratio',
            render: (ratio: number | null) => (ratio ?? 0).toFixed(3),
            sorter: (a: any, b: any) => (a.ratio ?? 0) - (b.ratio ?? 0),
        },
        {
            title: '做种数',
            dataIndex: 'seeding_count',
            key: 'seeding_count',
            render: (count: number | null) => count ?? 0,
            sorter: (a: any, b: any) => (a.seeding_count ?? 0) - (b.seeding_count ?? 0),
        },
        {
            title: '做种体积',
            dataIndex: 'seeding_size',
            key: 'seeding_size',
            render: (size: number | null) => formatSize(size ?? 0),
            sorter: (a: any, b: any) => (a.seeding_size ?? 0) - (b.seeding_size ?? 0),
        },
        {
            title: '更新时间',
            dataIndex: 'date',
            key: 'date',
            render: (date: string) => new Date(date).toLocaleDateString(),
            sorter: (a: any, b: any) => new Date(a.date).getTime() - new Date(b.date).getTime(),
        },
    ];

    // 转换数据为表格格式
    const tableData = Object.entries(statistics).map(([siteId, stats]: [string, SiteStatistics]) => ({
        key: siteId,
        siteId,
        ...stats.daily_results,
    }));

    const renderGridView = () => (
        <Row>
            {Object.entries(statistics).map(([siteId, stats]: [string, SiteStatistics]) => (
                <Col xs={24} sm={12} lg={8} xl={6} key={siteId} className={styles.siteCards}>
                    <Card 
                        title={`${siteId} (${stats.daily_results.username})`} 
                        extra={<a href={`/settings/site/${siteId}`}>设置</a>}
                        size="small"
                        className={styles.siteCard}
                    >
                        <Row gutter={[16, 16]}>
                            <Col span={12}>
                                <Statistic
                                    title="上传量"
                                    value={formatSize(stats.daily_results.upload ?? 0)}
                                    prefix={<UploadOutlined />}
                                    className={styles.statisticValue}
                                />
                            </Col>
                            <Col span={12}>
                                <Statistic
                                    title="下载量"
                                    value={formatSize(stats.daily_results.download ?? 0)}
                                    prefix={<DownloadOutlined />}
                                    className={styles.statisticValue}
                                />
                            </Col>
                            <Col span={12}>
                                <Statistic
                                    title="魔力值"
                                    value={(stats.daily_results.bonus ?? 0).toFixed(2)}
                                    prefix={<GiftOutlined />}
                                    className={styles.statisticValue}
                                />
                            </Col>
                            <Col span={12}>
                                <Statistic
                                    title="分享率"
                                    value={stats.daily_results.ratio ?? 0}
                                    prefix={<PercentageOutlined />}
                                    className={styles.statisticValue}
                                    formatter={(value) => (value as number).toFixed(3)}
                                />
                            </Col>
                            <Col span={12}>
                                <Statistic
                                    title="做种数"
                                    value={stats.daily_results.seeding_count ?? 0}
                                    prefix={<CloudUploadOutlined />}
                                    className={styles.statisticValue}
                                />
                            </Col>
                            <Col span={12}>
                                <Statistic
                                    title="做种体积"
                                    value={formatSize(stats.daily_results.seeding_size ?? 0)}
                                    prefix={<CloudUploadOutlined />}
                                    className={styles.statisticValue}
                                />
                            </Col>
                        </Row>
                        <div className={styles.updateTime}>
                            更新于: {new Date(stats.daily_results.date).toLocaleDateString()}
                        </div>
                    </Card>
                </Col>
            ))}
        </Row>
    );

    const renderListView = () => (
        <Table 
            columns={columns} 
            dataSource={tableData}
            className={styles.siteTable}
            scroll={{ x: true }}
            pagination={false}
        />
    );

    return (
        <div className={styles.statisticsContainer}>
            <Row gutter={[16, 16]} className={styles.summaryRow}>
                <Col span={6}>
                    <Card className={styles.summaryCard}>
                        <Statistic
                            title="总上传量"
                            value={formatSizeToTB(totals?.upload || 0)}
                            prefix={<UploadOutlined />}
                        />
                    </Card>
                </Col>
                <Col span={6}>
                    <Card className={styles.summaryCard}>
                        <Statistic
                            title="总下载量"
                            value={formatSizeToTB(totals?.download || 0)}
                            prefix={<DownloadOutlined />}
                        />
                    </Card>
                </Col>
                <Col span={6}>
                    <Card className={styles.summaryCard}>
                        <Statistic
                            title="总做种数"
                            value={totals?.seeding_count || 0}
                            prefix={<CloudUploadOutlined />}
                        />
                    </Card>
                </Col>
                <Col span={6}>
                    <Card className={styles.summaryCard}>
                        <Statistic
                            title="总做种体积"
                            value={formatSizeToTB(totals?.seeding_size || 0)}
                            prefix={<GiftOutlined />}
                        />
                    </Card>
                </Col>
            </Row>
            <BlockView />
            <div className={styles.viewControl}>
                <Segmented
                    options={[
                        {
                            value: 'grid',
                            icon: <AppstoreOutlined />,
                            label: '卡片视图'
                        },
                        {
                            value: 'list',
                            icon: <BarsOutlined />,
                            label: '列表视图'
                        },
                        {
                            value: 'chart',
                            icon: <LineChartOutlined />,
                            label: '统计视图'
                        }
                    ]}
                    value={viewMode}
                    onChange={(value) => setViewMode(value as ViewMode)}
                    size="large"
                />
            </div>
            {viewMode === 'grid' && renderGridView()}
            {viewMode === 'list' && renderListView()}
            {viewMode === 'chart' && <ChartView />}
        </div>
    );
};

export default Statistics;