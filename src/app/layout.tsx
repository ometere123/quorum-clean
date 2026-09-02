import type { Metadata } from "next";
import "./globals.css";
import { sourceLabel } from "@/lib/data-source";

export const metadata: Metadata = {
  title: { default: "Quorum Clean", template: "%s · Quorum Clean" },
  description: "Consensus-verified public-evidence screening for reviewer weight.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><div className="qc-provenance" role="status">DATA MODE · {sourceLabel === "LIVE CONTRACT" ? "LIVE" : "FIXTURES"} · StudioNet</div>{children}</body></html>;
}
