// API响应类型定义
export interface WebElement {
    name: string;
    selector: string;
    type?: 'text' | 'attribute' | 'html' | 'src' | 'password' | 'checkbox' | 'by_day';
    location?: string;
    second_selector?: string;
    required?: boolean;
    attribute?: string;
    ele_only?: boolean;
    need_pre_action?: boolean;
    index?: number;
    url_pattern?: string;
    page_url?: string;
    pre_action_type?: string;
    expect_text?: string;
}

export interface CaptchaConfig {
    type?: string;
    element: WebElement;
    input: WebElement;
    hash?: WebElement;
}

export interface LoginConfig {
    login_url: string;
    form_selector: string;
    pre_login?: any;
    fields: Record<string, WebElement>;
    captcha?: CaptchaConfig;
    success_check: WebElement;
}

export interface ExtractRuleSet {
    rules: WebElement[];
}

export interface CheckInConfig {
    enabled?: boolean;
    checkin_url?: string;
    checkin_button?: WebElement;
    success_check?: WebElement;
}

export interface SiteConfigResponse {
    site_id: string;
    site_url: string;
    login_config?: LoginConfig;
    extract_rules?: ExtractRuleSet;
    checkin_config?: CheckInConfig;
}

export interface CrawlerConfigResponse {
    site_id: string;
    enabled: boolean;
    use_proxy: boolean;
    proxy_url?: string;
    fresh_login: boolean;
    captcha_method?: 'manual' | 'api' | 'ocr' | 'skip';
    captcha_skip: boolean;
    timeout?: number;
    headless: boolean;
    login_max_retry?: number;
}

export interface BaseResponse {
    code: number;
    message: string;
    data?: any;
    metadata?: Record<string, any>;
}

export interface SettingsResponse {
    crawler_config_path: string;
    crawler_credential_path: string;
    crawler_storage_path: string;
    crawler_max_concurrency: number;
    fresh_login: boolean;
    login_max_retry: number;
    captcha_default_method: string;
    captcha_skip_sites: string;
    captcha_api_key?: string;
    captcha_api_url?: string;
    captcha_max_retries: number;
    captcha_poll_interval: number;
    captcha_timeout: number;
    browser_viewport_width: number;
    browser_viewport_height: number;
    chrome_path?: string;
    driver_path?: string;
    headless: boolean;
    page_timeout: number;
    navigation_timeout: number;
    request_timeout: number;
    verify_ssl: boolean;
    retry_times: number;
    log_level: string;
    console_log_level: string;
    file_log_level: string;
    error_log_level: string;
    log_file: string;
    error_log_file: string;
    storage_path: string;
    captcha_storage_path: string;
    enable_checkin: boolean;
    checkin_sites: string;
    id?: number;
    created_at?: string;
    updated_at?: string;
}

export interface SettingsUpdate extends Partial<Omit<SettingsResponse, 'id' | 'created_at' | 'updated_at'>> {}

export interface CrawlerCredentialResponse {
    site_id: string;
    enable_manual_cookies?: boolean;
    manual_cookies?: string;
    username?: string;
    password?: string;
    authorization?: string;
    apikey?: string;
}

export interface TaskResponse {
    task_id: string;
    site_id: string;
    status: 'ready' | 'pending' | 'queued' | 'running' | 'success' | 'failed' | 'cancelled';
    created_at: string;
    updated_at: string;
    completed_at?: string;
    msg?: string;
    error_details?: any;
    task_metadata?: any;
    system_info?: any;
    duration?: number;
    error_message?: string;
}

// 统计数据相关接口
export interface DailyResult {
    date: string;
    site_id: string;
    username: string;
    user_class: string;
    upload: number;
    download: number;
    ratio: number;
    bonus: number;
    bonus_per_hour: number | null;
    seeding_score: number | null;
    seeding_size: number;
    seeding_count: number;
    task_id: string;
}

export interface DailyIncrement {
    date: string;
    site_id: string;
    upload_increment: number;
    download_increment: number;
    bonus_increment: number;
    seeding_score_increment: number | null;
    seeding_size_increment: number | null;
    seeding_count_increment: number | null;
    task_id: string;
    reference_task_id: string;
}

export interface SiteStatistics {
    daily_results: DailyResult;
    daily_increments: DailyIncrement;
    last_success_time: string;
}

export interface StatisticsResponse {
    [site_id: string]: SiteStatistics;
}

export interface CheckinRecord {
    date: string;
    site_id: string;
    checkin_status: string;
    checkin_time: string;
    task_id: string;
}

export interface StatisticsHistoryResponse {
    time_range: {
        start: string;
        end: string;
    };
    metrics: {
        daily_results: DailyResult[];
        daily_increments: DailyIncrement[];
        checkins: CheckinRecord[];
    };
    summary: {
        total_sites: number;
        total_upload_increment: number;
        total_bonus_increment: number;
        successful_checkins: number;
    };
    metadata: {
        generated_at: string;
        applied_filters: {
            site_id?: string[];
            time_unit: string;
            calculation: string;
            metrics?: string[];
            include_fields?: string[];
            exclude_fields?: string[];
            group_by?: string[];
        };
    };
}

