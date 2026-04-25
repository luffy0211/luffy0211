import { useEffect, useState, useCallback } from 'react';
import { CloudDownload, CloudUpload, ChevronDown, CheckCircle2, XCircle, Loader2, Check, X } from 'lucide-react';
import { getTasks, createCrawlTask, cancelTask, type Task } from '../api/client';

type FilterType = 'all' | 'crawl' | 'upload';

export default function Tasks() {
  const [items, setItems] = useState<Task[]>([]);
  const [filter, setFilter] = useState<FilterType>('all');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [showScrape, setShowScrape] = useState(false);
  const [dataSource, setDataSource] = useState<'manual' | 'feishu'>('manual');
  const [urlText, setUrlText] = useState('');
  const [feishuUrl, setFeishuUrl] = useState('');
  const [crawlSource, setCrawlSource] = useState('tmall');
  const [scheduleType, setScheduleType] = useState('immediate');
  const [scheduledAt, setScheduledAt] = useState('');
  const [cronExpr, setCronExpr] = useState('');

  const load = useCallback(async () => {
    try {
      const params: Record<string, unknown> = { page_size: 50 };
      if (filter !== 'all') params.type = filter;
      const res = await getTasks(params);
      setItems(res.data.items);
    } catch { /* */ }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const hasRunning = items.some((t) => t.status === 'running' || t.status === 'pending');
    if (!hasRunning) return;
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [items, load]);

  const handleCreate = async () => {
    let urls: string[] = [];
    if (dataSource === 'manual') {
      urls = urlText.split('\n').map((u) => u.trim()).filter((u) => u.startsWith('http'));
    } else {
      urls = [feishuUrl.trim()].filter(Boolean);
    }
    if (urls.length === 0) return alert('请输入至少一个有效 URL');

    await createCrawlTask({
      urls,
      source: crawlSource,
      schedule_type: scheduleType,
      ...(scheduleType === 'once' && scheduledAt ? { scheduled_at: scheduledAt } : {}),
    });
    setShowScrape(false);
    setUrlText('');
    setFeishuUrl('');
    load();
  };

  const handleCancel = async (id: number) => {
    if (!confirm('确认取消此任务？')) return;
    await cancelTask(id);
    load();
  };

  const tabs: { key: FilterType; label: string }[] = [
    { key: 'all', label: '全部任务' },
    { key: 'crawl', label: '采集任务' },
    { key: 'upload', label: '上架任务' },
  ];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="dd-tabs">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => { setFilter(t.key); setExpandedId(null); }}
              className={`dd-nav-button ${filter === t.key ? 'dd-tab-active' : ''}`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setShowScrape(true)}
            className="dd-button-soft gap-2"
          >
            <CloudDownload size={16} /> 新建采集任务
          </button>
          <button className="dd-button gap-2">
            <CloudUpload size={16} /> 新建上架任务
          </button>
        </div>
      </div>

      {/* Task Table */}
      <div className="dd-table">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr>
              <th className="p-4 w-16 whitespace-nowrap text-center text-[#756aff]/60 text-xs font-extrabold uppercase">详情</th>
              <th className="p-4 text-xs font-extrabold text-neutral-500 uppercase">任务类型</th>
              <th className="p-4 text-xs font-extrabold text-neutral-500 uppercase">状态</th>
              <th className="p-4 text-xs font-extrabold text-neutral-500 uppercase">创建时间</th>
              <th className="p-4 text-xs font-extrabold text-neutral-500 uppercase w-[300px]">进度完成情况</th>
              <th className="p-4 text-xs font-extrabold text-neutral-500 uppercase w-20">操作</th>
            </tr>
          </thead>
          <tbody>
            {items.map((task) => {
              const expanded = expandedId === task.id;
              const successCount = task.items.filter((i) => i.status === 'success').length;
              const totalCount = task.items.length;
              const progress = totalCount > 0 ? Math.round((successCount / totalCount) * 100) : 0;

              return (
                <TaskRow
                  key={task.id}
                  task={task}
                  expanded={expanded}
                  progress={progress}
                  successCount={successCount}
                  totalCount={totalCount}
                  onToggle={() => setExpandedId(expanded ? null : task.id)}
                  onCancel={() => handleCancel(task.id)}
                />
              );
            })}
            {items.length === 0 && (
              <tr><td colSpan={6} className="p-8"><div className="dd-empty p-10 text-center text-sm">暂无任务</div></td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Create Scrape Modal */}
      {showScrape && (
        <div className="dd-overlay fixed inset-0 z-50 flex items-center justify-center">
          <div className="dd-modal w-[500px] overflow-hidden">
            <div className="flex items-center justify-between border-b border-[rgba(199,210,254,0.55)] bg-gradient-to-r from-[rgba(65,88,208,0.07)] to-[rgba(200,80,192,0.06)] px-6 py-4">
              <h3 className="font-bold text-lg flex items-center gap-2">
                <CloudDownload size={20} className="text-orange-500" /> 新建采集任务
              </h3>
              <button onClick={() => setShowScrape(false)} className="dd-close-button">✕</button>
            </div>
            <div className="p-6 space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">选择数据源</label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 cursor-pointer text-sm">
                    <input type="radio" checked={dataSource === 'manual'} onChange={() => setDataSource('manual')} className="w-4 h-4 text-blue-600" /> 手动输入链接
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer text-sm">
                    <input type="radio" checked={dataSource === 'feishu'} onChange={() => setDataSource('feishu')} className="w-4 h-4 text-blue-600" /> 飞书多维表格
                  </label>
                </div>
              </div>

              {dataSource === 'manual' ? (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">商品链接</label>
                  <textarea
                    value={urlText}
                    onChange={(e) => setUrlText(e.target.value)}
                    className="dd-input h-32 w-full resize-none rounded-2xl p-3 text-sm"
                    placeholder="每行输入一个商品URL..."
                  />
                </div>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">飞书多维表格 URL</label>
                  <input
                    value={feishuUrl}
                    onChange={(e) => setFeishuUrl(e.target.value)}
                    className="dd-input w-full px-4 text-sm"
                    placeholder="https://feishu.cn/base/xxxxx"
                  />
                </div>
              )}

              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-2">来源平台</label>
                  <select value={crawlSource} onChange={(e) => setCrawlSource(e.target.value)} className="dd-select w-full px-4 text-sm">
                    <option value="tmall">天猫</option>
                    <option value="taobao">淘宝</option>
                    <option value="3e3e">3e3e</option>
                  </select>
                </div>
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-2">执行方式</label>
                  <select value={scheduleType} onChange={(e) => setScheduleType(e.target.value)} className="dd-select w-full px-4 text-sm">
                    <option value="immediate">立即执行</option>
                    <option value="once">定时执行</option>
                    <option value="cron">周期执行</option>
                  </select>
                </div>
              </div>

              {scheduleType === 'once' && (
                <input type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} className="dd-input w-full px-4 text-sm" />
              )}
              {scheduleType === 'cron' && (
                <input value={cronExpr} onChange={(e) => setCronExpr(e.target.value)} placeholder="0 10 * * *  （每天10:00）" className="dd-input w-full px-4 text-sm" />
              )}
            </div>
            <div className="flex justify-end gap-3 border-t border-[rgba(199,210,254,0.55)] bg-white/70 px-6 py-4">
              <button onClick={() => setShowScrape(false)} className="dd-button-soft">取消</button>
              <button onClick={handleCreate} className="dd-button">创建任务</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TaskRow({ task, expanded, progress, successCount, totalCount, onToggle, onCancel }: {
  task: Task; expanded: boolean; progress: number; successCount: number; totalCount: number;
  onToggle: () => void; onCancel: () => void;
}) {
  const statusMap: Record<string, { label: string; color: string; icon: typeof Check }> = {
    pending: { label: '等待中', color: 'dd-badge-warning', icon: Loader2 },
    running: { label: '执行中', color: 'dd-badge-info', icon: Loader2 },
    done: { label: '已完成', color: 'dd-badge-success', icon: Check },
    failed: { label: '失败', color: 'dd-badge-danger', icon: XCircle },
    cancelled: { label: '已取消', color: 'dd-badge-muted', icon: X },
  };
  const st = statusMap[task.status] || statusMap.pending;
  const isRunning = task.status === 'running';
  const barColor = task.status === 'done' ? 'bg-green-500' : task.status === 'failed' ? 'bg-red-500' : 'bg-blue-500';

  return (
    <>
      <tr className="cursor-pointer" onClick={onToggle}>
        <td className="p-4 text-center">
          <ChevronDown size={20} className={`text-[#756aff]/65 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`} />
        </td>
        <td className="p-4">
          <span className={`dd-badge ${task.type === 'crawl' ? 'dd-badge-warning' : 'dd-badge-gradient'}`}>
            {task.type === 'crawl' ? '数据采集' : '批量上架'}
          </span>
        </td>
        <td className="p-4">
          <span className={`dd-badge flex w-max items-center gap-1.5 ${st.color}`}>
            {isRunning ? <Loader2 size={12} className="animate-spin" /> : <st.icon size={12} />}
            {st.label}
          </span>
        </td>
        <td className="p-4 text-sm font-medium text-neutral-600">{new Date(task.created_at).toLocaleString('zh-CN')}</td>
        <td className="p-4">
          <div className="flex items-center gap-3">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-[rgba(199,210,254,0.45)]">
              <div className={`h-full ${barColor} rounded-full transition-all`} style={{ width: `${progress}%` }} />
            </div>
            <span className="w-14 text-right text-xs font-semibold text-neutral-500">{successCount} / {totalCount}</span>
          </div>
        </td>
        <td className="p-4">
          {(task.status === 'pending' || task.status === 'running') && (
            <button onClick={(e) => { e.stopPropagation(); onCancel(); }} className="dd-button-soft !h-8 !min-h-8 !min-w-[64px] !px-3 text-xs !text-red-500 hover:!text-red-700">取消</button>
          )}
        </td>
      </tr>
      {expanded && (
        <tr className="bg-[rgba(246,244,255,0.72)]">
          <td colSpan={6} className="p-0">
            <div className="border-b border-[rgba(199,210,254,0.55)] px-14 py-4">
              <div className="mb-3 text-xs font-extrabold tracking-wider text-neutral-500">执行日志明细</div>
              <div className="space-y-2 text-sm">
                {task.items.map((item) => (
                  <div key={item.id} className="flex items-center gap-2 text-gray-700">
                    {item.status === 'success' ? <CheckCircle2 size={16} className="text-green-500" /> : item.status === 'failed' ? <XCircle size={16} className="text-red-500" /> : <Loader2 size={16} className="text-gray-400 animate-spin" />}
                    {item.url || `商品#${item.product_id}`}
                    {item.platform && ` → ${item.platform}`}
                    {item.status === 'success' && <span className="text-green-600 text-xs">— 成功</span>}
                    {item.status === 'failed' && <span className="text-red-500 text-xs bg-red-50 px-1 rounded border border-red-100">失败: {item.error_msg}</span>}
                  </div>
                ))}
                {task.items.length === 0 && <div className="text-gray-400">暂无明细</div>}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}