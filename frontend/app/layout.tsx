import type { Metadata } from "next";
import React from 'react'
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import "../styles/diff.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Medical PDF Deduplicator",
  description: "A system for detecting and managing duplicate medical PDFs",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-gray-100 dark:bg-gray-950 text-gray-900 dark:text-gray-100`}
      >
        <div className="min-h-screen flex flex-col">
          <header className="bg-black text-white p-4 shadow">
            <div className="container mx-auto">
              <h1 className="text-xl font-bold">Medical PDF Deduplicator</h1>
            </div>
          </header>
          <main className="flex-grow container mx-auto p-4 md:p-6">
            {children}
          </main>
          <footer className="bg-black text-gray-400 p-4 text-center text-sm">
            <p>© {new Date().getFullYear()} Medical PDF Deduplicator</p>
          </footer>
        </div>
      </body>
    </html>
  );
}