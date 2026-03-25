"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { apiFetch } from "@/lib/api"
import type { AggregationSummary } from "@/lib/types"

interface PurchaseEntry {
  catalog_item_id: string
  name: string
  unit: string
  to_buy: number
  quantity_bought: string
  price: string
}

export default function PurchasePage() {
  const today = new Date().toISOString().slice(0, 10)
  const [entries, setEntries] = useState<PurchaseEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState("")
  const router = useRouter()

  useEffect(() => {
    apiFetch<AggregationSummary>(`/aggregation/summary?target_date=${today}`)
      .then((data) => {
        const items = data.categories
          .flatMap((c) => c.items)
          .filter((i) => i.to_buy > 0)
        setEntries(
          items.map((i) => ({
            catalog_item_id: i.catalog_item_id,
            name: i.name,
            unit: i.unit,
            to_buy: i.to_buy,
            quantity_bought: String(i.to_buy),
            price: "",
          }))
        )
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Ошибка загрузки"))
      .finally(() => setLoading(false))
  }, [today])

  const update = (
    id: string,
    field: "quantity_bought" | "price",
    value: string
  ) => {
    setEntries((prev) =>
      prev.map((e) => (e.catalog_item_id === id ? { ...e, [field]: value } : e))
    )
  }

  const submit = async () => {
    setSubmitting(true)
    setError("")
    try {
      await apiFetch("/aggregation/mark-purchased", {
        method: "POST",
        body: JSON.stringify({
          date: today,
          purchases: entries
            .filter((e) => parseFloat(e.quantity_bought) > 0)
            .map((e) => ({
              catalog_item_id: e.catalog_item_id,
              quantity_bought: parseFloat(e.quantity_bought),
              price: e.price ? parseFloat(e.price) : null,
            })),
        }),
      })
      router.push("/dashboard")
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка при сохранении")
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="p-4">
        <p className="text-center text-muted-foreground">Загрузка...</p>
      </div>
    )
  }

  if (entries.length === 0) {
    return (
      <div className="p-4 text-center">
        <p className="text-muted-foreground mb-4">
          Нечего закупать — всё есть на складе
        </p>
        <Link href="/dashboard">
          <Button>К сводке</Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="p-4 pb-24">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Закупка на {today}</h1>
        <Link href="/dashboard">
          <Button variant="ghost" size="sm">← Сводка</Button>
        </Link>
      </div>

      <div className="space-y-3 mb-6">
        {entries.map((entry) => (
          <Card key={entry.catalog_item_id}>
            <CardContent className="p-3">
              <div className="flex items-center justify-between mb-2">
                <p className="font-medium">{entry.name}</p>
                <span className="text-sm text-muted-foreground">
                  нужно: {entry.to_buy} {entry.unit}
                </span>
              </div>
              <div className="flex gap-2">
                <div className="flex-1">
                  <p className="text-xs text-muted-foreground mb-1">
                    Куплено ({entry.unit})
                  </p>
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    value={entry.quantity_bought}
                    onChange={(e) =>
                      update(entry.catalog_item_id, "quantity_bought", e.target.value)
                    }
                  />
                </div>
                <div className="flex-1">
                  <p className="text-xs text-muted-foreground mb-1">Цена (сом)</p>
                  <Input
                    type="number"
                    step="1"
                    min="0"
                    placeholder="необязательно"
                    value={entry.price}
                    onChange={(e) =>
                      update(entry.catalog_item_id, "price", e.target.value)
                    }
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      <Button className="w-full" onClick={submit} disabled={submitting}>
        {submitting ? "Сохранение..." : "Отметить как куплено"}
      </Button>
    </div>
  )
}
