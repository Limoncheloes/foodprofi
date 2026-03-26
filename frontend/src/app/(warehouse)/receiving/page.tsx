"use client"

import { useCallback, useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch } from "@/lib/api"
import type { Order, Restaurant } from "@/lib/types"

const STATUS_LABEL: Record<string, string> = {
  at_warehouse: "На складе",
  packed: "Упакован",
}

const NEXT_STATUS: Record<string, string> = {
  at_warehouse: "packed",
  packed: "in_delivery",
}

const ACTION_LABEL: Record<string, string> = {
  at_warehouse: "Упаковать",
  packed: "Отправить",
}

export default function ReceivingPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [restaurants, setRestaurants] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [advancing, setAdvancing] = useState<string | null>(null)
  const [error, setError] = useState("")

  const load = useCallback(() => {
    setLoading(true)
    setError("")
    Promise.all([
      apiFetch<Order[]>("/orders?status=at_warehouse"),
      apiFetch<Order[]>("/orders?status=packed"),
      apiFetch<Restaurant[]>("/restaurants"),
    ])
      .then(([atWarehouse, packed, rests]) => {
        const combined = [...atWarehouse, ...packed].sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        )
        setOrders(combined)
        setRestaurants(Object.fromEntries(rests.map((r) => [r.id, r.name])))
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Ошибка загрузки"))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const advance = async (orderId: string, nextStatus: string) => {
    setAdvancing(orderId)
    setError("")
    try {
      await apiFetch(`/orders/${orderId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: nextStatus }),
      })
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка обновления статуса")
    } finally {
      setAdvancing(null)
    }
  }

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold mb-4">Приём и упаковка</h1>

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      {loading ? (
        <p className="text-center text-muted-foreground">Загрузка...</p>
      ) : orders.length === 0 ? (
        <p className="text-center text-muted-foreground">Нет заказов на складе</p>
      ) : (
        <div className="space-y-3">
          {orders.map((order) => (
            <Card key={order.id}>
              <CardContent className="p-3">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="font-medium">
                      {restaurants[order.restaurant_id] ?? "Ресторан"}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(order.created_at).toLocaleDateString("ru-RU")}
                    </p>
                  </div>
                  <div className="flex gap-1 flex-wrap justify-end">
                    {order.is_urgent && (
                      <Badge variant="destructive">Срочно</Badge>
                    )}
                    <Badge variant="outline">
                      {STATUS_LABEL[order.status] ?? order.status}
                    </Badge>
                  </div>
                </div>

                <ul className="text-sm text-muted-foreground mb-3 space-y-0.5">
                  {order.items.map((item) => (
                    <li key={item.id}>
                      {item.quantity}
                      {item.variant ? ` (${item.variant})` : ""}
                      {item.note ? ` — ${item.note}` : ""}
                    </li>
                  ))}
                </ul>

                {NEXT_STATUS[order.status] && (
                  <Button
                    size="sm"
                    className="w-full"
                    disabled={advancing === order.id}
                    onClick={() => advance(order.id, NEXT_STATUS[order.status])}
                  >
                    {advancing === order.id ? "..." : ACTION_LABEL[order.status]}
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
