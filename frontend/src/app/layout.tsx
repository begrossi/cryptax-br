import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "cryptax-br — Declaração de criptomoedas",
  description: "Ferramenta open-source e local para declaração de criptoativos à Receita Federal brasileira.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
