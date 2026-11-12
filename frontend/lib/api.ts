"use client";
import { useEffect, useState } from "react";

export class ErroApi extends Error {
  constructor(public status: number, mensagem: string) {
    super(mensagem);
  }
}

export async function api<T>(caminho: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`/api${caminho}`, {
    credentials: "same-origin",
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (r.status === 401 && typeof window !== "undefined" && !location.pathname.startsWith("/login")) {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => undefined); // limpa o cookie expirado
    location.href = "/login";
  }
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail ?? msg; } catch { /* corpo sem JSON */ }
    throw new ErroApi(r.status, String(msg));
  }
  return r.json() as Promise<T>;
}

export function useApi<T>(caminho: string | null) {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  useEffect(() => {
    if (!caminho) { setDados(null); setCarregando(false); return; }
    let vivo = true;
    setCarregando(true); setErro(null);
    api<T>(caminho)
      .then((d) => { if (vivo) setDados(d); })
      .catch((e: Error) => { if (vivo) setErro(e.message); })
      .finally(() => { if (vivo) setCarregando(false); });
    return () => { vivo = false; };
  }, [caminho]);
  return { dados, erro, carregando };
}
