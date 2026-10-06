import { useQuery } from "@tanstack/react-query"
import { instagramService } from "@/services/instagramService"

export function useNichosInstagram() {
  return useQuery({
    queryKey: ["instagram-nichos"],
    queryFn: instagramService.listarNichos,
  })
}
