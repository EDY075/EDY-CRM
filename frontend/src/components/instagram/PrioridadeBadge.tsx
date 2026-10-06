import { Badge } from "@/components/ui/badge"
import { COR_PRIORIDADE, LABEL_PRIORIDADE } from "@/lib/constants"
import { cn } from "@/lib/utils"
import type { PrioridadeLead } from "@/types/instagram"

interface PrioridadeBadgeProps {
  prioridade: PrioridadeLead | null
}

export function PrioridadeBadge({ prioridade }: PrioridadeBadgeProps) {
  if (!prioridade) {
    return (
      <Badge variant="outline" className="font-medium uppercase tracking-wide">
        Pendente de análise
      </Badge>
    )
  }

  return (
    <Badge
      variant="outline"
      className={cn(
        "font-medium uppercase tracking-wide",
        COR_PRIORIDADE[prioridade]
      )}
    >
      {LABEL_PRIORIDADE[prioridade]}
    </Badge>
  )
}
