"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch } from "@/lib/api"
import type { Template } from "@/lib/types"

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(true)
  const [using, setUsing] = useState<string | null>(null)
  const [error, setError] = useState("")
  const router = useRouter()

  useEffect(() => {
    apiFetch<Template[]>("/orders/templates")
      .then(setTemplates)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const useTemplate = async (templateId: string) => {
    setUsing(templateId)
    setError("")
    try {
      await apiFetch(`/orders/templates/${templateId}/use`, { method: "POST" })
      router.push("/orders")
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка")
      setUsing(null)
    }
  }

  return (
    <div className="max-w-lg mx-auto p-4">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Шаблоны заказов</h1>
        <Link href="/catalog">
          <Button variant="ghost" size="sm">← Каталог</Button>
        </Link>
      </div>

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      {loading ? (
        <p className="text-center text-muted-foreground">Загрузка...</p>
      ) : templates.length === 0 ? (
        <div className="text-center text-muted-foreground">
          <p>Нет шаблонов.</p>
          <p className="text-sm mt-1">
            Сохраните заказ из корзины как шаблон, чтобы быстро повторять его.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {templates.map((t) => (
            <Card key={t.id}>
              <CardContent className="p-3 flex items-center justify-between">
                <div>
                  <p className="font-medium">{t.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {t.items.length} позиций
                  </p>
                </div>
                <Button
                  size="sm"
                  onClick={() => useTemplate(t.id)}
                  disabled={using === t.id}
                >
                  {using === t.id ? "..." : "Использовать"}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
