import { httpClient } from '@/services/httpClient'
import type { Operation } from './preparationTypes'
export interface Alternative { id:string; layout:string; titulo:string; texto:string; cta:string; material_id:string; desktop:number[]; mobile:number[]; revisado:boolean; instrucoes:string; origem:string; versao:number }
export interface Block { id:string; tipo:string; escolhida:string; fixada:boolean; alternativas:Alternative[] }
export interface Composition { schema:number; revisao:number; tipo:string; requisitos:Record<string,string>; identidade:{fundo:string;tinta:string;acento:string;fonte:string}; movimento:Record<string,string>; referencias:{url:string;material_id:string;nicho:string;secoes:string;elementos:string;observacoes:string}[]; aprovacao_titular:{estado:string;evidencia:string}; secoes:Block[] }
export interface ImageVersion { id:string; largura:number;altura:number; modelo:string; natureza:string;estado:string; arquivo_url:string; instrucoes:Record<string,unknown>; criado_em:string }
export interface ImageStudio { avaliacao:{largura:number;altura:number;proporcao:number;bytes:number;motivos:string[];incertezas:string[];adequacao:Record<string,string>};original_sha256:string;versoes:ImageVersion[];versao_exportacao:string }
const root=(id:string)=>`/api/ed/empresas/${id}`
export const studioApi={
  composition:(id:string)=>httpClient.get<Composition>(`${root(id)}/composicao`),
  validateComposition:(id:string,data:Composition)=>httpClient.post<Composition>(`${root(id)}/composicao/validar`,data),
  saveComposition:(id:string,data:Composition)=>httpClient.put<Composition>(`${root(id)}/composicao`,data),
  history:(id:string)=>httpClient.get<{criado_em:string;composicao:Composition}[]>(`${root(id)}/composicao/historico`),
  image:(id:string,mid:string)=>httpClient.get<ImageStudio>(`${root(id)}/materiais/${mid}/studio`),
  editImage:(id:string,mid:string,data:Record<string,unknown>)=>httpClient.post<ImageVersion|Operation>(`${root(id)}/materiais/${mid}/studio/editar`,data),
  selectImage:(id:string,mid:string,versao:string,selecionado:boolean)=>httpClient.post(`${root(id)}/materiais/${mid}/studio/selecionar`,{versao,selecionado}),
}
