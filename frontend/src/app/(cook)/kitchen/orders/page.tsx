"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
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

export default function KitchenOrdersPage() {
  const [orders, setOrders] = useState<ProcurementOrder[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const load = useCallback(() => {
    setLoading(true)
    apiFetch<ProcurementOrder[]>("/kitchen/orders")
      .then(setOrders)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Ошибка загрузки"))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Мои заявки</h1>
        <Link href="/kitchen/new-order">
          <Button size="sm">+ Новая</Button>
        </Link>
      </div>

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      {loading ? (
        <p className="text-center text-muted-foreground">Загрузка...</p>
      ) : orders.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          <p>Заявок пока нет</p>
          <Link href="/kitchen/new-order">
            <Button className="mt-3" variant="outline">Создать первую заявку</Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {orders.map((order) => (
            <Card key={order.id}>
              <CardContent className="p-3">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm font-medium">
                      Заявка #{order.id.slice(0, 8)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(order.created_at).toLocaleDateString("ru-RU", {
                        day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"
                      })}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {order.items.length} позиций
                    </p>
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
