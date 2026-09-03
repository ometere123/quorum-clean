import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { sourceLabel } from "@/lib/data-source";
import { WalletControl } from "@/components/wallet-control";
import { WalletProvider } from "@/components/wallet-provider";

export const metadata: Metadata = {
  title: { default: "Quorum Clean", template: "%s · Quorum Clean" },
  description: "Consensus-verified public-evidence screening for reviewer weight.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><WalletProvider><div className="qc-masthead"><Link href="/" className="qc-masthead-mark">Quorum Clean</Link><WalletControl /></div><div className="qc-provenance" role="status">DATA MODE · {sourceLabel === "LIVE CONTRACT" ? "LIVE" : "FIXTURES"} · StudioNet</div>{children}</WalletProvider></body></html>;
}
