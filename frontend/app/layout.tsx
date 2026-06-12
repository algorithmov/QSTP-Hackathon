import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Masar Content Router",
  description: "AI content routing board for platform, market, language, and publishing time recommendations."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
