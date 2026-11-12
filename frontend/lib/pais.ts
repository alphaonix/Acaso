// Nome do pais na lingua da tela, a partir do codigo ISO (o navegador sabe os nomes em PT, EN e dezenas de outras).
// Sem codigo (so "Desconhecido") ou sem suporte do navegador, cai para o nome da base.
const cache = new Map<string, Intl.DisplayNames>();

export function nomePais(p: { pais: string; iso2: string | null; nome_exibicao: string }, idioma: string, desconhecido: string): string {
  if (p.pais === "Desconhecido") return desconhecido;
  if (p.iso2) {
    try {
      let nomes = cache.get(idioma);
      if (!nomes) { nomes = new Intl.DisplayNames([idioma], { type: "region" }); cache.set(idioma, nomes); }
      const n = nomes.of(p.iso2);
      if (n && n !== p.iso2) return n;
    } catch { /* navegador sem Intl.DisplayNames: usa o nome da base */ }
  }
  return p.nome_exibicao;
}