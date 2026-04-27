import { useEffect, useState } from 'react';
import { CheckCircle2, XCircle, RefreshCw, QrCode, Loader2, MessageCircle, BookHeart, ShoppingBag, X, Download, WifiOff, Wifi } from 'lucide-react';
import { getPlatforms, triggerLogin, type Platform } from '../api/client';

const PLATFORM_ICONS: Record<string, typeof MessageCircle> = {
  weixin: MessageCircle,
  shipinhao: MessageCircle,
  xhs: BookHeart,
  doudian: ShoppingBag,
  taobao: ShoppingBag,
  qianniu: ShoppingBag,
};

const ICON_COLORS: Record<string, { bg: string; fg: string }> = {
  weixin: { bg: 'bg-gradient-to-br from-green-100 to-emerald-50', fg: 'text-green-600' },
  shipinhao: { bg: 'bg-gradient-to-br from-green-100 to-emerald-50', fg: 'text-green-600' },
  xhs: { bg: 'bg-gradient-to-br from-red-100 to-pink-50', fg: 'text-red-500' },
  doudian: { bg: 'bg-gradient-to-br from-slate-100 to-indigo-50', fg: 'text-[#4158d0]' },
  taobao: { bg: 'bg-gradient-to-br from-orange-100 to-pink-50', fg: 'text-orange-600' },
  qianniu: { bg: 'bg-gradient-to-br from-amber-100 to-orange-50', fg: 'text-amber-600' },
  '3e3e': { bg: 'bg-gradient-to-br from-indigo-100 to-purple-50', fg: 'text-[#4158d0]' },
};

