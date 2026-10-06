import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import { Erro } from './shared'

export function LocalConnectionTest({ enabled }: { enabled: boolean }) {
  const client = useQueryClient(), [id, setId] = useState('')
  const test = useMutation({ mutationFn: () => api.testarIntegracao('osm'), onSuccess: j => { setId(j.id); client.setQueryData(['ed', 'operacao', j.id], j) } })
  const query = useQuery({ queryKey: ['ed', 'operacao', id], queryFn: async () => { const j = await api.operacao(id); if (!['na_fila', 'pesquisando'].includes(j.estado)) client.invalidateQueries({ queryKey: ['ed', 'integracoes-status'] }); return j }, enabled: !!id, refetchInterval: q => q.state.data && ['na_fila', 'pesquisando'].includes(q.state.data.estado) ? 1200 : false })
  const cancel = useMutation({ mutationFn: () => api.cancelarOperacao(id), onSuccess: () => client.invalidateQueries({ queryKey: ['ed', 'operacao', id] }) })
  const running = !!query.data && ['na_fila', 'pesquisando'].includes(query.data.estado)
  return <><p>Teste consulta um salão em Recife, sem cadastrar leads. Respeita o intervalo de uma consulta por minuto junto às campanhas.</p><button className="ed-button" disabled={!enabled || test.isPending || running} onClick={() => test.mutate()}>Testar conexão OpenStreetMap</button>
    {test.isError && <Erro error={test.error} />}{query.isError && <Erro error={query.error} />}{cancel.isError && <Erro error={cancel.error} />}
    {query.data && <div role="status"><p>{query.data.mensagem}</p><progress max={100} value={query.data.progresso} aria-label="Teste OpenStreetMap" />{running && <button className="ed-button" disabled={cancel.isPending} onClick={() => cancel.mutate()}>Cancelar teste OpenStreetMap</button>}</div>}</>
}
