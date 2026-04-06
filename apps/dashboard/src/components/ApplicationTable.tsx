import { createClient } from "@/lib/supabase/server";
import { STATUS_COLORS, type Application } from "@/lib/types";
import styles from "./ApplicationTable.module.css";
import { 
  EnvelopeIcon, 
  LinkIcon,
  MapPinIcon,
  CalendarIcon,
  BuildingOfficeIcon
} from "@heroicons/react/24/outline";

async function getApplications(query: string = ""): Promise<Application[]> {
  const supabase = await createClient();
  let request = supabase
    .from("applications")
    .select("*")
    .order("date_applied", { ascending: false });

  if (query) {
    request = request.or(`company_name.ilike.%${query}%,job_title.ilike.%${query}%`);
  }

  const { data, error } = await request.limit(200);

  if (error) return [];
  return (data as Application[]) || [];
}

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  "Applied": { label: "Pending", color: "var(--accent-orange)" },
  "Rejected": { label: "Rejected", color: "var(--accent-red)" },
  "Positive Response": { label: "Positive", color: "var(--accent-green)" },
  "Interview": { label: "Interview", color: "var(--chart-color-2)" },
  "Offer": { label: "Offer", color: "var(--accent-blue)" },
};

export default async function ApplicationTable({ highlightQuery }: { highlightQuery?: string }) {
  const applications = await getApplications(highlightQuery);

  if (applications.length === 0) {
    return (
      <div className={styles.empty}>
        <BuildingOfficeIcon className={styles.emptyIcon} />
        <p>No applications found matching your search.</p>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Company & Role</th>
              <th>Status</th>
              <th>Platform & Location</th>
              <th>Date</th>
              <th className={styles.actionsHeader}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {applications.map((app) => {
              const statusInfo = STATUS_MAP[app.status] || { label: app.status, color: "var(--text-muted)" };
              return (
                <tr key={app.id} className={styles.row}>
                  <td>
                    <div className={styles.companyInfo}>
                      <div className={styles.avatar} style={{ backgroundColor: `${statusInfo.color}15`, color: statusInfo.color }}>
                        {app.company_name.charAt(0)}
                      </div>
                      <div>
                        <div className={styles.companyName}>{app.company_name}</div>
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
                    <div className={styles.actions}>
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
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
