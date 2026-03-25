"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react"
import { apiFetch, clearTokens, getTokens, setTokens } from "./api"
import type { TokenResponse, User } from "./types"

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (phone: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  // Fix Critical 1: fetchMe now rethrows so login() can detect failure.
  // The useEffect init call wraps it in try/catch for silent handling.
  const fetchMe = useCallback(async () => {
    try {
      const me = await apiFetch<User>("/auth/me")
      setUser(me)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const { access } = getTokens()
    if (access) {
      // Silent on init: swallow errors, just set loading=false
      fetchMe().catch(() => {
        setUser(null)
        setLoading(false)
      })
    } else {
      setLoading(false)
    }
  }, [fetchMe])

  const login = async (phone: string, password: string) => {
    const data = await apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ phone, password }),
    })
    setTokens(data.access_token, data.refresh_token)
    // fetchMe throws on failure — caller (login form) will catch and show error
    await fetchMe()
  }

  // Fix Important 3: redirect to "/" on logout so no stale page is shown
  const logout = () => {
    clearTokens()
    setUser(null)
    window.location.href = "/"
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within AuthProvider")
  return ctx
}
