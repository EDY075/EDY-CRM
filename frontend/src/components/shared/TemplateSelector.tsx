import { useState } from "react"
import { BookmarkPlus, FileText } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useTemplateMutations, useTemplates } from "@/hooks/useTemplates"

interface TemplateSelectorProps {
  textoAtual: string
  onUsarTemplate: (texto: string) => void
  nichoSugerido?: string | null
}

export function TemplateSelector({
  textoAtual,
  onUsarTemplate,
  nichoSugerido,
}: TemplateSelectorProps) {
  const { templates } = useTemplates()
  const { criar, registrarUso } = useTemplateMutations()
  const [modalAberto, setModalAberto] = useState(false)
  const [titulo, setTitulo] = useState("")

  const handleUsar = (id: string) => {
    const template = templates.find((t) => t.id === Number(id))
    if (!template) return
    onUsarTemplate(template.texto)
    registrarUso.mutate(template.id)
  }

  const handleSalvar = () => {
    if (!titulo.trim() || !textoAtual.trim()) return
    criar.mutate(
      { titulo: titulo.trim(), texto: textoAtual, nicho: nichoSugerido ?? null },
      { onSuccess: () => setModalAberto(false) }
    )
    setTitulo("")
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        {templates.length > 0 && (
          <Select onValueChange={handleUsar}>
            <SelectTrigger className="h-8 w-[200px] text-xs">
              <SelectValue placeholder="Usar template salvo" />
            </SelectTrigger>
            <SelectContent>
              {templates.map((template) => (
                <SelectItem key={template.id} value={String(template.id)}>
                  {template.titulo}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        <Button
          size="sm"
          variant="outline"
          disabled={!textoAtual.trim()}
          onClick={() => setModalAberto(true)}
        >
          <BookmarkPlus className="size-4" />
          Salvar como template
        </Button>
      </div>

      <Dialog open={modalAberto} onOpenChange={setModalAberto}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="size-4" />
              Salvar como template
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>Título do template</Label>
              <Input
                value={titulo}
                onChange={(e) => setTitulo(e.target.value)}
                placeholder="Ex: Primeiro contato - advogados"
              />
            </div>
            <p className="rounded-md bg-muted/40 p-2 text-xs text-muted-foreground">
              {textoAtual}
            </p>
            <Button
              size="sm"
              disabled={!titulo.trim() || criar.isPending}
              onClick={handleSalvar}
            >
              {criar.isPending ? "Salvando..." : "Salvar template"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
