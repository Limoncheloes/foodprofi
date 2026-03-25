"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/lib/auth"
import { CartProvider } from "@/lib/cart"

export default function CookLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && (!user || user.role !== "cook")) {
      router.push("/")
    }
  }, [user, loading, router])

  if (loading || !user) return null

  return <CartProvider>{children}</CartProvider>
}
