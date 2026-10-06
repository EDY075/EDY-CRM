import { useQuery } from "@tanstack/react-query"
import { instagramService } from "@/services/instagramService"

export function useFunilInstagram() {
  return useQuery({
    queryKey: ["instagram-analytics", "funil"],
    queryFn: instagramService.funil,
  })
}

export function usePorNichoInstagram() {
  return useQuery({
    queryKey: ["instagram-analytics", "por-nicho"],
    queryFn: instagramService.porNicho,
  })
}

export function useMetricasInstagram() {
  return useQuery({
    queryKey: ["instagram-metricas"],
    queryFn: instagramService.metricas,
  })
}
