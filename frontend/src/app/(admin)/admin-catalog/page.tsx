"use client"

import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { apiFetch } from "@/lib/api"
import type { CatalogItem, Category } from "@/lib/types"

interface ItemForm {
  category_id: string
  name: string
  unit: string
  variants: string
}

export default function AdminCatalogPage() {
  const [categories, setCategories] = useState<Category[]>([])
  const [items, setItems] = useState<CatalogItem[]>([])
  const [adding, setAdding] = useState(false)
  const { register, handleSubmit, reset } = useForm<ItemForm>()

  const load = async () => {
    try {
      const [cats, itms] = await Promise.all([
        apiFetch<Category[]>("/catalog/categories"),
        apiFetch<CatalogItem[]>("/catalog/items"),
      ])
      setCategories(cats)
      setItems(itms)
    } catch {
      // silent on load error
    }
  }

  useEffect(() => { load() }, [])

  const onSubmit = async (data: ItemForm) => {
    try {
      await apiFetch("/catalog/items", {
        method: "POST",
        body: JSON.stringify({
          ...data,
          variants: data.variants ? data.variants.split(",").map((v) => v.trim()) : [],
        }),
      })
      reset()
      setAdding(false)
      load()
    } catch {
      // silent — form stays open
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Каталог</h1>
        <Button size="sm" onClick={() => setAdding(!adding)}>
          {adding ? "Отмена" : "Добавить"}
        </Button>
      </div>

      {adding && (
        <Card className="mb-4">
          <CardContent className="p-4">
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
              <div>
                <Label>Категория</Label>
                <select {...register("category_id", { required: true })}
                  className="w-full border rounded px-2 py-1 text-sm">
                  {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
              <div>
                <Label>Название</Label>
                <Input {...register("name", { required: true })} />
              </div>
              <div>
                <Label>Единица</Label>
                <select {...register("unit", { required: true })}
                  className="w-full border rounded px-2 py-1 text-sm">
                  <option value="kg">кг</option>
                  <option value="pcs">шт</option>
                  <option value="liters">л</option>
                  <option value="packs">уп</option>
                </select>
              </div>
              <div>
                <Label>Варианты (через запятую)</Label>
                <Input {...register("variants")} placeholder="с костью, без кости" />
              </div>
              <Button type="submit" className="w-full">Сохранить</Button>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="space-y-2">
        {items.map((item) => (
          <Card key={item.id}>
            <CardContent className="p-3 flex items-center justify-between">
              <div>
                <p className="font-medium">{item.name}</p>
                <p className="text-sm text-muted-foreground">
                  {categories.find((c) => c.id === item.category_id)?.name}
                </p>
              </div>
              <div className="flex gap-1 flex-wrap justify-end">
                {item.variants.map((v) => <Badge key={v} variant="outline">{v}</Badge>)}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
