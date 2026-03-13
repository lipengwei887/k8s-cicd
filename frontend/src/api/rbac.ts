import api from './index'

// 角色相关接口
export const getRoles = (params?: { role_type?: string; status?: number }) => {
  return api.get('/rbac/roles', { params })
}

export const getRole = (id: number) => {
  return api.get(`/rbac/roles/${id}`)
}

export const createRole = (data: {
  name: string
  code: string
  description?: string
  permission_ids: number[]
}) => {
  return api.post('/rbac/roles', data)
}

export const updateRole = (id: number, data: {
  name?: string
  description?: string
  status?: number
  permission_ids?: number[]
}) => {
  return api.put(`/rbac/roles/${id}`, data)
}

export const deleteRole = (id: number) => {
  return api.delete(`/rbac/roles/${id}`)
}

// 权限相关接口
export const getPermissions = (params?: { resource_type?: string }) => {
  return api.get('/rbac/permissions', { params })
}

// 用户角色相关接口
export const getUserRoles = (userId: number) => {
  return api.get(`/rbac/users/${userId}/roles`)
}

export const assignRoleToUser = (data: { user_id: number; role_id: number }) => {
  return api.post('/rbac/users/assign-role', data)
}

export const removeRoleFromUser = (userId: number, roleId: number) => {
  return api.delete(`/rbac/users/${userId}/roles/${roleId}`)
}

// 组织相关接口
export const getOrganizations = () => {
  return api.get('/rbac/organizations')
}

export const createOrganization = (data: {
  name: string
  code: string
  description?: string
  parent_id?: number
}) => {
  return api.post('/rbac/organizations', data)
}

// 初始化接口
export const initRBAC = () => {
  return api.post('/rbac/init')
}

// 权限检查接口
export const checkPermission = (permission: string) => {
  return api.get('/rbac/check', { params: { permission } })
}

export const getMyPermissions = () => {
  return api.get('/rbac/my-permissions')
}

// 角色组管理接口
export const getRoleGroups = () => {
  return api.get('/rbac/role-groups')
}

export const getRoleGroup = (id: number) => {
  return api.get(`/rbac/role-groups/${id}`)
}

export const createRoleGroup = (data: {
  name: string
  code: string
  description?: string
}) => {
  return api.post('/rbac/role-groups', data)
}

export const updateRoleGroup = (id: number, data: {
  name?: string
  description?: string
}) => {
  return api.put(`/rbac/role-groups/${id}`, data)
}

export const deleteRoleGroup = (id: number) => {
  return api.delete(`/rbac/role-groups/${id}`)
}

// 角色组服务管理
export const addServiceToRoleGroup = (groupId: number, serviceId: number) => {
  return api.post(`/rbac/role-groups/${groupId}/services`, { service_id: serviceId })
}

export const removeServiceFromRoleGroup = (groupId: number, serviceId: number) => {
  return api.delete(`/rbac/role-groups/${groupId}/services/${serviceId}`)
}

// 角色组命名空间管理
export const addNamespaceToRoleGroup = (groupId: number, namespaceId: number) => {
  return api.post(`/rbac/role-groups/${groupId}/namespaces`, { namespace_id: namespaceId })
}

export const removeNamespaceFromRoleGroup = (groupId: number, namespaceId: number) => {
  return api.delete(`/rbac/role-groups/${groupId}/namespaces/${namespaceId}`)
}

// 用户角色组管理
export const getUserRoleGroups = (userId: number) => {
  return api.get(`/rbac/users/${userId}/role-groups`)
}

export const assignRoleGroupToUser = (userId: number, roleGroupId: number) => {
  return api.post(`/rbac/users/${userId}/role-groups`, { role_group_id: roleGroupId })
}

export const removeRoleGroupFromUser = (userId: number, roleGroupId: number) => {
  return api.delete(`/rbac/users/${userId}/role-groups/${roleGroupId}`)
}
