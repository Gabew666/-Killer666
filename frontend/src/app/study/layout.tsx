"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import StudyDashboard from "./study-dashboard";

export default function StudyLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/study") return <StudyDashboard />;
  return children;
}
