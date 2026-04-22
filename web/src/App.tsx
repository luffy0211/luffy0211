import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Zap, LayoutDashboard, Package, ListTodo, Settings } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import Products from './pages/Products';
import Tasks from './pages/Tasks';
import Platforms from './pages/Platforms';

const navs = [
  { path: '/dashboard', name: '仪表盘', icon: LayoutDashboard },
  { path: '/products', name: '商品管理', icon: Package },
  { path: '/', name: '任务管理', icon: ListTodo },
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
    <>
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col z-10">
        <div className="h-16 flex items-center px-6 font-bold text-xl border-b border-gray-200 gap-2">
          <Zap className="text-blue-600" size={24} />
          商品分发中枢
        </div>
        <nav className="flex-1 p-4 space-y-2">
          {navs.map((nav) => {
            const isActive = location.pathname === nav.path;
            const Icon = nav.icon;
            return (
              <Link key={nav.path} to={nav.path} className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition-colors ${
                isActive 
                  ? 'bg-gray-100 font-semibold text-slate-900' 
                  : 'font-medium text-gray-500 hover:bg-gray-50'
              }`}>
                <Icon size={20} /> {nav.name}
              </Link>
            );
          })}
        </nav>
      </aside>

      <main className="flex-1 flex flex-col h-screen overflow-hidden relative bg-gray-50">
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0">
          <h2 className="text-lg font-semibold">{headerTitle}</h2>
          <div className="flex items-center gap-4">
             <div className="text-sm text-gray-500 flex items-center">
                系统调度正常运行中 <span className="inline-block w-2 h-2 bg-green-500 rounded-full animate-pulse ml-2"></span>
             </div>
          </div>
        </header>
        
        <div className="flex-1 overflow-y-auto p-6">
          <Routes>
            <Route path="/" element={<Tasks />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/products" element={<Products />} />
            <Route path="/platforms" element={<Platforms />} />
          </Routes>
        </div>
      </main>
    </>
  );
}

export default function App() {
  return <BrowserRouter><Layout /></BrowserRouter>;
}