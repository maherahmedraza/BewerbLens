"use client";

import { ArrowsPointingOutIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useMemo, useState } from "react";

import MonthlyChart from "@/components/charts/MonthlyChart";
import PlatformPie from "@/components/charts/PlatformPie";
import StatusFunnel from "@/components/charts/StatusFunnel";
import type { ConversionFunnel, MonthlyApplication, PlatformBreakdown } from "@/lib/types";

import styles from "./AnalyticsChartsClient.module.css";

type ChartKey = "monthly" | "platform" | "funnel";

interface AnalyticsChartsClientProps {
  monthlyData: MonthlyApplication[];
  platformData: PlatformBreakdown[];
  funnelData: ConversionFunnel[];
}

export default function AnalyticsChartsClient({
  monthlyData,
  platformData,
  funnelData,
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
    }),
    [funnelData, monthlyData, platformData]
  );

  return (
    <>
      <div className={styles.grid}>
        {(Object.keys(chartDefinitions) as ChartKey[]).map((key) => (
          <section key={key} className={styles.chartCard}>
            <div className={styles.cardHeader}>
              <div className={styles.cardHeaderText}>
                <h3 className={styles.cardTitle}>{chartDefinitions[key].title}</h3>
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
          <div className={styles.modal} onClick={(event) => event.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div>
                <h3 className={styles.modalTitle}>{chartDefinitions[selectedChart].title}</h3>
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
