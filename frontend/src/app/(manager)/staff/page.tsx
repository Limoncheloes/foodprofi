"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { apiFetch } from "@/lib/api"
import type { StaffMember } from "@/lib/types"

const ROLE_LABEL: Record<string, string> = {
  cook: "Повар",
  manager: "Менеджер",
}

export default function StaffPage() {
  const [staff, setStaff] = useState<StaffMember[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [phone, setPhone] = useState("")
  const [name, setName] = useState("")
  const [password, setPassword] = useState("")
  const [role, setRole] = useState<"cook" | "manager">("cook")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const load = async () => {
    try {
      const data = await apiFetch("/manager/staff") as StaffMember[]
      setStaff(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const addStaff = async () => {
    if (!phone || !name || !password) return
    setSaving(true)
    setError("")
    try {
      await apiFetch("/manager/staff", {
        method: "POST",
        body: JSON.stringify({ phone, name, password, role }),
      })
      setShowForm(false)
      setPhone(""); setName(""); setPassword("")
      await load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка")
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="p-4 text-muted-foreground">Загрузка...</div>

  return (
    <div className="max-w-lg mx-auto p-4">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Сотрудники</h1>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Отмена" : "+ Добавить"}
        </Button>
      </div>

      {showForm && (
        <Card className="mb-4">
          <CardContent className="p-3 space-y-2">
            <Input placeholder="Телефон (+996...)" value={phone} onChange={(e) => setPhone(e.target.value)} />
            <Input placeholder="Имя" value={name} onChange={(e) => setName(e.target.value)} />
            <Input placeholder="Пароль" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <div className="flex gap-2">
              <Button
                variant={role === "cook" ? "default" : "outline"}
                size="sm" className="flex-1"
                onClick={() => setRole("cook")}
              >Повар</Button>
              <Button
                variant={role === "manager" ? "default" : "outline"}
                size="sm" className="flex-1"
                onClick={() => setRole("manager")}
              >Менеджер</Button>
            </div>
            {error && <p className="text-sm text-red-500">{error}</p>}
            <Button className="w-full" onClick={addStaff} disabled={saving}>
              {saving ? "Сохранение..." : "Добавить сотрудника"}
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="space-y-2">
        {staff.map((s) => (
          <Card key={s.id}>
            <CardContent className="p-3 flex items-center justify-between">
              <div>
                <p className="font-medium text-sm">{s.name}</p>
                <p className="text-xs text-muted-foreground">{s.phone}</p>
              </div>
              <span className="text-xs text-muted-foreground">{ROLE_LABEL[s.role] ?? s.role}</span>
            </CardContent>
          </Card>
        ))}
        {staff.length === 0 && <p className="text-muted-foreground text-sm">Нет сотрудников</p>}
      </div>
    </div>
  )
}
