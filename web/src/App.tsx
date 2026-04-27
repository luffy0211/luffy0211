import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Blocks, Image as ImageIcon, LayoutDashboard, LayoutGrid, ListTodo, Package, Settings } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import Products from './pages/Products';
import Tasks from './pages/Tasks';
import Platforms from './pages/Platforms';

const appNavs = [
  { href: '/', name: '工作台', icon: LayoutGrid, active: false },
  { href: '/ecom', name: '图片优化', icon: ImageIcon, active: false },
  { href: '/luffy', name: '商品分发', icon: Blocks, active: true },
];

const navs = [
  { path: '/', name: '任务管理', icon: ListTodo },
  { path: '/dashboard', name: '仪表盘', icon: LayoutDashboard },
  { path: '/products', name: '商品管理', icon: Package },
  { path: '/platforms', name: '平台管理', icon: Settings },
];

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': '数据概览',
  '/products': '商品管理',
  '/': '任务调度中心',
  '/platforms': '平台管理',
};

function Layout() {
  const location = useLocation();
  const headerTitle = PAGE_TITLES[location.pathname] || '任务调度中心';

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_12%_8%,rgba(65,88,208,0.16),transparent_26%),radial-gradient(circle_at_88%_4%,rgba(200,80,192,0.14),transparent_28%),linear-gradient(135deg,#f0f2ff,#eef3ff_42%,#f6f4ff)] text-neutral-900">
      <header className="sticky top-0 z-30 border-b border-[rgba(199,210,254,0.5)] bg-white/85 backdrop-blur-sm">
        <div className="mx-auto flex h-[62px] max-w-7xl items-center justify-between px-5">
          <div className="flex min-w-[260px] items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#4158d0] to-[#c850c0] text-sm font-bold text-white">
              叮
            </div>
            <div className="text-[17px] font-bold dd-gradient-text">巨浪童装AI</div>
            <span className="ml-1 rounded bg-[rgba(200,80,192,0.1)] px-1.5 py-0.5 text-[11px] font-semibold text-[#c850c0]">BETA</span>
          </div>

          <nav className="flex items-center gap-2 rounded-full border border-[rgba(199,210,254,0.72)] bg-white/80 px-2 py-2 shadow-[0_8px_22px_rgba(65,88,208,0.08)] backdrop-blur">
            {appNavs.map((item) => {
              const Icon = item.icon;
              return (
                <a
                  key={item.name}
                  href={item.href}
                  className={`dd-nav-button gap-2 transition ${
                    item.active ? 'dd-nav-button-active' : 'text-neutral-600 hover:bg-[rgba(65,88,208,0.06)]'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {item.name}
                </a>
              );
            })}
          </nav>

          <div className="flex min-w-[260px] items-center justify-end text-sm text-neutral-500">
            系统调度正常运行中 <span className="ml-2 inline-block h-2 w-2 animate-pulse rounded-full bg-green-500" />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl px-5 py-6">
        <section className="dd-panel relative mb-5 overflow-hidden px-6 py-5">
          <div className="absolute right-[-40px] top-[-70px] h-36 w-36 rounded-full bg-[rgba(200,80,192,0.12)] blur-3xl" />
          <div className="relative flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex shrink-0 items-center gap-4 pr-6 xl:border-r xl:border-[rgba(199,210,254,0.62)]">
              <div className="h-12 w-1.5 rounded-full bg-gradient-to-b from-[#4158d0] to-[#c850c0]" />
              <div>
                <div className="whitespace-nowrap text-2xl font-black leading-none tracking-tight text-neutral-900">{headerTitle}</div>
                <div className="mt-2 whitespace-nowrap text-sm font-medium leading-none text-neutral-500">商品分发内部功能导航</div>
              </div>
            </div>
            <nav className="flex flex-wrap items-center gap-2 xl:justify-end">
              {navs.map((nav) => {
                const isActive = location.pathname === nav.path;
                const Icon = nav.icon;
                return (
                  <Link
                    key={nav.path}
                    to={nav.path}
                    className={`dd-nav-button gap-2 transition ${
                      isActive ? 'dd-nav-button-active' : 'border border-[rgba(199,210,254,0.72)] bg-white/75 text-neutral-600 hover:bg-[rgba(65,88,208,0.06)]'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {nav.name}
                  </Link>
                );
              })}
            </nav>
          </div>
        </section>

        <div className="pb-8">
          <Routes>
            <Route path="/" element={<Tasks />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/products" element={<Products />} />
            <Route path="/platforms" element={<Platforms />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return <BrowserRouter basename="/luffy"><Layout /></BrowserRouter>;
}
