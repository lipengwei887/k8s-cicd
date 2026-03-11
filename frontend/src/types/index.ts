export interface User {
  id: number
  username: string
  email: string
  real_name?: string
  role: string
  status: number
  created_at: string
}

export interface Cluster {
  id: number
  name: string
  display_name?: string
  api_server: string
  status: number
  description?: string
  created_at: string
}

export interface Namespace {
  id: number
  cluster_id: number
  name: string
  display_name?: string
  env_type: 'dev' | 'test' | 'staging' | 'prod'
  status: number
}

export interface Service {
  id: number
  namespace_id: number
  name: string
  display_name?: string
  type: 'deployment' | 'statefulset'
  deploy_name: string
  container_name?: string
  harbor_project?: string
  harbor_repo?: string
  port?: number
  replicas: number
  current_image?: string
}

export interface ReleaseRecord {
  id: number
  service_id: number
  operator_id: number
  version: string
  image_tag: string
  image_full_path?: string
  previous_image?: string
  status: 'pending' | 'approving' | 'running' | 'success' | 'failed' | 'rolled_back'
  strategy: string
  message?: string
  pod_status?: ReleaseProgress
  created_at: string
}

export interface ReleaseProgress {
  desired: number
  updated: number
  ready: number
  available: number
  unavailable: number
  progress_percent: number
  elapsed_seconds: number
  status: string
  message?: string
}

export interface ApiResponse<T> {
  data: T
  message?: string
}

export interface ListResponse<T> {
  items: T[]
  total: number
}
