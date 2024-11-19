// 通用响应类型
export interface ApiResponse<T = any> {
    success: boolean;
    data?: T;
    error?: string;
    timestamp: number;
}

// 任务状态
export enum TaskStatus {
    PENDING = 'PENDING',
    RUNNING = 'RUNNING',
    COMPLETED = 'COMPLETED',
    FAILED = 'FAILED',
    PAUSED = 'PAUSED',
}

// 任务进度
export interface TaskProgress {
    taskId: string;
    status: TaskStatus;
    progress: number;
    total?: number;
    error?: string;
    timestamp: number;
} 