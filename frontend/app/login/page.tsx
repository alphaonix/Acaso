"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { BotaoTema, SeletorIdioma } from "@/components/Controles";
import { api, ErroApi } from "@/lib/api";
import { R, useI18n } from "@/lib/i18n";

const traco = { width: 20, height: 20, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true, focusable: false };
function OlhoAberto() {
  return <svg {...traco}><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>;
}
function OlhoRiscado() {
  return <svg {...traco}><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" /></svg>;
}

export default function Login() {
  const router = useRouter();
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [ver, setVer] = useState(false);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro(""); setEnviando(true);
    try {
      await api("/auth/login", { method: "POST", body: JSON.stringify({ email, senha }) });
      router.replace("/visao-geral");
    } catch (err) {
      const s = err instanceof ErroApi ? err.status : 0;
      setErro(s === 429 ? t("login.erro429") : s === 401 ? t("login.erro401") : t("login.erroGeral"));
      setEnviando(false);
    }
  }

  return (
    <main className="login">
      <section className="login-painel" aria-label={t("login.apresentacao")}>
        <img className="login-logo" src="/logo-acaso-branco.svg" alt="Acaso" width={147} height={30} />

        <div className="login-centro">
          <img className="animacao" src="/login-animacao.webp" alt="" width={180} height={180} />
          <span className="eyebrow">{t("login.eyebrow")}</span>
          <h2><R texto={t("login.titulo")} /></h2>
          <p>{t("login.texto")}</p>
        </div>

        <p className="login-rodape">{t("login.rodape")}</p>
      </section>

      <section className="login-form-area">
        <div className="login-controles"><SeletorIdioma /><BotaoTema /></div>
        <form className="login-form" onSubmit={enviar} noValidate>
          <h1>{t("login.bemVindo")}</h1>
          <p className="dica">{t("login.acesse")}</p>
          <div className="campo">
            <label htmlFor="email">{t("login.email")}</label>
            <input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="campo">
            <label htmlFor="senha">{t("login.senha")}</label>
            <div className="senha-linha">
              <input id="senha" type={ver ? "text" : "password"} autoComplete="current-password" required value={senha} onChange={(e) => setSenha(e.target.value)} />
              <button type="button" className="olho" onClick={() => setVer(!ver)} aria-pressed={ver}
                aria-label={ver ? t("login.ocultarSenha") : t("login.mostrarSenha")} title={ver ? t("login.ocultarSenha") : t("login.mostrarSenha")}>
                {ver ? <OlhoRiscado /> : <OlhoAberto />}
              </button>
            </div>
          </div>
          <p className="erro-msg" role="alert" aria-live="assertive">{erro}</p>
          <button className="btn cheio" type="submit" disabled={enviando || !email || !senha}>{enviando ? t("login.entrando") : t("login.entrar")}</button>
          <p className="dica nota">{t("login.restrito")}</p>
        </form>
      </section>
    </main>
  );
}
