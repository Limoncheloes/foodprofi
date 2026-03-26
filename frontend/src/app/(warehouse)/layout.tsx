"use client"

import { useEffect } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth"

export default function WarehouseLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && (!user || user.role !== "warehouse")) {
      router.push("/")
    }
  }, [user, loading, router])

  if (loading || !user || user.role !== "warehouse") return null

  return (
    <div className="max-w-2xl mx-auto">
      <nav className="flex gap-2 p-4 border-b mb-2">
        <Link href="/receiving">
          <Button variant="ghost" size="sm">Приём</Button>
        </Link>
        <Link href="/inventory">
          <Button variant="ghost" size="sm">Склад</Button>
        </Link>
        <Link href="/history">
          <Button variant="ghost" size="sm">История</Button>
        </Link>
      </nav>
      {children}
    </div>
  )
}
