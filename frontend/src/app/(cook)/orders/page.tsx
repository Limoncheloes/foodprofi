"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch } from "@/lib/api"
import type { Order } from "@/lib/types"

const STATUS_LABEL: Record<string, string> = {
  draft: "Черновик",
  submitted: "Отправлен",
  in_purchase: "На закупке",
  at_warehouse: "На складе",
  packed: "Собран",
  in_delivery: "В доставке",
  delivered: "Доставлен",
  cancelled: "Отменён",
}

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch<Order[]>("/orders")
      .then(setOrders)
      .catch(() => setLoading(false))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="max-w-lg mx-auto p-4">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Мои заказы</h1>
        <div className="flex items-center gap-2">
          <Link href="/templates">
            <Button variant="outline" size="sm">Шаблоны</Button>
          </Link>
          <Link href="/catalog"><Button size="sm">Новый заказ</Button></Link>
        </div>
      </div>

      {loading ? (
        <p className="text-center text-muted-foreground">Загрузка...</p>
      ) : orders.length === 0 ? (
        <p className="text-center text-muted-foreground">Нет заказов</p>
      ) : (
        <div className="space-y-3">
          {orders.map((order) => (
            <Card key={order.id}>
              <CardContent className="p-3">
                <div className="flex items-center justify-between mb-1">
                  <div>
                    <p className="text-sm font-medium">{order.restaurant_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(order.created_at).toLocaleDateString("ru-RU")}
                    </p>
                  </div>
                  <div className="flex gap-1">
                    {order.is_urgent && (
                      <Badge variant="destructive">Срочно</Badge>
                    )}
                    <Badge>{STATUS_LABEL[order.status] ?? order.status}</Badge>
                  </div>
                </div>
                <p className="text-sm">{order.items.length} позиций</p>
                {order.deadline && (
                  <p className="text-xs text-muted-foreground mt-1">
                    до {new Date(order.deadline).toLocaleDateString("ru-RU")}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
