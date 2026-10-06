import {csrfHeaders} from './accessState'
import { httpClient } from '@/services/httpClient'
import type { Campanha, Config, Documento, Empresa, Exportacao, Material, Pesquisa, IntegracoesStatus, SiteAssociation, SiteProposal } from './types'
import type { Connector, Operation, Preparation } from './preparationTypes'

const base = '/api/ed'
export const api = {
  empresas: (params = '') => httpClient.get<Empresa[]>(`${base}/empresas${params}`),
  empresa: (id: string) => httpClient.get<Empresa>(`${base}/empresas/${id}`),
  associacaoSite: (id: string) => httpClient.get<SiteAssociation>(`${base}/empresas/${id}/site/associacao`),
  verificarSite: (id: string, site: string) => httpClient.post<SiteProposal>(`${base}/empresas/${id}/site/verificar`, { site }),
  confirmarSite: (id: string, site: string, evidencia: string) => httpClient.post<Empresa>(`${base}/empresas/${id}/site/confirmar`, { site, evidencia }),
  pesquisa: (id: string) => httpClient.get<Pesquisa | null>(`${base}/empresas/${id}/pesquisa`),
  diagnosticarPesquisa: (id: string, job: string) => httpClient.post<NonNullable<Pesquisa['diagnostico_atual']>>(`${base}/empresas/${id}/pesquisas/${job}/diagnostico`, {}),
  pesquisarSite: (id: string, site: string, fornecedor = 'site_local') => httpClient.post<Pesquisa>(`${base}/empresas/${id}/pesquisa`, { site_confirmado: true, site, fornecedor }),
  cancelarPesquisa: (id: string, job: string) => httpClient.post<Pesquisa>(`${base}/empresas/${id}/pesquisas/${job}/cancelar`, {}),
  preparacao: (id: string) => httpClient.get<Preparation>(`${base}/empresas/${id}/preparacao`),
  salvarPreparacao: (id: string, p: Preparation) => httpClient.put<Preparation>(`${base}/empresas/${id}/preparacao`, p),
  pendenciasPreparacao: (id: string) => httpClient.get<string[]>(`${base}/empresas/${id}/preparacao/pendencias`),
  configurarIntegracao: (provider: string, data: Record<string, string>) => httpClient.put<Connector>(`${base}/integracoes/${provider}`, data),
  testarIntegracao: (provider: string) => httpClient.post<Operation>(`${base}/integracoes/${provider}/testar`, {}),
  operacao: (id: string) => httpClient.get<Operation>(`${base}/operacoes/${id}`),
  cancelarOperacao: (id: string) => httpClient.post<Operation>(`${base}/operacoes/${id}/cancelar`, {}),
  gerarTexto: (id: string, revisao: number) => httpClient.post<Operation>(`${base}/empresas/${id}/preparacao/ia`, { revisao }),
  aplicarSugestoes: (id: string, pesquisa: string, sugestoes: { id: string; valor_atual: string }[]) =>
    httpClient.post<Empresa>(`${base}/empresas/${id}/pesquisa/aplicar`, { pesquisa_id: pesquisa, sugestoes }),
  importarCandidata: (id: string, pesquisa: string, imagem: string, atribuicao: string) =>
    httpClient.post<Material>(`${base}/empresas/${id}/pesquisas/${pesquisa}/imagens/${imagem}/importar`, { autorizado: true, atribuicao }),
  criar: (data: Partial<Empresa>) => httpClient.post<Empresa>(`${base}/empresas`, data),
  salvar: (id: string, data: Partial<Empresa>) => patch<Empresa>(`${base}/empresas/${id}`, data),
  config: () => httpClient.get<Config>(`${base}/config`),
  integracoesStatus: () => httpClient.get<IntegracoesStatus>(`${base}/integracoes/status`),
  configurar: (enabled: boolean) => httpClient.put<Config>(`${base}/config`, { osm_habilitado: enabled }),
  campanhas: () => httpClient.get<Campanha[]>(`${base}/campanhas`),
  buscar: (data: Partial<Campanha>) => httpClient.post<Campanha>(`${base}/campanhas`, data),
  campanha: (id: string, action: string) => httpClient.post<Campanha>(`${base}/campanhas/${id}/${action}`),
  documento: (id: string) => httpClient.get<Documento>(`${base}/empresas/${id}/documento`),
  exportar: (id: string) => httpClient.post<Exportacao>(`${base}/empresas/${id}/exportacoes`),
  material: (id: string, mid: string, data: Partial<Material>) => patch<Material>(`${base}/empresas/${id}/materiais/${mid}`, data),
  previa: (id: string, data: { url: string; exportacao_id: string; observacoes: string }) =>
    httpClient.post(`${base}/empresas/${id}/previas`, data),
  upload: async (id: string, data: FormData): Promise<Material> => {
    const res = await fetch(`${base}/empresas/${id}/materiais`, { method: 'POST', headers:csrfHeaders(), body: data })
    const result = await res.json()
    if (!res.ok) throw new Error(result.erro || 'Falha ao enviar imagem.')
    return result as Material
  },
}
function patch<T>(url: string, data: unknown): Promise<T> {
  return fetch(url, { method: 'PATCH', headers: { 'Content-Type': 'application/json',...csrfHeaders() }, body: JSON.stringify(data) })
    .then(async res => {
      const result = await res.json()
      if (!res.ok) throw new Error(result.erro || 'Falha ao salvar.')
      return result as T
    })
}
