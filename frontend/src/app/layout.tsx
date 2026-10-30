import type { Metadata, Viewport } from "next";

import "./globals.css";

/**
 * Root layout: the <html> and <body> every page shares. A Server Component with no data, so it is
 * part of the static shell that every page load gets instantly.
 */
export const metadata: Metadata = {
  title: { default: "Talent Matcher", template: "%s · Talent Matcher" },
  description: "Find the right current employees for internal project roles.",
  robots: { index: false, follow: false }, // an internal tool: keep it out of search engines
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f9fafb" },
    { media: "(prefers-color-scheme: dark)", color: "#16181d" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en-IN">
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}
