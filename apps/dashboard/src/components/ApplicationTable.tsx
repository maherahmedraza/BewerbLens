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

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  "Applied": { label: "Pending", color: "#00a4e4" },
  "Rejected": { label: "Rejected", color: "#e3120b" },
  "Positive Response": { label: "Positive", color: "#0f2e53" },
  "Interview": { label: "Interview", color: "#f59e0b" },
  "Offer": { label: "Offer", color: "#8b5cf6" },
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
    <div className={styles.container}>
      <ApplicationStats applications={applications} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '16px', marginTop: '24px' }}>
        {applications.map((app) => (
          <ApplicationThreadCard 
            key={app.id} 
            application={app as any} 
          />
        ))}
      </div>
    </div>
    </div>
  );
}
