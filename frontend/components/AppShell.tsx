"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const tabs = [
  { href: "/review", label: "AI Reviewer" },
  { href: "/personalize", label: "Personalized Targeter" }
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <main className="min-h-screen bg-paper">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-line pb-5 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-3xl font-black tracking-normal text-ink sm:text-4xl">Masar</h1>
            <p className="mt-2 max-w-2xl text-base leading-7 text-muted">
              Evidence-backed routing and localized delivery plans for Stars of Science ideas.
            </p>
          </div>
          <nav className="flex w-full rounded-md border border-line bg-white p-1 shadow-board md:w-auto">
            {tabs.map((tab) => {
              const active = pathname === tab.href || (pathname === "/" && tab.href === "/review");
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={`flex-1 rounded px-4 py-2 text-center text-sm font-bold transition md:flex-none ${
                    active ? "bg-accent text-white" : "text-ink hover:bg-paper"
                  }`}
                >
                  {tab.label}
                </Link>
              );
            })}
          </nav>
        </header>
        {children}
      </div>
    </main>
  );
}
