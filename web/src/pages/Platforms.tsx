import { useEffect, useState } from 'react';
import { CheckCircle2, XCircle, RefreshCw, QrCode, Loader2, MessageCircle, BookHeart, ShoppingBag, X } from 'lucide-react';
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
  weixin: { bg: 'bg-green-100', fg: 'text-green-600' },
  shipinhao: { bg: 'bg-green-100', fg: 'text-green-600' },
  xhs: { bg: 'bg-red-50', fg: 'text-red-500' },
  doudian: { bg: 'bg-slate-100', fg: 'text-slate-600' },
  taobao: { bg: 'bg-orange-100', fg: 'text-orange-600' },
  qianniu: { bg: 'bg-amber-100', fg: 'text-amber-600' },
  '3e3e': { bg: 'bg-indigo-100', fg: 'text-indigo-600' },
};

export default function Platforms() {
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [loading, setLoading] = useState<string | null>(null);
  const [qrModal, setQrModal] = useState<Platform | null>(null);

  const load = async () => {
    try {
      const res = await getPlatforms();
      setPlatforms(res.data);
    } catch { /* */ }
  };

  useEffect(() => { load(); }, []);

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
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
        {platforms.map((p) => {
          const Icon = PLATFORM_ICONS[p.code] || ShoppingBag;
          const colors = ICON_COLORS[p.code] || { bg: 'bg-gray-100', fg: 'text-gray-600' };
          const expired = !p.login_active;

          return (
            <div
              key={p.code}
              className={`bg-white rounded-xl border shadow-sm flex flex-col hover:border-blue-200 transition-colors relative overflow-hidden ${
                expired ? 'border-red-200' : 'border-gray-200'
              }`}
            >
              {expired && (
                <div className="absolute top-0 right-0 bg-red-500 text-white text-[10px] font-bold px-3 py-1 rounded-bl-lg shadow">
                  未登录
                </div>
              )}

              <div className="p-5 flex items-center gap-3 border-b border-gray-50">
                <div className={`w-12 h-12 rounded-full ${colors.bg} flex items-center justify-center`}>
                  <Icon size={24} className={colors.fg} />
                </div>
                <div className="font-bold text-lg">{p.name}</div>
              </div>

              <div className="p-5 flex-1 space-y-4">
                <div>
                  <div className="text-xs text-gray-400 mb-1">当前状态</div>
                  {p.login_active ? (
                    <span className="px-2 py-1 bg-green-50 text-green-700 border border-green-100 rounded-full text-xs font-medium flex items-center gap-1 w-max">
                      <CheckCircle2 size={12} /> 授权有效
                    </span>
                  ) : (
                    <span className="px-2 py-1 bg-red-50 text-red-700 border border-red-100 rounded-full text-xs font-medium flex items-center gap-1 w-max">
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
                    className="w-full py-2 bg-white border border-gray-200 text-slate-700 rounded-lg text-sm font-medium hover:bg-gray-50 flex justify-center items-center gap-2"
                  >
                    <RefreshCw size={16} /> 重新授权
                  </button>
                ) : (
                  <button
                    onClick={() => handleLogin(p)}
                    className="w-full py-2 bg-slate-900 text-white rounded-lg text-sm font-medium hover:bg-slate-800 flex justify-center items-center gap-2 shadow-sm"
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
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-[400px] overflow-hidden relative">
            <div className="absolute top-4 right-4">
              <button onClick={() => setQrModal(null)} className="text-gray-400 hover:text-gray-600 bg-gray-100/50 p-1.5 rounded-full">
                <X size={20} />
              </button>
            </div>
            <div className="p-8 pt-10 flex flex-col items-center">
              <div className={`w-12 h-12 ${ICON_COLORS[qrModal.code]?.bg || 'bg-gray-100'} rounded-full flex items-center justify-center mb-4`}>
                {(() => { const I = PLATFORM_ICONS[qrModal.code] || ShoppingBag; return <I size={24} className={ICON_COLORS[qrModal.code]?.fg || 'text-gray-600'} />; })()}
              </div>
              <h3 className="font-bold text-xl mb-1">登录 {qrModal.name}</h3>
              <p className="text-sm text-gray-500 mb-6 text-center">请在弹出的浏览器窗口中完成扫码登录</p>

              <div className="w-48 h-48 border-2 border-dashed border-gray-300 rounded-2xl bg-gray-50 flex flex-col items-center justify-center mb-6">
                <QrCode size={40} className="text-gray-300 mb-2" />
                <span className="text-xs text-gray-400">浏览器已弹出...</span>
              </div>

              <div className="flex items-center gap-2 text-sm text-blue-600 font-medium bg-blue-50 px-4 py-2 rounded-full">
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
