"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { useCart } from "@/lib/cart"

export default function CartPage() {
  const { items, removeItem, updateQuantity, clear } = useCart()
  const { user } = useAuth()
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  const UNIT_LABEL: Record<string, string> = {
    kg: "кг", pcs: "шт", liters: "л", packs: "уп"
  }

  const submit = async () => {
    if (!user?.restaurant_id) {
      setError("Вы не привязаны к ресторану")
      return
    }
    if (items.length === 0) return

    setLoading(true)
    try {
      await apiFetch("/orders", {
        method: "POST",
        body: JSON.stringify({
          restaurant_id: user.restaurant_id,
          is_urgent: false,
          items: items.map((i) => ({
            catalog_item_id: i.item.id,
            quantity: i.quantity,
            variant: i.variant,
            note: i.note,
          })),
        }),
      })
      clear()
      router.push("/orders")
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка при отправке заказа")
    } finally {
      setLoading(false)
    }
  }

  if (items.length === 0) {
    return (
      <div className="max-w-lg mx-auto p-4 text-center">
        <p className="text-muted-foreground mb-4">Корзина пуста</p>
        <Link href="/catalog"><Button>В каталог</Button></Link>
      </div>
    )
  }

  return (
    <div className="max-w-lg mx-auto p-4 pb-24">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Корзина</h1>
        <Link href="/catalog"><Button variant="ghost" size="sm">← Каталог</Button></Link>
      </div>

      <div className="space-y-2 mb-6">
        {items.map((cartItem) => (
          <Card key={`${cartItem.item.id}-${cartItem.variant}`}>
            <CardContent className="p-3 flex items-center justify-between gap-3">
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{cartItem.item.name}</p>
                {cartItem.variant && (
                  <p className="text-sm text-muted-foreground">{cartItem.variant}</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline" size="icon" className="h-8 w-8"
                  onClick={() => updateQuantity(cartItem.item.id, Math.max(1, cartItem.quantity - 1))}
                >−</Button>
                <span className="w-10 text-center">
                  {cartItem.quantity} {UNIT_LABEL[cartItem.item.unit]}
                </span>
                <Button
                  variant="outline" size="icon" className="h-8 w-8"
                  onClick={() => updateQuantity(cartItem.item.id, cartItem.quantity + 1)}
                >+</Button>
                <Button
                  variant="ghost" size="sm" className="text-red-500"
                  onClick={() => removeItem(cartItem.item.id)}
                >✕</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {error && <p className="text-sm text-red-500 mb-3">{error}</p>}

      <Button className="w-full" onClick={submit} disabled={loading}>
        {loading ? "Отправка..." : `Отправить заказ (${items.length} позиций)`}
      </Button>
    </div>
  )
}
