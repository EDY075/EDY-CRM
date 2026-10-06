import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { templatesService } from "@/services/templatesService"

export function useTemplates(nicho?: string) {
  const query = useQuery({
    queryKey: ["templates", nicho],
    queryFn: () => templatesService.listar(nicho),
  })

  return { templates: query.data?.templates ?? [], ...query }
}

export function useTemplateMutations() {
  const queryClient = useQueryClient()
  const invalidar = () =>
    queryClient.invalidateQueries({ queryKey: ["templates"] })

  const criar = useMutation({
    mutationFn: templatesService.criar,
    onSuccess: () => {
      invalidar()
      toast.success("Template salvo.")
    },
  })

  const atualizar = useMutation({
    mutationFn: (input: {
      id: number
      titulo: string
      texto: string
      nicho: string | null
    }) => templatesService.atualizar(input.id, input),
    onSuccess: () => {
      invalidar()
      toast.success("Template atualizado.")
    },
  })

  const excluir = useMutation({
    mutationFn: templatesService.excluir,
    onSuccess: () => {
      invalidar()
      toast.success("Template excluído.")
    },
  })

  const registrarUso = useMutation({
    mutationFn: templatesService.registrarUso,
    onSuccess: invalidar,
  })

  return { criar, atualizar, excluir, registrarUso }
}
