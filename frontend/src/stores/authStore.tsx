import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { api } from '../api/client'

interface User {
  id: number
  username: string
  phone: string
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
}

interface AuthState {
  token: string | null
  user: User | null
  isLoggedIn: boolean
  currentLedgerId: number | null
  userLedgers: Ledger[]
  authContext: AuthContextState | null
  setToken: (token: string) => void
  setUser: (user: User | null) => void
  setCurrentLedger: (ledgerId: number | null) => void
  setUserLedgers: (ledgers: Ledger[]) => void
  setAuthContext: (context: AuthContextState) => void
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

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('current_ledger_id')
    setTokenState(null)
    setUserState(null)
    setIsLoggedIn(false)
    setCurrentLedgerIdState(null)
    setUserLedgersState([])
    setAuthContextState(null)
  }, [])

  useEffect(() => {
    if (!token) return
    api.getAuthContext()
      .then((context) => {
        setUserState({
          id: context.user.id,
          username: context.user.username || '',
          phone: context.user.phone || '',
        })
        setUserLedgersState(context.ledgers)
        setCurrentLedgerIdState(context.current_ledger_id)
        setAuthContextState({
          missing_bindings: context.missing_bindings,
          temporary_status: context.temporary_status,
          next_action: context.next_action,
        })
        if (context.current_ledger_id !== null) {
          localStorage.setItem('current_ledger_id', String(context.current_ledger_id))
        } else {
          localStorage.removeItem('current_ledger_id')
        }
      })
      .catch(() => logout())
  }, [token, logout])

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        isLoggedIn,
        currentLedgerId,
        userLedgers,
        authContext,
        setToken,
        setUser,
        setCurrentLedger,
        setUserLedgers,
        setAuthContext,
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
