"use client"

import { useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch } from "@/lib/api"
import type { User } from "@/lib/types"

const ROLE_LABEL: Record<string, string> = {
  cook: "Повар", buyer: "Закупщик", warehouse: "Кладовщик",
  driver: "Водитель", admin: "Администратор",
}

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch<User[]>("/admin/users")
      .then(setUsers)
      .catch(() => setLoading(false))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Пользователи</h1>
      {loading ? (
        <p className="text-muted-foreground">Загрузка...</p>
      ) : (
        <div className="space-y-2">
          {users.map((u) => (
            <Card key={u.id}>
              <CardContent className="p-3 flex items-center justify-between">
                <div>
                  <p className="font-medium">{u.name}</p>
                  <p className="text-sm text-muted-foreground">{u.phone}</p>
                </div>
                <Badge>{ROLE_LABEL[u.role] ?? u.role}</Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
