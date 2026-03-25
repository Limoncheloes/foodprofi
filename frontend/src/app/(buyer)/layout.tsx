"use client"

import { useEffect } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth"

export default function BuyerLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && (!user || user.role !== "buyer")) {
      router.push("/")
    }
  }, [user, loading, router])

  if (loading || !user || user.role !== "buyer") return null

  return (
    <div className="max-w-2xl mx-auto">
      <nav className="flex gap-2 p-4 border-b mb-2">
        <Link href="/dashboard">
          <Button variant="ghost" size="sm">Сводка</Button>
        </Link>
        <Link href="/purchase">
          <Button variant="ghost" size="sm">Закупить</Button>
        </Link>
      </nav>
      {children}
    </div>
  )
}
