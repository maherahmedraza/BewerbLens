"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import styles from "./Sidebar.module.css";
import { 
  HomeIcon, 
  TableCellsIcon, 
  ChartPieIcon, 
  Cog6ToothIcon 
} from "@heroicons/react/24/outline";

const NAV_ITEMS = [
  { name: "Dashboard", href: "/", icon: HomeIcon },
  { name: "Applications", href: "/applications", icon: TableCellsIcon },
  { name: "Analytics", href: "/analytics", icon: ChartPieIcon },
  { name: "Settings", href: "/settings", icon: Cog6ToothIcon },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className={styles.sidebar}>
      <div className={styles.logoContainer}>
        <Link href="/" className={styles.logo}>
          <Image 
            src="/logo.png" 
            alt="BewerbLens Logo" 
            width={200} 
            height={60} 
            className={styles.logoImage} 
            priority
          />
        </Link>
      </div>

      <nav className={styles.nav}>
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`${styles.navLink} ${isActive ? styles.active : ""}`}
            >
              <item.icon className={styles.icon} />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>

      <div className={styles.footer}>
        <div className={styles.userSection}>
          <div className={styles.avatar}>M</div>
          <div className={styles.userInfo}>
            <p className={styles.userName}>Maher Ahmed</p>
            <p className={styles.userRole}>Premium Plan</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
