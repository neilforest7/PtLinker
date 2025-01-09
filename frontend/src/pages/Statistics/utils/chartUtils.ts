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

export const formatValue = (value: number | null | undefined, type: MetricType) => {
    if (value === null || value === undefined) {
        switch (type) {
            case 'upload':
            case 'download':
                return '0 GB';
            case 'seeding_size':
                return '0 TB';
            default:
                return '0';
        }
    }

    switch (type) {
        case 'upload':
        case 'download':
            return `${value.toFixed(1)} GB`;
        case 'seeding_size':
            return `${(value / 1024).toFixed(2)} TB`;  // 转换为 TB
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

// 处理日期范围内的数据
export const filterDataByTimeRange = (data: ChartDataItem[], timeRange: TimeRange) => {
    if (timeRange === 'all') return data;

    const days = parseInt(timeRange);
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - days + 1);

    return data.filter(item => {
        const itemDate = new Date(item.date);
        return itemDate >= start && itemDate <= end;
    });
}; 