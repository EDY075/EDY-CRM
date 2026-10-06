import { httpClient } from "@/services/httpClient"
import type { TemplateMensagem } from "@/types/template"

export const templatesService = {
  listar: (nicho?: string) =>
    httpClient.get<{ templates: TemplateMensagem[] }>(
      `/api/templates${nicho ? `?nicho=${encodeURIComponent(nicho)}` : ""}`
    ),

  criar: (input: { titulo: string; texto: string; nicho: string | null }) =>
    httpClient.post<{ ok: true; id: number }>("/api/templates", input),

  atualizar: (
    id: number,
    input: { titulo: string; texto: string; nicho: string | null }
  ) =>
    httpClient.put<{ ok: true }>(`/api/templates/${id}`, input),

  excluir: (id: number) =>
    httpClient.delete<{ ok: true }>(`/api/templates/${id}`),

  registrarUso: (id: number) =>
    httpClient.post<{ ok: true }>(`/api/templates/${id}/usar`),
}
