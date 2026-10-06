import { usePorNichoInstagram } from "@/hooks/useInstagramAnalytics"
import { BreakdownPorNicho } from "@/components/dashboard/BreakdownPorNicho"

export function BreakdownNichoInstagram() {
  const { data, isLoading } = usePorNichoInstagram()

  return (
    <BreakdownPorNicho
      nichos={data?.nichos}
      isLoading={isLoading}
      corBarra="bg-gradient-to-r from-instagram-start to-instagram-end"
    />
  )
}
