import type { Metadata } from "next";
import { requireChatGPTUser } from "@/app/chatgpt-auth";
import "./globals.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Опора — расходы бизнеса",
  description: "Персональная CRM для учёта и анализа бизнес-расходов.",
  other: {
    "codex-preview": "development",
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  await requireChatGPTUser("/");

  return (
    <html lang="ru">
      <body className="antialiased">{children}</body>
    </html>
  );
}
