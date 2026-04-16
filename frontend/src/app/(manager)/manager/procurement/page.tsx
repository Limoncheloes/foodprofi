"use client"

import { useCallback, useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { apiFetch } from "@/lib/api"
import type { ProcurementOrder } from "@/lib/types"

const STATUS_LABEL: Record<string, string> = {
  draft: "Черновик",
  routing: "Распределяется",
  in_purchase: "В закупке",
  received: "Получено",
  closed: "Закрыто",
  cancelled: "Отменено",
}

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  draft: "outline",
  routing: "secondary",
  in_purchase: "default",
  received: "default",
  closed: "secondary",
  cancelled: "destructive",
}

export default function ManagerProcurementPage() {
  const [orders, setOrders] = useState<ProcurementOrder[]>([])
  const [filter, setFilter] = useState<string>("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const load = useCallback((status?: string) => {
    setLoading(true)
    const params = status ? `?status=${status}` : ""
    apiFetch<ProcurementOrder[]>(`/kitchen/orders${params}`)
      .then(setOrders)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Ошибка загрузки"))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load(filter || undefined) }, [load, filter])

  const statuses = ["", "draft", "routing", "in_purchase", "received", "closed"]

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold mb-4">Заявки ресторана</h1>

      {/* Status filter */}
      <div className="flex gap-1 flex-wrap mb-4">
        {statuses.map((s) => (
          <Button
            key={s}
            size="sm"
            variant={filter === s ? "default" : "outline"}
            onClick={() => setFilter(s)}
          >
            {s ? (STATUS_LABEL[s] ?? s) : "Все"}
          </Button>
        ))}
      </div>

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      {loading ? (
        <p className="text-center text-muted-foreground">Загрузка...</p>
      ) : orders.length === 0 ? (
        <p className="text-center text-muted-foreground py-8">Нет заявок</p>
      ) : (
        <div className="space-y-2">
          {orders.map((order) => (
            <Card key={order.id}>
              <CardContent className="p-3">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-sm">#{order.id.slice(0, 8)}</p>
                    <p className="text-xs text-muted-foreground">
                      {order.user_name} · {new Date(order.created_at).toLocaleString("ru-RU", {
                        day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"
                      })}
                    </p>
                    <p className="text-xs text-muted-foreground">{order.items.length} позиций</p>
                  </div>
                  <Badge variant={STATUS_VARIANT[order.status] ?? "outline"}>
                    {STATUS_LABEL[order.status] ?? order.status}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
