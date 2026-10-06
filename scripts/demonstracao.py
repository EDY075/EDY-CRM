"""Empresas fictícias completas; sem consulta, IA, contatos reais ou banco de trabalho."""
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / 'data-demo'

BUSINESSES = [
    dict(nome='Casa Aurora — demonstração', nicho='Padarias', bairro='Jardim Modelo',
         descricao='Uma padaria fictícia dedicada ao pão de fermentação natural e aos encontros à mesa. Todos os dados deste cadastro são demonstrativos.',
         servicos='Pães de fermentação natural; viennoiserie; café coado; cestas de café da manhã sob encomenda.',
         horarios='Segunda a sábado, 07h–19h. Domingo, 08h–13h. Horários fictícios.',
         site='https://casa-aurora.example', email='contato@casa-aurora.example',
         instagram='https://www.instagram.com/exemplo_ficticio_casa_aurora/',
         endereco='Rua do Exemplo, 100 · Jardim Modelo · Cidade Fictícia, SP',
         publico='Pessoas do bairro que valorizam um café tranquilo, pão artesanal e presentes à mesa.',
         oferta='Pães e café no salão; encomendas de cestas com antecedência. Oferta fictícia, sem preços reais.',
         objetivo='Apresentar a padaria fictícia, explicar a oferta e facilitar o planejamento de uma visita.',
         cta='Planejar minha visita', paleta='#382a22 / #f3ecdf / #a65d34',
         estilo='Editorial acolhedor: papel, terracota, grandes títulos e ilustrações originais.',
         headline='O tempo do pão. O prazer do encontro.',
         itens=[('Feito com tempo', 'Fermentação natural, fornadas ao longo do dia e uma seleção simples de pães. Conteúdo fictício.'),
                ('Para a sua mesa', 'Café coado, viennoiserie e cestas sob encomenda. Nenhum preço ou produto real é anunciado.'),
                ('Sua próxima pausa', 'Conheça o endereço e os horários demonstrativos. Os canais são exemplos e não devem ser acionados.')]),
    dict(nome='Studio Horizonte — demonstração', nicho='Pilates', bairro='Parque Modelo',
         descricao='Estúdio fictício de movimento com orientação individual e aulas em pequenos grupos. Não representa equipe, instalação ou serviço real.',
         servicos='Pilates em aparelhos; sessões de mobilidade; avaliação inicial; aulas em pequenos grupos.',
         horarios='Segunda a sexta, 06h–20h. Sábado, 08h–12h. Horários fictícios.',
         site='https://studio-horizonte.example', email='ola@studio-horizonte.example',
         instagram='https://www.instagram.com/exemplo_ficticio_studio_horizonte/',
         endereco='Alameda Demonstrativa, 200 · Parque Modelo · Cidade Fictícia, SP',
         publico='Adultos que desejam inserir movimento orientado e constância na rotina.',
         oferta='Avaliação inicial e planejamento de aulas em pequenos grupos. Sem promessas clínicas.',
         objetivo='Explicar como funciona o estúdio fictício e apresentar o caminho de uma primeira conversa.',
         cta='Conhecer o primeiro passo', paleta='#213d43 / #edf1e8 / #68857b',
         estilo='Calmo, preciso e arejado; tipografia moderna e ritmo de espaços, sem fotos falsas de pessoas.',
         headline='Movimento com espaço para você.',
         itens=[('Comece pelo seu ritmo', 'Uma conversa inicial ajuda a organizar a rotina de aulas. Processo inteiramente demonstrativo.'),
                ('Presença e constância', 'Pilates, mobilidade e pequenos grupos compõem a oferta fictícia. Sem garantia de resultado físico.'),
                ('Um espaço na rotina', 'Consulte os horários de exemplo. Equipe, certificações e imagens reais não fazem parte desta demonstração.')]),
    dict(nome='Flor de Papel — demonstração', nicho='Floriculturas', bairro='Vila Modelo',
         descricao='Ateliê floral fictício para presentes, pequenos encontros e arranjos sob encomenda. Ilustrações e textos não representam produtos reais.',
         servicos='Buquês sazonais; arranjos para presentes; flores para pequenos eventos; orientação de cuidados.',
         horarios='Terça a sábado, 09h–18h. Segunda, atendimento por encomenda. Horários fictícios.',
         site='https://flor-de-papel.example', email='atelier@flor-de-papel.example',
         instagram='https://www.instagram.com/exemplo_ficticio_flor_de_papel/',
         endereco='Travessa Fictícia, 300 · Vila Modelo · Cidade Fictícia, SP',
         publico='Pessoas que desejam presentear com flores e organizar pequenos encontros.',
         oferta='Buquês e arranjos sob encomenda, conforme disponibilidade sazonal demonstrativa.',
         objetivo='Apresentar o ateliê fictício e orientar a escolha de um arranjo sem prometer estoque ou entrega.',
         cta='Explorar os arranjos', paleta='#49363f / #f4e9df / #9a566c',
         estilo='Botânico editorial; curvas orgânicas, contraste vinho e papel e ilustrações autorais.',
         headline='Um gesto que floresce.',
         itens=[('Cada ocasião, um gesto', 'Buquês sazonais e arranjos para presentes fazem parte desta oferta fictícia.'),
                ('Composição com cuidado', 'Textura, cor e equilíbrio orientam as ilustrações. Elas não são um catálogo real.'),
                ('Vamos imaginar seu arranjo', 'Contato e localização são exemplos. Não há pedido, pagamento ou envio nesta demonstração.')]),
]


