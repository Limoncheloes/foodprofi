"use client"

import { useCallback, useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch } from "@/lib/api"
import type { InventoryLogEntry } from "@/lib/types"

const REASON_LABEL: Record<string, string> = {
  received: "Приход",
  consumed: "Расход",
  adjusted: "Корректировка",
}

const REASON_VARIANT: Record<string, "default" | "destructive" | "outline"> = {
  received: "default",
  consumed: "destructive",
  adjusted: "outline",
}

export default function HistoryPage() {
  const [logs, setLogs] = useState<InventoryLogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const load = useCallback(() => {
    setLoading(true)
    setError("")
    apiFetch<InventoryLogEntry[]>("/warehouse/inventory/logs")
      .then(setLogs)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Ошибка загрузки"))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold mb-4">История движения</h1>

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      {loading ? (
        <p className="text-center text-muted-foreground">Загрузка...</p>
      ) : logs.length === 0 ? (
        <p className="text-center text-muted-foreground">История пуста</p>
      ) : (
        <div className="space-y-2">
          {logs.map((log) => (
            <Card key={log.id}>
              <CardContent className="p-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{log.item_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {log.user_name} · {new Date(log.created_at).toLocaleDateString("ru-RU")}
                    </p>
                    {log.note && (
                      <p className="text-xs text-muted-foreground mt-0.5">{log.note}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 ml-2">
                    <span
                      className={`text-sm font-semibold ${
                        log.delta > 0 ? "text-green-600" : "text-red-600"
                      }`}
                    >
                      {log.delta > 0 ? "+" : ""}{log.delta}
                    </span>
                    <Badge variant={REASON_VARIANT[log.reason] ?? "outline"}>
                      {REASON_LABEL[log.reason] ?? log.reason}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
