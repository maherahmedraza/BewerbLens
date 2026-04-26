"use client";

import { ResponsiveContainer, Sankey, Tooltip } from "recharts";
import type {
  LinkProps as RechartsSankeyLinkProps,
  NodeProps as RechartsSankeyNodeProps,
} from "recharts/types/chart/Sankey";

import type { StatusFlowSankeyData } from "@/lib/types";

import styles from "./StatusFlowSankey.module.css";

interface StatusFlowSankeyProps {
  data: StatusFlowSankeyData;
  height?: number;
}

type SankeyNodePayload = StatusFlowSankeyData["nodes"][number];

const STATUS_STYLES: Record<string, { fill: string; stroke: string }> = {
  "Applications Submitted": { fill: "var(--chart-submitted)", stroke: "var(--chart-submitted)" },
  Applied: { fill: "var(--chart-applied)", stroke: "var(--chart-applied)" },
  "Positive Response": { fill: "var(--chart-positive)", stroke: "var(--chart-positive)" },
  Interview: { fill: "var(--chart-interview)", stroke: "var(--chart-interview)" },
  Offer: { fill: "var(--chart-offer)", stroke: "var(--chart-offer)" },
  Rejected: { fill: "var(--chart-rejected)", stroke: "var(--chart-rejected)" },
};

function getStatusStyle(status: string) {
  return STATUS_STYLES[status] || { fill: "#94a3b8", stroke: "#64748b" };
}

function getNodePayload(payload: RechartsSankeyNodeProps["payload"] | undefined): SankeyNodePayload | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const name =
    "name" in payload && typeof payload.name === "string" ? payload.name : null;

  if (!name) {
    return null;
  }

  const status =
    "status" in payload && typeof payload.status === "string" ? payload.status : name;
  const depth =
    "depth" in payload && typeof payload.depth === "number" ? payload.depth : 0;
  const count =
    "count" in payload && typeof payload.count === "number" ? payload.count : 0;

  return { name, status, depth, count };
}

function SankeyNode({ x, y, width, height, payload }: RechartsSankeyNodeProps) {
  const nodePayload = getNodePayload(payload);

  if (x == null || y == null || width == null || height == null || !nodePayload) {
    return null;
  }

  const { fill, stroke } = getStatusStyle(nodePayload.status);
  const labelX = nodePayload.depth === 0 ? x - 14 : x + width + 14;
  const textAnchor = nodePayload.depth === 0 ? "end" : "start";
  const labelY = y + height / 2 - 6;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={Math.max(height, 6)}
        rx={8}
        fill={fill}
        fillOpacity={0.92}
        stroke={stroke}
        strokeWidth={1.5}
        shapeRendering="geometricPrecision"
      />
      <text
        x={labelX}
        y={labelY}
        textAnchor={textAnchor}
        fontSize={12}
        fontWeight={700}
        fill="var(--text-primary)"
      >
        <tspan x={labelX}>{nodePayload.name}</tspan>
        <tspan x={labelX} dy="1.15em" fontSize={11} fontWeight={600} fill="var(--text-secondary)">
          {nodePayload.count}
        </tspan>
      </text>
    </g>
  );
}

function SankeyLink({
  sourceX,
  targetX,
  sourceY,
  targetY,
  sourceControlX,
  targetControlX,
  linkWidth,
  payload,
}: RechartsSankeyLinkProps) {
  if (
    sourceX == null ||
    targetX == null ||
    sourceY == null ||
    targetY == null ||
    sourceControlX == null ||
    targetControlX == null ||
    linkWidth == null
  ) {
    return <path d="" fill="none" stroke="none" />;
  }

  const targetPayload = getNodePayload(payload?.target);
  const { fill } = getStatusStyle(targetPayload?.status || "");
  const path = [
    `M${sourceX},${sourceY}`,
    `C${sourceControlX},${sourceY}`,
    `${targetControlX},${targetY}`,
    `${targetX},${targetY}`,
  ].join(" ");

  return (
    <path
      d={path}
      fill="none"
      stroke={fill}
      strokeOpacity={0.28}
      strokeWidth={Math.max(linkWidth, 1)}
      shapeRendering="geometricPrecision"
    />
  );
}

export default function StatusFlowSankey({ data, height = 380 }: StatusFlowSankeyProps) {
  if (data.nodes.length === 0 || data.links.length === 0) {
    return <div className={styles.empty}>No status flow data yet.</div>;
  }

  return (
    <div className={styles.wrapper}>
      <div
        className={styles.chartShell}
        role="img"
        aria-label="Status flow chart showing movement from submitted applications to interview, rejection, and offer outcomes"
      >
        <ResponsiveContainer width="100%" height={height}>
          <Sankey
            data={data}
            node={SankeyNode}
            link={SankeyLink}
            nodePadding={32}
            nodeWidth={20}
            sort
            margin={{ top: 20, right: 180, bottom: 20, left: 160 }}
          >
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--bg-card)",
                border: "1px solid var(--border-color)",
                borderRadius: "var(--radius)",
                boxShadow: "var(--shadow-md)",
                fontSize: "13px",
                fontWeight: 600,
                padding: "8px 12px",
              }}
              labelStyle={{ color: "var(--text-primary)", marginBottom: "4px" }}
              itemStyle={{ fontWeight: 600, color: "var(--text-secondary)" }}
            />
          </Sankey>
        </ResponsiveContainer>
      </div>

      <div className={styles.summaryRow}>
        <div className={styles.summaryChip}>
          <span className={styles.summaryLabel}>Tracked</span>
          <span className={styles.summaryValue}>{data.summary.total}</span>
        </div>
        <div className={styles.summaryChip}>
          <span className={styles.summaryLabel}>Still active</span>
          <span className={styles.summaryValue}>{data.summary.active}</span>
        </div>
        <div className={styles.summaryChip}>
          <span className={styles.summaryLabel}>Positive path</span>
          <span className={styles.summaryValue}>{data.summary.progressing}</span>
        </div>
        <div className={styles.summaryChip}>
          <span className={styles.summaryLabel}>Rejected</span>
          <span className={styles.summaryValue}>{data.summary.rejected}</span>
        </div>
        <div className={styles.summaryChip}>
          <span className={styles.summaryLabel}>Offers</span>
          <span className={styles.summaryValue}>{data.summary.offers}</span>
        </div>
      </div>
    </div>
  );
}
