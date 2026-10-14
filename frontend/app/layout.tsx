import type { Metadata, Viewport } from "next";
import { Geist, Noto_Sans_Devanagari, Noto_Sans_Tamil } from "next/font/google";
import "./globals.css";

const geist = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const tamil = Noto_Sans_Tamil({ variable: "--font-tamil", subsets: ["tamil"], weight: ["400", "600"] });
const hindi = Noto_Sans_Devanagari({ variable: "--font-hindi", subsets: ["devanagari"], weight: ["400", "600"] });

export const metadata: Metadata = {
  title: "Royal Stack",
  description: "Your in-store and online shopping assistant",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, title: "Royal Stack", statusBarStyle: "default" },
};
export const viewport: Viewport = { themeColor: "#059669", width: "device-width", initialScale: 1, viewportFit: "cover" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geist.variable} ${tamil.variable} ${hindi.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
