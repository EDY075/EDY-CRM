import { AtSign } from "lucide-react"

export function InstagramEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border py-16 text-center">
      <AtSign className="size-8 text-muted-foreground" />
      <p className="text-sm text-muted-foreground">
        Nenhum post analisado ainda. Cole o link de um post acima para começar.
      </p>
    </div>
  )
}
