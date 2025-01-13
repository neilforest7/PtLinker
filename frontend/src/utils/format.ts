export const formatSize = (size: number | null | undefined): string => {
    if (size === null || size === undefined) return 'N/A';
    if (size === 0) return '0 GB';
    return `${(size).toFixed(2)} GB`;
};

export const formatNumber = (num: number | null | undefined): string => {
    if (num === null || num === undefined) return 'N/A';
    return num.toLocaleString('zh-CN');
}; 