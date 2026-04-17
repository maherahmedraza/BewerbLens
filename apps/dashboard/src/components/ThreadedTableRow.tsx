"use client";

import { useState } from "react";
import { Application } from "@/lib/types";
import { normalizeStatus } from "@/lib/status";
import styles from "./ApplicationTable.module.css";
import { 
  EnvelopeIcon, 
  LinkIcon,
  MapPinIcon,
  CalendarIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ClockIcon
} from "@heroicons/react/24/outline";

interface Props {
  app: Application;
  statusMap: Record<string, { label: string; color: string }>;
}

export default function ThreadedTableRow({ app, statusMap }: Props) {
  const [expanded, setExpanded] = useState(false);
  const normalizedStatus = normalizeStatus(app.status);
  const statusInfo = statusMap[normalizedStatus] || { label: normalizedStatus, color: "var(--text-muted)" };
  
  const history = app.status_history || [];
  const hasHistory = history.length > 1;

  return (
    <>
      <tr className={`${styles.row} ${expanded ? styles.expandedParent : ""}`} onClick={() => hasHistory && setExpanded(!expanded)}>
        <td>
          <div className={styles.companyInfo}>
            <div className={styles.avatar} style={{ backgroundColor: `${statusInfo.color}15`, color: statusInfo.color }}>
              {app.company_name.charAt(0)}
            </div>
            <div>
              <div className={styles.companyName}>
                {app.company_name}
                {hasHistory && (
                  <span className={styles.threadBadge}>
                    <ClockIcon className={styles.miniIcon} />
                    {history.length} updates
                  </span>
                )}
              </div>
              <div className={styles.jobTitle}>{app.job_title}</div>
            </div>
          </div>
        </td>
        <td>
          <span
            className={styles.statusBadge}
            style={{
              backgroundColor: `${statusInfo.color}15`,
              color: statusInfo.color,
            }}
          >
            <span className={styles.dot} style={{ backgroundColor: statusInfo.color }} />
            {statusInfo.label}
          </span>
        </td>
        <td>
          <div className={styles.meta}>
            <div className={styles.platform}>{app.platform}</div>
            <div className={styles.location}>
              <MapPinIcon className={styles.miniIcon} />
              {app.location || "Remote"}
            </div>
          </div>
        </td>
        <td>
          <div className={styles.dateInfo}>
            <CalendarIcon className={styles.miniIcon} />
            {new Date(app.date_applied).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric"
            })}
          </div>
        </td>
        <td>
          <div className={styles.actions} onClick={(e) => e.stopPropagation()}>
            {app.gmail_link && (
              <a href={app.gmail_link} target="_blank" className={styles.actionBtn} title="View Email">
                <EnvelopeIcon />
              </a>
            )}
            {app.job_listing_url && (
              <a href={app.job_listing_url} target="_blank" className={styles.actionBtn} title="View Job Listing">
                <LinkIcon />
              </a>
            )}
            {hasHistory && (
              <button className={styles.expandBtn} onClick={() => setExpanded(!expanded)}>
                {expanded ? <ChevronUpIcon /> : <ChevronDownIcon />}
              </button>
            )}
          </div>
        </td>
      </tr>

      {expanded && hasHistory && (
        <tr className={styles.historyRow}>
          <td colSpan={5}>
            <div className={styles.historyContainer}>
              <div className={styles.timeline}>
                {history.slice().reverse().map((entry, idx) => {
                  const entryStatus = statusMap[normalizeStatus(entry.status)] || { label: normalizeStatus(entry.status), color: "var(--text-muted)" };
                  return (
                    <div key={idx} className={styles.timelineItem}>
                      <div className={styles.timelineDot} style={{ backgroundColor: entryStatus.color }} />
                      <div className={styles.timelineLine} />
                      <div className={styles.timelineContent}>
                        <div className={styles.timelineHeader}>
                          <span className={styles.timelineStatus} style={{ color: entryStatus.color }}>
                            {entryStatus.label}
                          </span>
                          <span className={styles.timelineDate}>
                            {new Date(entry.changed_at || entry.date).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit"
                            })}
                          </span>
                        </div>
                        <div className={styles.timelineSubject}>{entry.email_subject}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