export default function Platforms() {
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [loading, setLoading] = useState<string | null>(null);
  const [qrModal, setQrModal] = useState<Platform | null>(null);
  const [agentStatus, setAgentStatus] = useState<'checking' | 'online' | 'offline'>('checking');

  const load = async () => {
    try {
      const res = await getPlatforms();
      setPlatforms(res.data);
    } catch { /* */ }
  };

  const checkAgent = () => {
    fetch('http://localhost:8000/api/health', { signal: AbortSignal.timeout(3000) })
      .then(r => setAgentStatus(r.ok ? 'online' : 'offline'))
      .catch(() => setAgentStatus('offline'));
  };

  useEffect(() => {
    load();
    checkAgent();
  }, []);

  const handleLogin = async (p: Platform) => {
    setQrModal(p);
    setLoading(p.code);
    try {
      await triggerLogin(p.code);
    } catch { /* */ }
    setLoading(null);
    setTimeout(() => { load(); }, 8000);
  };

  return (
    <div className="space-y-6">

      {/* 本地代理状态横幅 */}
      {agentStatus === 'offline' && (
        <div className="rounded-2xl border border-amber-200 bg-gradient-to-r from-amber-50 to-orange-50 p-5">
          <div className="flex flex-col sm:flex-row sm:items-center gap-4">
            <div className="flex items-center gap-3 flex-1">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-100">
                <WifiOff size={20} className="text-amber-600" />
              </div>
              <div>
                <div className="font-bold text-amber-800">本地代理未运行</div>
                <div className="text-sm text-amber-600 mt-0.5">
                  首次使用请下载并安装本地代理，安装后开机自动运行，无需手动操作
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <a
                href="/luffy/downloads/luffy-agent.zip"
                download
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 px-4 py-2.5 text-sm font-bold text-white shadow-[0_4px_12px_rgba(245,158,11,0.35)] hover:opacity-90 transition"
              >
                <Download size={16} /> 下载本地代理
              </a>
              <button
                onClick={checkAgent}
                className="inline-flex items-center gap-1.5 rounded-xl border border-amber-200 bg-white px-3 py-2.5 text-sm text-amber-700 hover:bg-amber-50 transition"
              >
                <RefreshCw size={14} /> 重新检测
              </button>
            </div>
          </div>
          <div className="mt-3 ml-13 text-xs text-amber-500">
            安装步骤：解压 ZIP → 双击 install_windows.bat → 刷新此页面
          </div>
        </div>
      )}
      {agentStatus === 'online' && (
        <div className="flex items-center gap-2 rounded-xl border border-green-200 bg-green-50 px-4 py-2.5 text-sm text-green-700 w-fit">
          <Wifi size={15} className="text-green-500" /> 本地代理运行中
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
        {platforms.map((p) => {
          const Icon = PLATFORM_ICONS[p.code] || ShoppingBag;
          const colors = ICON_COLORS[p.code] || { bg: 'bg-gradient-to-br from-indigo-100 to-purple-50', fg: 'text-[#4158d0]' };
          const expired = !p.login_active;

          return (
            <div
              key={p.code}
              className={`dd-card relative flex flex-col overflow-hidden transition hover:-translate-y-0.5 hover:shadow-[0_14px_34px_rgba(65,88,208,0.12)] ${
                expired ? 'border-red-200' : ''
              }`}
            >
              {expired && (
                <div className="absolute right-0 top-0 rounded-bl-lg bg-red-500 px-3 py-1 text-[10px] font-bold text-white shadow">
                  未登录
                </div>
              )}

              <div className="flex items-center gap-3 border-b border-[rgba(199,210,254,0.55)] bg-gradient-to-r from-[rgba(65,88,208,0.06)] to-[rgba(200,80,192,0.05)] p-5">
                <div className={`flex h-12 w-12 items-center justify-center rounded-2xl ${colors.bg}`}>
                  <Icon size={24} className={colors.fg} />
                </div>
                <div className="text-lg font-black text-neutral-800">{p.name}</div>
              </div>

              <div className="p-5 flex-1 space-y-4">
                <div>
                  <div className="text-xs text-gray-400 mb-1">当前状态</div>
                  {p.login_active ? (
                    <span className="dd-badge dd-badge-success w-max">
                      <CheckCircle2 size={12} /> 授权有效
                    </span>
                  ) : (
                    <span className="dd-badge dd-badge-danger w-max">
                      <XCircle size={12} /> 登录已过期
                    </span>
                  )}
                </div>
                <div>
                  <div className="text-xs text-gray-400 mb-1">上次授权时间</div>
                  <div className="text-sm font-medium text-gray-700">
                    {p.last_login ? new Date(p.last_login).toLocaleString('zh-CN') : '从未登录'}
                  </div>
                </div>
              </div>

              <div className="p-5 pt-0 mt-auto">
                {p.login_active ? (
                  <button
                    onClick={() => handleLogin(p)}
                    className="dd-button-soft w-full gap-2"
                  >
                    <RefreshCw size={16} /> 重新授权
                  </button>
                ) : (
                  <button
                    onClick={() => handleLogin(p)}
                    className="dd-button w-full gap-2"
                  >
                    <QrCode size={16} /> 扫码登录
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* QR Code Login Modal */}
      {qrModal && (
        <div className="dd-overlay fixed inset-0 z-50 flex items-center justify-center">
          <div className="dd-modal relative w-[400px] overflow-hidden">
            <div className="absolute top-4 right-4">
              <button onClick={() => setQrModal(null)} className="dd-close-button">
                <X size={20} />
              </button>
            </div>
            <div className="p-8 pt-10 flex flex-col items-center">
              <div className={`w-12 h-12 ${ICON_COLORS[qrModal.code]?.bg || 'bg-gradient-to-br from-indigo-100 to-purple-50'} rounded-full flex items-center justify-center mb-4`}>
                {(() => { const I = PLATFORM_ICONS[qrModal.code] || ShoppingBag; return <I size={24} className={ICON_COLORS[qrModal.code]?.fg || 'text-[#4158d0]'} />; })()}
              </div>
              <h3 className="font-bold text-xl mb-1">登录 {qrModal.name}</h3>
              <p className="text-sm text-gray-500 mb-6 text-center">请在弹出的浏览器窗口中完成扫码登录</p>

              <div className="mb-6 flex h-48 w-48 flex-col items-center justify-center rounded-2xl border-2 border-dashed border-[rgba(199,210,254,0.9)] bg-gradient-to-br from-white to-[#f6f4ff]">
                <QrCode size={40} className="mb-2 text-[#756aff]/45" />
                <span className="text-xs text-gray-400">浏览器已弹出...</span>
              </div>

              <div className="dd-badge dd-badge-info flex items-center gap-2 px-4 py-2 text-sm">
                {loading === qrModal.code ? (
                  <><Loader2 size={16} className="animate-spin" /> 等待扫码确认...</>
                ) : (
                  <><CheckCircle2 size={16} /> 登录流程已启动</>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
