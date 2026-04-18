import { createClient } from "@/lib/supabase/server";
import { STATUS_COLORS, type ApplicationStats } from "@/lib/types";
import styles from "./StatsCards.module.css";
import { 
  BriefcaseIcon, 
  ClockIcon, 
  XCircleIcon, 
  CheckCircleIcon,
  UserGroupIcon,
  TrophyIcon
} from "@heroicons/react/24/outline";

async function getStats(): Promise<ApplicationStats | null> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("application_stats")
    .select("*")
    .single();

  if (error || !data) return null;
  return data as ApplicationStats;
}

export default async function StatsCards() {
  const stats = await getStats();

  if (!stats) {
    return <div className={styles.empty}>No data available</div>;
  }

  const cards = [
    { label: "Total Applications", value: stats.total_applications, color: "var(--accent-blue)", icon: BriefcaseIcon },
    { label: "Pending", value: stats.applied, color: "var(--accent-orange)", icon: ClockIcon },
    { label: "Rejected", value: stats.rejected, color: "var(--accent-red)", icon: XCircleIcon },
    { label: "Positive Response", value: stats.positive_response, color: "var(--accent-green)", icon: CheckCircleIcon },
    { label: "Interview", value: stats.interview, color: "#6366f1", icon: UserGroupIcon },
    { label: "Offer", value: stats.offer, color: "#a855f7", icon: TrophyIcon },
  ];

  return (
    <div className={styles.container}>
      <div className={styles.grid}>
        {cards.map((card) => (
          <div key={card.label} className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.iconWrapper} style={{ backgroundColor: `${card.color}15`, color: card.color }}>
                <card.icon className={styles.icon} />
              </div>
            </div>
            <div className={styles.cardContent}>
              <div className={styles.value}>{card.value}</div>
              <div className={styles.label}>{card.label}</div>
            </div>
          </div>
        ))}
      </div>
      
      <div className={styles.statsRow}>
        <div className={styles.miniCard}>
          <div className={styles.miniLabel}>Response Rate</div>
          <div className={styles.miniValue} style={{ color: "var(--accent-blue)" }}>
            {stats.response_rate_pct ?? 0}%
          </div>
          <div className={styles.progressTrack}>
            <div className={styles.progressBar} style={{ width: `${stats.response_rate_pct}%`, backgroundColor: "var(--accent-blue)" }} />
          </div>
        </div>
        <div className={styles.miniCard}>
          <div className={styles.miniLabel}>Success Rate</div>
          <div className={styles.miniValue} style={{ color: "var(--accent-green)" }}>
            {stats.success_rate_pct ?? 0}%
          </div>
          <div className={styles.progressTrack}>
            <div className={styles.progressBar} style={{ width: `${stats.success_rate_pct}%`, backgroundColor: "var(--accent-green)" }} />
          </div>
        </div>
      </div>
    </div>
  );
}
