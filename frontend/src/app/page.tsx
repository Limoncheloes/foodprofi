"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuth } from "@/lib/auth"

const schema = z.object({
  phone: z.string().min(1, "Введите номер телефона"),
  password: z.string().min(1, "Введите пароль"),
})

type FormData = z.infer<typeof schema>

const ROLE_HOME: Record<string, string> = {
  cook: "/catalog",
  buyer: "/dashboard",
  warehouse: "/receiving",
  driver: "/routes",
  admin: "/users",
}

export default function LoginPage() {
  const { login, user, loading } = useAuth()
  const router = useRouter()
  const [error, setError] = useState("")

  const { register, handleSubmit, formState: { errors, isSubmitting } } =
    useForm<FormData>({ resolver: zodResolver(schema) })

  // Redirect if already logged in
  useEffect(() => {
    if (!loading && user) {
      router.push(ROLE_HOME[user.role] ?? "/")
    }
  }, [user, loading, router])

  const onSubmit = async (data: FormData) => {
    try {
      setError("")
      await login(data.phone, data.password)
      // redirect will happen via useEffect when user state updates
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка входа")
    }
  }

  if (loading) return null

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl text-center">SupplyFlow</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="phone">Телефон</Label>
              <Input
                id="phone"
                placeholder="+996700000000"
                {...register("phone")}
              />
              {errors.phone && (
                <p className="text-sm text-red-500">{errors.phone.message}</p>
              )}
            </div>
            <div className="space-y-1">
              <Label htmlFor="password">Пароль</Label>
              <Input
                id="password"
                type="password"
                {...register("password")}
              />
              {errors.password && (
                <p className="text-sm text-red-500">{errors.password.message}</p>
              )}
            </div>
            {error && <p className="text-sm text-red-500 text-center">{error}</p>}
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? "Вход..." : "Войти"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
