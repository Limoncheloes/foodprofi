"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect } from "react"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth"

export default function ManagerLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && (!user || user.role !== "manager")) {
      router.replace("/")
    }
  }, [user, loading, router])

  if (loading || !user) return null

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b px-4 py-2 flex items-center gap-2">
        <span className="font-semibold text-sm mr-2">Менеджер</span>
        <Link href="/manager/orders"><Button variant="ghost" size="sm">Заказы</Button></Link>
        <Link href="/manager/staff"><Button variant="ghost" size="sm">Сотрудники</Button></Link>
        <Link href="/manager/settings"><Button variant="ghost" size="sm">Настройки</Button></Link>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  )
}
