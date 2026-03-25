"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch } from "@/lib/api"
import type { AggregationSummary } from "@/lib/types"

export default function BuyerDashboard() {
  const [data, setData] = useState<AggregationSummary | null>(null)
  const [selectedDate, setSelectedDate] = useState(
    () => new Date().toISOString().slice(0, 10)
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const load = (d: string) => {
    setLoading(true)
    setError("")
    apiFetch<AggregationSummary>(`/aggregation/summary?target_date=${d}`)
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Ошибка загрузки"))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load(selectedDate) }, [selectedDate])

  const itemsToBuy = data?.categories.flatMap((c) => c.items).filter((i) => i.to_buy > 0) ?? []

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Сводка заказов</h1>
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="text-sm border rounded px-2 py-1"
          />
          {itemsToBuy.length > 0 && (
            <Link href="/purchase">
              <Button size="sm">
                Закупить <Badge className="ml-1">{itemsToBuy.length}</Badge>
              </Button>
            </Link>
          )}
        </div>
      </div>

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      {loading ? (
        <p className="text-center text-muted-foreground">Загрузка...</p>
      ) : !data || data.categories.length === 0 ? (
        <p className="text-center text-muted-foreground">Нет заказов на эту дату</p>
      ) : (
        <div className="space-y-6">
          {data.categories.map((cat) => (
            <div key={cat.category_id}>
              <h2 className="text-base font-medium mb-2 text-muted-foreground uppercase tracking-wide">
                {cat.category_name}
              </h2>
              <div className="space-y-2">
                {cat.items.map((item) => (
                  <Card key={item.catalog_item_id}>
                    <CardContent className="p-3">
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <p className="font-medium">{item.name}</p>
                        <div className="flex flex-wrap gap-1 justify-end">
                          <Badge variant="outline">
                            {item.total_needed} {item.unit}
                          </Badge>
                          {item.in_stock > 0 && (
                            <Badge variant="secondary">
                              склад: {item.in_stock}
                            </Badge>
                          )}
                          {item.to_buy > 0 && (
                            <Badge>купить: {item.to_buy} {item.unit}</Badge>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1">
                        {item.restaurants.map((r, i) => (
                          <span key={i} className="text-xs text-muted-foreground">
                            {r.quantity} {item.unit}
                            {r.variant ? ` (${r.variant})` : ""}
                          </span>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
