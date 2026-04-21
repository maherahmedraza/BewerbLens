"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import styles from "./MonthlyChart.module.css";

interface MonthlyChartProps {
  data: {
    month: string;
    total: number;
    applied: number;
    rejected: number;
    positive: number;
  }[];
  height?: number;
}

export default function MonthlyChart({ data, height = 300 }: MonthlyChartProps) {
  if (data.length === 0) {
    return <div className={styles.empty}>No monthly data</div>;
  }

  const chartData = data.map((d) => ({
    ...d,
    month: new Date(d.month).toLocaleDateString("en-GB", {
      month: "short",
      year: "2-digit",
    }),
  }));

  return (
    <div className={styles.chartShell}>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={chartData} margin={{ top: 8, right: 0, left: -20, bottom: 0 }} barCategoryGap="18%">
          <defs>
            <linearGradient id="colorApplied" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#6366f1" stopOpacity={0.95}/>
              <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.24}/>
            </linearGradient>
            <linearGradient id="colorRejected" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.95}/>
              <stop offset="95%" stopColor="#fb7185" stopOpacity={0.24}/>
            </linearGradient>
            <linearGradient id="colorPositive" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#14b8a6" stopOpacity={0.95}/>
              <stop offset="95%" stopColor="#34d399" stopOpacity={0.22}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="0" vertical={false} stroke="var(--chart-grid)" />
          <XAxis dataKey="month" stroke="var(--chart-axis)" fontSize={12} fontWeight={500} tickLine={false} axisLine={false} />
          <YAxis stroke="var(--chart-axis)" fontSize={12} fontWeight={500} tickLine={false} axisLine={false} />
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
          <Legend
            wrapperStyle={{ paddingTop: "18px", fontSize: "12px", fontWeight: 600 }}
            iconType="circle"
          />
          <Bar dataKey="applied" fill="url(#colorApplied)" name="Applications" radius={[8, 8, 0, 0]} animationDuration={800} />
          <Bar dataKey="rejected" fill="url(#colorRejected)" name="Rejected Responses" radius={[8, 8, 0, 0]} animationDuration={800} />
          <Bar dataKey="positive" fill="url(#colorPositive)" name="Positive Progress" radius={[8, 8, 0, 0]} animationDuration={800} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
