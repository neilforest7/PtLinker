// 站点相关类型定义 

export interface SiteData {
    id: string;
    site_id: string;
    name: string;
    base_url: string;
    connect_status: 'online' | 'offline';
    favicon?: string;
    upload: number;
    download: number;
    ratio: number;
}

export interface SiteSettings {
    site_url: string;
    enabled: boolean;
    login_config?: string;
    extract_rules?: string;
    checkin_config?: string;
    manual_cookies?: string;
    username?: string;
    password?: string;
    authorization?: string;
    apikey?: string;
    use_proxy: boolean;
    proxy_url?: string;
    fresh_login: boolean;
    captcha_skip: boolean;
    captcha_method?: 'ddddocr' | '2captcha' | 'manual';
    timeout?: number;
    headless: boolean;
    login_max_retry?: number;
}
