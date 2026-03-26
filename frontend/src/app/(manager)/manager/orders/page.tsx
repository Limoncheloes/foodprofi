"use client"

import { useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch } from "@/lib/api"
import type { ManagerOrder } from "@/lib/types"

const STATUS_LABEL: Record<string, string> = {
  pending_approval: "Ожидает подтверждения",
  submitted: "Отправлен",
  in_purchase: "Закупка",
  at_warehouse: "На складе",
  packed: "Упакован",
  in_delivery: "В доставке",
  delivered: "Доставлен",
  cancelled: "Отменён",
}

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  pending_approval: "outline",
  submitted: "default",
  in_purchase: "secondary",
  cancelled: "destructive",
  delivered: "secondary",
}

export default function ManagerOrdersPage() {
  const [orders, setOrders] = useState<ManagerOrder[]>([])
  const [loading, setLoading] = useState(true)
  const [actionError, setActionError] = useState("")

  const load = async () => {
    try {
      const data = await apiFetch("/manager/orders") as ManagerOrder[]
      setOrders(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const transition = async (orderId: string, status: string) => {
    setActionError("")
    try {
      await apiFetch(`/orders/${orderId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      })
      await load()
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Ошибка")
    }
  }

  if (loading) return <div className="p-4 text-muted-foreground">Загрузка...</div>

  return (
    <div className="max-w-2xl mx-auto p-4">
      <h1 className="text-xl font-semibold mb-4">Заказы ресторана</h1>
      {actionError && <p className="text-sm text-red-500 mb-3">{actionError}</p>}
      {orders.length === 0 && <p className="text-muted-foreground">Заказов нет</p>}
      <div className="space-y-3">
        {orders.map((order) => (
          <Card key={order.id}>
            <CardContent className="p-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium text-sm">{order.user_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(order.created_at).toLocaleString("ru-RU")}
                    {order.deadline && ` · до ${new Date(order.deadline).toLocaleDateString("ru-RU")}`}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {order.items.length} позиц.
                  </p>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <div className="flex gap-1">
                    {order.is_urgent && <Badge variant="destructive" className="text-xs">Срочно</Badge>}
                    <Badge variant={STATUS_VARIANT[order.status] ?? "secondary"}>
                      {STATUS_LABEL[order.status] ?? order.status}
                    </Badge>
                  </div>
                  {order.status === "pending_approval" && (
                    <div className="flex gap-1">
                      <Button
                        size="sm" variant="default"
                        onClick={() => transition(order.id, "submitted")}
                      >
                        Подтвердить
                      </Button>
                      <Button
                        size="sm" variant="destructive"
                        onClick={() => transition(order.id, "cancelled")}
                      >
                        Отклонить
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
