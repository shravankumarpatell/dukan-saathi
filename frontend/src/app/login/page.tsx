"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Kbd } from "@/components/ui/kbd";
import { Loader2 } from "lucide-react";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("admin@demo.tileos");
  const [password, setPassword] = useState("Admin@123");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      toast.success("Welcome back");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="grain relative hidden flex-col justify-between bg-sidebar p-10 lg:flex">
        <div className="flex items-center gap-2">
          <div className="grid size-9 place-items-center rounded-lg bg-primary text-primary-foreground font-heading font-bold">T</div>
          <span className="font-heading text-lg font-semibold">TileOS</span>
        </div>
        <div className="max-w-md space-y-6">
          <h1 className="font-heading text-4xl font-semibold leading-tight tracking-tight">The operating system for tile, sanitary & building-material businesses.</h1>
          <p className="text-muted-foreground">Accounting that is always correct. Inventory by batch, shade and calibre. Invoices in under 30 seconds - entirely from the keyboard.</p>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li className="flex items-center gap-2">
              <Kbd>Ctrl</Kbd>
              <Kbd>K</Kbd> <span>jump anywhere with the command palette</span>
            </li>
            <li className="flex items-center gap-2">
              <Kbd>G</Kbd> <span>then</span> <Kbd>S</Kbd> <span>go to sales invoices</span>
            </li>
            <li className="flex items-center gap-2">
              <Kbd>?</Kbd> <span>see every shortcut</span>
            </li>
          </ul>
        </div>
        <p className="text-xs text-muted-foreground">Double-entry ledger &middot; GST &middot; Multi-company &middot; Keyboard-first</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle className="font-heading text-xl">Sign in</CardTitle>
            <CardDescription>Use your company credentials to continue.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={submit} className="space-y-4" data-testid="login-form">
              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" autoFocus autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="login-email-input" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password">Password</Label>
                <Input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required data-testid="login-password-input" />
              </div>
              {error && (
                <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive" role="alert" data-testid="login-error">
                  {error}
                </p>
              )}
              <Button type="submit" className="w-full" size="lg" disabled={busy} data-testid="login-form-submit-button">
                {busy && <Loader2 className="size-4 animate-spin" />} Sign in
              </Button>
              <div className="rounded-md bg-muted p-3 text-xs text-muted-foreground">
                <div className="mb-1 font-medium text-foreground">Demo accounts</div>
                <div>
                  Owner: <span className="font-mono">admin@demo.tileos / Admin@123</span>
                </div>
                <div>
                  Accountant: <span className="font-mono">accounts@demo.tileos / Demo@123</span>
                </div>
                <div>
                  Sales: <span className="font-mono">sales@demo.tileos / Demo@123</span>
                </div>
                <div>
                  Second tenant: <span className="font-mono">owner@ganesh.tileos / Admin@123</span>
                </div>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
