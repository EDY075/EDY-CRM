import { usePorNichoCombinado } from "@/hooks/useCombinado"
import { BreakdownPorNicho } from "@/components/dashboard/BreakdownPorNicho"

export function BreakdownNichoCombinado() {
  const { data, isLoading } = usePorNichoCombinado()

  return (
    <BreakdownPorNicho
      nichos={data?.nichos}
      isLoading={isLoading}
      corBarra="bg-primary"
    />
  )
}
