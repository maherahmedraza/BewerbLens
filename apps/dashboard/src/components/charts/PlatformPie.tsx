"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import styles from "./PlatformPie.module.css";

interface PlatformPieProps {
  data: { platform: string; count: number }[];
  height?: number;
}

const COLORS = [
  "#6366f1",
  "#8b5cf6",
  "#14b8a6",
  "#f59e0b",
  "#3b82f6",
  "#ec4899",
  "#06b6d4",
  "#f43f5e",
  "#84cc16",
];

export default function PlatformPie({ data, height = 320 }: PlatformPieProps) {
  if (data.length === 0) {
    return <div className={styles.empty}>No platform data</div>;
  }

  const maxSlices = 7;
  const baseData = [...data].sort((left, right) => right.count - left.count);
  const primary = baseData.slice(0, maxSlices);
  const remainder = baseData.slice(maxSlices);
  const otherCount = remainder.reduce((sum, entry) => sum + entry.count, 0);
  const chartData = otherCount > 0 ? [...primary, { platform: "Other", count: otherCount }] : primary;
  const total = chartData.reduce((sum, entry) => sum + entry.count, 0);

  return (
    <div className={styles.wrapper}>
      <div className={styles.chartArea}>
        <ResponsiveContainer width="100%" height={height}>
          <PieChart margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
          <Pie
            data={chartData}
            dataKey="count"
            nameKey="platform"
            cx="50%"
            cy="50%"
            outerRadius={112}
            innerRadius={74}
            paddingAngle={3}
            labelLine={false}
            label={false}
            shapeRendering="geometricPrecision"
          >
            {chartData.map((_entry, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={COLORS[index % COLORS.length]} 
                stroke="var(--bg-card)"
                strokeWidth={2}
                style={{ outline: "none", shapeRendering: "geometricPrecision" }}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--bg-card)",
              border: "1px solid var(--border-color)",
              borderRadius: "var(--radius)",
              boxShadow: "var(--shadow-md)",
              fontSize: "13px",
              fontWeight: 600,
              padding: "8px 12px"
            }}
              labelStyle={{ color: "var(--text-primary)", marginBottom: "4px" }}
              itemStyle={{ fontWeight: 600, color: "var(--text-secondary)" }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className={styles.centerBadge}>
          <div className={styles.centerBadgeInner}>
            <span className={styles.centerValue}>{total}</span>
            <span className={styles.centerLabel}>active apps</span>
          </div>
        </div>
      </div>

      <ul className={styles.legendList}>
        {chartData.map((entry, index) => (
          <li key={entry.platform} className={styles.legendItem}>
            <span className={styles.legendMeta}>
              <span
                className={styles.legendDot}
                style={{ backgroundColor: COLORS[index % COLORS.length] }}
              />
              <span className={styles.legendName}>{entry.platform}</span>
            </span>
            <span className={styles.legendCount}>{entry.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
