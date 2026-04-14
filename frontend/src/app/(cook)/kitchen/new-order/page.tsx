"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { apiFetch } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import type { CatalogItem, SubmitOrderResponse } from "@/lib/types"

interface CartItem {
  catalog_item_id?: string
  raw_name?: string
  display_name: string
  quantity_ordered: string
  unit: string
  is_catalog: boolean
}

function openWhatsApp(primary: string | null, fallback: string) {
  if (!primary) {
    window.location.href = fallback
    return
  }
  let appOpened = false
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) appOpened = true
  }, { once: true })
  window.location.href = primary
  setTimeout(() => {
    if (!appOpened) window.location.href = fallback
  }, 1500)
}

export default function NewOrderPage() {
  const router = useRouter()
  const { user } = useAuth()

  const [search, setSearch] = useState("")
  const [searchResults, setSearchResults] = useState<CatalogItem[]>([])
  const [cart, setCart] = useState<CartItem[]>([])
  const [rawName, setRawName] = useState("")
  const [rawQty, setRawQty] = useState("")
  const [rawUnit, setRawUnit] = useState("шт")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState("")

  // Debounced catalog search
  useEffect(() => {
    if (!search.trim()) {
      setSearchResults([])
      return
    }
    const t = setTimeout(async () => {
      try {
        const results = await apiFetch<CatalogItem[]>(
          `/catalog/items?search=${encodeURIComponent(search)}`
        )
        setSearchResults(results)
      } catch {
        setSearchResults([])
      }
    }, 300)
    return () => clearTimeout(t)
  }, [search])

  function addCatalogItem(item: CatalogItem) {
    setCart((prev) => [
      ...prev,
      {
        catalog_item_id: item.id,
        display_name: item.name,
        quantity_ordered: "1",
        unit: item.unit,
        is_catalog: true,
      },
    ])
    setSearch("")
    setSearchResults([])
  }

  function addRawItem() {
    if (!rawName.trim() || !rawQty || parseFloat(rawQty) <= 0) return
    setCart((prev) => [
      ...prev,
      {
        raw_name: rawName.trim(),
        display_name: rawName.trim(),
        quantity_ordered: rawQty,
        unit: rawUnit,
        is_catalog: false,
      },
    ])
    setRawName("")
    setRawQty("")
  }

  function removeItem(index: number) {
    setCart((prev) => prev.filter((_, i) => i !== index))
  }

  function updateQty(index: number, value: string) {
    setCart((prev) =>
      prev.map((item, i) => (i === index ? { ...item, quantity_ordered: value } : item))
    )
  }

  async function handleSubmit() {
    if (!user?.restaurant_id || cart.length === 0) return
    setSubmitting(true)
    setError("")
    try {
      // 1. Create draft order
      const order = await apiFetch<{ id: string }>("/kitchen/orders", {
        method: "POST",
        body: JSON.stringify({
          restaurant_id: user.restaurant_id,
          items: cart.map((item) => ({
            catalog_item_id: item.catalog_item_id ?? null,
            raw_name: item.raw_name ?? null,
            quantity_ordered: item.quantity_ordered,
            unit: item.unit,
          })),
        }),
      })

      // 2. Submit
      const result = await apiFetch<SubmitOrderResponse>(
        `/kitchen/orders/${order.id}/submit`,
        { method: "POST" }
      )

      // 3. Open WhatsApp
      openWhatsApp(result.whatsapp.primary, result.whatsapp.fallback)

      router.push("/kitchen/orders")
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка отправки")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="p-4 max-w-lg mx-auto">
      <h1 className="text-xl font-semibold mb-4">Новая заявка</h1>

      {/* Catalog search */}
      <div className="mb-4">
        <Input
          placeholder="Поиск по каталогу..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {searchResults.length > 0 && (
          <div className="border rounded-md mt-1 divide-y">
            {searchResults.map((item) => (
              <button
                key={item.id}
                className="w-full text-left px-3 py-2 text-sm hover:bg-muted"
                onClick={() => addCatalogItem(item)}
              >
                {item.name} <span className="text-muted-foreground">({item.unit})</span>
              </button>
            ))}
          </div>
        )}
        {search.trim() && searchResults.length === 0 && (
          <p className="text-xs text-muted-foreground mt-1">Не найдено в каталоге — добавьте ниже вручную</p>
        )}
      </div>

      {/* Raw item input */}
      <div className="flex gap-2 mb-4">
        <Input
          placeholder="Название (не в каталоге)"
          value={rawName}
          onChange={(e) => setRawName(e.target.value)}
          className="flex-1"
        />
        <Input
          placeholder="Кол-во"
          type="number"
          min="0.001"
          step="0.001"
          value={rawQty}
          onChange={(e) => setRawQty(e.target.value)}
          className="w-24"
        />
        <Input
          placeholder="Ед."
          value={rawUnit}
          onChange={(e) => setRawUnit(e.target.value)}
          className="w-16"
        />
        <Button type="button" variant="outline" onClick={addRawItem}>+</Button>
      </div>

      {/* Cart */}
      {cart.length > 0 && (
        <div className="space-y-2 mb-4">
          <h2 className="text-sm font-medium text-muted-foreground">Позиции ({cart.length})</h2>
          {cart.map((item, i) => (
            <Card key={i}>
              <CardContent className="p-3 flex items-center gap-2">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{item.display_name}</p>
                  {!item.is_catalog && (
                    <Badge variant="outline" className="text-xs">вручную</Badge>
                  )}
                </div>
                <Input
                  type="number"
                  min="0.001"
                  step="0.001"
                  value={item.quantity_ordered}
                  onChange={(e) => updateQty(i, e.target.value)}
                  className="w-20 text-right"
                />
                <span className="text-sm text-muted-foreground w-8">{item.unit}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => removeItem(i)}
                  className="text-destructive"
                >
                  ✕
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      <Button
        className="w-full"
        onClick={handleSubmit}
        disabled={submitting || cart.length === 0}
      >
        {submitting ? "Отправляем..." : `Отправить заявку (${cart.length} поз.)`}
      </Button>
    </div>
  )
}
