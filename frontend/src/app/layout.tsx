import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import '../styles/globals.css';
import { AuthProvider } from '@/hooks/useAuth';
import ErrorBoundary from '@/components/ErrorBoundary';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'StockAnalyzer AI — Institutional-Grade Stock Analysis',
  description:
    'AI-powered fundamental stock analysis with DCF valuation, technical indicators, risk metrics, and sentiment analysis. Get comprehensive reports in under a minute.',
  openGraph: {
    title: 'StockAnalyzer AI',
    description: 'Institutional-grade stock analysis powered by multi-agent AI.',
    type: 'website',
    locale: 'en_US',
    siteName: 'StockAnalyzer AI',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'StockAnalyzer AI',
    description: 'Institutional-grade stock analysis powered by multi-agent AI.',
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <ErrorBoundary>
          <AuthProvider>{children}</AuthProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
