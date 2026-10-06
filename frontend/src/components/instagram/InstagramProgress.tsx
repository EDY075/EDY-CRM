import { Loader2 } from "lucide-react"
import type { EstadoAnaliseInstagram } from "@/types/instagram"

interface InstagramProgressProps {
  estado: EstadoAnaliseInstagram
}

export function InstagramProgress({ estado }: InstagramProgressProps) {
  const indeterminado = estado.etapa === "raspando" || estado.etapa === "classificando"
  const percentual =
    estado.etapa === "enriquecendo" && estado.perfis_encontrados > 0
      ? Math.min(
          100,
          Math.round(
            (estado.perfis_processados / estado.perfis_encontrados) * 100
          )
        )
      : 0

  return (
    <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-3">
      <div className="flex items-center gap-2 text-sm">
        <Loader2 className="size-4 animate-spin text-instagram-mid" />
        <span>{estado.mensagem}</span>
      </div>

      {estado.etapa === "enriquecendo" && (
        <p className="text-xs text-muted-foreground">
          Encontrados {estado.perfis_encontrados} · Processados{" "}
          {estado.perfis_processados}
        </p>
      )}

      <div className="h-2 overflow-hidden rounded-full bg-border">
        {indeterminado ? (
          <div className="h-full w-[30%] animate-[deslizar_1.2s_ease-in-out_infinite] rounded-full bg-gradient-to-r from-instagram-start via-instagram-mid to-instagram-end" />
        ) : (
          <div
            className="h-full rounded-full bg-gradient-to-r from-instagram-start via-instagram-mid to-instagram-end transition-all"
            style={{ width: `${percentual}%` }}
          />
        )}
      </div>
    </div>
  )
}
