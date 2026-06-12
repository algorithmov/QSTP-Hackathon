import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Masar",
  description: "Evidence-backed idea reviewer and personalized delivery planner for Stars of Science."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
