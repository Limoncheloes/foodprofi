"use client"

import { useCallback, useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch } from "@/lib/api"
import type { Order, Restaurant } from "@/lib/types"

export default function RoutesPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [restaurants, setRestaurants] = useState<Record<string, Restaurant>>({})
  const [loading, setLoading] = useState(true)
  const [delivering, setDelivering] = useState<string | null>(null)
  const [error, setError] = useState("")

  const load = useCallback(() => {
    setLoading(true)
    setError("")
    Promise.all([
      apiFetch<Order[]>("/orders?status=in_delivery"),
      apiFetch<Restaurant[]>("/restaurants"),
    ])
      .then(([deliveries, rests]) => {
        setOrders(deliveries.sort(
          (a, b) => (a.is_urgent ? -1 : 1) - (b.is_urgent ? -1 : 1)
        ))
        setRestaurants(Object.fromEntries(rests.map((r) => [r.id, r])))
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Ошибка загрузки"))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const markDelivered = async (orderId: string) => {
    setDelivering(orderId)
    setError("")
    try {
      await apiFetch(`/orders/${orderId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: "delivered" }),
      })
      setOrders((prev) => prev.filter((o) => o.id !== orderId))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка")
    } finally {
      setDelivering(null)
    }
  }

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold mb-4">Маршруты доставки</h1>

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      {loading ? (
        <p className="text-center text-muted-foreground">Загрузка...</p>
      ) : orders.length === 0 ? (
        <p className="text-center text-muted-foreground">Нет активных доставок</p>
      ) : (
        <div className="space-y-3">
          {orders.map((order) => {
            const rest = restaurants[order.restaurant_id]
            return (
              <Card key={order.id}>
                <CardContent className="p-3">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="font-medium">{rest?.name ?? "Ресторан"}</p>
                      {rest?.address && (
                        <p className="text-sm text-muted-foreground">{rest.address}</p>
                      )}
                      {rest?.contact_phone && (
                        <p className="text-xs text-muted-foreground">{rest.contact_phone}</p>
                      )}
                    </div>
                    {order.is_urgent && (
                      <Badge variant="destructive">Срочно</Badge>
                    )}
                  </div>

                  <p className="text-xs text-muted-foreground mb-3">
                    {order.items.length} позиций ·{" "}
                    {new Date(order.created_at).toLocaleDateString("ru-RU")}
                  </p>

                  <Button
                    className="w-full"
                    size="sm"
                    disabled={delivering === order.id}
                    onClick={() => markDelivered(order.id)}
                  >
                    {delivering === order.id ? "..." : "Доставлено"}
                  </Button>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
