"use client"

import { useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch, getTokens } from "@/lib/api"
import type { PendingItemRead } from "@/lib/types"

async function downloadFile(url: string, filename: string) {
  const { access } = getTokens()
  const resp = await fetch(url, {
    headers: { Authorization: `Bearer ${access ?? ""}` },
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: "Ошибка скачивания" }))
    throw new Error(err.detail)
  }
  const blob = await resp.blob()
  const a = document.createElement("a")
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

export default function CuratorQueuePage() {
  const [items, setItems] = useState<PendingItemRead[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const load = async () => {
    try {
      const data = await apiFetch<PendingItemRead[]>("/curator/pending")
      setItems(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="p-4 text-muted-foreground">Загрузка...</div>

  return (
    <div className="max-w-2xl mx-auto p-4">
      <h1 className="text-xl font-semibold mb-4">Очередь закупок</h1>
      {error && <p className="text-sm text-red-500 mb-3">{error}</p>}
      {items.length === 0 && <p className="text-muted-foreground">Нет позиций в очереди</p>}
      <div className="space-y-3">
        {items.map((item) => (
          <Card key={item.id}>
            <CardContent className="p-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium text-sm">{item.display_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {item.restaurant_name} · {item.quantity_ordered} {item.unit}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(item.created_at).toLocaleString("ru-RU")}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <Badge variant={item.is_catalog_item ? "secondary" : "outline"} className="text-xs">
                    {item.is_catalog_item ? "Каталог" : "Свободный"}
                  </Badge>
                  <div className="flex gap-1 mt-1">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        downloadFile(
                          `/api/orders/${item.order_id}/export/docx`,
                          `zakupka_${item.order_id.slice(0, 8)}.docx`
                        ).catch((e: Error) => setError(e.message))
                      }
                    >
                      Скачать DOCX
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        downloadFile(
                          `/api/orders/${item.order_id}/export/xlsx`,
                          `1c_${item.order_id.slice(0, 8)}.xlsx`
                        ).catch((e: Error) => setError(e.message))
                      }
                    >
                      Экспорт 1C
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
