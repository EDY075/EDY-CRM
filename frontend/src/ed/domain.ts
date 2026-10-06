export const etapas: Record<string, string> = {
  encontrado: 'Encontrado', pesquisando: 'Em pesquisa', documento_pronto: 'Documento pronto',
  exportado_codex: 'Exportado para o Codex', previa_pronta: 'Prévia pronta',
}
export const estados: Record<string, string> = {
  na_fila: 'Na fila', pesquisando: 'Pesquisando', concluida: 'Concluída', parcial: 'Resultado parcial',
  cancelada: 'Cancelada', erro: 'Falha na coleta', interrompida: 'Interrompida',sem_resultados:'Sem resultados · revisar busca',
}
export function date(value: string) {
  return new Date(value).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'short' })
}
