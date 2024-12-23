import React, { useState, useEffect } from 'react';
import { Card, List, Tag, Typography, Space, Spin, message, Slider, Row, Col, Progress, Button, Popconfirm } from 'antd';
import { PlayCircleOutlined, DeleteOutlined } from '@ant-design/icons';
import { siteConfigApi } from '../../api/siteConfig';
import { TaskResponse } from '../../types/api';
import styles from './Tasks.module.css';

const { Text } = Typography;

interface TaskCardProps {
    task: TaskResponse;
}

const TaskCard: React.FC<TaskCardProps> = ({ task }) => {
    const getStatusColor = (status: string) => {
        switch (status) {
            case 'success':
                return 'success';
            case 'failed':
                return 'error';
            case 'running':
                return 'processing';
            case 'ready':
                return '';
            case 'pending':
                return 'orange';
            case 'cancelled':
                return 'pink';
            default:
                return 'default';
        }
    };

    const getStatusText = (status: string) => {
        switch (status) {
            case 'success':
                return '成功';
            case 'failed':
                return '失败';
            case 'running':
                return '运行中';
            case 'ready':
                return '待命';
            case 'pending':
                return '等待中';
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
                
            case 'ready':
            case 'pending':
                if (task.created_at) {
                    content.push(
                        <Text key="created" type="secondary">创建时间：{formatDate(task.created_at)}</Text>
                    );
                }
                break;
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

const Tasks: React.FC = () => {
    const [tasks, setTasks] = useState<TaskResponse[]>([]);
    const [loading, setLoading] = useState(false);
    const [pollInterval, setPollInterval] = useState(30000);
    const [columnCount, setColumnCount] = useState(4);

    const loadTasks = async () => {
        try {
            setLoading(true);
            const tasksData = await siteConfigApi.getAllSitesTasks(50);
            setTasks(tasksData);
            
            // 检查是否有运行中的任务
            const hasRunningTasks = tasksData.some(task => task.status === 'running');
            setPollInterval(hasRunningTasks ? 2000 : 30000);
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
                loadTasks(); // 刷新任务列表
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
                loadTasks(); // 刷新任务列表
            } else {
                message.error(result.message);
            }
        } catch (error) {
            message.error('清除队列任务失败');
            console.error('清除队列任务失败:', error);
        }
    };

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
                    <Col span={4}>
                        <Typography.Text>列数调整：</Typography.Text>
                    </Col>
                    <Col span={12}>
                        <Slider
                            min={1}
                            max={9}
                            value={columnCount}
                            onChange={setColumnCount}
                            marks={{
                                1: '1',
                                3: '3',
                                5: '5',
                                7: '7',
                                9: '9',
                            }}
                        />
                    </Col>
                </Row>
                <List
                    grid={{
                        gutter: 16,
                        column: columnCount,
                    }}
                    dataSource={tasks}
                    renderItem={(task) => (
                        <List.Item>
                            <TaskCard task={task} />
                        </List.Item>
                    )}
                />
            </div>
        </Spin>
    );
};

export default Tasks; 