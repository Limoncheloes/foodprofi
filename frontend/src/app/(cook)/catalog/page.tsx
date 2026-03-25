"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch } from "@/lib/api"
import { useCart } from "@/lib/cart"
import type { CatalogItem, Category } from "@/lib/types"

export default function CatalogPage() {
  const [categories, setCategories] = useState<Category[]>([])
  const [items, setItems] = useState<Record<string, CatalogItem[]>>({})
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const { addItem, total } = useCart()

  useEffect(() => {
    apiFetch<Category[]>("/catalog/categories").then((cats) => {
      setCategories(cats)
      if (cats.length) setActiveCategory(cats[0].id)
    }).catch(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!activeCategory || items[activeCategory]) return
    setLoading(true)
    apiFetch<CatalogItem[]>(`/catalog/items?category_id=${activeCategory}`).then(
      (data) => setItems((prev) => ({ ...prev, [activeCategory]: data }))
    ).catch(() => setLoading(false)).finally(() => setLoading(false))
  }, [activeCategory])

  const currentItems = activeCategory ? (items[activeCategory] ?? []) : []

  return (
    <div className="max-w-lg mx-auto p-4 pb-24">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Каталог</h1>
        <div className="flex items-center gap-2">
          <Link href="/templates">
            <Button variant="ghost" size="sm">Шаблоны</Button>
          </Link>
          <Link href="/cart">
            <Button variant="outline" size="sm">
              Корзина {total > 0 && <Badge className="ml-1">{total}</Badge>}
            </Button>
          </Link>
        </div>
      </div>

      {/* Category tabs */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-4">
        {categories.map((cat) => (
          <Button
            key={cat.id}
            variant={activeCategory === cat.id ? "default" : "outline"}
            size="sm"
            onClick={() => setActiveCategory(cat.id)}
            className="whitespace-nowrap"
          >
            {cat.name}
          </Button>
        ))}
      </div>

      {/* Items */}
      {loading ? (
        <p className="text-center text-muted-foreground">Загрузка...</p>
      ) : currentItems.length === 0 ? (
        <p className="text-center text-muted-foreground">Нет товаров в категории</p>
      ) : (
        <div className="space-y-2">
          {currentItems.map((item) => (
            <CatalogCard key={item.id} item={item} onAdd={addItem} />
          ))}
        </div>
      )}
    </div>
  )
}

function CatalogCard({
  item,
  onAdd,
}: {
  item: CatalogItem
  onAdd: (item: CatalogItem, qty: number, variant: string | null) => void
}) {
  const [qty, setQty] = useState(1)
  const [variant, setVariant] = useState<string | null>(
    item.variants.length ? item.variants[0] : null
  )

  const UNIT_LABEL: Record<string, string> = {
    kg: "кг", pcs: "шт", liters: "л", packs: "уп"
  }

  return (
    <Card>
      <CardContent className="p-3 flex items-center justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="font-medium truncate">{item.name}</p>
          <p className="text-sm text-muted-foreground">{UNIT_LABEL[item.unit]}</p>
          {item.variants.length > 0 && (
            <select
              value={variant ?? ""}
              onChange={(e) => setVariant(e.target.value)}
              className="mt-1 text-sm border rounded px-1 py-0.5 w-full"
            >
              {item.variants.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline" size="icon" className="h-8 w-8"
            onClick={() => setQty(Math.max(1, qty - 1))}
          >−</Button>
          <span className="w-8 text-center">{qty}</span>
          <Button
            variant="outline" size="icon" className="h-8 w-8"
            onClick={() => setQty(qty + 1)}
          >+</Button>
          <Button size="sm" onClick={() => onAdd(item, qty, variant)}>
            В корзину
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
