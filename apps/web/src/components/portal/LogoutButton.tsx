"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api/client";
import styles from "./PortalHeader.module.css";

export function LogoutButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function handleLogout() {
    setLoading(true);
    try {
      await authApi.logout();
    } finally {
      router.push("/login");
    }
  }

  return (
    <button className={styles.ghostBtn} onClick={handleLogout} disabled={loading}>
      {loading ? "…" : "Déconnexion"}
    </button>
  );
}
