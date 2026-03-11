import axios, { AxiosInstance, AxiosResponse } from 'axios'
import type { ApiResponse, ListResponse } from '@/types'

// 创建 axios 实例
const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器 - 添加 token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器 - 处理错误
api.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// 认证相关 API
export const authApi = {
  login: (username: string, password: string) =>
    api.post('/auth/login', 
      new URLSearchParams({ username, password }).toString(),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    ),
  
  logout: () => api.post('/auth/logout'),
  
  getMe: () => api.get('/auth/me'),
}

// 用户管理 API (管理员)
export const userApi = {
  getUsers: (params?: { skip?: number; limit?: number; role?: string }) =>
    api.get('/users', { params }),
  
  createUser: (data: any) => api.post('/users', data),
  
  updateUser: (id: number, data: any) => api.put(`/users/${id}`, data),
  
  deleteUser: (id: number) => api.delete(`/users/${id}`),
  
  getUserPermissions: (userId: number) =>
    api.get(`/users/${userId}/permissions`),
  
  addUserPermission: (userId: number, data: any) =>
    api.post(`/users/${userId}/permissions`, data),
  
  removeUserPermission: (userId: number, permissionId: number) =>
    api.delete(`/users/${userId}/permissions/${permissionId}`),
}

// 集群相关 API
export const clusterApi = {
  getClusters: (params?: { skip?: number; limit?: number }) =>
    api.get<ListResponse<any>>('/clusters', { params }),
  
  getCluster: (id: number) => api.get<any>(`/clusters/${id}`),
  
  createCluster: (data: any) => api.post('/clusters', data),
  
  updateCluster: (id: number, data: any) => api.put(`/clusters/${id}`, data),
  
  deleteCluster: (id: number) => api.delete(`/clusters/${id}`),
  
  getNamespaces: (clusterId: number) =>
    api.get<ListResponse<any>>(`/clusters/${clusterId}/namespaces`),
  
  // 管理员功能
  syncCluster: (id: number) => api.post(`/clusters/${id}/sync`),
  
  uploadKubeconfig: (formData: FormData) =>
    api.post('/clusters/upload-kubeconfig', formData),
}

// 服务相关 API
export const serviceApi = {
  getServices: (params?: { skip?: number; limit?: number; namespace_id?: number }) =>
    api.get<ListResponse<any>>('/services', { params }),
  
  getService: (id: number) => api.get<any>(`/services/${id}`),
  
  createService: (data: any) => api.post('/services', data),
  
  getServiceImages: (id: number) =>
    api.get<ListResponse<string>>(`/services/${id}/images`),
}

// 发布相关 API
export const releaseApi = {
  getReleases: (params?: { skip?: number; limit?: number; service_id?: number; status?: string }) =>
    api.get<ListResponse<any>>('/releases', { params }),
  
  getRelease: (id: number) => api.get<any>(`/releases/${id}`),
  
  createRelease: (data: { service_id: number; image_tag: string; version?: string; require_approval?: boolean }) =>
    api.post('/releases', data),
  
  executeRelease: (id: number) => api.post(`/releases/${id}/execute`),
  
  rollbackRelease: (id: number) => api.post(`/releases/${id}/rollback`),
  
  approveRelease: (id: number, data: { approved: boolean; comment?: string }) =>
    api.post(`/releases/${id}/approve`, data),
}

// Harbor 相关 API
export const harborApi = {
  // 根据 project/repo 获取镜像标签
  getImageTags: (params: { project: string; repository: string; limit?: number }) =>
    api.get<ListResponse<string>>('/harbor/tags', { params }),
  
  // 根据服务 ID 获取镜像标签（自动从服务获取 harbor 配置）
  getServiceImageTags: (serviceId: number, limit?: number) =>
    api.get<any>(`/harbor/service/${serviceId}/tags`, { params: { limit } }),
  
  // 解析镜像地址
  parseImageUrl: (imageUrl: string) =>
    api.get('/harbor/parse-image', { params: { image_url: imageUrl } }),
  
  // 检查 Harbor 连接状态
  checkHealth: () => api.get('/harbor/health'),
}

export default api
