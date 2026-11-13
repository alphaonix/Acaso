import { redirect } from "next/navigation";

// Esta tela agora se chama Ajuda; o endereco antigo continua valendo.
export default function Antigo() {
  redirect("/ajuda");
}
