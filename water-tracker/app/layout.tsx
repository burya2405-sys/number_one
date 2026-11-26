import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Глоток — дневник напитков",
  description: "Учёт воды, чая и кофе в течение дня.",
  other: {
    "codex-preview": "development",
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body className="antialiased">{children}</body>
    </html>
  );
}