def illustration(business, variant=0):
    """Arte geométrica própria. Não fotografia e não saída de fornecedor de IA."""
    palette=business['paleta'].split(' / ')
    canvas=Image.new('RGB',(1440,960),palette[1]);draw=ImageDraw.Draw(canvas)
    ink,accent=palette[0],palette[2]
    draw.ellipse((560,-100,1550,860),fill=ink)
    if business['nicho']=='Padarias':
        for i in range(4):
            x=600+i*100;y=190+i*70
            draw.rounded_rectangle((x,y,x+430,y+150),radius=75,fill=accent,outline=palette[1],width=3)
            for j in range(4):draw.line((x+85+j*75,y+25,x+45+j*75,y+110),fill=palette[1],width=8)
    elif business['nicho']=='Pilates':
        for i in range(6):draw.arc((640-i*22,150-i*22,1290+i*22,800+i*22),30,305,fill=palette[1],width=9)
        draw.ellipse((900,360,1080,540),fill=accent)
    else:
        for x,y in ((840,360),(1070,290),(1090,540),(770,600)):
            for dx,dy in ((-70,0),(70,0),(0,-70),(0,70)):draw.ellipse((x+dx-80,y+dy-80,x+dx+80,y+dy+80),fill=accent,outline=palette[1],width=3)
            draw.ellipse((x-35,y-35,x+35,y+35),fill=palette[1])
    font=ImageFont.load_default(size=36)
    draw.text((70,125),'ESTUDO VISUAL',fill=ink,font=font)
    draw.text((70,185),business['nome'].split(' — ')[0],fill=ink,font=ImageFont.load_default(size=42))
    draw.text((70,820),'ILUSTRAÇÃO ORIGINAL · EMPRESA FICTÍCIA',fill=ink,font=ImageFont.load_default(size=25))
    if variant:canvas=canvas.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    output=io.BytesIO();canvas.save(output,'PNG');return output.getvalue()


