"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import styles from "./Sidebar.module.css";
import { 
  HomeIcon, 
  TableCellsIcon, 
  ChartPieIcon, 
  Cog6ToothIcon,
  RectangleStackIcon,
  Bars3Icon,
  XMarkIcon
} from "@heroicons/react/24/outline";

const NAV_ITEMS = [
  { name: "Dashboard", href: "/", icon: HomeIcon },
  { name: "Applications", href: "/applications", icon: TableCellsIcon },
  { name: "Analytics", href: "/analytics", icon: ChartPieIcon },
  { name: "Pipeline", href: "/pipeline", icon: RectangleStackIcon },
  { name: "Settings", href: "/settings", icon: Cog6ToothIcon },
];

export default function Sidebar() {
  const pathname = usePathname();
  const supabase = useMemo(() => createClient(), []);
  const [profile, setProfile] = useState<{ full_name: string | null; email: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    async function loadProfile() {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return;

        const { data, error } = await supabase
          .from("user_profiles")
          .select("full_name, email")
          .eq("id", user.id)
          .single();

        if (error) throw error;
        setProfile(data);
      } catch (error) {
        console.error("Error loading sidebar profile:", error);
      } finally {
        setLoading(false);
      }
    }

    loadProfile();
  }, [supabase]);

  function isActivePath(href: string) {
    if (href === "/") {
      return pathname === href;
    }
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  function handleNavigate() {
    setMobileOpen(false);
  }

  return (
    <>
      {/* Mobile hamburger toggle */}
      <button
        className="sidebar-toggle"
        onClick={() => setMobileOpen(!mobileOpen)}
        aria-label="Toggle sidebar"
      >
        {mobileOpen ? <XMarkIcon width={22} height={22} /> : <Bars3Icon width={22} height={22} />}
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="sidebar-overlay open" onClick={() => setMobileOpen(false)} />
      )}

      <aside className={`${styles.sidebar} ${mobileOpen ? styles.open : ""}`}>
        <div className={styles.logoContainer}>
          <Link href="/" className={styles.logo}>
            <Image 
              src="/geometric_logo.png" 
              alt="BewerbLens Logo" 
              width={400} 
              height={400} 
              className={styles.logoImage} 
              priority
            />
          </Link>
        </div>

        <nav className={styles.nav}>
          {NAV_ITEMS.map((item) => {
            const isActive = isActivePath(item.href);
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`${styles.navLink} ${isActive ? styles.active : ""}`}
                onClick={handleNavigate}
              >
                <item.icon className={styles.icon} />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        <div className={styles.footer}>
          <Link
            href="/profile"
            className={`${styles.userLink} ${isActivePath("/profile") ? styles.active : ""}`}
            onClick={handleNavigate}
          >
            <div className={styles.avatar}>
              {profile?.full_name?.charAt(0) || profile?.email?.charAt(0) || "?"}
            </div>
            <div className={styles.userInfo}>
              {loading ? (
                <div className={styles.skeletonText} />
              ) : (
                <>
                  <p className={styles.userName}>{profile?.full_name || "User"}</p>
                  <p className={styles.userRole}>{profile?.email}</p>
                </>
                )}
            </div>
          </Link>
        </div>
      </aside>
    </>
  );
}
