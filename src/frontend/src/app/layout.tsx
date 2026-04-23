import type { Metadata, Viewport } from "next";
import { Outfit, DM_Mono } from "next/font/google";
import NavHeader from "@/components/NavHeader";
import AuroraBackground from "@/components/ui/AuroraBackground";
import "./globals.css";

const outfit = Outfit({
  variable: "--font-display",
  subsets: ["latin"],
});

const dmMono = DM_Mono({
  variable: "--font-mono",
  weight: ["400", "500"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SIGNAL — 공매도 커버링 시그널",
  description: "대차잔고 급감, 추세전환, 숏스퀴즈 패턴을 분석하여 상승 가능성이 높은 종목을 탐지합니다.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className={`${outfit.variable} ${dmMono.variable} dark`}>
      <body className="min-h-screen bg-[#0B0E11] text-[#E8ECF1] antialiased">
        <AuroraBackground />
        <div className="relative z-[1]">
          <NavHeader />
          {children}
          <footer className="border-t border-white/5 bg-[#0B0E11]/90 backdrop-blur">
            <div className="max-w-6xl mx-auto px-5 py-3">
              <p className="text-xs text-[#7A8699] leading-relaxed">
                <span className="text-yellow-500 mr-1">&#9888;</span>
                본 시스템은 투자 자문이 아닌 정보 제공 목적의 참고 도구입니다.
                모든 투자 판단과 그에 따른 결과의 책임은 투자자 본인에게 있습니다.
                과거 성과가 미래 수익을 보장하지 않습니다.
              </p>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
