import Link from "next/link";
import { StateCard } from "@/components/auth/StateCard";
import { Button } from "@/components/shared/Button";

export default function AccessDeniedPage() {
  return (
    <div className="auth-standalone-bg">
      <StateCard
        icon="✕"
        tone="danger"
        title="Accès non autorisé"
        description="Votre compte ne dispose pas d'un accès actif à cette ressource. Si vous pensez que c'est une erreur, contactez l'agence."
      >
        <Link href="/portal" style={{ width: "100%" }}>
          <Button>Retour à mon portail</Button>
        </Link>
        <Button variant="secondary">Contacter l&apos;agence</Button>
      </StateCard>
    </div>
  );
}
