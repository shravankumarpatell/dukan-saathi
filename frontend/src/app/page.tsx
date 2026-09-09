"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function Home() {
  const { ready, authenticated } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!ready) return;
    router.replace(authenticated ? "/dashboard" : "/login");
  }, [ready, authenticated, router]);
  return null;
}
