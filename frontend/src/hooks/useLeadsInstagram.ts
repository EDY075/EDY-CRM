import { useQuery } from "@tanstack/react-query"
import { instagramService } from "@/services/instagramService"

export function useLeadsInstagram(
  postId: number | null,
  filtros?: { status?: string; nicho?: string; busca?: string }
) {
  const query = useQuery({
    queryKey: [
      "instagram-leads",
      postId,
      filtros?.status,
      filtros?.nicho,
      filtros?.busca,
    ],
    queryFn: () => instagramService.listarLeads(postId as number, filtros),
    enabled: postId !== null,
  })

  return { leads: query.data?.leads ?? [], ...query }
}
