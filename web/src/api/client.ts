import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

export interface Product {
  id: number;
  title: string;
  price: string;
  url: string;
  style: string;
  color: string;
  season: string;
  material: string;
  fabric: string;
  safety_level: string;
  height: string;
  gender: string;
  main_images: string;
  sku_images: string;
  source: string;
  status: string;
  crawled_at: string | null;
  created_at: string;
}

export interface TaskItem {
  id: number;
  product_id: number | null;
  platform: string;
  url: string;
  status: string;
  error_msg: string;
}

export interface Task {
  id: number;
  type: string;
  status: string;
  schedule_type: string;
  cron_expr: string;
  scheduled_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  config_json: string;
  result_json: string;
  created_at: string;
  items: TaskItem[];
}

export interface Platform {
  id: number;
  name: string;
  code: string;
  login_active: boolean;
  last_login: string | null;
}

export interface DashboardStats {
  total_products: number;
  today_crawl: number;
  today_upload: number;
  pending_tasks: number;
}

export interface RecentTask {
  id: number;
  type: string;
  status: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  total_items: number;
  success_items: number;
  failed_items: number;
  errors: string[];
}

// Products
export const getProducts = (params?: Record<string, unknown>) =>
  api.get<{ total: number; items: Product[] }>('/products', { params });

export const deleteProduct = (id: number) => api.delete(`/products/${id}`);

// Tasks
export const getTasks = (params?: Record<string, unknown>) =>
  api.get<{ total: number; items: Task[] }>('/tasks', { params });

export const getTask = (id: number) => api.get<Task>(`/tasks/${id}`);

export const createCrawlTask = (data: { urls: string[]; source?: string; schedule_type?: string; scheduled_at?: string }) =>
  api.post<Task>('/tasks/crawl', data);

export const createUploadTask = (data: { product_ids: number[]; platforms: string[]; schedule_type?: string; scheduled_at?: string }) =>
  api.post<Task>('/tasks/upload', data);

export const cancelTask = (id: number) => api.put(`/tasks/${id}/cancel`);

// Dashboard
export const getDashboardStats = () => api.get<DashboardStats>('/dashboard/stats');
export const getRecentActivities = () => api.get<RecentTask[]>('/dashboard/recent-activities');

// Platforms
export const getPlatforms = () => api.get<Platform[]>('/platforms');

export const triggerLogin = (code: string) => api.post(`/platforms/${code}/login`);

export default api;
