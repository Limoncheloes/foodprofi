export type UserRole = "cook" | "buyer" | "warehouse" | "driver" | "admin"

export interface User {
  id: string
  name: string
  phone: string
  role: UserRole
  restaurant_id: string | null
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface Category {
  id: string
  name: string
  sort_order: number
}

export interface CatalogItem {
  id: string
  category_id: string
  name: string
  unit: "kg" | "pcs" | "liters" | "packs"
  variants: string[]
  is_active: boolean
}

export interface OrderItem {
  id: string
  catalog_item_id: string
  quantity: number
  variant: string | null
  note: string | null
}

export interface Order {
  id: string
  user_id: string
  restaurant_id: string
  status: string
  is_urgent: boolean
  created_at: string
  items: OrderItem[]
}

export interface Restaurant {
  id: string
  name: string
  address: string
  contact_phone: string
  is_active: boolean
}

export interface ApiError {
  detail: string
  code?: string
}
