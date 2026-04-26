"use client";

import { useState, useEffect } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { ThemeToggle } from "./ThemeToggle";
import styles from "./Header.module.css";
import { 
  MagnifyingGlassIcon, 
  BellIcon, 
  QuestionMarkCircleIcon 
} from "@heroicons/react/24/outline";

export default function Header() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [search, setSearch] = useState(searchParams.get("q") || "");

  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    const currentSearch = searchParams.get("q") || "";

    if (search !== currentSearch) {
      if (search) {
        params.set("q", search);
      } else {
        params.delete("q");
      }
      
      // Only replace URL if we are on a searchable page
      if (pathname === "/applications" || pathname === "/dashboard") {
        router.replace(`${pathname}?${params.toString()}`);
      }
    }
  }, [search, pathname, router, searchParams]);

  return (
    <header className={styles.header}>
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

      <div className={styles.actions}>
        <button className={styles.iconButton} title="Help">
          <QuestionMarkCircleIcon />
        </button>
        <button className={styles.iconButton} title="Notifications">
          <BellIcon />
          <span className={styles.badge} />
        </button>
        <div className={styles.divider} />
        <ThemeToggle />
      </div>
    </header>
  );
}