def seed(app):
    # Guarda estrita: nem argumento arbitrário, nem fallback para banco de trabalho.
    if Path(app.config['DATA_DIR']).resolve()!=DEMO_ROOT.resolve():
        raise ValueError('O seed só pode operar em data-demo deste checkout.')
    import ed_store as store
    with app.app_context(),store.conectar() as con:
        if con.execute("SELECT 1 FROM ed_config WHERE chave='public-case-seed-v1'").fetchone():return
        if con.execute('SELECT COUNT(*) FROM ed_empresas').fetchone()[0]:
            raise ValueError('data-demo já contém empresas; seed não mistura ou sobrescreve dados.')
    client=app.test_client()
    def call(method,path,**kwargs):
        result=getattr(client,method)(path,**kwargs)
        if result.status_code>=400:raise RuntimeError(f'{path}: {result.status_code} {result.json}')
        return result.json
    for b in BUSINESSES:
        values={k:b[k] for k in ('nome','nicho','bairro','descricao','servicos','horarios','site','email','instagram','endereco')}
        values.update(cidade='Cidade Fictícia',uf='SP',telefone='(00) 0000-0000',redes_sociais=b['instagram'],
            demonstracao=True,confirmado=True,observacoes='100% FICTÍCIO. Domínios .example reservados, telefone inválido e perfil de exemplo. Não contatar, pesquisar, publicar em nome de empresa ou enviar prospecção.',
            briefing=dict(objetivo=b['objetivo'],publico=b['publico'],cta=b['cta'],direcao=b['estilo'],diagnostico='Cadastro completo para demonstrar o fluxo local. Nenhuma empresa real foi consultada.'))
        lead=call('post','/api/ed/empresas',json=values);company=lead['id'];base='/api/ed/empresas/'+company
        mids=[]
        for index in range(2):
            material=call('post',base+'/materiais',data={'arquivo':(io.BytesIO(illustration(b,index)),f'ilustracao-ficticia-{index+1}.png'),
                'origem':'Ilustração geométrica original do script demonstracao.py; sem IA',
                'atribuicao':'EDY GOMES · ilustração de demonstração', 'categoria':'referencia','natureza':'ilustracao',
                'posicao':'Estudo abstrato; não produto, equipe ou instalação real','autorizado':'true'})
            call('patch',base+'/materiais/'+material['id'],json={'selecionado':True});mids.append(material['id'])
        preparation=call('get',base+'/preparacao')
        preparation.update(objetivo=b['objetivo'],publico=b['publico'],oferta=b['oferta'],cta=b['cta'],prospeccao='TEXTO DE DEMONSTRAÇÃO, NÃO ENVIAR. Olá! Este exemplo mostra uma proposta personalizada para '+b['nome']+'. A prévia organiza a apresentação e o contato conforme o brief fictício.')
        preparation['design'].update(paleta=b['paleta'],estilo=b['estilo'],fonte_titulos='Serifada editorial' if b['nicho']!='Pilates' else 'Sans-serif moderna',fonte_texto='Geist / sistema, legível',composicao='Ilustrações próprias, alternância de layout e CTA por âncora interna.')
        preparation['secoes']=[dict(id='abertura',titulo=b['headline'],texto=b['descricao'],revisado=True)]+[
            dict(id=k,titulo=t,texto=text,revisado=True) for k,(t,text) in zip(('apresentacao','servicos','contato'),b['itens'])]
        call('put',base+'/preparacao',json=preparation)
        composition=call('get',base+'/composicao')
        for i,section in enumerate(composition['secoes']):
            section['tipo']=('hero','apresentacao','servicos','contato')[i]
            section['escolhida']=('a','d','c','a')[i]
            for alternative in section['alternativas']:
                alternative.update(material_id=mids[i%2],revisado=True,cta=b['cta'] if i==0 else 'Ver informações de exemplo')
        call('put',base+'/composicao',json=composition)
        analyzed=call('post','/api/ed/adaptativo/analisar',json={'empresa_ids':[company],'chave':'demo-'+company})
        dossier=analyzed['resultados'][0]
        call('post',base+'/adaptativo/revisar',json={'versao':dossier['versao'],'observacoes':'Revisão de dados integralmente fictícios; não valida operação externa.'})
        package=call('post',base+'/exportacoes')
        # Executa o construtor local real já existente, jamais uma inferência simulada.
        construction=call('post',base+'/construcoes/local',json={'exportacao_id':package['id']})
        if construction['estado']!='concluida':raise RuntimeError('Falha na construção determinística de demonstração.')
        call('post','/api/ed/crm/registros/oportunidade',json={'empresa_id':company,'titulo':'Estudo fictício · '+b['nome'],
             'fase':('proposta' if b['nicho']=='Padarias' else 'qualificado' if b['nicho']=='Pilates' else 'novo'),
             'origem':'Seed de demonstração; não cliente ou negociação real','prioridade':'normal','pacote_id':package['id']})
        call('post','/api/ed/crm/registros/tarefa',json={'empresa_id':company,'titulo':'Revisar estudo visual · '+b['nome'],
             'prioridade':'normal','concluida':False,'observacoes':'Exemplo fictício de revisão, sem prazo ou compromisso comercial.'})
        call('post','/api/ed/assistente/conversas',json={'empresa_id':company,'geracao':'templates','modo':'assistido','escopo':'previa'})
        # Importar estudos raster depois do template preserva o contrato do estúdio.
        for index in range(2):
            call('post',base+'/estudio/importar',data={'arquivo':(io.BytesIO(illustration(b,index)),f'composicao-demo-{index+1}.png'),'uso_referencia':'true','secao_id':'pagina'})
    with app.app_context(),store.conectar() as con:
        con.execute('INSERT INTO ed_config VALUES (?,?)',('public-case-seed-v1','true'))


if __name__=='__main__':
    import sys
    sys.path.insert(0,str(ROOT/'backend'))
    from ed_app import criar_app
    seed(criar_app({'DATA_DIR':DEMO_ROOT,'PREVIEW_ROOT':DEMO_ROOT/'previas','RUN_JOBS':False}))
    print('Três empresas fictícias preparadas somente em data-demo.')
