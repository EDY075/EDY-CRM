import { BarChart3, MapPin } from "lucide-react"
import { Link } from "react-router-dom"
import { CLASSE_ACAO_HERO, PageHero } from "@/components/shared/PageHero"

export function GoogleMapsBanner() {
  return (
    <PageHero
      icone={<MapPin className="size-6" />}
      titulo="Leads do Google Maps"
      descricao="Busque empresas sem site ou com site ruim, acompanhe o funil e gerencie follow-ups com sugestões geradas por IA."
      gradiente="from-google-maps-start/85 via-google-maps-mid/85 to-google-maps-end/85"
      acoes={
        <Link to="/analytics" className={CLASSE_ACAO_HERO}>
          <BarChart3 className="size-4" />
          <span className="hidden sm:inline">Analytics</span>
        </Link>
      }
    />
  )
}
