"use client"

import { useEffect } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth"

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && (!user || user.role !== "admin")) {
      router.push("/")
    }
  }, [user, loading, router])

  if (loading || !user || user.role !== "admin") return null

  return (
    <div className="max-w-2xl mx-auto p-4">
      <nav className="flex gap-2 mb-6">
        <Link href="/users"><Button variant="ghost" size="sm">Пользователи</Button></Link>
        <Link href="/restaurants"><Button variant="ghost" size="sm">Рестораны</Button></Link>
        <Link href="/admin-catalog"><Button variant="ghost" size="sm">Каталог</Button></Link>
      </nav>
      {children}
    </div>
  )
}
