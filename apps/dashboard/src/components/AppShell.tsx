"use client";

import { Suspense } from "react";
import { usePathname } from "next/navigation";

import Header from "@/components/Header";
import Sidebar from "@/components/Sidebar";

const PUBLIC_ROUTES = new Set(["/", "/login"]);

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublicRoute = PUBLIC_ROUTES.has(pathname);

  if (isPublicRoute) {
    return <div className="public-app">{children}</div>;
  }

  return (
    <div className="app-container">
      <Sidebar />
      <div className="main-content">
        <Suspense fallback={null}>
          <Header />
        </Suspense>
        <main className="page-container">{children}</main>
      </div>
    </div>
  );
}
