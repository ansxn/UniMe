import type { Metadata } from "next";
import { Inter } from "next/font/google";
import AuthProvider from "@/components/AuthProvider";
import AuthPill from "@/components/AuthPill";
import "./globals.css";
import "./accounts.css";

const inter = Inter({ subsets: ['latin'] })


export const metadata: Metadata = {
  title: "UniMe — find your Ontario university match",
  description:
    "Take a 3-minute quiz to find Ontario university programs that fit you, estimate your admission chances, and connect with current students.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={inter.className}
      >
        <AuthProvider>
          <AuthPill />
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
