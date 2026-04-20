"use client";

import { useState, useMemo } from "react";
import { EnvCard } from "@/components/portal/EnvCard";
import type { EnvironmentItem, MeResponse } from "@/lib/api/server";
import styles from "./portal.module.css";

const KIND_FILTERS = [
  { label: "Tous", value: "" },
  { label: "Staging", value: "staging" },
  { label: "Preview", value: "preview" },
  { label: "Dev", value: "dev" },
];

interface Props {
  user: MeResponse;
  environments: EnvironmentItem[];
}

export function PortalDashboard({ user, environments }: Props) {
  const [search, setSearch] = useState("");
  const [kindFilter, setKindFilter] = useState("");

  const filtered = useMemo(() => {
    return environments.filter((e) => {
      const matchKind = kindFilter === "" || e.kind === kindFilter;
      const q = search.toLowerCase();
      const matchSearch =
        q === "" ||
        e.organization_name.toLowerCase().includes(q) ||
        e.project_name.toLowerCase().includes(q) ||
        e.environment_name.toLowerCase().includes(q);
      return matchKind && matchSearch;
    });
  }, [environments, search, kindFilter]);

  const firstName = (user.display_name ?? user.email).split(/[\s@]/)[0];

  if (environments.length === 0) {
    return (
      <div className={styles.main}>
        <div className={styles.emptyWrap}>
          <div className={styles.emptyCard}>
            <div className={styles.emptyIcon}>📭</div>
            <h1 className={styles.emptyTitle}>Aucune ressource visible</h1>
            <p className={styles.emptyDesc}>
              Votre compte est bien reconnu, mais aucune ressource active n&apos;est
              disponible pour le moment.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.main}>
      <div className={styles.banner}>
        <div className={styles.bannerText}>
          <h2>Bonjour {firstName}, vos accès sont prêts.</h2>
          <p>Retrouvez ci-dessous les ressources disponibles sur votre compte.</p>
        </div>
        <div className={styles.metrics}>
          <div className={styles.metric}>
            <div className={styles.metricValue}>{environments.length}</div>
            <div className={styles.metricLabel}>Environnements</div>
          </div>
        </div>
      </div>

      <div className={styles.pageTitle}>Mes environnements</div>
      <div className={styles.pageSub}>
        {filtered.length} ressource{filtered.length !== 1 ? "s" : ""} accessible
        {filtered.length !== 1 ? "s" : ""}
      </div>

      <div className={styles.filters}>
        <input
          className={styles.searchInput}
          type="text"
          placeholder="Rechercher…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {KIND_FILTERS.map((f) => (
          <button
            key={f.value}
            className={`${styles.chip} ${kindFilter === f.value ? styles.chipActive : ""}`}
            onClick={() => setKindFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className={styles.grid}>
        {filtered.map((env) => (
          <EnvCard key={env.id} env={env} />
        ))}
      </div>
    </div>
  );
}
