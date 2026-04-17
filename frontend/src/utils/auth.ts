export interface AuthUser {
  id: number
  username: string
  email?: string
  real_name?: string
  role?: string | null
  status?: number
  is_superuser?: boolean
  permissions?: string[]
}

const USER_STORAGE_KEY = 'auth_user'

const getStorages = () => [localStorage, sessionStorage]

const getActiveStorage = () => {
  if (localStorage.getItem('token')) {
    return localStorage
  }
  if (sessionStorage.getItem('token')) {
    return sessionStorage
  }
  return localStorage
}

export const getStoredToken = () =>
  localStorage.getItem('token') || sessionStorage.getItem('token')

export const clearAuthStorage = () => {
  for (const storage of getStorages()) {
    storage.removeItem('token')
    storage.removeItem('tokenExpiry')
    storage.removeItem(USER_STORAGE_KEY)
  }
}

export const getStoredCurrentUser = (): AuthUser | null => {
  for (const storage of getStorages()) {
    const raw = storage.getItem(USER_STORAGE_KEY)
    if (!raw) {
      continue
    }
    try {
      return JSON.parse(raw) as AuthUser
    } catch {
      storage.removeItem(USER_STORAGE_KEY)
    }
  }
  return null
}

export const setStoredCurrentUser = (user: AuthUser) => {
  const activeStorage = getActiveStorage()
  activeStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user))

  for (const storage of getStorages()) {
    if (storage !== activeStorage) {
      storage.removeItem(USER_STORAGE_KEY)
    }
  }
}

export const hasPermission = (user: AuthUser | null | undefined, permission: string) => {
  if (!user) {
    return false
  }
  if (user.is_superuser) {
    return true
  }
  return !!user.permissions?.includes(permission)
}

export const hasAnyPermission = (user: AuthUser | null | undefined, permissions: string[]) =>
  permissions.some(permission => hasPermission(user, permission))
