"use client";

import { ArrowsPointingOutIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useMemo, useState } from "react";
import clsx from "clsx";

import MonthlyChart from "@/components/charts/MonthlyChart";
import PlatformPie from "@/components/charts/PlatformPie";
import StatusFlowSankey from "@/components/charts/StatusFlowSankey";
import StatusFunnel from "@/components/charts/StatusFunnel";
import type {
  ConversionFunnel,
  MonthlyApplication,
  PlatformBreakdown,
  StatusFlowSankeyData,
} from "@/lib/types";

import styles from "./AnalyticsChartsClient.module.css";

type ChartKey = "monthly" | "platform" | "funnel" | "sankey";

interface AnalyticsChartsClientProps {
  monthlyData: MonthlyApplication[];
  platformData: PlatformBreakdown[];
  funnelData: ConversionFunnel[];
  sankeyData: StatusFlowSankeyData;
}

export default function AnalyticsChartsClient({
  monthlyData,
  platformData,
  funnelData,
  sankeyData,
}: AnalyticsChartsClientProps) {
  const [selectedChart, setSelectedChart] = useState<ChartKey | null>(null);

  const chartDefinitions = useMemo(
    () => ({
      monthly: {
        title: "Monthly Trends",
        description: "Applications submitted vs. positive or rejected responses over time.",
        render: (expanded: boolean) => (
          <MonthlyChart data={monthlyData} height={expanded ? 420 : 300} />
        ),
      },
      platform: {
        title: "Platform Distribution",
        description: "Where your tracked applications originate, normalized for cleaner comparison.",
        render: (expanded: boolean) => (
          <PlatformPie
            height={expanded ? 380 : 320}
            data={platformData.map((entry) => ({
              platform: entry.platform,
              count: entry.count,
            }))}
          />
        ),
      },
      funnel: {
        title: "Conversion Funnel",
        description: "A compact view of the current pipeline from submitted applications to offers.",
        render: (expanded: boolean) => (
          <StatusFunnel data={funnelData} height={expanded ? 360 : 260} />
        ),
      },
      sankey: {
        title: "Status Flow",
        description: "Stage-to-stage movement from submission into response, interview, rejection, and offer.",
        render: (expanded: boolean) => (
          <StatusFlowSankey data={sankeyData} height={expanded ? 520 : 420} />
        ),
      },
    }),
    [funnelData, monthlyData, platformData, sankeyData]
  );

  return (
    <>
      <div className={styles.grid}>
        {(Object.keys(chartDefinitions) as ChartKey[]).map((key) => (
          <section
            key={key}
            className={clsx(styles.chartCard, key === "sankey" && styles.sankeyCard)}
            aria-labelledby={`chart-title-${key}`}
          >
            <div className={styles.cardHeader}>
              <div className={styles.cardHeaderText}>
                <h3 id={`chart-title-${key}`} className={styles.cardTitle}>{chartDefinitions[key].title}</h3>
                <p className={styles.cardDescription}>{chartDefinitions[key].description}</p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedChart(key)}
                className={styles.expandButton}
                aria-label={`Expand ${chartDefinitions[key].title}`}
              >
                <ArrowsPointingOutIcon className={styles.expandIcon} />
              </button>
            </div>
            {chartDefinitions[key].render(false)}
          </section>
        ))}
      </div>

      {selectedChart ? (
        <div className={styles.overlay} onClick={() => setSelectedChart(null)}>
          <div
            className={styles.modal}
            role="dialog"
            aria-modal="true"
            aria-labelledby="analytics-lightbox-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className={styles.modalHeader}>
              <div>
                <h3 id="analytics-lightbox-title" className={styles.modalTitle}>
                  {chartDefinitions[selectedChart].title}
                </h3>
                <p className={styles.modalDescription}>
                  {chartDefinitions[selectedChart].description}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedChart(null)}
                className={styles.closeButton}
                aria-label="Close chart lightbox"
              >
                <XMarkIcon className={styles.closeIcon} />
              </button>
            </div>
            <div className={styles.modalBody}>{chartDefinitions[selectedChart].render(true)}</div>
          </div>
        </div>
      ) : null}
    </>
  );
}
