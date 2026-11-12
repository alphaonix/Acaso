// O navegador fala so com este dominio: /api/* e encaminhado para a API (sem CORS; o cookie de sessao e do mesmo dominio).
// API_URL e lido na hora do build (compose passa http://api:8000); em desenvolvimento local o padrao e a porta 8000.
const API = process.env.API_URL || "http://localhost:8000";

export default {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};
