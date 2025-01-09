// 将 UTC 日期转换为东八区（UTC+8）日期字符串 YYYY-MM-DD
export const toUTC8DateString = (date: Date): string => {
    const utc8Date = new Date(date.getTime() + 8 * 60 * 60 * 1000);
    return utc8Date.toISOString().split('T')[0];
};

// 将 YYYY-MM-DD 格式的日期字符串解析为 UTC+8 的 Date 对象
export const parseUTC8Date = (dateStr: string): Date => {
    const [year, month, day] = dateStr.split('-').map(Number);
    const date = new Date();
    date.setUTCFullYear(year);
    date.setUTCMonth(month - 1);
    date.setUTCDate(day);
    date.setUTCHours(-8, 0, 0, 0);  // 设置为 UTC+8 时区的 00:00:00
    return date;
};

// 格式化日期为 YYYY/MM/DD
export const formatDate = (date: Date): string => {
    const utc8Date = new Date(date.getTime() + 8 * 60 * 60 * 1000);
    return `${utc8Date.getUTCFullYear()}/${String(utc8Date.getUTCMonth() + 1).padStart(2, '0')}/${String(utc8Date.getUTCDate()).padStart(2, '0')}`;
}; 