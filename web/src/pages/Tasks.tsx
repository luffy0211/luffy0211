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
      <div className="flex justify-between items-center">
        <div className="bg-gray-200/60 p-1 rounded-lg flex gap-1">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => { setFilter(t.key); setExpandedId(null); }}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                filter === t.key
                  ? 'bg-white text-slate-900 shadow font-semibold'
                  : 'text-gray-500 hover:text-slate-900'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setShowScrape(true)}
            className="bg-white border border-gray-200 text-slate-900 px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 flex items-center gap-2 shadow-sm"
          >
            <CloudDownload size={16} /> 新建采集任务
          </button>
          <button className="bg-slate-900 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-800 flex items-center gap-2 shadow-sm">
            <CloudUpload size={16} /> 新建上架任务
          </button>
        </div>
      </div>

      {/* Task Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead className="bg-gray-50/80 border-b border-gray-200">
            <tr>
              <th className="p-4 w-12 text-center text-gray-400 text-xs font-semibold uppercase">详情</th>
              <th className="p-4 text-xs font-semibold text-gray-500 uppercase">任务类型</th>
              <th className="p-4 text-xs font-semibold text-gray-500 uppercase">状态</th>
              <th className="p-4 text-xs font-semibold text-gray-500 uppercase">创建时间</th>
              <th className="p-4 text-xs font-semibold text-gray-500 uppercase w-[300px]">进度完成情况</th>
              <th className="p-4 text-xs font-semibold text-gray-500 uppercase w-20">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
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
              <tr><td colSpan={6} className="p-16 text-center text-gray-400">暂无任务</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Create Scrape Modal */}
      {showScrape && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-[500px] overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
              <h3 className="font-bold text-lg flex items-center gap-2">
                <CloudDownload size={20} className="text-orange-500" /> 新建采集任务
              </h3>
              <button onClick={() => setShowScrape(false)} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
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
                    className="w-full border border-gray-300 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 h-32 resize-none"
                    placeholder="每行输入一个商品URL..."
                  />
                </div>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">飞书多维表格 URL</label>
                  <input
                    value={feishuUrl}
                    onChange={(e) => setFeishuUrl(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg p-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="https://feishu.cn/base/xxxxx"
                  />
                </div>
              )}

              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-2">来源平台</label>
                  <select value={crawlSource} onChange={(e) => setCrawlSource(e.target.value)} className="w-full border border-gray-300 rounded-lg p-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="tmall">天猫</option>
                    <option value="taobao">淘宝</option>
                    <option value="3e3e">3e3e</option>
                  </select>
                </div>
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-2">执行方式</label>
                  <select value={scheduleType} onChange={(e) => setScheduleType(e.target.value)} className="w-full border border-gray-300 rounded-lg p-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="immediate">立即执行</option>
                    <option value="once">定时执行</option>
                    <option value="cron">周期执行</option>
                  </select>
                </div>
              </div>

              {scheduleType === 'once' && (
                <input type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} className="w-full border border-gray-300 rounded-lg p-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              )}
              {scheduleType === 'cron' && (
                <input value={cronExpr} onChange={(e) => setCronExpr(e.target.value)} placeholder="0 10 * * *  （每天10:00）" className="w-full border border-gray-300 rounded-lg p-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              )}
            </div>
            <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex justify-end gap-3">
              <button onClick={() => setShowScrape(false)} className="px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-100 text-gray-700">取消</button>
              <button onClick={handleCreate} className="px-4 py-2 bg-slate-900 text-white rounded-lg text-sm font-medium hover:bg-slate-800 shadow-sm">创建任务</button>
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
    pending: { label: '等待中', color: 'text-yellow-700 bg-yellow-50 border-yellow-100', icon: Loader2 },
    running: { label: '执行中', color: 'text-blue-700 bg-blue-50 border-blue-100', icon: Loader2 },
    done: { label: '已完成', color: 'text-green-700 bg-green-50 border-green-100', icon: Check },
    failed: { label: '失败', color: 'text-red-700 bg-red-50 border-red-100', icon: XCircle },
    cancelled: { label: '已取消', color: 'text-gray-500 bg-gray-50 border-gray-200', icon: X },
  };
  const st = statusMap[task.status] || statusMap.pending;
  const isRunning = task.status === 'running';
  const barColor = task.status === 'done' ? 'bg-green-500' : task.status === 'failed' ? 'bg-red-500' : 'bg-blue-500';

  return (
    <>
      <tr className="hover:bg-gray-50/50 cursor-pointer transition-colors" onClick={onToggle}>
        <td className="p-4 text-center">
          <ChevronDown size={20} className={`text-gray-400 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`} />
        </td>
        <td className="p-4">
          <span className={`px-2.5 py-1 rounded text-xs font-medium border ${task.type === 'crawl' ? 'bg-orange-50 text-orange-700 border-orange-100' : 'bg-purple-50 text-purple-700 border-purple-100'}`}>
            {task.type === 'crawl' ? '数据采集' : '批量上架'}
          </span>
        </td>
        <td className="p-4">
          <span className={`px-2.5 py-1 rounded-full text-xs font-medium border flex w-max items-center gap-1.5 ${st.color}`}>
            {isRunning ? <Loader2 size={12} className="animate-spin" /> : <st.icon size={12} />}
            {st.label}
          </span>
        </td>
        <td className="p-4 text-sm text-gray-600">{new Date(task.created_at).toLocaleString('zh-CN')}</td>
        <td className="p-4">
          <div className="flex items-center gap-3">
            <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div className={`h-full ${barColor} rounded-full transition-all`} style={{ width: `${progress}%` }} />
            </div>
            <span className="text-xs font-medium text-gray-500 w-14 text-right">{successCount} / {totalCount}</span>
          </div>
        </td>
        <td className="p-4">
          {(task.status === 'pending' || task.status === 'running') && (
            <button onClick={(e) => { e.stopPropagation(); onCancel(); }} className="text-xs text-red-500 hover:text-red-700 font-medium">取消</button>
          )}
        </td>
      </tr>
      {expanded && (
        <tr className="bg-slate-50">
          <td colSpan={6} className="p-0">
            <div className="px-14 py-4 border-b border-gray-200">
              <div className="text-xs font-semibold text-gray-500 mb-3 tracking-wider">执行日志明细</div>
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