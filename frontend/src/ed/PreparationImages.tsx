import type { Empresa } from './types'
import type { Placement } from './preparationTypes'
import { Field } from './shared'

export function PreparationImages({ empresa, images, onChange }: { empresa: Empresa; images: Placement[]; onChange: (m: Placement[]) => void }) {
  const update = (index: number, m: Placement) => onChange(images.map((x, i) => i === index ? m : x))
  return <section className="ed-panel ed-form"><h2>Imagens e enquadramento</h2><p>Escolha o papel de cada imagem. A seleção para exportação e a autorização continuam na galeria Materiais.</p>
    {empresa.materiais.length === 0 && <p>Sem imagens na galeria. Importe candidatas ou envie arquivos na aba Materiais. Use placeholders até confirmar direitos.</p>}
    <Field label="Adicionar imagem à composição"><select value="" onChange={e => { if (!e.target.value) return; onChange([...images, { material_id: e.target.value, funcao: 'abertura', natureza: 'a_confirmar', pessoa: '', desktop: { x: 50, y: 50, recorte: 'cover', enquadramento: '' }, mobile: { x: 50, y: 50, recorte: 'cover', enquadramento: '' } }]) }}><option value="">Escolher material…</option>{empresa.materiais.filter(m => !images.some(x => x.material_id === m.id)).map(m => <option key={m.id} value={m.id}>{m.nome_original} · {m.selecionado && m.autorizado ? 'anexável' : 'não selecionado/autorizado'}</option>)}</select></Field>
    {images.map((m, i) => { const asset = empresa.materiais.find(x => x.id === m.material_id); return <article key={m.material_id} className="ed-placement">
      <h3>{asset?.nome_original || 'Material ausente'}</h3><p>{asset?.autorizado && asset.selecionado ? 'Autorizado e selecionado para o ZIP.' : 'Não será anexado; confira autorização e seleção na galeria.'}</p>
      <div className="ed-form-grid"><Field label="Função na página"><select value={m.funcao} onChange={e => update(i, { ...m, funcao: e.target.value })}>{['abertura', 'ambiente', 'servicos', 'produtos', 'pessoas', 'logo', 'referencia'].map(x => <option key={x}>{x}</option>)}</select></Field>
        <Field label="Natureza da imagem"><select value={m.natureza} onChange={e => update(i, { ...m, natureza: e.target.value })}><option value="a_confirmar">Identidade a confirmar</option><option value="registro_empresa">Registro real da empresa · conferido</option><option value="ilustrativa">Ilustrativa · não é registro real</option><option value="referencia">Referência de design</option></select></Field></div>
      {m.funcao === 'pessoas' && <Field label="Pessoas identificadas e evidência"><input maxLength={200} value={m.pessoa} onChange={e => update(i, { ...m, pessoa: e.target.value })} placeholder="Nome e vínculo confirmados; sem inferir pela fotografia" /></Field>}
      <div className="ed-framing-grid">{(['desktop', 'mobile'] as const).map(v => <div key={v}><h4>{v === 'desktop' ? 'Desktop' : 'Celular'}</h4>
        {asset && <div className={`ed-frame-preview ${v}`}><img src={asset.arquivo_url} alt={`Prévia de recorte em ${v}; ${m.natureza}`} style={{ objectFit: m[v].recorte as 'cover' | 'contain', objectPosition: `${m[v].x}% ${m[v].y}%` }} /></div>}
        <div className="ed-form-grid">{(['x', 'y'] as const).map(axis => <Field key={axis} label={`${v} · posição ${axis.toUpperCase()} (%)`}><input type="number" min={0} max={100} value={m[v][axis]} onChange={e => update(i, { ...m, [v]: { ...m[v], [axis]: Number(e.target.value) } })} /></Field>)}</div>
        <Field label={`${v} · recorte`}><select value={m[v].recorte} onChange={e => update(i, { ...m, [v]: { ...m[v], recorte: e.target.value } })}><option value="cover">Preencher · cortar excedente</option><option value="contain">Mostrar imagem inteira</option></select></Field>
        <Field label={`${v} · enquadramento`}><input value={m[v].enquadramento} maxLength={500} onChange={e => update(i, { ...m, [v]: { ...m[v], enquadramento: e.target.value } })} placeholder="Ex.: preservar rosto e espaço para o título" /></Field>
      </div>)}</div><button className="ed-button" type="button" onClick={() => onChange(images.filter((_, n) => n !== i))}>Remover da composição</button>
    </article> })}
  </section>
}
