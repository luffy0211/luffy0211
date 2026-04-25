import { useEffect, useState, useCallback } from 'react';
import { Search, Send, Image, ChevronLeft, ChevronRight, ImageIcon, Tag, Ruler, Palette, ShieldCheck, Shirt, Sparkles, Sun } from 'lucide-react';
import { getProducts, createUploadTask, getPlatforms, type Product, type Platform } from '../api/client';

const SOURCES = ['', 'tmall', '3e3e', 'taobao'];

export default function Products() {
  const [items, setItems] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [source, setSource] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [showPublish, setShowPublish] = useState(false);
  const [detailProduct, setDetailProduct] = useState<Product | null>(null);
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [selectedPlatforms, setSelectedPlatforms] = useState<Set<string>>(new Set());
  const [scheduleMode, setScheduleMode] = useState('immediate');
  const [scheduledAt, setScheduledAt] = useState('');

  const pageSize = 20;

  const load = useCallback(async () => {
    try {
      const res = await getProducts({ page, page_size: pageSize, search, source });
      setItems(res.data.items);
      setTotal(res.data.total);
    } catch { /* */ }
  }, [page, search, source]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    getPlatforms().then((r) => setPlatforms(r.data)).catch(() => {});
  }, []);

  const toggleSelect = (id: number) => {
    setSelected((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  };
  const toggleAll = () => {
    setSelected(selected.size === items.length ? new Set() : new Set(items.map((i) => i.id)));
  };

  const handlePublish = async () => {
    if (selected.size === 0 || selectedPlatforms.size === 0) return;
    await createUploadTask({
      product_ids: Array.from(selected),
      platforms: Array.from(selectedPlatforms),
      schedule_type: scheduleMode,
      ...(scheduleMode === 'once' ? { scheduled_at: scheduledAt } : {}),
    });
    setShowPublish(false);
    setSelected(new Set());
    setSelectedPlatforms(new Set());
    alert('上架任务已创建！');
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-4 relative">
      {/* Floating batch action bar */}
      <div
        className={`fixed left-1/2 top-20 z-20 flex -translate-x-1/2 items-center gap-4 rounded-full border border-[rgba(199,210,254,0.7)] bg-white/90 px-5 py-3 text-neutral-800 shadow-[0_16px_42px_rgba(65,88,208,0.16)] backdrop-blur transition-all duration-300 ${
          selected.size > 0 ? 'translate-y-0 opacity-100' : 'pointer-events-none -translate-y-4 opacity-0'
        }`}
      >
        <span className="text-sm font-semibold">已选择 {selected.size} 项商品</span>
        <div className="h-4 w-px bg-indigo-100" />
        <button
          onClick={() => setShowPublish(true)}
          className="dd-button gap-1 transition-colors"
        >
          <Send size={14} /> 批量上架到...
        </button>
      </div>

      {/* Toolbar */}
      <div className="dd-panel flex items-center justify-between p-4">
        <div className="flex gap-3">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-3 text-neutral-400" />
            <input
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              placeholder="搜索商品标题..."
              className="dd-input w-72 py-2 pl-9 pr-4 text-sm"
            />
          </div>
          <select
            value={source}
            onChange={(e) => { setSource(e.target.value); setPage(1); }}
            className="dd-select px-4 text-sm"
          >
            {SOURCES.map((s) => <option key={s} value={s}>{s || '全部来源平台'}</option>)}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="dd-table">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr>
              <th className="p-4 w-12 text-center">
                <input type="checkbox" checked={selected.size === items.length && items.length > 0} onChange={toggleAll} className="w-4 h-4 rounded border-gray-300 text-blue-600 cursor-pointer" />
              </th>
              <th className="p-4 text-xs font-extrabold text-neutral-500 uppercase">图片</th>
              <th className="p-4 text-xs font-extrabold text-neutral-500 uppercase">商品标题</th>
              <th className="p-4 text-xs font-extrabold text-neutral-500 uppercase">价格</th>
              <th className="p-4 text-xs font-extrabold text-neutral-500 uppercase">来源</th>
              <th className="p-4 text-xs font-extrabold text-neutral-500 uppercase">采集时间</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="cursor-pointer" onDoubleClick={() => setDetailProduct(item)}>
                <td className="p-4 text-center">
                  <input type="checkbox" checked={selected.has(item.id)} onChange={() => toggleSelect(item.id)} className="w-4 h-4 rounded border-gray-300 text-blue-600 cursor-pointer" />
                </td>
                <td className="p-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-[rgba(199,210,254,0.65)] bg-gradient-to-br from-white to-[#f6f4ff]">
                    <Image size={16} className="text-[#756aff]" />
                  </div>
                </td>
                <td className="p-4 max-w-md truncate text-sm font-semibold text-neutral-800">{item.title || '—'}</td>
                <td className="p-4 text-sm font-bold text-red-600">¥ {item.price || '—'}</td>
                <td className="p-4">
                  <span className="dd-badge dd-badge-warning">{item.source}</span>
                </td>
                <td className="p-4 text-sm text-gray-500">{item.crawled_at ? new Date(item.crawled_at).toLocaleString('zh-CN') : '—'}</td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={6} className="p-8"><div className="dd-empty p-10 text-center text-sm">暂无商品数据</div></td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-neutral-500">共 {total} 条</span>
          <div className="flex gap-2">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="dd-button-soft dd-icon-button disabled:opacity-30">
              <ChevronLeft size={16} />
            </button>
            <span className="inline-flex h-11 min-w-[88px] items-center justify-center rounded-full border border-[rgba(199,210,254,0.68)] bg-white/75 px-4 text-sm font-bold text-neutral-600">{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(page + 1)} className="dd-button-soft dd-icon-button disabled:opacity-30">
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* Product Detail Modal */}
      {detailProduct && (
        <div className="dd-overlay fixed inset-0 z-50 flex items-center justify-center" onClick={() => setDetailProduct(null)}>
          <div className="dd-modal flex max-h-[85vh] w-[600px] flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex shrink-0 items-center justify-between border-b border-[rgba(199,210,254,0.55)] bg-gradient-to-r from-[rgba(65,88,208,0.07)] to-[rgba(200,80,192,0.06)] px-6 py-4">
              <h3 className="font-bold text-lg truncate pr-4">{detailProduct.title || '未命名商品'}</h3>
              <button onClick={() => setDetailProduct(null)} className="dd-close-button shrink-0">✕</button>
            </div>
            <div className="p-6 space-y-5 overflow-y-auto">
              {/* 基本信息 */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-gray-500">价格</span>
                  <span className="text-red-600 font-semibold text-base">¥ {detailProduct.price || '—'}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-gray-500">来源</span>
                  <span className="dd-badge dd-badge-warning py-0.5">{detailProduct.source}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-gray-500">状态</span>
                  <span className="dd-badge dd-badge-info py-0.5">{detailProduct.status}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-gray-500">采集时间</span>
                  <span className="text-gray-700">{detailProduct.crawled_at ? new Date(detailProduct.crawled_at).toLocaleString('zh-CN') : '—'}</span>
                </div>
              </div>
              {detailProduct.url && (
                <div className="text-sm">
                  <span className="text-gray-500 mr-2">商品链接</span>
                  <a href={detailProduct.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline break-all">{detailProduct.url.length > 80 ? detailProduct.url.slice(0, 80) + '...' : detailProduct.url}</a>
                </div>
              )}

              {/* 图片统计 */}
              <div>
                <h4 className="mb-3 text-sm font-bold text-neutral-700">图片统计</h4>
                <div className="grid grid-cols-2 gap-3">
                  <div className="dd-card flex items-center gap-3 p-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[rgba(65,88,208,0.14)] to-[rgba(200,80,192,0.14)]">
                      <ImageIcon size={20} className="text-blue-600" />
                    </div>
                    <div>
                      <div className="text-xs text-gray-500">主图</div>
                      <div className="text-lg font-bold text-gray-800">{countImages(detailProduct.main_images)} <span className="text-sm font-normal text-gray-500">张</span></div>
                    </div>
                  </div>
                  <div className="dd-card flex items-center gap-3 p-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[rgba(65,88,208,0.14)] to-[rgba(200,80,192,0.14)]">
                      <Palette size={20} className="text-purple-600" />
                    </div>
                    <div>
                      <div className="text-xs text-gray-500">SKU图</div>
                      <div className="text-lg font-bold text-gray-800">{countImages(detailProduct.sku_images)} <span className="text-sm font-normal text-gray-500">张</span></div>
                    </div>
                  </div>
                </div>
              </div>

              {/* 商品属性 */}
              <div>
                <h4 className="mb-3 text-sm font-bold text-neutral-700">商品属性</h4>
                <div className="grid grid-cols-2 gap-2">
                  {([
                    { icon: Sparkles, label: '风格', value: detailProduct.style },
                    { icon: Palette, label: '颜色分类', value: detailProduct.color },
                    { icon: Sun, label: '适用季节', value: detailProduct.season },
                    { icon: Shirt, label: '面料', value: detailProduct.fabric },
                    { icon: Tag, label: '材质成分', value: detailProduct.material },
                    { icon: ShieldCheck, label: '安全等级', value: detailProduct.safety_level },
                    { icon: Ruler, label: '身高', value: detailProduct.height },
                    { icon: Tag, label: '适用性别', value: detailProduct.gender },
                  ] as const).map(({ icon: Icon, label, value }) => (
                    <div key={label} className="flex items-center gap-2 rounded-xl border border-[rgba(199,210,254,0.45)] bg-white/70 p-2 text-sm">
                      <Icon size={14} className="shrink-0 text-[#756aff]" />
                      <span className="text-gray-500 shrink-0">{label}</span>
                      <span className="text-gray-800 truncate">{value || '—'}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex shrink-0 justify-end border-t border-[rgba(199,210,254,0.55)] bg-white/70 px-6 py-4">
              <button onClick={() => setDetailProduct(null)} className="dd-button-soft">关闭</button>
            </div>
          </div>
        </div>
      )}

      {/* Publish Modal */}
      {showPublish && (
        <div className="dd-overlay fixed inset-0 z-50 flex items-center justify-center">
          <div className="dd-modal w-[500px] overflow-hidden">
            <div className="flex items-center justify-between border-b border-[rgba(199,210,254,0.55)] bg-gradient-to-r from-[rgba(65,88,208,0.07)] to-[rgba(200,80,192,0.06)] px-6 py-4">
              <h3 className="font-bold text-lg flex items-center gap-2">
                <CloudUploadIcon /> 配置上架任务
              </h3>
              <button onClick={() => setShowPublish(false)} className="dd-close-button">✕</button>
            </div>
            <div className="p-6 space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">目标分发平台 (多选)</label>
                <div className="grid grid-cols-2 gap-3">
                  {platforms.map((p) => {
                    const disabled = !p.login_active;
                    const checked = selectedPlatforms.has(p.code);
                    return (
                      <label
                        key={p.code}
                        className={`relative flex items-center gap-2 overflow-hidden rounded-2xl border p-3 text-sm font-semibold transition-colors ${
                          disabled
                            ? 'cursor-not-allowed border-[rgba(203,213,225,0.7)] bg-slate-50/70 text-slate-400'
                            : checked
                              ? 'cursor-pointer border-[rgba(117,106,255,0.5)] bg-[rgba(117,106,255,0.08)] text-[#4158d0] hover:bg-[rgba(117,106,255,0.12)]'
                              : 'cursor-pointer border-[rgba(199,210,254,0.75)] bg-white/80 hover:bg-[rgba(65,88,208,0.04)]'
                        }`}
                      >
                        <input
                          type="checkbox"
                          disabled={disabled}
                          checked={checked}
                          onChange={() => {
                            if (disabled) return;
                            setSelectedPlatforms((prev) => { const n = new Set(prev); n.has(p.code) ? n.delete(p.code) : n.add(p.code); return n; });
                          }}
                          className="w-4 h-4 rounded text-blue-600"
                        />
                        {p.name}
                        {disabled && (
                          <span className="absolute right-0 top-0 bottom-0 bg-red-100 text-red-600 text-xs px-2 flex items-center font-bold">未登录</span>
                        )}
                      </label>
                    );
                  })}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">执行调度</label>
                <div className="flex gap-3">
                  <select
                    value={scheduleMode}
                    onChange={(e) => setScheduleMode(e.target.value)}
                    className="dd-select w-1/2 px-4 text-sm"
                  >
                    <option value="immediate">立即上架</option>
                    <option value="once">定时上架</option>
                  </select>
                  {scheduleMode === 'once' && (
                    <input
                      type="datetime-local"
                      value={scheduledAt}
                      onChange={(e) => setScheduledAt(e.target.value)}
                      className="dd-input w-1/2 px-4 text-sm text-gray-600"
                    />
                  )}
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 border-t border-[rgba(199,210,254,0.55)] bg-white/70 px-6 py-4">
              <button onClick={() => setShowPublish(false)} className="dd-button-soft">取消</button>
              <button
                onClick={handlePublish}
                disabled={selectedPlatforms.size === 0}
                className="dd-button disabled:opacity-50"
              >
                确认上架
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function countImages(imagesStr: string): number {
  if (!imagesStr || !imagesStr.trim()) return 0;
  return imagesStr.split(';').filter(s => s.trim()).length;
}

function CloudUploadIcon() {
  return <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-purple-500"><path d="M12 13v8"/><path d="m4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="m8 17 4-4 4 4"/></svg>;
}
