import React, { useState } from 'react';
import { Card, Button, Dropdown, Space, Tag, Typography, Popconfirm } from 'antd';
import {
    MoreOutlined,
    SyncOutlined,
    ExperimentOutlined,
    BarChartOutlined,
    HolderOutlined,
    UploadOutlined,
    DownloadOutlined,
    PercentageOutlined,
    SettingOutlined
} from '@ant-design/icons';
import type { MenuProps } from 'antd';
import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    DragEndEvent
} from '@dnd-kit/core';
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    useSortable,
    rectSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import styles from './Sites.module.css';
import SiteSettingsModal from '../../components/SiteSettingsModal';

const { Text, Link } = Typography;

interface SiteData {
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

interface SortableSiteCardProps {
    site: SiteData;
    onSettingsClick: (site: SiteData) => void;
}

const SortableSiteCard: React.FC<SortableSiteCardProps> = ({ site, onSettingsClick }) => {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging
    } = useSortable({ id: site.id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
    };

    const handleVisitSite = (e: React.MouseEvent) => {
        e.preventDefault();
    };

    return (
        <div ref={setNodeRef} style={style} className={styles.siteWrapper}>
            <Card
                className={styles.siteCard}
                bodyStyle={{ padding: '12px' }}
                actions={[
                    <SyncOutlined key="update" title="更新" />,
                    <ExperimentOutlined key="test" title="测试" />,
                    <BarChartOutlined key="stats" title="数据" />,
                    <SettingOutlined 
                        key="setting" 
                        title="设置"
                        onClick={(e) => {
                            e.stopPropagation();
                            onSettingsClick(site);
                        }}
                    />
                ]}
            >
                <div className={styles.cardHeader}>
                    <div
                        className={styles.dragHandle}
                        {...attributes}
                        {...listeners}
                    >
                        <HolderOutlined />
                    </div>
                    <div className={styles.siteInfo}>
                        {site.favicon && (
                            <img
                                src={site.favicon}
                                alt={site.name}
                                className={styles.favicon}
                            />
                        )}
                        <Text strong>{site.name}</Text>
                    </div>
                </div>
                <div className={styles.siteContent}>
                    <Popconfirm
                        placement='topLeft'
                        title="站点地址"
                        description="要访问该站点吗？"
                        okText="确定"
                        cancelText="取消"
                        onConfirm={() => window.open(site.base_url, '_blank')}
                    >
                        <Link 
                            href={site.base_url} 
                            onClick={handleVisitSite}
                        >
                            {site.base_url}
                        </Link>
                    </Popconfirm>
                    <Tag
                        color={site.connect_status === 'online' ? 'success' : 'error'}
                        className={styles.statusTag}
                    >
                        {site.connect_status === 'online' ? '在线' : '离线'}
                    </Tag>
                    <Space className={styles.stats}>
                        <span>
                            <UploadOutlined /> {site.upload} TB
                        </span>
                        <span>
                            <DownloadOutlined /> {site.download} TB
                        </span>
                        <span>
                            <PercentageOutlined /> {site.ratio}
                        </span>
                    </Space>
                </div>
            </Card>
        </div>
    );
};

const Sites: React.FC = () => {
    // 模拟数据
    const [sites, setSites] = useState<SiteData[]>([
        {
            id: '1',
            site_id: 'hdatoms',
            name: '馒头',
            base_url: 'https://hdatoms.org',
            connect_status: 'online',
            favicon: 'https://kp.m-team.cc/favicon.ico',
            upload: 1.5,
            download: 2.3,
            ratio: parseFloat((1.5 / 2.3).toFixed(2))
        },
        {
            id: '2',
            site_id: 'pthome',
            name: '铂金家',
            base_url: 'https://pthome.net',
            connect_status: 'offline',
            favicon: 'https://pthome.net/favicon.ico',
            upload: 0.8,
            download: 1.2,
            ratio: parseFloat((0.8 / 1.2).toFixed(2))
        },
        {
            id: '3',
            site_id: 'hdsky',
            name: '天空',
            base_url: 'https://hdsky.me',
            connect_status: 'online',
            favicon: 'https://hdsky.me/favicon.ico',
            upload: 2.1,
            download: 1.8,
            ratio: parseFloat((2.1 / 1.8).toFixed(2))
        },
        {
            id: '4',
            site_id: 'ttg',
            name: '听听歌',
            base_url: 'https://totheglory.im',
            connect_status: 'online',
            favicon: 'https://totheglory.im/favicon.ico',
            upload: 3.2,
            download: 2.5,
            ratio: parseFloat((3.2 / 2.5).toFixed(2))
        },
        {
            id: '5',
            site_id: 'chdbits',
            name: '彩虹岛',
            base_url: 'https://chdbits.co',
            connect_status: 'offline',
            favicon: 'https://chdbits.co/favicon.ico',
            upload: 1.7,
            download: 1.4,
            ratio: parseFloat((1.7 / 1.4).toFixed(2))
        },
        {
            id: '6',
            site_id: 'ourbits',
            name: '我堡',
            base_url: 'https://ourbits.club',
            connect_status: 'online',
            favicon: 'https://ourbits.club/favicon.ico',
            upload: 4.5,
            download: 3.8,
            ratio: parseFloat((4.5 / 3.8).toFixed(2))
        },
        {
            id: '7',
            site_id: 'pterclub',
            name: '猫站',
            base_url: 'https://pterclub.com',
            connect_status: 'online',
            favicon: 'https://pterclub.com/favicon.ico',
            upload: 2.8,
            download: 2.1,
            ratio: parseFloat((2.8 / 2.1).toFixed(2))
        },
        {
            id: '8',
            site_id: 'hdchina',
            name: 'HDC',
            base_url: 'https://hdchina.org',
            connect_status: 'online',
            favicon: 'https://hdhome.org/favicon.ico',
            upload: 5.6,
            download: 4.2,
            ratio: parseFloat((5.6 / 4.2).toFixed(2))
        }
    ]);

    const [selectedSite, setSelectedSite] = useState<SiteData | undefined>();
    const [settingsVisible, setSettingsVisible] = useState(false);

    const sensors = useSensors(
        useSensor(PointerSensor),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

    const handleDragEnd = (event: DragEndEvent) => {
        const { active, over } = event;

        if (over && active.id !== over.id) {
            setSites((items) => {
                const oldIndex = items.findIndex(item => item.id === active.id);
                const newIndex = items.findIndex(item => item.id === over.id);
                return arrayMove(items, oldIndex, newIndex);
            });
        }
    };

    const handleSettingsClick = (site: SiteData) => {
        setSelectedSite(site);
        setSettingsVisible(true);
    };

    const handleSettingsSave = (values: any) => {
        console.log('Settings saved:', values);
        setSettingsVisible(false);
    };

    return (
        <div className={styles.sitesContainer}>
            <div className={styles.header}>
                <Button type="primary">添加站点</Button>
            </div>
            <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={handleDragEnd}
            >
                <SortableContext
                    items={sites.map(site => site.id)}
                    strategy={rectSortingStrategy}
                >
                    <div className={styles.sitesGrid}>
                        {sites.map((site) => (
                            <SortableSiteCard
                                key={site.id}
                                site={site}
                                onSettingsClick={handleSettingsClick}
                            />
                        ))}
                    </div>
                </SortableContext>
            </DndContext>

            <SiteSettingsModal
                visible={settingsVisible}
                site={selectedSite}
                onClose={() => setSettingsVisible(false)}
                onSave={handleSettingsSave}
            />
        </div>
    );
};

export default Sites;

