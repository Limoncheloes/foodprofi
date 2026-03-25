"use client"

import { createContext, useContext, useState } from "react"
import type { CatalogItem } from "./types"

interface CartItem {
  item: CatalogItem
  quantity: number
  variant: string | null
  note: string | null
}

interface CartContextValue {
  items: CartItem[]
  addItem: (item: CatalogItem, quantity: number, variant: string | null) => void
  removeItem: (itemId: string, variant: string | null) => void
  updateQuantity: (itemId: string, variant: string | null, quantity: number) => void
  clear: () => void
  total: number
}

const CartContext = createContext<CartContextValue | null>(null)

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([])

  const addItem = (item: CatalogItem, quantity: number, variant: string | null) => {
    setItems((prev) => {
      const existing = prev.find((i) => i.item.id === item.id && i.variant === variant)
      if (existing) {
        return prev.map((i) =>
          i.item.id === item.id && i.variant === variant
            ? { ...i, quantity: i.quantity + quantity }
            : i
        )
      }
      return [...prev, { item, quantity, variant, note: null }]
    })
  }

  const removeItem = (itemId: string, variant: string | null) => {
    setItems((prev) => prev.filter((i) => !(i.item.id === itemId && i.variant === variant)))
  }

  const updateQuantity = (itemId: string, variant: string | null, quantity: number) => {
    setItems((prev) =>
      prev.map((i) => (i.item.id === itemId && i.variant === variant ? { ...i, quantity } : i))
    )
  }

  const clear = () => setItems([])
  const total = items.reduce((acc, i) => acc + i.quantity, 0)

  return (
    <CartContext.Provider value={{ items, addItem, removeItem, updateQuantity, clear, total }}>
      {children}
    </CartContext.Provider>
  )
}

export function useCart() {
  const ctx = useContext(CartContext)
  if (!ctx) throw new Error("useCart must be used within CartProvider")
  return ctx
}
