export type UserRole = "cook" | "buyer" | "warehouse" | "driver" | "admin" | "manager" | "curator"

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
  item_name: string
  quantity: number
  variant: string | null
  note: string | null
}

export interface Order {
  id: string
  user_id: string
  user_name: string
  restaurant_id: string
  restaurant_name: string
  restaurant_address: string
  restaurant_phone: string
  status: string
  is_urgent: boolean
  deadline: string | null
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

// Aggregation

export interface AggregationRestaurantNeed {
  restaurant_id: string
  quantity: number
  variant: string | null
}

export interface AggregationItem {
  catalog_item_id: string
  name: string
  unit: string
  total_needed: number
  in_stock: number
  to_buy: number
  restaurants: AggregationRestaurantNeed[]
}

export interface AggregationCategory {
  category_id: string
  category_name: string
  items: AggregationItem[]
}

export interface AggregationSummary {
  date: string
  categories: AggregationCategory[]
}

// Order Templates

export interface TemplateItem {
  id: string
  catalog_item_id: string
  quantity: number
  variant: string | null
  note: string | null
}

export interface Template {
  id: string
  user_id: string
  restaurant_id: string
  name: string
  created_at: string
  items: TemplateItem[]
}

// Warehouse Inventory

export interface InventoryItem {
  catalog_item_id: string
  name: string
  unit: string
  quantity: number
  updated_at: string
}

// Inventory Log

export interface InventoryLogEntry {
  id: string
  catalog_item_id: string
  item_name: string
  delta: number
  reason: "received" | "consumed" | "adjusted"
  user_name: string
  note: string | null
  created_at: string
}

export interface ManagerOrder {
  id: string
  user_id: string
  user_name: string
  restaurant_id: string
  status: string
  is_urgent: boolean
  deadline: string | null
  created_at: string
  items: OrderItem[]
}

export interface StaffMember {
  id: string
  name: string
  phone: string
  role: string
  restaurant_id: string | null
}

export interface RestaurantSettings {
  restaurant_id: string
  requires_approval: boolean
}

// Procurement Module

export interface ProcurementItem {
  id: string
  order_id: string
  catalog_item_id: string | null
  raw_name: string | null
  display_name: string
  quantity_ordered: number
  quantity_received: number | null
  unit: string
  status: "pending_curator" | "assigned" | "purchased" | "not_found" | "substituted"
  buyer_id: string | null
  category_id: string | null
  curator_note: string | null
  substitution_note: string | null
  is_catalog_item: boolean
  created_at: string
}

export interface ProcurementOrder {
  id: string
  restaurant_id: string
  restaurant_name: string
  user_id: string
  user_name: string
  status: string
  created_at: string
  items: ProcurementItem[]
}

export interface BuyerItemRead {
  id: string
  order_id: string
  display_name: string
  quantity_ordered: number
  quantity_received: number | null
  unit: string
  restaurant_name: string
  order_date: string
}

export interface WhatsAppUrls {
  primary: string | null
  fallback: string
}

export interface SubmitOrderResponse {
  order: ProcurementOrder
  whatsapp: WhatsAppUrls
}

export interface PendingItemRead {
  id: string
  order_id: string
  display_name: string
  raw_name: string | null
  quantity_ordered: number
  unit: string
  is_catalog_item: boolean
  restaurant_name: string
  created_at: string
}
