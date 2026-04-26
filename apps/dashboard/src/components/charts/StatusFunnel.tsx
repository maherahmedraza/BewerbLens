"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import styles from "./StatusFunnel.module.css";

interface StatusFunnelProps {
  data: { stage: string; count: number }[];
  height?: number;
}

const FUNNEL_COLORS: Record<string, { main: string; light: string }> = {
  "Applications Submitted": { main: "var(--chart-submitted)", light: "var(--chart-submitted-soft)" },
  "Awaiting Response": { main: "var(--chart-applied)", light: "var(--chart-applied-soft)" },
  "Positive Response": { main: "var(--chart-positive)", light: "var(--chart-positive-soft)" },
  Interview: { main: "var(--chart-interview)", light: "var(--chart-interview-soft)" },
  Offer: { main: "var(--chart-offer)", light: "var(--chart-offer-soft)" },
};

export default function StatusFunnel({ data, height = 250 }: StatusFunnelProps) {
  if (data.length === 0) {
    return <div className={styles.empty}>No funnel data</div>;
  }

  return (
    <div
      className={styles.chartShell}
      role="img"
      aria-label="Application conversion funnel from submitted applications to offers"
    >
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout="vertical" margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            {data.map((entry, index) => (
              <linearGradient key={`grad-${index}`} id={`grad-${index}`} x1="0" y1="0" x2="1" y2="0">
                <stop offset="5%" stopColor={(FUNNEL_COLORS[entry.stage] || { main: "var(--chart-applied)" }).main} stopOpacity={0.95}/>
                <stop offset="95%" stopColor={(FUNNEL_COLORS[entry.stage] || { main: "var(--chart-applied)" }).main} stopOpacity={0.3}/>
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="0" horizontal={false} vertical={true} stroke="var(--chart-grid)" />
          <XAxis type="number" stroke="var(--chart-axis)" fontSize={12} fontWeight={500} tickLine={false} axisLine={false} />
          <YAxis dataKey="stage" type="category" stroke="var(--text-primary)" fontSize={12} width={140} tickLine={false} axisLine={false} fontWeight={600} />
          <Tooltip
            cursor={{ fill: "var(--bg-hover)", opacity: 0.4 }}
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
          <Bar dataKey="count" radius={[0, 8, 8, 0]} animationDuration={800} shapeRendering="geometricPrecision">
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={`url(#grad-${index})`} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
