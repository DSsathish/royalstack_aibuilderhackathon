import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Figtree, JetBrains_Mono, Noto_Sans_Devanagari, Noto_Sans_Tamil } from "next/font/google";
import "./globals.css";

const display = Bricolage_Grotesque({ variable: "--font-display", subsets: ["latin"], weight: ["500", "600", "700"] });
const body = Figtree({ variable: "--font-body", subsets: ["latin"], weight: ["400", "500", "600"] });
const mono = JetBrains_Mono({ variable: "--font-mono", subsets: ["latin"], weight: ["500"] });
const tamil = Noto_Sans_Tamil({ variable: "--font-tamil", subsets: ["tamil"], weight: ["400", "600"] });
const hindi = Noto_Sans_Devanagari({ variable: "--font-hindi", subsets: ["devanagari"], weight: ["400", "600"] });

export const metadata: Metadata = {
  title: "Royal Stack",
  description: "Your in-store and online shopping assistant",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, title: "Royal Stack", statusBarStyle: "default" },
};
export const viewport: Viewport = { themeColor: "#e39a0c", width: "device-width", initialScale: 1, viewportFit: "cover" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable} ${tamil.variable} ${hindi.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
