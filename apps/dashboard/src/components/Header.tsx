"use client";

import Link from "next/link";
import Image from "next/image";
import { useState, useEffect, useMemo, useRef } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { formatDistanceToNow } from "date-fns";
import { ThemeToggle } from "./ThemeToggle";
import styles from "./Header.module.css";
import { 
  MagnifyingGlassIcon, 
  BellIcon, 
  QuestionMarkCircleIcon 
} from "@heroicons/react/24/outline";
import { usePipelineRuns } from "@/hooks/usePipeline";

type HeaderPanel = "help" | "notifications" | null;

export default function Header() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [search, setSearch] = useState(searchParams.get("q") || "");
  const [openPanel, setOpenPanel] = useState<HeaderPanel>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const showSearch = pathname === "/applications";
  const pageTitle = useMemo(() => {
    if (pathname === "/dashboard") return "Dashboard";
    if (pathname === "/applications") return "Applications";
    if (pathname === "/analytics") return "Analytics";
    if (pathname === "/pipeline") return "Pipeline";
    if (pathname === "/settings") return "Settings";
    return "Workspace";
  }, [pathname]);

  const { data: recentRuns } = usePipelineRuns(5);

  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    const currentSearch = searchParams.get("q") || "";

    if (search !== currentSearch) {
      if (search) {
        params.set("q", search);
      } else {
        params.delete("q");
      }
      
      if (pathname === "/applications") {
        router.replace(`${pathname}?${params.toString()}`);
      }
    }
  }, [search, pathname, router, searchParams]);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!panelRef.current?.contains(event.target as Node)) {
        setOpenPanel(null);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  const notificationItems = useMemo(() => {
    return (recentRuns || []).slice(0, 4);
  }, [recentRuns]);

  const notificationCount = notificationItems.filter((run) => run.status !== "success").length;

  function togglePanel(panel: Exclude<HeaderPanel, null>) {
    setOpenPanel((current) => (current === panel ? null : panel));
  }

  return (
    <header className={styles.header}>
      {showSearch ? (
        <div className={styles.searchContainer}>
          <MagnifyingGlassIcon className={styles.searchIcon} />
          <input
            type="text"
            placeholder="Search for applications, companies, or roles..."
            className={styles.searchInput}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      ) : (
        <div className={styles.pageContext}>
          <Image src="/bewerblens-logo.svg" alt="" width={26} height={26} className={styles.pageContextLogo} aria-hidden="true" />
          <div>
            <span className={styles.pageContextLabel}>BewerbLens</span>
            <strong>{pageTitle}</strong>
          </div>
        </div>
      )}

      <div className={styles.actionsWrap} ref={panelRef}>
        <div className={styles.actions}>
        <button
          className={styles.iconButton}
          title="Help"
          aria-expanded={openPanel === "help"}
          onClick={() => togglePanel("help")}
        >
          <QuestionMarkCircleIcon />
        </button>
        <button
          className={styles.iconButton}
          title="Notifications"
          aria-expanded={openPanel === "notifications"}
          onClick={() => togglePanel("notifications")}
        >
          <BellIcon />
          {notificationCount > 0 ? (
            <span className={styles.badge}>{notificationCount > 9 ? "9+" : notificationCount}</span>
          ) : null}
        </button>
        <div className={styles.divider} />
        <ThemeToggle />
        </div>

        {openPanel === "notifications" ? (
          <div className={styles.popover}>
            <div className={styles.popoverHeader}>
              <div>
                <strong>Pipeline notifications</strong>
                <p>Recent run activity and completion outcomes.</p>
              </div>
              <Link href="/pipeline" className={styles.popoverLink} onClick={() => setOpenPanel(null)}>
                Open pipeline
              </Link>
            </div>
            <div className={styles.popoverList}>
              {notificationItems.length ? (
                notificationItems.map((run) => (
                  <button
                    key={run.id}
                    type="button"
                    className={styles.popoverItem}
                    onClick={() => {
                      setOpenPanel(null);
                      router.push("/pipeline");
                    }}
                  >
                    <span className={`${styles.statusBadge} ${styles[`status${run.status}`] || ""}`}>
                      {run.status}
                    </span>
                    <div className={styles.popoverMeta}>
                      <strong>{run.run_id}</strong>
                      <span>
                        {run.status === "success"
                          ? `${run.summary_stats?.added || 0} added, ${run.summary_stats?.updated || 0} updated`
                          : run.error_message || "Pipeline activity updated."}
                      </span>
                    </div>
                    <time>{run.started_at ? formatDistanceToNow(new Date(run.started_at), { addSuffix: true }) : "just now"}</time>
                  </button>
                ))
              ) : (
                <div className={styles.popoverEmpty}>No pipeline notifications yet.</div>
              )}
            </div>
          </div>
        ) : null}

        {openPanel === "help" ? (
          <div className={styles.popover}>
            <div className={styles.popoverHeader}>
              <div>
                <strong>Quick help</strong>
                <p>Common actions for sync, logs, and notifications.</p>
              </div>
            </div>
            <div className={styles.helpList}>
              <Link href="/settings#sync-controls" className={styles.helpItem} onClick={() => setOpenPanel(null)}>
                <strong>Queue a sync</strong>
                <span>Pick a backfill date or start an incremental run from Workspace Settings.</span>
              </Link>
              <Link href="/pipeline" className={styles.helpItem} onClick={() => setOpenPanel(null)}>
                <strong>Inspect execution logs</strong>
                <span>Open Pipeline to monitor stages, recent runs, and failure details in real time.</span>
              </Link>
              <Link href="/settings" className={styles.helpItem} onClick={() => setOpenPanel(null)}>
                <strong>Manage Gmail and Telegram</strong>
                <span>Reconnect Gmail, link Telegram, and control personal integration behavior.</span>
              </Link>
            </div>
          </div>
        ) : null}
      </div>
    </header>
  );
}
