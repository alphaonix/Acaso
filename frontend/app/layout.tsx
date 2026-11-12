import type { Metadata } from "next";
// Mesmas fontes do projeto insight-hub-portal: Inter no texto, Plus Jakarta Sans nos titulos.
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/plus-jakarta-sans/400.css";
import "@fontsource/plus-jakarta-sans/500.css";
import "@fontsource/plus-jakarta-sans/600.css";
import "@fontsource/plus-jakarta-sans/700.css";
import "@fontsource/plus-jakarta-sans/800.css";
import "./globals.css";
import { Provedores } from "@/components/Provedores";

export const metadata: Metadata = {
  title: "Dashboard de retenção | Acaso",
  description: "Dashboard: o que faz quem experimenta o assistente de IA voltar a usá-lo em até 7 dias.",
  icons: { icon: "/favicon.svg" },
};

// Aplica o tema salvo (ou a preferencia do sistema) ANTES da primeira pintura, para nao piscar claro->escuro.
const SCRIPT_TEMA = `try{var t=localStorage.getItem('tema');if(t!=='claro'&&t!=='escuro'){t=matchMedia('(prefers-color-scheme: dark)').matches?'escuro':'claro'}document.documentElement.dataset.tema=t}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: SCRIPT_TEMA }} /></head>
      <body><Provedores>{children}</Provedores></body>
    </html>
  );
}
