import { Fraunces, IBM_Plex_Mono, Instrument_Sans } from "next/font/google";
import "./globals.css";
import "./v3-components.css";
import { ThemeProvider } from "../components/ThemeProvider";
import AppShell from "@/components/AppShell";

const bodyFont = Instrument_Sans({
  variable: "--font-body-sans",
  subsets: ["latin"],
});

const displayFont = Fraunces({
  variable: "--font-display-serif",
  subsets: ["latin"],
});

const monoFont = IBM_Plex_Mono({
  variable: "--font-body-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

import { Providers } from "../components/Providers";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${bodyFont.variable} ${displayFont.variable} ${monoFont.variable}`}
      suppressHydrationWarning
    >
      <body suppressHydrationWarning>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <Providers>
            <AppShell>{children}</AppShell>
          </Providers>
        </ThemeProvider>
      </body>
    </html>
  );
}
