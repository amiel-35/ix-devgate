import Link from "next/link";
import { StateCard } from "@/components/auth/StateCard";
import { Button } from "@/components/shared/Button";

export default function SessionExpiredPage() {
  return (
    <div className="auth-standalone-bg">
      <StateCard
        icon="⏱"
        tone="warn"
        title="Votre session a expiré"
        description="Vous avez été déconnecté automatiquement après 7 jours. Votre compte est intact, reconnectez-vous pour retrouver vos ressources."
        footer="Pas de panique — vos accès sont conservés."
      >
        <Link href="/login" style={{ width: "100%" }}>
          <Button>Se reconnecter</Button>
        </Link>
      </StateCard>
    </div>
  );
}
