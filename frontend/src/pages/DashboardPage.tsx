import { BarChart3, ListTodo, MapPin, Zap } from "lucide-react"
import { Header } from "@/components/layout/Header"
import { InstagramIcon } from "@/components/icons/InstagramIcon"
import { VisaoGeralCombinada } from "@/components/dashboard/VisaoGeralCombinada"
import { FunilConversaoCombinado } from "@/components/dashboard/FunilConversaoCombinado"
import { BreakdownNichoCombinado } from "@/components/dashboard/BreakdownNichoCombinado"
import { NavCard } from "@/components/dashboard/NavCard"

export function DashboardPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />

      <main className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6">
        <VisaoGeralCombinada />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <FunilConversaoCombinado />
          <BreakdownNichoCombinado />
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <NavCard
            to="/sessao"
            titulo="Sessão de prospecção"
            descricao="Um lead por vez, do mais quente ao mais frio - modo foco"
            icone={<Zap className="size-5" />}
          />
          <NavCard
            to="/tarefas"
            titulo="Tarefas de hoje"
            descricao="Follow-ups vencidos e leads quentes com abordagem em 1 clique"
            icone={<ListTodo className="size-5" />}
          />
          <NavCard
            to="/leads"
            titulo="Leads do Maps"
            descricao="Lista, kanban e nova busca de leads do Google Maps"
            icone={<MapPin className="size-5" />}
          />
          <NavCard
            to="/instagram"
            titulo="Leads do Instagram"
            descricao="Analisar posts e gerenciar leads do Instagram"
            icone={<InstagramIcon className="size-5" />}
            destaqueInstagram
          />
          <NavCard
            to="/analytics"
            titulo="Analytics do Maps"
            descricao="Funil e conversão por nicho, só do Google Maps"
            icone={<BarChart3 className="size-5" />}
          />
        </div>
      </main>
    </div>
  )
}
