import { Archive, BarChart3 } from "lucide-react"
import { Link } from "react-router-dom"
import { InstagramIcon } from "@/components/icons/InstagramIcon"
import { CLASSE_ACAO_HERO, PageHero } from "@/components/shared/PageHero"

export function InstagramBanner() {
  return (
    <PageHero
      icone={<InstagramIcon className="size-6" />}
      titulo="Leads do Instagram"
      descricao="Cole o link de um post para extrair os comentários, enriquecer os perfis e classificar os leads automaticamente por IA."
      gradiente="from-instagram-start/85 via-instagram-mid/85 to-instagram-end/85"
      acoes={
        <>
          <Link to="/instagram/arquivados" className={CLASSE_ACAO_HERO}>
            <Archive className="size-4" />
            <span className="hidden sm:inline">Arquivados</span>
          </Link>
          <Link to="/instagram/analytics" className={CLASSE_ACAO_HERO}>
            <BarChart3 className="size-4" />
            <span className="hidden sm:inline">Analytics</span>
          </Link>
        </>
      }
    />
  )
}
