import { redirect } from "next/navigation";

// A tela Explorar foi incorporada a "O que faz voltar"; o endereco antigo continua valendo.
export default function Explorar() {
  redirect("/fatores");
}
