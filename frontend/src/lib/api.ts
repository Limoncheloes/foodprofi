const BASE_URL = "/api"

function getTokens() {
  if (typeof window === "undefined") return { access: null, refresh: null }
  return {
    access: localStorage.getItem("access_token"),
    refresh: localStorage.getItem("refresh_token"),
  }
}

function setTokens(access: string, refresh: string) {
  localStorage.setItem("access_token", access)
  localStorage.setItem("refresh_token", refresh)
}

function clearTokens() {
  localStorage.removeItem("access_token")
  localStorage.removeItem("refresh_token")
}

async function refreshAccessToken(): Promise<string | null> {
  const { refresh } = getTokens()
  if (!refresh) return null

  const resp = await fetch(`${BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  })

  if (!resp.ok) {
    clearTokens()
    return null
  }

  const data = await resp.json()
  setTokens(data.access_token, data.refresh_token)
  return data.access_token
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const { access } = getTokens()

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  }
  if (access) headers["Authorization"] = `Bearer ${access}`

  let resp = await fetch(`${BASE_URL}${path}`, { ...options, headers })

  if (resp.status === 401 && access) {
    const newToken = await refreshAccessToken()
    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`
      resp = await fetch(`${BASE_URL}${path}`, { ...options, headers })
    }
  }

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: "Ошибка сервера" }))
    throw new Error(err.detail ?? "Ошибка сервера")
  }

  return resp.json()
}

export { setTokens, clearTokens, getTokens }
