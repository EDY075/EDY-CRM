import { httpClient } from '@/services/httpClient'
import { csrfHeaders } from './accessState'
export interface VisualDirection {versao:number;estado:string;paleta:string;tipografia:string;estilo:string;composicao:string;movimento:string;invariantes:string}
export interface VisualSection {id:string;titulo:string;texto:string;papel:string;altura:number}
export interface VisualVariant {id:string;secao_id:string;direcao_versao:number;titulo:string;origem:string;fornecedor:string;modelo:string;situacao_uso:string;arquivo_url:string;largura:number;altura:number;consumo:unknown;custo_usd?:number;origem_id?:string;prompt?:string;observacoes?:string}
export interface VisualApproval {id:string;criado_em:string;brief_versao:number;direcao:VisualDirection;montagem:{secao:VisualSection;variante:VisualVariant}[];modo:string}
export interface VisualStudio {empresa_id:string;projeto_id:string;revisao:number;direcao:VisualDirection;secoes:VisualSection[];variantes:VisualVariant[];escolhas:Record<string,string>;aprovacoes:VisualApproval[];quantidade:number;modo:string}
export interface VisualJob {id:string;estado:string;mensagem:string;progresso:number;resultados_parciais?:string[];diagnostico?:unknown;chamada_em_curso?:boolean;parametros:{secao_id:string;quantidade:number;concluidas?:string[]};resultado?:{variantes:string[]};thread_id?:string;turn_id?:string}
const path=(c:string,p='')=>`/api/ed/empresas/${c}/estudio${p?'?projeto_id='+encodeURIComponent(p):''}`
const action=(c:string,n:string,p='')=>path(c)+'/'+n+(p?'?projeto_id='+encodeURIComponent(p):'')
export const visualStudioApi={
 read:(c:string,p='')=>httpClient.get<VisualStudio>(path(c,p)),
 save:(c:string,s:VisualStudio)=>{const {versao,estado,...direcao}=s.direcao;void versao;void estado;return httpClient.put<VisualStudio>(path(c,s.projeto_id),{revisao:s.revisao,direcao,secoes:s.secoes,quantidade:s.quantidade,modo:s.modo})},
 choose:(c:string,s:VisualStudio,id:string)=>httpClient.post<VisualStudio>(action(c,'escolher',s.projeto_id),{revisao:s.revisao,variante_id:id}),
 approve:(c:string,s:VisualStudio,brief:number)=>httpClient.post<VisualApproval>(action(c,'aprovar',s.projeto_id),{revisao:s.revisao,brief_versao:brief,confirmar:true}),
 generate:(c:string,s:VisualStudio,section:string,provider:string,instructions:string,parent:string,key:string,quantity?:number)=>httpClient.post<VisualJob>(action(c,'gerar',s.projeto_id),{revisao:s.revisao,secao_id:section,quantidade:parent?1:quantity??s.quantidade,fornecedor:provider,instrucoes:instructions,origem_id:parent,chave:key}),
 jobs:(c:string,p='')=>httpClient.get<VisualJob[]>(action(c,'operacoes',p)),
 resume:(c:string,id:string)=>httpClient.post(`/api/ed/empresas/${c}/estudio/operacoes/${id}/retomar`,{}),
 upload:async(c:string,s:VisualStudio,file:File,title:string,section:string,notes:string)=>{
  const data=new FormData();data.set('arquivo',file);data.set('titulo',title);data.set('secao_id',section);data.set('projeto_id',s.projeto_id);data.set('observacoes',notes);data.set('uso_referencia','true')
  const r=await fetch(action(c,'importar'),{method:'POST',headers:csrfHeaders(),body:data});const value=await r.json();if(!r.ok)throw Error(value.erro||'Falha ao importar proposta');return value as VisualVariant
 }
}
