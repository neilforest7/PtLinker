import React, { useState, useEffect } from 'react';
import { Card, List, Tag, Typography, Space, Spin, message, Slider, Row, Col, Progress, Button, Popconfirm, Tooltip, Select } from 'antd';
import { PlayCircleOutlined, DeleteOutlined, ScheduleFilled, ProjectFilled, CloseCircleOutlined } from '@ant-design/icons';
import { siteConfigApi } from '../../api/siteConfig';
import { TaskResponse } from '../../types/api';
import styles from './Tasks.module.css';

const { Text } = Typography;

interface TaskCardProps {
    task: TaskResponse;
    onTaskUpdate?: () => void;
}

const TaskCard: React.FC<TaskCardProps> = ({ task, onTaskUpdate }) => {
    const getStatusColor = (status: string) => {
        switch (status) {
            case 'pending':
                return 'orange';
            case 'queued':
                return 'blue';
            case 'ready':
                return '';
            case 'success':
                return 'success';
            case 'failed':
                return 'error';
            case 'running':
                return 'processing';
            case 'cancelled':
                return 'pink';
            default:
                return 'default';
        }
    };

    const getStatusText = (status: string) => {
        switch (status) {
            case 'pending':
                return '等待队列';
            case 'queued':
                return '队列中';
            case 'ready':
                return '可以开始';
            case 'success':
                return '成功';
            case 'failed':
                return '失败';
            case 'running':
                return '运行中';
            case 'cancelled':
                return '已取消';
            default:
                return '未知';
        }
    };

    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    };

    const handleCancelTask = async () => {
        try {
            const response = await siteConfigApi.cancelTask(task.task_id);
            if (response.message === '任务已取消'){
                message.success(response.message);
                onTaskUpdate?.();
            } else {
                message.error("未能取消任务: " + response.message);
            }
        } catch (error) {
            message.error('取消任务失败');
            console.error('取消任务失败:', error);
        }
    };

    const renderTaskContent = () => {
        const content = [];

        switch (task.status) {
            case 'running':
                if (task.msg) {
                    content.push(
                        <Text key="msg" type="secondary" ellipsis={{ tooltip: task.msg }}>
                            消息：{task.msg}
                        </Text>
                    );
                }
                if (task.task_metadata?.pid) {
                    content.push(
                        <Text key="pid" type="secondary">PID：{task.task_metadata.pid}</Text>
                    );
                }
                if (task.updated_at) {
                    content.push(
                        <Text key="updated" type="secondary">更新时间：{formatDate(task.updated_at)}</Text>
                    );
                }
                break;


            case 'success':
                if (task.msg) {
                    content.push(
                        <Text key="msg" type="secondary" ellipsis={{ tooltip: task.msg }}>
                            消息：{task.msg}
                        </Text>
                    );
                }
                if (task.task_metadata?.pid) {
                    content.push(
                        <Text key="pid" type="secondary">PID：{task.task_metadata.pid}</Text>
                    );
                }
                if (task.updated_at) {
                    content.push(
                        <Text key="updated" type="secondary">更新时间：{formatDate(task.updated_at)}</Text>
                    );
                }
                break;

            case 'failed':
                if (task.msg) {
                    content.push(
                        <Text key="msg" type="danger" ellipsis={{ tooltip: task.msg }}>
                            错误信息：{task.msg}
                        </Text>
                    );
                }
                if (task.updated_at) {
                    content.push(
                        <Text key="created" type="secondary">更新时间：{formatDate(task.updated_at)}</Text>
                    );
                }
                if (task.completed_at) {
                    content.push(
                        <Text key="completed" type="secondary">结束时间：{formatDate(task.completed_at)}</Text>
                    );
                }
                break;

            case 'cancelled':
                if (task.msg) {
                    content.push(
                        <Text key="msg" type="danger" ellipsis={{ tooltip: task.msg }}>
                            错误信息：{task.msg}
                        </Text>
                    );
                }
                if (task.completed_at) {
                    content.push(
                        <Text key="cancelled" type="secondary">取消时间：{formatDate(task.completed_at)}</Text>
                    );
                }
                if (task.created_at) {
                    content.push(
                        <Text key="created" type="secondary">创建时间：{formatDate(task.created_at)}</Text>
                    );
                }
                break;
            
            case 'queued':
            case 'ready':
            case 'pending':
                if (task.created_at) {
                    content.push(
                        <Text key="created" type="secondary">创建时间：{formatDate(task.created_at)}</Text>
                    );
                }
                break;
        }

        if (task.status === 'ready' || task.status === 'pending' || task.status === 'queued') {
            content.push(
                <div key="cancel-button" className={styles.taskActions}>
                    <Popconfirm
                        title="确认取消任务"
                        description="确定要取消这个任务吗？"
                        onConfirm={handleCancelTask}
                        okText="确定"
                        cancelText="取消"
                    >
                        <Tooltip title="取消任务">
                            <Button 
                                type="text" 
                                danger 
                                size="small"
                                icon={<CloseCircleOutlined />}
                            />
                        </Tooltip>
                    </Popconfirm>
                </div>
            );
        }

        return content;
    };

    const renderProgress = () => {
        if (task.status !== 'success' && task.status !== 'running') {
            return null;
        }

        const percent = task.status === 'success' ? 100 : 
            (task.task_metadata?.progress || 0);

        return (
            <Progress 
                percent={percent} 
                size="small" 
                status={task.status === 'running' ? 'active' : 'success'}
                strokeWidth={4}
            />
        );
    };

    return (
        <Card className={styles.taskCard} size="small">
            <div className={styles.taskHeader}>
                <Text strong>{task.site_id}</Text>
                <Tag color={getStatusColor(task.status)}>
                    <span className={styles.smallText}>{getStatusText(task.status)}</span>
                </Tag>
            </div>
            <div className={styles.taskContent}>
                <Space direction="vertical" size="small" className={styles.smallText}>
                    {renderTaskContent()}
                </Space>
                {renderProgress()}
            </div>
        </Card>
    );
};

