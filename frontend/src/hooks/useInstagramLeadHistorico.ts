import { useQuery } from "@tanstack/react-query"
import { instagramService } from "@/services/instagramService"

export function useInstagramLeadHistorico(leadId: number, habilitado: boolean) {
  return useQuery({
    queryKey: ["instagram-lead-historico", leadId],
    queryFn: () => instagramService.historico(leadId),
    enabled: habilitado,
  })
}
