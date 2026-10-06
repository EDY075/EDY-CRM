import { ArrowLeft } from "lucide-react"
import { Link } from "react-router-dom"
import { Header } from "@/components/layout/Header"
import { InstagramMetricsDashboard } from "@/components/instagram/InstagramMetricsDashboard"
import { FunilConversaoInstagram } from "@/components/instagram/FunilConversaoInstagram"
import { BreakdownNichoInstagram } from "@/components/instagram/BreakdownNichoInstagram"

export function InstagramAnalyticsPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />

      <main className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6">
        <Link
          to="/instagram"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Voltar para leads do Instagram
        </Link>

        <h2 className="bg-gradient-to-r from-instagram-start via-instagram-mid to-instagram-end bg-clip-text text-xl font-semibold tracking-tight text-transparent">
          Analytics do Instagram
        </h2>

        <InstagramMetricsDashboard />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <FunilConversaoInstagram />
          <BreakdownNichoInstagram />
        </div>
      </main>
    </div>
  )
}
