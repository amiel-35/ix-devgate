"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./AdminSidebar.module.css";

const NAV = [
  { href: "/admin", label: "Dashboard", icon: "⊞", exact: true },
  { href: "/admin/clients", label: "Clients", icon: "🏢", exact: false },
  { href: "/admin/environments", label: "Environnements", icon: "🌐", exact: false },
  { href: "/admin/access", label: "Accès", icon: "🔑", exact: false },
  { href: "/admin/audit", label: "Audit", icon: "📋", exact: false },
];

export function AdminSidebar() {
  const pathname = usePathname();

  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <div className={styles.logo}>AG</div>
        <div>
          <div className={styles.brandName}>DevGate</div>
          <div className={styles.brandSub}>Back-office</div>
        </div>
      </div>

      <nav className={styles.nav}>
        {NAV.map(({ href, label, icon, exact }) => {
          const active = exact ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`${styles.navItem} ${active ? styles.navItemActive : ""}`}
            >
              <span className={styles.navIcon}>{icon}</span>
              {label}
            </Link>
          );
        })}
      </nav>

      <div className={styles.footer}>
        <div className={styles.footerBadge}>Agence admin</div>
      </div>
    </aside>
  );
}
