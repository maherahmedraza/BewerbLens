import { createClient } from "@/lib/supabase/server";
import { type Application } from "@/lib/types";
import { BuildingOfficeIcon } from "@heroicons/react/24/outline";
import styles from "./ApplicationTable.module.css";
import ApplicationThreadCard, { ApplicationStats } from "./ApplicationThreadCard";

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
      <div className={styles.toolbar}>
        <div className={styles.toolbarContent}>
          <h2 className={styles.toolbarTitle}>Application Tracker</h2>
          <p className={styles.toolbarSubtitle}>
            Export the current dataset as CSV for Excel or Google Sheets.
          </p>
        </div>
        <a href="/api/applications/export" className={styles.exportButton}>
          Export CSV
        </a>
      </div>

      <ApplicationStats applications={applications} />
      <div className={styles.threadList}>
        {applications.map((app) => (
          <ApplicationThreadCard 
            key={app.id} 
            application={app} 
          />
        ))}
      </div>
    </div>
  );
}
