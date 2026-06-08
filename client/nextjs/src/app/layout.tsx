import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const plusJakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plus-jakarta",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "iRecommend — Customer Intelligence for Modern Merchants",
    template: "%s — iRecommend",
  },
  description:
    "Build behavioural customer personas from review data, simulate product launches, and power better recommendations.",
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${plusJakarta.variable} scroll-smooth bg-background text-text-primary`}
    >
      <body className="min-h-screen bg-background font-sans text-text-primary antialiased">
        {children}
        <Toaster richColors position="top-right" />
      </body>
    </html>
  );
}
