import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Quorum Clean", template: "%s · Quorum Clean" },
  description: "Consensus-verified public-evidence screening for reviewer weight.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
