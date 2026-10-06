import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { instagramService } from "@/services/instagramService"

export function usePostsInstagram(arquivados = false) {
  const query = useQuery({
    queryKey: ["instagram-posts", arquivados],
    queryFn: () => instagramService.listarPosts(arquivados),
  })

  return { posts: query.data?.posts ?? [], ...query }
}

export function usePostInstagramMutations() {
  const queryClient = useQueryClient()
  const invalidar = () =>
    queryClient.invalidateQueries({ queryKey: ["instagram-posts"] })

  const arquivar = useMutation({
    mutationFn: (postId: number) => instagramService.arquivarPost(postId),
    onSuccess: () => {
      invalidar()
      toast.success("Post arquivado.")
    },
  })

  const desarquivar = useMutation({
    mutationFn: (postId: number) => instagramService.desarquivarPost(postId),
    onSuccess: () => {
      invalidar()
      toast.success("Post restaurado.")
    },
  })

  const excluirDefinitivamente = useMutation({
    mutationFn: (postId: number) =>
      instagramService.excluirPostDefinitivamente(postId),
    onSuccess: () => {
      invalidar()
      toast.success("Post excluído definitivamente.")
    },
  })

  return { arquivar, desarquivar, excluirDefinitivamente }
}
