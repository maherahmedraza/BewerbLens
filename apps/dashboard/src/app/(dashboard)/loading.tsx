import Skeleton from "@/components/ui/Skeleton";
import styles from "@/components/StatsCards.module.css";
import tableStyles from "@/components/ApplicationTable.module.css";

export default function Loading() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "32px", width: "100%" }}>
      {/* Stats Cards Skeleton */}
      <div className={styles.grid}>
        {[...Array(6)].map((_, i) => (
          <div key={i} className={styles.card} style={{ minHeight: "140px" }}>
            <div className={styles.cardHeader}>
              <Skeleton width={40} height={40} borderRadius={10} />
            </div>
            <div className={styles.cardContent} style={{ marginTop: "16px" }}>
              <Skeleton width="40%" height={24} borderRadius={4} />
              <div style={{ marginTop: "8px" }}>
                <Skeleton width="60%" height={16} borderRadius={4} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Table Skeleton */}
      <div className={tableStyles.container}>
        <div className={tableStyles.tableWrapper}>
          <div style={{ padding: "20px" }}>
            <Skeleton width="100%" height={400} borderRadius={8} />
          </div>
        </div>
      </div>
    </div>
  );
}
