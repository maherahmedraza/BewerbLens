import ApplicationTable from "@/components/ApplicationTable";
import styles from "./page.module.css";

export default async function ApplicationsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const query = (await searchParams).q || "";

  return (
    <div className={styles.container}>
      <header className={styles.pageHeader}>
        <h1 className="heading">Applications</h1>
        <p className="subheading">Track and manage your application history with detailed status updates.</p>
      </header>
      <ApplicationTable highlightQuery={query} />
    </div>
  );
}
