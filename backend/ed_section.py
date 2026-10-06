"""Estruturas semânticas por seção, sem assumir fatos comerciais."""
from html import escape


def body(block,a,lead,assets,visual):
    kind=block['tipo']
    if kind not in ('servicos','produtos','processo','faq','galeria','equipe','rodape','cta','dados','operacoes'):return None
    e=lambda v:escape(str(v),quote=True)
    header=f'<div class="lp-section-heading"><span class="lp-eyebrow">{e(lead["nome"])} · {e(kind)}</span><h2>{e(a["titulo"])}</h2>'+('' if a['revisado'] else '<small>Texto proposto · revisão pendente</small>')+'</div>'
    lines=[x for x in a['texto'].splitlines() if x.strip()]
    if kind=='faq':
        rows=[]
        for line in lines:
            q,*answer=line.split('|');rows.append(f'<details><summary>{e(q)}</summary><p>{e("|".join(answer) or "Resposta a revisar; não inventar.")}</p></details>')
        content='<div class="lp-items">'+(''.join(rows) or '<p>Perguntas e respostas verificadas pendentes.</p>')+'</div>'
    elif kind in ('galeria','equipe'):
        selected=[x for x in assets if x.get('arquivo') and not x.get('papel') and (kind!='equipe' or x.get('direcao',{}).get('natureza')=='pessoa')]
        content='<p>'+e(a['texto'])+'</p><div class="lp-media-grid">'+(''.join(f'<figure><img src="{e(x["arquivo"])}" alt="{e(x["nome_original"])}" loading="lazy"><figcaption>{e("Ilustração de demonstração" if x.get("natureza_original")=="ilustracao" else x["nome_original"])}</figcaption></figure>' for x in selected) or visual)+'</div>'
    elif kind=='rodape':content=f'<p>{e(a["texto"])}</p><nav aria-label="Links do rodapé"><a href="#contato">Contato</a></nav><small>Prévia para revisão · não publicada</small>'
    elif kind=='cta':content=f'<p>{e(a["texto"])}</p><a class="lp-cta" href="#contato">{e(a["cta"])} ↗</a>'
    else:content='<div class="lp-items'+(' lp-steps' if kind=='processo' else '')+'">'+(''.join(f'<article><span class="lp-item-number">{i+1:02}</span><p>{e(line)}</p></article>' for i,line in enumerate(lines)) or '<p>Conteúdo confirmado pendente.</p>')+'</div>'
    return header+content
