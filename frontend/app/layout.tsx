import type { Metadata } from "next";
import React from 'react'
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import "../styles/diff.css";
import { ClientThemeProvider } from "../components/core/ClientThemeProvider";
import { ClientThemeWrapper } from "../components/core/ClientThemeWrapper";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Document Duplication Detection",
  description: "A system for detecting and managing duplicate documents",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-text-primary`}
      >
        <ClientThemeProvider>
          <div className="min-h-screen flex flex-col">
            <header className="bg-surface shadow">
              <div className="container mx-auto flex justify-between items-center p-4">
                <h1 className="text-xl font-bold text-accent-primary">Document Duplication Detection</h1>
                <ClientThemeWrapper />
              </div>
            </header>
            <main className="flex-grow container mx-auto p-4 md:p-6">
              {children}
            </main>
            <footer className="bg-surface text-text-secondary p-4 text-center text-sm">
              <p>© {new Date().getFullYear()} Document Duplication Detection</p>
            </footer>
          </div>
        </ClientThemeProvider>
      </body>
    </html>
  );
}