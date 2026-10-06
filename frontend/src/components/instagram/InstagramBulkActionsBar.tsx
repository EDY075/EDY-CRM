import { motion } from "framer-motion"
import { Trash2, X } from "lucide-react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useBulkMutationsInstagram } from "@/hooks/useBulkMutationsInstagram"
import { LABEL_STATUS } from "@/lib/constants"
import { STATUS_VALIDOS, type StatusLead } from "@/types/lead"

interface InstagramBulkActionsBarProps {
  postId: number
  leadIdsSelecionados: number[]
  onLimparSelecao: () => void
  modoIgnorados?: boolean
}

export function InstagramBulkActionsBar({
  postId,
  leadIdsSelecionados,
  onLimparSelecao,
  modoIgnorados = false,
}: InstagramBulkActionsBarProps) {
  const { atualizarStatusEmLote, ignorarEmLote, excluirEmLoteDefinitivamente } =
    useBulkMutationsInstagram(postId)

  const handleMudarStatus = (status: StatusLead) => {
    atualizarStatusEmLote.mutate(
      { leadIds: leadIdsSelecionados, status },
      { onSuccess: onLimparSelecao }
    )
  }

  const handleExcluir = () => {
    if (modoIgnorados) {
      excluirEmLoteDefinitivamente.mutate(leadIdsSelecionados, {
        onSuccess: onLimparSelecao,
      })
    } else {
      ignorarEmLote.mutate(leadIdsSelecionados, { onSuccess: onLimparSelecao })
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
      className="fixed bottom-5 left-1/2 z-30 flex -translate-x-1/2 items-center gap-3 rounded-full border border-border bg-card px-4 py-2.5 shadow-lg"
    >
      <span className="text-sm font-medium">
        {leadIdsSelecionados.length} selecionado(s)
      </span>

      {!modoIgnorados && (
        <Select onValueChange={(v) => handleMudarStatus(v as StatusLead)}>
          <SelectTrigger className="h-8 w-[160px]">
            <SelectValue placeholder="Mudar status" />
          </SelectTrigger>
          <SelectContent>
            {STATUS_VALIDOS.filter((s) => s !== "ignorado").map((status) => (
              <SelectItem key={status} value={status}>
                {LABEL_STATUS[status]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button size="sm" variant="outline" className="text-destructive hover:bg-destructive/10">
            <Trash2 className="size-4" />
            {modoIgnorados ? "Excluir definitivamente" : "Excluir"}
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {modoIgnorados
                ? `Excluir ${leadIdsSelecionados.length} lead(s) definitivamente?`
                : `Excluir ${leadIdsSelecionados.length} lead(s)?`}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {modoIgnorados
                ? "Isso apaga esses leads de vez do banco de dados. Não tem como desfazer."
                : "Eles não vão mais aparecer na lista deste post."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={handleExcluir}>
              {modoIgnorados ? "Excluir definitivamente" : "Excluir"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Button size="icon" variant="ghost" className="size-8" onClick={onLimparSelecao}>
        <X className="size-4" />
      </Button>
    </motion.div>
  )
}
