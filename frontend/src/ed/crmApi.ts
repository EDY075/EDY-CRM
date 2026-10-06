import {httpClient} from '@/services/httpClient'
export interface CrmRecord{id:string;tipo:string;empresa_id:string|null;versao:number;estado:string;criado_em:string;atualizado_em:string;[key:string]:unknown}
export interface Stage{id:string;nome:string}
export const crmApi={
 list:(kind:string,company='',archived=false,page=1,q='')=>httpClient.get<{items:CrmRecord[];total:number;pagina:number;limite:number}>(`/api/ed/crm/registros/${kind}?pagina=${page}&limite=50&q=${encodeURIComponent(q)}&arquivados=${archived}${company?'&empresa_id='+company:''}`),
 save:(kind:string,data:Partial<CrmRecord>)=>data.id?httpClient.put<CrmRecord>(`/api/ed/crm/registros/${kind}/${data.id}`,data):httpClient.post<CrmRecord>(`/api/ed/crm/registros/${kind}`,data),
 stages:()=>httpClient.get<Stage[]>('/api/ed/crm/funil'),
}
