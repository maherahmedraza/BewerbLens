"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <button className="nav-link" style={{ background: "transparent", border: "none", cursor: "pointer" }}>
        <span style={{ opacity: 0 }}>☀️</span>
      </button>
    );
  }

  const isDark = resolvedTheme === "dark";

  return (
    <button
      className="nav-link"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      title={`Switch to ${isDark ? "light" : "dark"} theme`}
      style={{
        background: "transparent",
        border: "none",
        cursor: "pointer",
        padding: "6px 8px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        marginLeft: "8px",
      }}
    >
      <span style={{ fontSize: "16px" }}>{isDark ? "☀️" : "🌙"}</span>
    </button>
  );
}
