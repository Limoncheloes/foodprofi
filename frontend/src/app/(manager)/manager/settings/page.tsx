"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch } from "@/lib/api"
import type { RestaurantSettings } from "@/lib/types"

export default function SettingsPage() {
  const [settings, setSettings] = useState<RestaurantSettings | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    const load = async () => {
      try {
        const data = await apiFetch("/manager/settings")
        setSettings(data as RestaurantSettings)
      } catch (e) {
        setError(e instanceof Error ? e.message : "Ошибка загрузки")
      }
    }
    load()
  }, [])

  const toggle = async () => {
    if (!settings) return
    setSaving(true)
    setError("")
    try {
      const updated = await apiFetch("/manager/settings", {
        method: "PATCH",
        body: JSON.stringify({ requires_approval: !settings.requires_approval }),
      }) as RestaurantSettings
      setSettings(updated)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка")
    } finally {
      setSaving(false)
    }
  }

  if (!settings) return <div className="p-4 text-muted-foreground">Загрузка...</div>

  return (
    <div className="max-w-sm mx-auto p-4">
      <h1 className="text-xl font-semibold mb-4">Настройки</h1>
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">Согласование заказов</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {settings.requires_approval
                  ? "Заказы требуют подтверждения менеджера"
                  : "Заказы отправляются сразу"}
              </p>
            </div>
            <Button
              variant={settings.requires_approval ? "default" : "outline"}
              size="sm"
              onClick={toggle}
              disabled={saving}
            >
              {settings.requires_approval ? "Вкл" : "Выкл"}
            </Button>
          </div>
          {error && <p className="text-sm text-red-500 mt-2">{error}</p>}
        </CardContent>
      </Card>
    </div>
  )
}
