import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Banco Azul E2E Demo',
  description: 'E2E test suite for async payment flows (PSE, PIX, OXXO)',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
