import { Skeleton } from "@/components/ui/skeleton"
import { usePostInstagramMutations, usePostsInstagram } from "@/hooks/usePostsInstagram"
import { PostCard } from "@/components/instagram/PostCard"
import { InstagramEmptyState } from "@/components/instagram/InstagramEmptyState"

interface PostListProps {
  postSelecionadoId: number | null
  onSelecionarPost: (postId: number) => void
  arquivados?: boolean
  onRetomar?: (postId: number) => void
}

export function PostList({
  postSelecionadoId,
  onSelecionarPost,
  arquivados = false,
  onRetomar,
}: PostListProps) {
  const { posts, isLoading } = usePostsInstagram(arquivados)
  const { arquivar, desarquivar, excluirDefinitivamente } =
    usePostInstagramMutations()

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-[120px]" />
        ))}
      </div>
    )
  }

  if (posts.length === 0) {
    return arquivados ? (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Nenhum post arquivado.
      </p>
    ) : (
      <InstagramEmptyState />
    )
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {posts.map((post) => (
        <PostCard
          key={post.id}
          post={post}
          onClick={() => onSelecionarPost(post.id)}
          selecionado={post.id === postSelecionadoId}
          onArquivar={
            arquivados ? undefined : () => arquivar.mutate(post.id)
          }
          onDesarquivar={
            arquivados ? () => desarquivar.mutate(post.id) : undefined
          }
          onExcluirDefinitivamente={
            arquivados
              ? () => excluirDefinitivamente.mutate(post.id)
              : undefined
          }
          onRetomar={onRetomar ? () => onRetomar(post.id) : undefined}
        />
      ))}
    </div>
  )
}
