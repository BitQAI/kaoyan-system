import type { Metadata, Viewport } from "next";
import { Suspense } from "react";
import { AiProvider } from "@/components/AiProvider";
import { FavoritesProvider } from "@/components/FavoritesProvider";
import BottomNav from "@/components/BottomNav";
import "./globals.css";
import "./read.css";
import "./memo.css";
import "./listen.css";
import "./ai.css";

export const metadata: Metadata = {
  title: "考研 · 听 / 学 / 记",
  description: "538 个知识点的读、背、听与随时提问",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <FavoritesProvider>
          <Suspense fallback={null}>
            <AiProvider>{children}</AiProvider>
          </Suspense>
          <BottomNav />
        </FavoritesProvider>
      </body>
    </html>
  );
}
