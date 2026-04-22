import { useEffect, useState, useCallback } from 'react';
import { Search, Send, Image, ChevronLeft, ChevronRight, X, ImageIcon, Tag, Ruler, Palette, ShieldCheck, Shirt, Sparkles, Sun } from 'lucide-react';
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
        className={`fixed left-1/2 -translate-x-1/2 top-20 bg-slate-900 text-white px-5 py-3 rounded-full shadow-xl flex items-center gap-4 z-20 transition-all duration-300 ${
          selected.size > 0 ? 'opacity-100 translate-y-0' : 'opacity-0 pointer-events-none -translate-y-4'
        }`}
      >
        <span className="text-sm font-medium">已选择 {selected.size} 项商品</span>
        <div className="h-4 w-px bg-slate-700" />
        <button
          onClick={() => setShowPublish(true)}
          className="text-sm bg-white text-slate-900 px-4 py-1.5 rounded-full font-semibold hover:bg-gray-100 transition-colors flex items-center gap-1"
        >
          <Send size={14} /> 批量上架到...
        </button>
      </div>

      {/* Toolbar */}
      <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex justify-between items-center">
        <div className="flex gap-3">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-2.5 text-gray-400" />
            <input
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              placeholder="搜索商品标题..."
              className="pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm w-64 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-shadow"
            />
          </div>
          <select
            value={source}
            onChange={(e) => { setSource(e.target.value); setPage(1); }}
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:outline-none focus:border-blue-500"
          >
            {SOURCES.map((s) => <option key={s} value={s}>{s || '全部来源平台'}</option>)}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead className="bg-gray-50/80 border-b border-gray-200">
            <tr>
              <th className="p-4 w-12 text-center">
                <input type="checkbox" checked={selected.size === items.length && items.length > 0} onChange={toggleAll} className="w-4 h-4 rounded border-gray-300 text-blue-600 cursor-pointer" />
              </th>
              <th className="p-4 text-xs font-semibold text-gray-500 uppercase">图片</th>
              <th className="p-4 text-xs font-semibold text-gray-500 uppercase">商品标题</th>
              <th className="p-4 text-xs font-semibold text-gray-500 uppercase">价格</th>
              <th className="p-4 text-xs font-semibold text-gray-500 uppercase">来源</th>
              <th className="p-4 text-xs font-semibold text-gray-500 uppercase">采集时间</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {items.map((item) => (
              <tr key={item.id} className="hover:bg-gray-50/50 transition-colors cursor-pointer" onDoubleClick={() => setDetailProduct(item)}>
                <td className="p-4 text-center">
                  <input type="checkbox" checked={selected.has(item.id)} onChange={() => toggleSelect(item.id)} className="w-4 h-4 rounded border-gray-300 text-blue-600 cursor-pointer" />
                </td>
                <td className="p-4">
                  <div className="w-10 h-10 bg-gray-100 rounded-md border border-gray-200 flex items-center justify-center">
                    <Image size={16} className="text-gray-400" />
                  </div>
                </td>
                <td className="p-4 font-medium text-sm text-gray-800 max-w-md truncate">{item.title || '—'}</td>
                <td className="p-4 text-sm text-red-600 font-semibold">¥ {item.price || '—'}</td>
                <td className="p-4">
                  <span className="px-2 py-1 bg-orange-50 text-orange-600 border border-orange-100 rounded text-xs">{item.source}</span>
                </td>
                <td className="p-4 text-sm text-gray-500">{item.crawled_at ? new Date(item.crawled_at).toLocaleString('zh-CN') : '—'}</td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={6} className="p-16 text-center text-gray-400">暂无商品数据</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500">共 {total} 条</span>
          <div className="flex gap-2">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="p-2 rounded-lg border border-gray-200 disabled:opacity-30 hover:bg-gray-50">
              <ChevronLeft size={16} />
            </button>
            <span className="px-3 py-2 text-sm text-gray-600">{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(page + 1)} className="p-2 rounded-lg border border-gray-200 disabled:opacity-30 hover:bg-gray-50">
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* Product Detail Modal */}
      {detailProduct && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50" onClick={() => setDetailProduct(null)}>
          <div className="bg-white rounded-2xl shadow-2xl w-[600px] max-h-[85vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50 shrink-0">
              <h3 className="font-bold text-lg truncate pr-4">{detailProduct.title || '未命名商品'}</h3>
              <button onClick={() => setDetailProduct(null)} className="text-gray-400 hover:text-gray-600 text-xl shrink-0">✕</button>
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
                  <span className="px-2 py-0.5 bg-orange-50 text-orange-600 border border-orange-100 rounded text-xs">{detailProduct.source}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-gray-500">状态</span>
                  <span className="px-2 py-0.5 bg-blue-50 text-blue-600 border border-blue-100 rounded text-xs">{detailProduct.status}</span>
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
                <h4 className="text-sm font-semibold text-gray-700 mb-3">图片统计</h4>
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex items-center gap-3 p-3 bg-blue-50/50 border border-blue-100 rounded-lg">
                    <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                      <ImageIcon size={20} className="text-blue-600" />
                    </div>
                    <div>
                      <div className="text-xs text-gray-500">主图</div>
                      <div className="text-lg font-bold text-gray-800">{countImages(detailProduct.main_images)} <span className="text-sm font-normal text-gray-500">张</span></div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 p-3 bg-purple-50/50 border border-purple-100 rounded-lg">
                    <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
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
                <h4 className="text-sm font-semibold text-gray-700 mb-3">商品属性</h4>
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
                    <div key={label} className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg text-sm">
                      <Icon size={14} className="text-gray-400 shrink-0" />
                      <span className="text-gray-500 shrink-0">{label}</span>
                      <span className="text-gray-800 truncate">{value || '—'}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex justify-end shrink-0">
              <button onClick={() => setDetailProduct(null)} className="px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-100 text-gray-700">关闭</button>
            </div>
          </div>
        </div>
      )}

      {/* Publish Modal */}
      {showPublish && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-[500px] overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
              <h3 className="font-bold text-lg flex items-center gap-2">
                <CloudUploadIcon /> 配置上架任务
              </h3>
              <button onClick={() => setShowPublish(false)} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
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
                        className={`flex items-center gap-2 p-2.5 border rounded-lg text-sm font-medium transition-colors relative overflow-hidden ${
                          disabled
                            ? 'border-gray-100 bg-gray-50 cursor-not-allowed text-gray-400'
                            : checked
                              ? 'border-blue-200 bg-blue-50/30 cursor-pointer hover:bg-blue-50'
                              : 'border-gray-200 cursor-pointer hover:bg-gray-50'
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
                    className="w-1/2 border border-gray-300 rounded-lg p-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="immediate">立即上架</option>
                    <option value="once">定时上架</option>
                  </select>
                  {scheduleMode === 'once' && (
                    <input
                      type="datetime-local"
                      value={scheduledAt}
                      onChange={(e) => setScheduledAt(e.target.value)}
                      className="w-1/2 border border-gray-300 rounded-lg p-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-600"
                    />
                  )}
                </div>
              </div>
            </div>
            <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex justify-end gap-3">
              <button onClick={() => setShowPublish(false)} className="px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-100 text-gray-700">取消</button>
              <button
                onClick={handlePublish}
                disabled={selectedPlatforms.size === 0}
                className="px-4 py-2 bg-slate-900 text-white rounded-lg text-sm font-medium hover:bg-slate-800 shadow-sm disabled:opacity-50"
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
