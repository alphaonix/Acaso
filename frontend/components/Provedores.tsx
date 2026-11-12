"use client";
import type { ReactNode } from "react";
import { I18nProvider } from "@/lib/i18n";
import { TemaProvider } from "@/lib/tema";

export function Provedores({ children }: { children: ReactNode }) {
  return <TemaProvider><I18nProvider>{children}</I18nProvider></TemaProvider>;
}
