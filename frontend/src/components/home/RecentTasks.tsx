import { Button, Empty, Table, Tag, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { formatShortDateTime } from '../../utils/time';

interface HistoryItem {
  id: string;
  project_name?: string | null;
  tender_unit?: string | null;
  created_at?: string | null;
  stage?: string | null;
  action?: string | null;
  next_step?: string | null;
  next_action?: string | null;
  section_count?: number;
  leaf_section_count?: number;
  generated_section_count?: number;
  generated_leaf_count?: number;
  word_count?: number;
  writing_total_count?: number;
  writing_done_count?: number;
  writing_partial_count?: number;
  parse_status?: string | null;
}

const statusColor: Record<string, string> = {
  待编辑: 'orange',
  生成中: 'blue',
  已导出: 'green',
  解析完成: 'purple',
  解析中: 'processing',
  解析失败: 'red',
  已上传: 'cyan',
  解读完成: 'blue',
  标书编制: 'green',
  待投标确认: 'gold',
  正文生成中: 'processing',
  草稿待续写: 'orange',
  正文初稿完成: 'green',
};

function sectionProgress(record: HistoryItem): { done: number; total: number; words: number } {
  const total = record.leaf_section_count ?? record.writing_total_count ?? 0;
  const done = record.generated_leaf_count ?? record.generated_section_count ?? record.writing_done_count ?? 0;
  return {
    done,
    total,
    words: record.word_count || 0,
  };
}

interface RecentTasksProps {
  refreshKey?: number;
}

export function RecentTasks({ refreshKey = 0 }: RecentTasksProps): JSX.Element {
  const navigate = useNavigate();
  const [recentTasks, setRecentTasks] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchRecentTasks = async () => {
    try {
      setLoading(true);
      const { data } = await apiClient.get<{ items: HistoryItem[] }>('/api/bidding/history?limit=5', {
        skipGlobalLoading: true,
      });
      setRecentTasks(data.items || []);
    } catch (error: any) {
      message.error(error.message || '最近任务加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchRecentTasks();
  }, [refreshKey]);

  const openTask = (record: HistoryItem) => {
    const nextStep = record.next_step || '';
    if (nextStep === 'prefill') {
      window.location.href = `/prefill?projectId=${record.id}&fromHistory=1`;
      return;
    }
    if (nextStep === 'resume_partial') {
      window.location.href = `/bid-editor?projectId=${record.id}&action=resume-partial`;
      return;
    }
    if (nextStep === 'formal_check') {
      window.location.href = `/formal-check?projectId=${record.id}`;
      return;
    }
    if (nextStep === 'editor' || (record.section_count || 0) > 0 || record.stage === '标书编制') {
      window.location.href = `/bid-editor?projectId=${record.id}`;
      return;
    }
    navigate(`/interpretation?projectId=${record.id}`);
  };

  const columns: ColumnsType<HistoryItem> = [
    { title: '项目名称', dataIndex: 'project_name', ellipsis: true, render: value => value || '未命名招标项目' },
    { title: '招标单位', dataIndex: 'tender_unit', width: 120, ellipsis: true, render: value => value || '-' },
    { title: '创建时间', dataIndex: 'created_at', width: 120, render: formatShortDateTime },
    {
      title: '当前状态',
      dataIndex: 'stage',
      width: 96,
      render: (_, record) => (
        <div className="flex flex-col items-start gap-1">
          <Tag color={statusColor[record.stage as string] || 'default'}>{record.stage || record.parse_status || '已上传'}</Tag>
          {sectionProgress(record).total ? (
            <span className="text-[11px] font-semibold text-slate-400">
              正文 {sectionProgress(record).done}/{sectionProgress(record).total}
              {record.writing_partial_count ? ` · 草稿 ${record.writing_partial_count}` : ''}
              {sectionProgress(record).words ? ` · ${sectionProgress(record).words.toLocaleString('zh-CN')}字` : ''}
            </span>
          ) : null}
        </div>
      ),
    },
    {
      title: '操作',
      dataIndex: 'action',
      width: 70,
      render: (_, record) => (
        <Button type="link" onClick={() => openTask(record)}>
          {record.next_action || record.action || '查看'}
        </Button>
      ),
    },
  ];

  return (
    <section className="panel-card">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="panel-title mb-0">最近任务</h2>
        <Button type="link" onClick={() => navigate('/history')}>查看全部 &gt;</Button>
      </div>
      <Table
        rowKey="id"
        size="small"
        pagination={false}
        columns={columns}
        dataSource={recentTasks}
        loading={loading}
        className="compact-table"
        locale={{
          emptyText: loading
            ? <span className="text-xs font-semibold text-slate-500">正在加载最近任务...</span>
            : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无真实任务，上传招标文件后会显示在这里" />,
        }}
      />
    </section>
  );
}