interface QueueProgressState {
    total: number;
    running: number;
    success: number;
    percentage: number;
    failed?: number;
    startTime: string;
}

const Tasks: React.FC = () => {
    const [tasks, setTasks] = useState<TaskResponse[]>([]);
    const [loading, setLoading] = useState(false);
    const [pollInterval, setPollInterval] = useState(30000);
    const [columnCount, setColumnCount] = useState(4);
    const [queueProgress, setQueueProgress] = useState<QueueProgressState | null>(null);
    const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
    const [selectedSites, setSelectedSites] = useState<string[]>([]);

    // 状态选项
    const statusOptions = [
        { label: '成功', value: 'success' },
        { label: '失败', value: 'failed' },
        { label: '运行中', value: 'running' },
        { label: '待命', value: 'ready' },
        { label: '等待中', value: 'pending' },
        { label: '已取消', value: 'cancelled' },
    ];

    // 获取唯一的站点 ID 列表
    const getSiteOptions = () => {
        const uniqueSites = Array.from(new Set(tasks.map(task => task.site_id)));
        return uniqueSites.map(site => ({
            label: site,
            value: site,
        }));
    };

    // 过滤任务
    const getFilteredTasks = () => {
        return tasks.filter(task => {
            const statusMatch = selectedStatuses.length === 0 || selectedStatuses.includes(task.status);
            const siteMatch = selectedSites.length === 0 || selectedSites.includes(task.site_id);
            return statusMatch && siteMatch;
        });
    };

    const loadTasks = async () => {
        try {
            setLoading(true);
            const tasksData = await siteConfigApi.getAllSitesTasks(50);
            setTasks(tasksData);
            
            // 检查是否有运行中的任务
            const hasRunningTasks = tasksData.some(task => task.status === 'running');
            setPollInterval(hasRunningTasks ? 4000 : 30000);
        } catch (error) {
            message.error('加载任务数据失败');
            console.error('加载任务数据失败:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadTasks();
        const interval = setInterval(loadTasks, pollInterval);
        return () => clearInterval(interval);
    }, [pollInterval]); // 当轮询时间改变时重新设置定时器

    const handleStartQueue = async () => {
        try {
            const result = await siteConfigApi.startQueueTasks();
            if (result.code === 200) {
                message.success(result.message);
                // 设置初始进度，记录启动时间
                setQueueProgress({
                    total: result.data.started_count,
                    running: result.data.started_count,
                    success: 0,
                    percentage: 0,
                    failed: result.data.totol_count - result.data.started_count,
                    startTime: new Date().toISOString()
                });
                loadTasks();
            } else {
                message.error(result.message);
            }
        } catch (error) {
            message.error('启动队列任务失败');
            console.error('启动队列任务失败:', error);
        }
    };

    const handleClearQueue = async () => {
        try {
            const result = await siteConfigApi.clearPendingTasks();
            if (result.code === 200) {
                message.success(result.message);
                setQueueProgress(null); // 清除进度显示
                loadTasks(); // 刷新任务列表
            } else {
                message.error(result.message);
            }
        } catch (error) {
            message.error('清除队列任务失败');
            console.error('清除队列任务失败:', error);
        }
    };

    // 修改计算队列进度的逻辑
    const calculateQueueProgress = (tasks: TaskResponse[]) => {
        if (!tasks.length) return null;

        const totalTasks = tasks.length;
        const successTasks = tasks.filter(task => task.status === 'success');
        const runningTasks = tasks.filter(task => task.status === 'running');

        // 计算运行中任务的进度总和
        const runningProgress = runningTasks.reduce((sum, task) => {
            return sum + (task.task_metadata?.progress || 0);
        }, 0);

        // 计算总进度：成功任务算100%，运行中任务算实际进度
        const totalProgress = (successTasks.length * 100 + runningProgress) / (totalTasks * 100);
        // console.log('totalProgress', totalProgress);
        return {
            total: totalTasks,
            running: runningTasks.length,
            success: successTasks.length,
            percentage: Math.round(totalProgress * 100)
        };
    };

    // 计算当前队列进度
    useEffect(() => {
        if (queueProgress && tasks.length > 0) {
            // 只统计在队列启动后创建的任务
            const queueTasks = tasks.filter(task => 
                new Date(task.updated_at) >= new Date(queueProgress.startTime)
            );
            
            const progress = calculateQueueProgress(queueTasks);
            if (progress) {
                setQueueProgress(prev => ({
                    ...prev!,
                    total: progress.total,
                    success: progress.success,
                    running: progress.running,
                    percentage: progress.percentage
                }));
            }
        }
    }, [tasks]);

    return (
        <Spin spinning={loading}>
            <div className={styles.tasksContainer}>
                <Row align="middle" className={styles.controlBar}>
                    <Col span={8}>
                        <Space>
                            <Popconfirm
                                placement='bottomLeft'
                                title="确认启动队列"
                                description="确定要启动所有待处理的任务吗？"
                                onConfirm={handleStartQueue}
                                okText="确定"
                                cancelText="取消"
                            >
                                <Button 
                                    type="primary" 
                                    icon={<PlayCircleOutlined />}
                                >
                                    启动队列
                                </Button>
                            </Popconfirm>
                            <Popconfirm
                                placement='bottomLeft'
                                title="确认清除队列"
                                description="确定要清除所有待处理的任务吗？"
                                onConfirm={handleClearQueue}
                                okText="确定"
                                cancelText="取消"
                            >
                                <Button 
                                    danger
                                    icon={<DeleteOutlined />}
                                >
                                    清除队列
                                </Button>
                            </Popconfirm>
                        </Space>
                    </Col>
                    {queueProgress && (
                        <Col span={15}>
                            <Tooltip title={`${queueProgress.success} 成功 / ${queueProgress.running} 运行中 / ${queueProgress.total} 总数`}>
                                <Progress
                                    // type="dashboard"
                                    size="small"
                                    status={queueProgress.running > 0 ? 'active' : undefined}
                                    percent={queueProgress.percentage}
                                    success={{percent: Math.round(queueProgress.success / queueProgress.total * 100)}}
                                />
                            </Tooltip>
                        </Col>
                    )}
                </Row>
                <Row align="middle" className={styles.controlBar}>
                    <Col>
                        <Select
                            prefix="状态"
                            suffixIcon={<ProjectFilled />}
                            mode="multiple"
                            allowClear
                            style={{ width: '100%', minWidth: '200px' }}
                            placeholder="按状态筛选"
                            value={selectedStatuses}
                            onChange={setSelectedStatuses}
                            options={statusOptions}
                        />
                    </Col>
                    <Col>
                        <Select
                            prefix="站点"
                            suffixIcon={<ScheduleFilled />}
                            mode="multiple"
                            allowClear
                            style={{ width: '100%', minWidth: '300px' }}
                            placeholder="按站点筛选"
                            value={selectedSites}
                            onChange={setSelectedSites}
                            options={getSiteOptions()}
                        />
                    </Col>
                    <Typography.Text>列数调整：</Typography.Text>
                    <Col>
                        <Slider
                            min={1}
                            max={9}
                            value={columnCount}
                            onChange={setColumnCount}
                            style={{ width: '100%', minWidth: '200px' }}
                        />
                    </Col>
                </Row>
                <List
                    grid={{
                        gutter: 16,
                        column: columnCount,
                    }}
                    dataSource={getFilteredTasks()}
                    renderItem={(task) => (
                        <List.Item>
                            <TaskCard 
                                task={task} 
                                onTaskUpdate={loadTasks}
                            />
                        </List.Item>
                    )}
                />
            </div>
        </Spin>
    );
};

export default Tasks; 