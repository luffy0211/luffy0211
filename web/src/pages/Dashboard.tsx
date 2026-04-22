import { useEffect, useState } from 'react';
import { Package, CloudDownload, CloudUpload, Clock, Activity, ShieldCheck, CheckCircle2, XCircle, Loader2, MessageCircle, BookHeart, ShoppingBag, AlertTriangle, X as XIcon } from 'lucide-react';
import { getPlatforms, getDashboardStats, getRecentActivities, type Platform, type RecentTask } from '../api/client';

export default function Dashboard() {
  const [stats, setStats] = useState({ totalProducts: 0, todayCrawl: 0, todayUpload: 0, pendingTasks: 0 });
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [activities, setActivities] = useState<RecentTask[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [statsRes, plRes, actRes] = await Promise.all([
          getDashboardStats(),
          getPlatforms(),
          getRecentActivities(),
        ]);
        setStats({
          totalProducts: statsRes.data.total_products,
          todayCrawl: statsRes.data.today_crawl,
          todayUpload: statsRes.data.today_upload,
          pendingTasks: statsRes.data.pending_tasks,
        });
        setPlatforms(plRes.data);
        setActivities(actRes.data);
      } catch { /* API not ready */ }
    })();
  }, []);

  const cards = [
    { label: '商品总数', value: stats.totalProducts, icon: Package },
    { label: '今日采集', value: stats.todayCrawl, icon: CloudDownload },
    { label: '今日上架', value: stats.todayUpload, icon: CloudUpload },
    { label: '待处理任务', value: stats.pendingTasks, icon: Clock, highlight: true },
  ];

  const platformIcons: Record<string, typeof MessageCircle> = {
    weixin: MessageCircle,
    shipinhao: MessageCircle,
    xhs: BookHeart,
    doudian: ShoppingBag,
    taobao: ShoppingBag,
    qianniu: ShoppingBag,
    '3e3e': ShoppingBag,
  };

  const allErrors = activities.flatMap((a) =>
    a.errors.map((msg) => ({ taskId: a.id, type: a.type, time: a.created_at, msg }))
  );

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {cards.map((c) => (
          <div
            key={c.label}
            className={`p-5 rounded-xl border shadow-sm hover:shadow transition-shadow ${
              c.highlight ? 'bg-blue-50/80 border-blue-200' : 'bg-white border-gray-200'
            }`}
          >
            <div className={`flex justify-between items-center mb-2 ${c.highlight ? 'text-blue-600' : 'text-gray-500'}`}>
              <span className="text-sm font-medium">{c.label}</span>
              <c.icon size={16} />
            </div>
            <div className={`text-2xl font-bold ${c.highlight ? 'text-blue-700' : ''}`}>{c.value}</div>
            {c.highlight && stats.pendingTasks > 0 && (
              <div className="text-xs mt-1 flex items-center gap-1 text-blue-600">
                <Loader2 size={12} className="animate-spin" /> 后台排队执行中
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Error Banner */}
      {allErrors.length > 0 && (
        <ErrorBanner errors={allErrors} />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Timeline — real data */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm lg:col-span-2 flex flex-col">
          <div className="p-5 border-b border-gray-100 font-semibold flex items-center gap-2">
            <Activity size={16} className="text-gray-400" /> 近期任务活动
          </div>
          <div className="p-6 ml-3 border-l-2 border-gray-100 relative space-y-7 flex-1">
            {activities.length === 0 && (
              <div className="text-sm text-gray-400 pl-6">暂无任务记录</div>
            )}
            {activities.map((a) => {
              const isRunning = a.status === 'running' || a.status === 'pending';
              const isFailed = a.status === 'failed';
              const color = isRunning ? 'bg-blue-500' : isFailed ? 'bg-red-500' : a.failed_items > 0 ? 'bg-yellow-500' : 'bg-green-500';
              const typeLabel = a.type === 'crawl' ? '数据采集' : '批量上架';
              const timeStr = formatTime(a.finished_at || a.started_at || a.created_at);
              const hasErrors = a.errors.length > 0;
              const isExpanded = expandedId === a.id;

              return (
                <TimelineItem
                  key={a.id}
                  time={timeStr}
                  color={color}
                  pulse={isRunning}
                  clickable={hasErrors}
                  onClick={() => setExpandedId(isExpanded ? null : a.id)}
                >
                  <span className="font-medium">{typeLabel}</span>任务
                  {a.status === 'running' && '，正在执行中...'}
                  {a.status === 'pending' && '，等待执行...'}
                  {a.status === 'done' && (
                    <span className={`ml-1 px-1.5 rounded text-xs ${a.failed_items > 0 ? 'text-yellow-700 bg-yellow-50' : 'text-green-600 bg-green-50'}`}>
                      (成功 {a.success_items} / 失败 {a.failed_items})
                    </span>
                  )}
                  {a.status === 'failed' && (
                    <span className="ml-1 text-red-600 text-xs bg-red-50 px-1.5 rounded">执行失败</span>
                  )}
                  {a.status === 'cancelled' && (
                    <span className="ml-1 text-gray-500 text-xs bg-gray-100 px-1.5 rounded">已取消</span>
                  )}
                  {hasErrors && !isExpanded && (
                    <span className="ml-1 text-red-500 text-xs cursor-pointer hover:underline">({a.errors.length} 条错误，点击查看)</span>
                  )}
                  {hasErrors && isExpanded && (
                    <div className="mt-1.5 space-y-1">
                      {a.errors.map((err, i) => (
                        <div key={i} className="text-xs text-red-500 bg-red-50 border border-red-100 rounded px-2 py-1 flex items-start gap-1.5">
                          <XCircle size={12} className="shrink-0 mt-0.5" /> <span className="break-all">{err}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </TimelineItem>
              );
            })}
          </div>
        </div>

        {/* Platform status */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
          <div className="p-5 border-b border-gray-100 font-semibold flex items-center gap-2">
            <ShieldCheck size={16} className="text-gray-400" /> 各平台状态一览
          </div>
          <div className="p-5 space-y-5">
            {platforms.map((p) => {
              const Icon = platformIcons[p.code] || ShoppingBag;
              return (
                <div key={p.code} className="flex items-center justify-between">
                  <span className="text-sm font-medium flex items-center gap-2">
                    <div className={`w-6 h-6 rounded flex items-center justify-center ${p.login_active ? 'bg-green-100' : 'bg-red-50'}`}>
                      <Icon size={14} className={p.login_active ? 'text-green-600' : 'text-red-500'} />
                    </div>
                    {p.name}
                  </span>
                  {p.login_active ? (
                    <span className="px-2 py-1 bg-green-50 border border-green-100 text-green-700 rounded text-[11px] font-medium flex items-center gap-1">
                      <CheckCircle2 size={12} /> 已登录
                    </span>
                  ) : (
                    <span className="px-2 py-1 bg-red-50 border border-red-100 text-red-600 rounded text-[11px] font-medium flex items-center gap-1">
                      <XCircle size={12} /> 未登录
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function TimelineItem({ time, color, pulse, clickable, onClick, children }: { time: string; color: string; pulse: boolean; clickable?: boolean; onClick?: () => void; children: React.ReactNode }) {
  return (
    <div className={`pl-6 relative ${clickable ? 'cursor-pointer' : ''}`} onClick={clickable ? onClick : undefined}>
      <span className={`absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full ${color} ring-4 ring-white ${pulse ? 'animate-pulse' : ''}`} />
      <div className="text-sm font-medium text-gray-400 mb-1">{time}</div>
      <div className="text-sm text-gray-700">{children}</div>
    </div>
  );
}

function ErrorBanner({ errors }: { errors: { taskId: number; type: string; time: string; msg: string }[] }) {
  const [collapsed, setCollapsed] = useState(false);
  if (collapsed) return null;

  return (
    <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 relative flex items-center justify-between">
      <div className="flex items-center gap-2 text-red-700 font-semibold text-sm">
        <AlertTriangle size={16} /> 最近任务中有 {errors.length} 条错误
      </div>
      <button onClick={() => setCollapsed(true)} className="text-red-300 hover:text-red-500">
        <XIcon size={16} />
      </button>
    </div>
  );
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  const hhmm = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  if (isToday) return `今天 ${hhmm}`;
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) return `昨天 ${hhmm}`;
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) + ' ' + hhmm;
}
