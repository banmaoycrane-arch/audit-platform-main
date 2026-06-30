import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { api } from '../api/client'

export interface User {
  id: number
  username: string
  phone: string
  email?: string
  platform_role?: string
  is_super_admin?: boolean
}

interface Ledger {
  id: number
  name: string
  team_id?: number
  organization_id?: number
  is_default?: boolean
  role?: string
  status: string
}

interface AuthContextState {
  missing_bindings: string[]
  temporary_status: 'onboarding_pending' | 'ready'
  next_action: string
  teams: Array<{ id: number; name: string }>
  projects: Array<{ id: number; name: string; team_id?: number; status?: string; type?: string }>
  current_ledger_role?: string | null
  current_team_type?: string | null
  can_use_ledger_without_project?: boolean
  platform_role?: string
  is_super_admin?: boolean
}

interface AuthState {
  token: string | null
  user: User | null
  isLoggedIn: boolean
  authContextReady: boolean
  currentLedgerId: number | null
  userLedgers: Ledger[]
  authContext: AuthContextState | null
  setToken: (token: string) => void
  setUser: (user: User | null) => void
  setCurrentLedger: (ledgerId: number | null) => void
  setUserLedgers: (ledgers: Ledger[]) => void
  setAuthContext: (context: AuthContextState) => void
  refreshAuthContext: () => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => localStorage.getItem('token'))
  const [user, setUserState] = useState<User | null>(null)
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(() => !!localStorage.getItem('token'))
  const [currentLedgerId, setCurrentLedgerIdState] = useState<number | null>(() => {
    const saved = localStorage.getItem('current_ledger_id')
    return saved ? Number(saved) : null
  })
  const [userLedgers, setUserLedgersState] = useState<Ledger[]>([])
  const [authContext, setAuthContextState] = useState<AuthContextState | null>(null)
  const [authContextReady, setAuthContextReady] = useState<boolean>(() => !localStorage.getItem('token'))

  const setToken = useCallback((t: string) => {
    localStorage.setItem('token', t)
    setTokenState(t)
    setIsLoggedIn(true)
  }, [])

  const setUser = useCallback((u: User | null) => {
    setUserState(u)
  }, [])

  const setCurrentLedger = useCallback((ledgerId: number | null) => {
    if (ledgerId !== null) {
      localStorage.setItem('current_ledger_id', String(ledgerId))
    } else {
      localStorage.removeItem('current_ledger_id')
    }
    setCurrentLedgerIdState(ledgerId)
  }, [])

  const setUserLedgers = useCallback((ledgers: Ledger[]) => {
    setUserLedgersState(ledgers)
  }, [])

  const setAuthContext = useCallback((context: AuthContextState) => {
    setAuthContextState(context)
  }, [])

  const refreshAuthContext = useCallback(async () => {
    const context = await api.getAuthContext()
    const authorizedLedgerIds = new Set(context.ledgers.map((ledger) => ledger.id))
    let nextLedgerId = context.current_ledger_id
    if (nextLedgerId !== null && !authorizedLedgerIds.has(nextLedgerId)) {
      nextLedgerId = context.ledgers[0]?.id ?? null
    }

    setUserState({
      id: context.user.id,
      username: context.user.username || '',
      phone: context.user.phone || '',
      email: context.user.email || '',
      platform_role: context.user.platform_role || context.platform_role || 'user',
      is_super_admin: Boolean(context.user.is_super_admin || context.is_super_admin),
    })
    setUserLedgersState(context.ledgers)
    setCurrentLedgerIdState(nextLedgerId)
    setAuthContextState({
      missing_bindings: context.missing_bindings,
      temporary_status: context.temporary_status,
      next_action: context.next_action,
      teams: context.teams.map((team) => ({ id: team.id, name: team.name })),
      projects: context.projects.map((project) => ({
        id: project.id,
        name: project.name,
        team_id: project.team_id,
        status: project.status,
        type: project.type,
      })),
      current_ledger_role: context.current_ledger_role,
      current_team_type: context.current_team_type,
      can_use_ledger_without_project: context.can_use_ledger_without_project,
      platform_role: context.platform_role || context.user.platform_role || 'user',
      is_super_admin: Boolean(context.is_super_admin || context.user.is_super_admin),
    })
    if (nextLedgerId !== null) {
      localStorage.setItem('current_ledger_id', String(nextLedgerId))
    } else {
      localStorage.removeItem('current_ledger_id')
    }
    setAuthContextReady(true)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('current_ledger_id')
    setTokenState(null)
    setUserState(null)
    setIsLoggedIn(false)
    setCurrentLedgerIdState(null)
    setUserLedgersState([])
    setAuthContextState(null)
    setAuthContextReady(true)
  }, [])

  useEffect(() => {
    if (!token) {
      setAuthContextReady(true)
      return
    }
    setAuthContextReady(false)
    refreshAuthContext().catch(() => logout())
  }, [token, logout, refreshAuthContext])

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        isLoggedIn,
        authContextReady,
        currentLedgerId,
        userLedgers,
        authContext,
        setToken,
        setUser,
        setCurrentLedger,
        setUserLedgers,
        setAuthContext,
        refreshAuthContext,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuthStore(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuthStore must be used within AuthProvider')
  }
  return ctx
}
