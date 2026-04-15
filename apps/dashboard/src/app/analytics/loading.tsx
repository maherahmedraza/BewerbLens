import Skeleton from "@/components/ui/Skeleton";
import styles from "./page.module.css";

export default function AnalyticsLoading() {
  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <Skeleton width={160} height={32} borderRadius={6} />
        <Skeleton width="60%" height={18} borderRadius={4} />
      </header>

      <div className={styles.grid}>
        {/* Chart card skeletons */}
        {[...Array(3)].map((_, i) => (
          <div key={i} className={styles.chartCard}>
            <Skeleton width="40%" height={20} borderRadius={4} />
            <div style={{ marginTop: 16 }}>
              <Skeleton width="100%" height={260} borderRadius={8} />
            </div>
          </div>
        ))}

        {/* List cards skeleton */}
        <div className={styles.listCardWrapper}>
          {[...Array(2)].map((_, i) => (
            <div key={i} className={styles.listCard}>
              <Skeleton width="50%" height={20} borderRadius={4} />
              <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 12 }}>
                {[...Array(5)].map((_, j) => (
                  <Skeleton key={j} width="100%" height={44} borderRadius={8} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
