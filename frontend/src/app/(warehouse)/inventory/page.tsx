"use client"

import { useCallback, useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { apiFetch } from "@/lib/api"
import type { CatalogItem, InventoryItem } from "@/lib/types"

export default function InventoryPage() {
  const [inventory, setInventory] = useState<InventoryItem[]>([])
  const [catalogItems, setCatalogItems] = useState<CatalogItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  // Receive form state
  const [selectedItemId, setSelectedItemId] = useState("")
  const [receiveQty, setReceiveQty] = useState("")
  const [receiveNote, setReceiveNote] = useState("")
  const [receiving, setReceiving] = useState(false)
  const [receiveError, setReceiveError] = useState("")

  // Per-row adjust state
  const [adjustingId, setAdjustingId] = useState<string | null>(null)
  const [adjustQty, setAdjustQty] = useState("")
  const [adjustNote, setAdjustNote] = useState("")
  const [adjustingSubmit, setAdjustingSubmit] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      apiFetch<InventoryItem[]>("/warehouse/inventory"),
      apiFetch<CatalogItem[]>("/catalog/items"),
    ])
      .then(([inv, items]) => {
        setInventory(inv)
        setCatalogItems(items)
        if (!selectedItemId && items.length > 0) setSelectedItemId(items[0].id)
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Ошибка загрузки"))
      .finally(() => setLoading(false))
  }, [selectedItemId])

  useEffect(() => { load() }, [])

  const receive = async () => {
    if (!selectedItemId || !receiveQty) return
    setReceiving(true)
    setReceiveError("")
    try {
      await apiFetch("/warehouse/inventory/receive", {
        method: "POST",
        body: JSON.stringify({
          catalog_item_id: selectedItemId,
          quantity: parseFloat(receiveQty),
          note: receiveNote || null,
        }),
      })
      setReceiveQty("")
      setReceiveNote("")
      load()
    } catch (e: unknown) {
      setReceiveError(e instanceof Error ? e.message : "Ошибка")
    } finally {
      setReceiving(false)
    }
  }

  const adjust = async (catalogItemId: string) => {
    if (!adjustQty) return
    setAdjustingSubmit(true)
    try {
      await apiFetch("/warehouse/inventory/adjust", {
        method: "POST",
        body: JSON.stringify({
          catalog_item_id: catalogItemId,
          quantity: parseFloat(adjustQty),
          note: adjustNote || null,
        }),
      })
      setAdjustingId(null)
      setAdjustQty("")
      setAdjustNote("")
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка корректировки")
    } finally {
      setAdjustingSubmit(false)
    }
  }

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold mb-4">Склад</h1>

      {/* Receive form */}
      <Card className="mb-4">
        <CardContent className="p-3">
          <p className="font-medium mb-3">Принять товар</p>
          <div className="space-y-2">
            <div>
              <Label className="text-xs">Товар</Label>
              <select
                className="w-full border rounded px-2 py-1 text-sm mt-1"
                value={selectedItemId}
                onChange={(e) => setSelectedItemId(e.target.value)}
              >
                {catalogItems.map((ci) => (
                  <option key={ci.id} value={ci.id}>
                    {ci.name} ({ci.unit})
                  </option>
                ))}
              </select>
            </div>
            <div className="flex gap-2">
              <div className="flex-1">
                <Label className="text-xs">Количество</Label>
                <Input
                  type="number"
                  step="0.1"
                  min="0.01"
                  placeholder="0.0"
                  value={receiveQty}
                  onChange={(e) => setReceiveQty(e.target.value)}
                  className="mt-1"
                />
              </div>
              <div className="flex-1">
                <Label className="text-xs">Примечание</Label>
                <Input
                  placeholder="необязательно"
                  value={receiveNote}
                  onChange={(e) => setReceiveNote(e.target.value)}
                  className="mt-1"
                />
              </div>
            </div>
            {receiveError && <p className="text-sm text-red-500">{receiveError}</p>}
            <Button
              size="sm"
              onClick={receive}
              disabled={receiving || !selectedItemId || !receiveQty}
            >
              {receiving ? "..." : "Принять"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      {/* Inventory list */}
      {loading ? (
        <p className="text-center text-muted-foreground">Загрузка...</p>
      ) : inventory.length === 0 ? (
        <p className="text-center text-muted-foreground">Склад пуст</p>
      ) : (
        <div className="space-y-2">
          {inventory.map((item) => (
            <Card key={item.catalog_item_id}>
              <CardContent className="p-3">
                <div className="flex items-center justify-between mb-1">
                  <p className="font-medium">{item.name}</p>
                  <span className="text-sm font-medium">
                    {item.quantity} {item.unit}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mb-2">
                  обновлено {new Date(item.updated_at).toLocaleDateString("ru-RU")}
                </p>

                {adjustingId === item.catalog_item_id ? (
                  <div className="space-y-2">
                    <div className="flex gap-2">
                      <Input
                        type="number"
                        step="0.1"
                        min="0"
                        placeholder="Новое кол-во"
                        value={adjustQty}
                        onChange={(e) => setAdjustQty(e.target.value)}
                        className="flex-1"
                      />
                      <Input
                        placeholder="Причина"
                        value={adjustNote}
                        onChange={(e) => setAdjustNote(e.target.value)}
                        className="flex-1"
                      />
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1"
                        onClick={() => { setAdjustingId(null); setAdjustQty(""); setAdjustNote("") }}
                      >
                        Отмена
                      </Button>
                      <Button
                        size="sm"
                        className="flex-1"
                        disabled={adjustingSubmit || !adjustQty}
                        onClick={() => adjust(item.catalog_item_id)}
                      >
                        {adjustingSubmit ? "..." : "Сохранить"}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setAdjustingId(item.catalog_item_id)
                      setAdjustQty(String(item.quantity))
                      setAdjustNote("")
                    }}
                  >
                    Скорректировать
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
