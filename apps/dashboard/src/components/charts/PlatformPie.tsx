"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import styles from "./PlatformPie.module.css";

interface PlatformPieProps {
  data: { platform: string; count: number }[];
}

const COLORS = [
  "var(--chart-applied)",
  "var(--chart-interview)",
  "var(--chart-positive)",
  "var(--chart-offer)",
  "var(--accent-blue)",
  "var(--accent-purple)",
  "var(--chart-applied-light)",
  "var(--chart-rejected)",
  "var(--accent-green)",
];

export default function PlatformPie({ data }: PlatformPieProps) {
  if (data.length === 0) {
    return <div className={styles.empty}>No platform data</div>;
  }

  return (
    <div className={styles.container}>
      <ResponsiveContainer width="100%" height={320}>
        <PieChart margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
          <Pie
            data={data}
            dataKey="count"
            nameKey="platform"
            cx="50%"
            cy="45%"
            outerRadius={100}
            innerRadius={70}
            paddingAngle={4}
            labelLine={false}
            label={false}
          >
            {data.map((_entry, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={COLORS[index % COLORS.length]} 
                stroke="var(--bg-card)"
                strokeWidth={2}
                style={{ outline: "none" }}
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
          <Legend 
            verticalAlign="bottom" 
            align="center" 
            layout="horizontal" 
            iconType="circle" 
            wrapperStyle={{ 
              paddingTop: "30px",
              fontSize: "13px",
              fontWeight: 600,
              color: "var(--text-secondary)"
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
