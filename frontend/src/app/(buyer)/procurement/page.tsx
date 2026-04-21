"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { apiFetch } from "@/lib/api"
import type { BuyerItemRead } from "@/lib/types"

interface ItemState {
  quantity_received: string
  submitting: boolean
  error: string
}

export default function BuyerProcurementPage() {
  const [items, setItems] = useState<BuyerItemRead[]>([])
  const [states, setStates] = useState<Record<string, ItemState>>({})
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState("")

  const load = async () => {
    try {
      const data = await apiFetch<BuyerItemRead[]>("/buyer/items")
      setItems(data)
      setStates(
        Object.fromEntries(
          data.map((item) => [
            item.id,
            {
              quantity_received: String(item.quantity_ordered),
              submitting: false,
              error: "",
            },
          ])
        )
      )
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : "Ошибка загрузки")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const updateQty = (id: string, value: string) => {
    setStates((prev) => ({ ...prev, [id]: { ...prev[id], quantity_received: value } }))
  }

  const markPurchased = async (item: BuyerItemRead) => {
    const qty = parseFloat(states[item.id]?.quantity_received ?? "")
    if (isNaN(qty) || qty <= 0) {
      setStates((prev) => ({
        ...prev,
        [item.id]: { ...prev[item.id], error: "Введите количество > 0" },
      }))
      return
    }

    setStates((prev) => ({
      ...prev,
      [item.id]: { ...prev[item.id], submitting: true, error: "" },
    }))

    try {
      await apiFetch(`/buyer/items/${item.id}/purchased`, {
        method: "PATCH",
        body: JSON.stringify({ quantity_received: qty }),
      })
      setItems((prev) => prev.filter((i) => i.id !== item.id))
    } catch (e: unknown) {
      setStates((prev) => ({
        ...prev,
        [item.id]: {
          ...prev[item.id],
          submitting: false,
          error: e instanceof Error ? e.message : "Ошибка",
        },
      }))
    }
  }

  if (loading) return <div className="p-4 text-muted-foreground">Загрузка...</div>

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold mb-4">Мои позиции</h1>
      {loadError && <p className="text-sm text-red-500 mb-3">{loadError}</p>}
      {items.length === 0 && (
        <p className="text-muted-foreground">Нет назначенных позиций</p>
      )}
      <div className="space-y-3">
        {items.map((item) => {
          const state = states[item.id] ?? {
            quantity_received: String(item.quantity_ordered),
            submitting: false,
            error: "",
          }
          return (
            <Card key={item.id}>
              <CardContent className="p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">{item.display_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {item.restaurant_name} · заказано: {item.quantity_ordered} {item.unit}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(item.order_date).toLocaleDateString("ru-RU")}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        step="0.1"
                        min="0.01"
                        className="w-24 h-8 text-sm"
                        value={state.quantity_received}
                        onChange={(e) => updateQty(item.id, e.target.value)}
                        disabled={state.submitting}
                      />
                      <span className="text-xs text-muted-foreground">{item.unit}</span>
                    </div>
                    {state.error && (
                      <p className="text-xs text-red-500">{state.error}</p>
                    )}
                    <Button
                      size="sm"
                      onClick={() => markPurchased(item)}
                      disabled={state.submitting}
                    >
                      {state.submitting ? "..." : "Куплено"}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
