"use client"

import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { apiFetch } from "@/lib/api"
import type { Restaurant } from "@/lib/types"

export default function RestaurantsPage() {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState("")
  const { register, handleSubmit, reset } = useForm<Omit<Restaurant, "id" | "is_active">>()

  const load = () => {
    apiFetch<Restaurant[]>("/admin/restaurants")
      .then(setRestaurants)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const onSubmit = async (data: Omit<Restaurant, "id" | "is_active">) => {
    setError("")
    try {
      await apiFetch("/admin/restaurants", { method: "POST", body: JSON.stringify(data) })
      reset()
      setAdding(false)
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка при сохранении")
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Рестораны</h1>
        <Button size="sm" onClick={() => setAdding(!adding)}>
          {adding ? "Отмена" : "Добавить"}
        </Button>
      </div>

      {adding && (
        <Card className="mb-4">
          <CardContent className="p-4">
            {error && <p className="text-sm text-red-500 mb-2">{error}</p>}
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
              <div>
                <Label>Название</Label>
                <Input {...register("name", { required: true })} />
              </div>
              <div>
                <Label>Адрес</Label>
                <Input {...register("address", { required: true })} />
              </div>
              <div>
                <Label>Телефон</Label>
                <Input {...register("contact_phone", { required: true })} />
              </div>
              <Button type="submit" className="w-full">Сохранить</Button>
            </form>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <p className="text-muted-foreground">Загрузка...</p>
      ) : (
        <div className="space-y-2">
          {restaurants.map((r) => (
            <Card key={r.id}>
              <CardContent className="p-3">
                <p className="font-medium">{r.name}</p>
                <p className="text-sm text-muted-foreground">{r.address}</p>
                <p className="text-sm text-muted-foreground">{r.contact_phone}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
