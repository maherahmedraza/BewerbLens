import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import "./v3-components.css";
import type { Metadata } from "next";
import { ThemeProvider } from "../components/ThemeProvider";
import { ThemeToggle } from "../components/ThemeToggle";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

import { Providers } from "../components/Providers";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`} suppressHydrationWarning>
      <body suppressHydrationWarning>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <Providers>
            <div className="app-container">
              <Sidebar />
              <div className="main-content">
                <Header />
                <main className="page-container">{children}</main>
              </div>
            </div>
          </Providers>
        </ThemeProvider>
      </body>
    </html>
  );
}
