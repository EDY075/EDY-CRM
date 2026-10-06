"""Prévia portátil dos templates selecionados, sem depender de IA ou do CRM."""
from html import escape
from pathlib import Path
import re


def render(lead,composition,assets):
    identity=composition['identidade']; motion=composition['movimento']
    attached={a.get('material_id'):a for a in assets if a.get('material_id') and not a.get('papel')}
    mobile={a['material_id']:a['arquivo'] for a in assets if a.get('papel')=='alternativa_aprovada' and a.get('destino')=='mobile'}
    def e(value):return escape(str(value),quote=True)
    sections=[]
    for block in composition['secoes']:
        a=next(x for x in block['alternativas'] if x['id']==block['escolhida'])
        asset=attached.get(a['material_id'])
        pos=a['desktop'];mob=a['mobile']
        if asset:
            visual=f'<div class="lp-visual"><img src="{e(asset["arquivo"])}" alt="{e(asset["nome_original"])}" style="--desktop-pos:{pos[0]}% {pos[1]}%;--mobile-pos:{mob[0]}% {mob[1]}%;object-position:var(--desktop-pos)" loading="lazy"></div>'
            if mobile.get(a['material_id']):visual=visual.replace('<img ',f'<picture><source media="(max-width:600px)" srcset="{e(mobile[a["material_id"]])}"><img ').replace('</div>','</picture></div>')
        else:visual='<div class="lp-visual"><div class="lp-placeholder"><span>Imagem autorizada pendente</span><small>Enviar original com autorização · não usar fotos genéricas como registros reais</small></div></div>'
        text=''.join('<p>'+e(line)+'</p>' for line in a['texto'].split('\n') if line.strip()) or '<p>Texto pendente de revisão.</p>'
        heading='h1' if not sections else 'h2'
        copy=f'<div class="lp-copy"><span class="lp-eyebrow">{e(lead["nome"])} · {e(lead["nicho"])}</span><{heading}>{e(a["titulo"] or lead["nome"])}</{heading}>{text}'+('<small class="lp-review">Ilustração de demonstração · não representa produtos ou instalações reais.</small>' if asset and asset.get('natureza_original')=='ilustracao' else '')+('' if a['revisado'] else '<small class="lp-review">Sugestão de texto · revisão pendente</small>')+f'<a class="lp-cta" href="#contato">{e(a["cta"] or "Entrar em contato")} ↗</a></div>'
        content=visual+copy if a['layout']=='compacta' else copy+visual
        if a['layout']=='mosaico':content=f'<div class="lp-mosaic-label"><span>{e(block["tipo"])}</span><strong>{e(lead["nome"])}</strong></div>'+content
        from ed_section import body
        specialized=body(block,a,lead,assets,visual)
        if specialized is not None:content=specialized
        contact=''
        if block['tipo']=='contato':
            for key in ('endereco','horarios','telefone','email'):
                if not lead[key] or lead['fontes'].get(key,{}).get('verificacao')!='confirmado_usuario':continue
                value=e(lead[key])
                if key=='telefone':value=f'<a href="tel:{re.sub(r"[^0-9+]","",lead[key])}">{value}</a>'
                if key=='email':value=f'<a href="mailto:{value}">{value}</a>'
                contact+='<p>'+value+'</p>'
            content+='<div class="lp-contact"><h3>Contato e localização revisados</h3>'+contact+'</div>'
        classes=' '.join('lp-'+k+'-'+v for k,v in [('title',motion['titulos']),('transition',motion['transicoes']),('image',motion['imagens']),('card',motion['cartoes']),('button',motion['botoes']),('cursor',motion['cursor']),('parallax',motion['parallax']),('shader',motion['shader'])])
        ident='contato' if block['tipo']=='contato' else block['id']
        sections.append(f'<section id="{e(ident)}" class="lp-section lp-{a["layout"]} lp-{block["tipo"]} lp-font-{identity["fonte"]} {classes}">{content}</section>')
    if not any(s['tipo']=='contato' for s in composition['secoes']):sections.append('<section id="contato" class="lp-section"><p>Canal e seção de contato pendentes de revisão.</p></section>')
    html=f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(lead['nome'])} · prévia EDY CRM</title><link rel="stylesheet" href="previa-local.css"></head><body><a class="skip" href="#pagina">Ir para o conteúdo</a><header class="preview-header"><strong>{e(lead['nome'])}</strong><span>Prévia visual para revisão · template local</span><a href="#contato">Contato ↗</a><button type="button" id="motion-toggle" aria-pressed="false">Pausar movimento</button></header><main id="pagina" style="--lp-paper:{identity['fundo']};--lp-ink:{identity['tinta']};--lp-accent:{identity['acento']}">{''.join(sections)}</main><footer>EDY CRM · sem publicação · aprovação do titular {e(composition['aprovacao_titular']['estado'])}</footer><script>document.getElementById('motion-toggle').addEventListener('click',e=>{{const paused=document.body.classList.toggle('is-motion-paused');e.target.setAttribute('aria-pressed',String(paused));e.target.textContent=paused?'Retomar movimento':'Pausar movimento'}});document.addEventListener('visibilitychange',()=>document.body.classList.toggle('is-hidden',document.hidden));if(matchMedia('(hover:hover) and (pointer:fine) and (prefers-reduced-motion:no-preference)').matches)document.querySelectorAll('.lp-cursor-halo').forEach(node=>node.addEventListener('pointermove',e=>{{if(document.hidden||document.body.classList.contains('is-motion-paused')||matchMedia('(prefers-reduced-motion:reduce)').matches)return;const b=node.getBoundingClientRect();node.style.setProperty('--cursor-x',(e.clientX-b.left)+'px');node.style.setProperty('--cursor-y',(e.clientY-b.top)+'px')}}));</script></body></html>'''
    source=(Path(__file__).resolve().parent.parent/'frontend/src/ed/studio.css').read_text(encoding='utf-8')
    css=source[source.index('.lp-section'):]
    css+='\nhtml{scroll-behavior:smooth}body{margin:0;background:'+identity['fundo']+';color:'+identity['tinta']+';font-family:Arial,sans-serif}main{container-type:inline-size}.preview-header{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:20px 5vw;background:'+identity['fundo']+';color:'+identity['tinta']+';border-bottom:1px solid currentColor}.preview-header span{font-size:11px}.preview-header a{color:inherit}footer{padding:28px;font-size:12px}.skip{position:absolute;left:-10000px}.skip:focus{left:12px;top:12px;z-index:20;background:#fff;color:#111;padding:16px}.is-hidden *,.is-hidden *:before,.is-motion-paused *,.is-motion-paused *:before{animation-play-state:paused!important}.preview-header button{border:1px solid currentColor;color:inherit;background:transparent;padding:10px;font:inherit;font-size:11px;cursor:pointer}@media(max-width:600px){.preview-header{flex-wrap:wrap}.lp-visual img{object-position:var(--mobile-pos)!important}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}'
    return html,css
