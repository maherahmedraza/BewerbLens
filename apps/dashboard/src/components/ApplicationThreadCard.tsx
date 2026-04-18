// ╔══════════════════════════════════════════════════════════════╗
// ║  Application Thread Card — Proper Counting & Threading      ║
// ║                                                             ║
// ║  Displays:                                                  ║
// ║  • Single application with status timeline                  ║
// ║  • Correct count (Körber = 1 app, not 2)                   ║
// ║  • Visual thread showing email progression                  ║
// ║  • Expandable to show full email history                    ║
// ╚══════════════════════════════════════════════════════════════╝

"use client";

import { useState } from "react";
import { ChevronDownIcon, ChevronUpIcon } from "@heroicons/react/24/outline";

import { type Application, type StatusHistoryEntry as StatusUpdate } from "@/lib/types";

interface ApplicationThreadCardProps {
  application: Application;
}

export default function ApplicationThreadCard({ application }: ApplicationThreadCardProps) {
  const [expanded, setExpanded] = useState(false);

  // ── Status Styling ─────────────────────────────────────────────
  const statusColors: Record<string, string> = {
    'Applied': '#3b82f6',
    'Rejected': '#ef4444',
    'Positive Response': '#10b981',
    'Interview': '#f59e0b',
    'Offer': '#8b5cf6',
  };

  const currentStatusColor = statusColors[application.status] || '#6b7280';

  // ── Timeline Rendering ─────────────────────────────────────────
  const renderTimeline = () => {
    if (!application.status_history || application.status_history.length === 0) {
      return null;
    }

    return (
      <div className="timeline">
        {application.status_history.map((update, index) => {
          const u = update as unknown as Record<string, unknown>;
          const timestamp = u.timestamp || u.changed_at || u.date;
          const source_email_id = u.source_email_id || u.email_id || `migration-${index}`;
          const confidence = (u.confidence ?? 0.8) as number;
          
          return (
            <div key={source_email_id} className="timeline-item">
              <div className="timeline-marker" style={{ backgroundColor: statusColors[update.status] }}>
                {index + 1}
              </div>
              <div className="timeline-content">
                <div className="timeline-header">
                  <span className="timeline-status" style={{ color: statusColors[update.status] }}>
                    {update.status}
                  </span>
                  <span className="timeline-date">
                    {timestamp ? new Date(timestamp).toLocaleDateString("en-US") : "Unknown"}
                  </span>
                </div>
                <div className="timeline-subject">{update.email_subject || "Migrated Status"}</div>
                <div className="timeline-confidence">
                  Confidence: {(confidence * 100).toFixed(0)}%
                </div>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="application-card">
      {/* Header */}
      <div className="card-header">
        <div className="header-left">
          <h3 className="company-name">{application.company_name}</h3>
          <p className="job-title">{application.job_title}</p>
          <div className="metadata">
            <span className="platform">{application.platform}</span>
            <span className="dot">•</span>
            <span className="date">Applied {new Date(application.date_applied).toLocaleDateString("en-US")}</span>
          </div>
        </div>

        <div className="header-right">
          {/* Current Status Badge */}
          <div className="status-badge" style={{ backgroundColor: currentStatusColor }}>
            {application.status}
          </div>

          {/* Email Count Badge (shows thread depth) */}
          {application.email_count > 1 && (
            <div className="email-count-badge">
              {application.email_count} updates
            </div>
          )}
        </div>
      </div>

      {/* Expand/Collapse Button (only if multiple emails) */}
      {application.email_count > 1 && (
        <button 
          className="expand-button"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <>
              <ChevronUpIcon className="icon" style={{ width: '16px', height: '16px', display: 'inline-block', marginRight: '6px', verticalAlign: 'text-bottom' }} />
              Hide Timeline
            </>
          ) : (
            <>
              <ChevronDownIcon className="icon" style={{ width: '16px', height: '16px', display: 'inline-block', marginRight: '6px', verticalAlign: 'text-bottom' }} />
              Show Timeline ({application.email_count} emails)
            </>
          )}
        </button>
      )}

      {/* Timeline (expanded view) */}
      {expanded && renderTimeline()}

      {/* Footer Actions */}
      <div className="card-footer">
        {application.gmail_link && (
          <a 
            href={application.gmail_link} 
            target="_blank" 
            rel="noopener noreferrer"
            className="gmail-link"
          >
            View in Gmail →
          </a>
        )}
      </div>
    </div>
  );
}


// ╔══════════════════════════════════════════════════════════════╗
// ║  Application Stats Component — CORRECT Count                ║
// ╚══════════════════════════════════════════════════════════════╝

interface ApplicationStatsProps {
  applications: Application[];
}

export function ApplicationStats({ applications }: ApplicationStatsProps) {
  // ✅ Count UNIQUE applications (not total rows)
  const uniqueCount = applications.filter(app => app.is_active).length;

  // Count by current status
  const statusCounts = applications.reduce((acc, app) => {
    if (!app.is_active) return acc;
    acc[app.status] = (acc[app.status] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  // Total emails processed (sum of email_count)
  const totalEmails = applications.reduce((sum, app) => sum + app.email_count, 0);

  return (
    <div className="stats-grid">
      <div className="stat-card">
        <div className="stat-value">{uniqueCount}</div>
        <div className="stat-label">Total Applications</div>
        <div className="stat-subtext">{totalEmails} emails tracked</div>
      </div>

      <div className="stat-card">
        <div className="stat-value">{statusCounts['Applied'] || 0}</div>
        <div className="stat-label">Pending</div>
      </div>

      <div className="stat-card">
        <div className="stat-value">{statusCounts['Rejected'] || 0}</div>
        <div className="stat-label">Rejected</div>
      </div>

      <div className="stat-card">
        <div className="stat-value">
          {(statusCounts['Positive Response'] || 0) + 
           (statusCounts['Interview'] || 0) + 
           (statusCounts['Offer'] || 0)}
        </div>
        <div className="stat-label">Positive</div>
      </div>

      <div className="stat-card">
        <div className="stat-value">
          {uniqueCount > 0 
            ? ((((statusCounts['Positive Response'] || 0) + 
                 (statusCounts['Interview'] || 0) + 
                 (statusCounts['Offer'] || 0)) / uniqueCount) * 100).toFixed(1)
            : 0}%
        </div>
        <div className="stat-label">Success Rate</div>
      </div>
    </div>
  );
}


// ╔══════════════════════════════════════════════════════════════╗
// ║  CSS Styles                                                 ║
// ╚══════════════════════════════════════════════════════════════╝

/*
.application-card {
  background: #1a1a1a;
  border-radius: 12px;
  padding: 20px;
  border: 1px solid #2a2a2a;
  transition: border-color 0.2s;
}

.application-card:hover {
  border-color: #3a3a3a;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.company-name {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
  margin: 0 0 4px 0;
}

.job-title {
  color: #9ca3af;
  margin: 0 0 8px 0;
}

.metadata {
  display: flex;
  gap: 8px;
  font-size: 13px;
  color: #6b7280;
}

.status-badge {
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
}

.email-count-badge {
  padding: 6px 12px;
  background: #374151;
  border-radius: 20px;
  font-size: 12px;
  color: #9ca3af;
  margin-top: 8px;
}

.expand-button {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 10px;
  background: #2a2a2a;
  border: none;
  border-radius: 6px;
  color: #9ca3af;
  cursor: pointer;
  margin-top: 12px;
  transition: background 0.2s;
}

.expand-button:hover {
  background: #3a3a3a;
}

.timeline {
  margin-top: 16px;
  padding-left: 12px;
  border-left: 2px solid #374151;
}

.timeline-item {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  position: relative;
}

.timeline-marker {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  flex-shrink: 0;
  margin-left: -20px;
}

.timeline-content {
  flex: 1;
  padding-bottom: 8px;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.timeline-status {
  font-weight: 600;
  font-size: 14px;
}

.timeline-date {
  color: #6b7280;
  font-size: 13px;
}

.timeline-subject {
  color: #9ca3af;
  font-size: 13px;
  margin-bottom: 4px;
}

.timeline-confidence {
  color: #6b7280;
  font-size: 12px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 12px;
  padding: 20px;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 4px;
}

.stat-label {
  color: #9ca3af;
  font-size: 14px;
  margin-bottom: 4px;
}

.stat-subtext {
  color: #6b7280;
  font-size: 12px;
}
*/
