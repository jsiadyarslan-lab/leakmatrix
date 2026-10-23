import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "LeakMatrix Console — وحدة تحكم اختبار العبور الأفقي",
  description:
    "واجهة تحكم تفاعلية لأداة LeakMatrix: فحص IDOR/BOLA عبر مصفوفة توكن × معرفات من أي مواصفة OpenAPI/Swagger، مع سباق متزامن وماسح أسرار — للاستخدام المصرح به فقط.",
  keywords: [
    "LeakMatrix",
    "IDOR",
    "BOLA",
    "bug bounty",
    "authorization testing",
    "OpenAPI",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ar" dir="rtl" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-foreground`}
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}
