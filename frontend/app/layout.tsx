import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Kriterion | HPLC Validation Engine',
  description:
    'Motor estadístico determinista para la validación de métodos cromatográficos (ICH Q2(R2)).',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
