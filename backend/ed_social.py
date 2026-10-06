"""Meta autorizada e coleta pública separadas, com associação humana e proveniência."""
import json
import re
import time
from urllib.parse import urlsplit,quote
from flask import jsonify,request,send_file
from PIL import Image
import ed_store as store
import ed_secrets
from ed_connectors import request_json,auth
from ed_services import config,lock,ler_job,log,fingerprint
from ed_tasks import iniciar,ativo


def perfil(raw):
    value=store.texto(raw,500).strip()
    if value.startswith(('https://','http://')):
        parsed=urlsplit(value)
        if parsed.hostname not in ('instagram.com','www.instagram.com') or parsed.query or parsed.fragment: raise ValueError('Use URL de perfil Instagram sem consulta.')
        value=parsed.path.strip('/')
    value=value.removeprefix('@')
    if not re.fullmatch(r'[a-zA-Z0-9._]{1,30}',value) or value.lower() in ('p','reel','reels','stories','explore','accounts'):
        raise ValueError('Informe @usuário ou URL de um perfil; posts e buscas não identificam a conta.')
    return value.lower()


def normalizar(rows,provider,username):
    profiles=[];media=[];seen=set()
    def image(post,child,index):
        if child.get('media_type')=='VIDEO' or child.get('type')=='Video': return
        url=child.get('media_url') or child.get('displayUrl')
        if not url: return
        try: url=store.url(url)
        except ValueError: return
        if url in seen: return
        seen.add(url)
        origin=post.get('permalink') or post.get('url') or 'https://www.instagram.com/'+username+'/'
        try: origin=store.url(origin)
        except ValueError: origin='https://www.instagram.com/'+username+'/'
        media.append(dict(id=store.novo_id(),url=url,origem=origin,categoria='a_confirmar',post_id=str(post.get('id',''))[:100],
            data_post=str(post.get('timestamp',''))[:100],carrossel_indice=index,largura=child.get('dimensionsWidth'),altura=child.get('dimensionsHeight'),
            legenda=str(post.get('caption',''))[:4000],perfil='https://www.instagram.com/'+username+'/',fornecedor=provider,
            consultado_em=store.agora(),autorizado=False,melhor_arquivo='Arquivo de mídia fornecido pela fonte; não é screenshot. Resolução efetiva conferida ao importar.'))
    for row in rows[:50]:
        if not isinstance(row,dict): continue
        if row.get('username'):
            profiles.append(dict(usuario=str(row.get('username'))[:30],nome=str(row.get('fullName') or row.get('name') or '')[:300],
                bio=str(row.get('biography') or '')[:4000],site=str(row.get('externalUrl') or row.get('website') or '')[:1000],
                origem='https://www.instagram.com/'+str(row['username'])[:30]+'/',fornecedor=provider,estado='candidato'))
        posts=row.get('latestPosts',[]) if isinstance(row.get('latestPosts'),list) else []
        if row.get('media_url') or row.get('displayUrl') or row.get('childPosts') or row.get('children'): posts=[row]+posts
        for post in posts[:30]:
            children=post.get('children',{}).get('data',[]) if isinstance(post.get('children'),dict) else post.get('childPosts',[])
            if children:
                for i,child in enumerate(children[:20]):
                    if isinstance(child,dict): image(post,child,i)
            else:
                images=post.get('images',[])
                if images and all(isinstance(x,str) for x in images):
                    for i,url in enumerate(images[:20]): image(post,{**post,'displayUrl':url},i)
                else: image(post,post,0)
    return dict(perfis=profiles[:20],imagens=media[:100],pendencias=['Acesso à mídia não concede direitos de uso. Conferir autorização e pessoas identificadas.','Links de mídia podem expirar; importação pode falhar mesmo depois de uma coleta válida.'])


def evidencias(result,lead):
    """Comparar dados disponíveis; sinais não promovem candidatos automaticamente."""
    from ed_sites import classificar
    for candidate in result.get('perfis',[]):
        signals=[];text=store.normalizar(candidate.get('nome','')+' '+candidate.get('bio',''))
        name=store.normalizar(lead['nome'])
        if len(name)>3 and name in text:signals.append('Nome completo encontrado no perfil; sozinho não confirma associação.')
        for key in ('cidade','bairro'):
            value=store.normalizar(lead.get(key,''))
            if len(value)>3 and value in text:signals.append('Localização publicada corresponde a '+key+': '+lead[key])
        digits=re.sub(r'\D','',candidate.get('bio',''));phone=re.sub(r'\D','',lead.get('telefone',''))
        if len(phone)>=8 and phone in digits:signals.append('Contato numérico corresponde ao registrado: '+lead['telefone'])
        site=candidate.get('site','');known=lead.get('site','')
        if site and known and classificar(site)['tipo']=='candidato' and classificar(known)['tipo']=='candidato':
            a,b=urlsplit(site),urlsplit(known)
            if a.hostname==b.hostname and a.path.rstrip('/')==b.path.rstrip('/'):signals.append('Perfil publica o mesmo endereço de site cadastrado. Confira a associação do site e a filial.')
        candidate['evidencias']=signals or ['Nenhum vínculo suficiente encontrado nos dados recebidos. Compare fontes antes de confirmar.']
        candidate['estado']='candidato'
    return result


class ApifyPublic:
    def test(self,settings):
        value=request_json('GET','https://api.apify.com/v2/users/me',headers=auth('apify'))
        if not value.get('data',{}).get('id'): raise ValueError('Apify não confirmou usuário autenticado.')
        return dict(mensagem='Token Apify validado; execução do Actor e direitos da mídia ainda precisam de operação própria.',consumo=None)

    def collect(self,job,progress):
        p=job['parametros']; user=p['perfil']; cap=p['orcamento']; phases=['details'] if p['modo']=='descobrir' else ['details','posts']
        rows=[];usage=[];runs=[]
        for phase in phases:
            payload={'resultsType':phase,'resultsLimit':p['limite'],'addParentData':True}
            if p['modo']=='descobrir': payload.update(search=p['consulta'],searchType='user',searchLimit=p['limite'])
            else: payload['directUrls']=['https://www.instagram.com/'+user+'/']
            run=request_json('POST',f'https://api.apify.com/v2/acts/apify~instagram-scraper/runs?waitForFinish=0&timeout=180&maxTotalChargeUsd={cap/len(phases):.4f}',headers=auth('apify'),payload=payload).get('data',{})
            rid=str(run.get('id',''))
            if not re.fullmatch(r'[a-zA-Z0-9]{1,80}',rid): raise ValueError('Apify não retornou ID de execução válido.')
            runs.append(rid);progress(25,f'Apify: coletando {phase}; prazo de 180 s e teto informado ao fornecedor.',runs=runs)
            started=time.monotonic()
            try:
                while run.get('status') in ('READY','RUNNING','ABORTING'):
                    ativo(job['id'])
                    if time.monotonic()-started>190: raise ValueError('Coleta Apify excedeu prazo; execução remota recebeu pedido de cancelamento.')
                    time.sleep(2)
                    run=request_json('GET','https://api.apify.com/v2/actor-runs/'+rid,headers=auth('apify')).get('data',{})
                    progress(45,'Apify: aguardando resultados; edições da ficha preservadas.',runs=runs)
            except (InterruptedError,ValueError):
                try: request_json('POST','https://api.apify.com/v2/actor-runs/'+rid+'/abort',headers=auth('apify'))
                except ValueError: pass
                raise
            did=str(run.get('defaultDatasetId',''))
            if not re.fullmatch(r'[a-zA-Z0-9]{1,80}',did): raise ValueError('Apify sem dataset disponível.')
            items=request_json('GET',f'https://api.apify.com/v2/datasets/{did}/items?clean=true&limit=50',headers=auth('apify'),allow_list=True)
            if not isinstance(items,list): raise ValueError('Dataset Apify inválido.')
            rows.extend(items);normalized=normalizar(rows,'apify',user)
            progress(70,'Resultados parciais disponíveis para revisão.',parcial=normalized,runs=runs)
            if type(run.get('usageTotalUsd')) in (int,float): usage.append(run['usageTotalUsd'])
            if run.get('status')!='SUCCEEDED': raise ValueError('Actor '+str(run.get('status','desconhecido'))+'. Resultados parciais preservados; nenhuma identidade confirmada.')
        return normalized,{'usageTotalUsd':sum(usage)} if usage else None


class MetaOwn:
    def test(self,settings):
        from ed_connectors import InstagramAuthorized
        return InstagramAuthorized().test(settings)

    def collect(self,job,progress):
        settings=config('instagram'); version,account=settings.get('api_version',''),settings.get('account_id','')
        if not re.fullmatch(r'v\d{2}\.\d+',version) or not account.isdigit(): raise ValueError('Configure conta e versão Meta suportada.')
        url=f'https://graph.instagram.com/{version}/{account}'
        me=request_json('GET',url+'?fields=id,username,name',headers=auth('instagram'))
        if perfil(str(me.get('username','')))!=job['parametros']['perfil']: raise ValueError('A conta autorizada não corresponde ao perfil solicitado. Não concede acesso a outras contas.')
        progress(40,'Conta autorizada corresponde ao perfil; lendo mídia.')
        media=request_json('GET',url+'/media?fields=id,media_type,media_url,permalink,timestamp,children{id,media_type,media_url}&limit='+str(job['parametros']['limite']),headers=auth('instagram'))
        rows=[me]+media.get('data',[])
        result=normalizar(rows,'instagram',job['parametros']['perfil'])
        if media.get('paging',{}).get('next'): result['pendencias'].append('Limite desta execução atingido. Mais páginas existem; não consultadas automaticamente.')
        result['pendencias'].append('Bio, website e legendas não solicitados neste fluxo Instagram Login; a documentação atual limita esses campos. Use entrada manual ou outra fonte adequada.')
        return result,None


class MetaDiscovery:
    def test(self,settings):
        version,account=settings.get('api_version',''),settings.get('account_id','')
        if not re.fullmatch(r'v\d{2}\.\d+',version) or not account.isdigit(): raise ValueError('Configure conta profissional vinculada à Página, token Facebook Login e versão da API.')
        data=request_json('GET',f'https://graph.facebook.com/{version}/{account}?fields=id,username',headers=auth('meta_discovery'))
        if str(data.get('id'))!=account: raise ValueError('Meta não confirmou conta configurada.')
        return dict(mensagem='Conta Facebook Login consultada. Business Discovery requer permissões próprias e outra operação; não acessa perfis pessoais.',consumo=None,limitado=True)

    def collect(self,job,progress):
        settings=config('meta_discovery');self.test(settings)
        version,account=settings['api_version'],settings['account_id'];username=job['parametros']['perfil']
        fields=f'business_discovery.username({username}){{id,username,name,biography,website,media.limit({job["parametros"]["limite"]}){{id,media_type,media_url,permalink,caption,timestamp,children{{id,media_type,media_url}}}}}}'
        progress(40,'Consultando outra conta profissional via Business Discovery; não é busca universal.')
        data=request_json('GET',f'https://graph.facebook.com/{version}/{account}?fields='+quote(fields,safe=''),headers=auth('meta_discovery')).get('business_discovery')
        if not isinstance(data,dict) or perfil(str(data.get('username','')))!=username: raise ValueError('Business Discovery não retornou o perfil profissional solicitado. Pode haver limite de idade, permissão ou conta pessoal.')
        result=normalizar([data]+data.get('media',{}).get('data',[]),'meta_discovery',username)
        if data.get('media',{}).get('paging',{}).get('next'): result['pendencias'].append('Há mais mídia; não coletada nesta execução limitada.')
        return result,None


def associacao(company):
    lead=store.ler_empresa(company)
    with store.conectar() as con: row=con.execute('SELECT valor FROM ed_config WHERE chave=?',('associacao:instagram:'+company,)).fetchone()
    data=json.loads(row['valor']) if row else None
    if data and data['url']!=lead['instagram']: data=None
    return data or dict(estado='pendente',url=lead['instagram'],evidencia='')


def confirmar(company,data):
    if not isinstance(data,dict) or set(data)!={'perfil','valor_anterior','evidencia'}: raise ValueError('Revisão do perfil inválida.')
    username=perfil(data['perfil']); evidence=store.texto(data['evidencia'],2000)
    if len(evidence)<15: raise ValueError('Registre evidências conferidas: endereço, contato ou vínculo com site; nome sozinho não basta.')
    with lock,store.conectar() as con:
        row=con.execute('SELECT dados FROM ed_empresas WHERE id=?',(company,)).fetchone()
        if not row: raise LookupError('Empresa não encontrada.')
        lead=json.loads(row['dados'])
        if lead['instagram']!=data['valor_anterior']: return None
        link='https://www.instagram.com/'+username+'/'
        lead.setdefault('historico_instagram',[]).append(dict(valor_anterior=lead['instagram'],valor_novo=link,fonte_anterior=lead['fontes'].get('instagram'),evidencia=evidence,revisado_em=store.agora()))
        lead['instagram']=link; lead['fontes']['instagram']={**store.fonte('instagram',link,'revisao_usuario',link,True),'evidencia':evidence}
        con.execute('UPDATE ed_empresas SET dados=?,atualizado_em=? WHERE id=?',(json.dumps(lead,ensure_ascii=False),store.agora(),company))
        state=dict(estado='confirmado',url=link,evidencia=evidence,revisado_em=store.agora())
        con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',('associacao:instagram:'+company,json.dumps(state,ensure_ascii=False)))
    return state


def media_job(company,jid,image):
    job=ler_job(jid)
    if job.get('empresa_id')!=company or job['tipo']!='instagram_coleta': raise LookupError('Coleta não pertence a esta empresa.')
    result=job.get('resultado') or job.get('parcial') or {}
    item=next((x for x in result.get('imagens',[]) if x['id']==image),None)
    if not item: raise LookupError('Material não encontrado na coleta.')
    return job,item


def registrar(bp):
    @bp.get('/empresas/<company>/instagram')
    def social_get(company):
        with store.conectar() as con:
            jobs=[json.loads(r['dados']) for r in con.execute('SELECT dados FROM ed_operacoes ORDER BY rowid DESC')]
        return jsonify(associacao=associacao(company),execucoes=[j for j in jobs if j.get('empresa_id')==company and j['tipo']=='instagram_coleta'][:20])

    @bp.post('/empresas/<company>/instagram/confirmar')
    def social_confirm(company):
        out=confirmar(company,request.get_json())
        if out is None: return jsonify(erro='Perfil mudou durante a revisão. Atualize antes de confirmar.'),409
        return jsonify(out)

    @bp.post('/empresas/<company>/instagram/pesquisar')
    def social_research(company):
        data=request.get_json()
        if not isinstance(data,dict) or set(data)!={'fornecedor','perfil','modo','consulta','limite','orcamento'}: raise ValueError('Pesquisa Instagram inválida.')
        provider=data['fornecedor']
        if provider not in ('apify','instagram','meta_discovery'): raise ValueError('Escolha Meta autorizada, Business Discovery ou Apify público.')
        if not ed_secrets.get(provider): raise ValueError('Sem credencial do fornecedor. Confirme o perfil e envie materiais manualmente.')
        limit=data['limite']; budget=data['orcamento']
        if type(limit)!=int or not 1<=limit<=20 or type(budget) not in (int,float) or not .01<=budget<=5: raise ValueError('Limite de 1–20 e orçamento de US$ 0,01–5.')
        mode=data['modo']
        if mode not in ('descobrir','materiais') or mode=='descobrir' and provider!='apify': raise ValueError('Descoberta por consulta está disponível somente no adaptador Apify.')
        user=perfil(data['perfil']) if mode=='materiais' else ''
        query=store.texto(data['consulta'],300)
        if mode=='descobrir' and len(query)<3: raise ValueError('Descreva nome e localização para pesquisar candidatos.')
        association=associacao(company)
        if mode=='materiais' and (association['estado']!='confirmado' or perfil(association['url'])!=user): raise ValueError('Confirme o vínculo do perfil com a empresa antes de coletar materiais.')
        parameters=dict(perfil=user,modo=mode,consulta=query,limite=limit,orcamento=budget)
        def worker(job,progress):
            try:
                result,usage={'apify':ApifyPublic(),'instagram':MetaOwn(),'meta_discovery':MetaDiscovery()}[provider].collect(job,progress)
                evidencias(result,store.ler_empresa(company))
                progress(90,'Conferindo resultados sem substituir informações revisadas.',consumo=usage)
                if not result['perfis'] and not result['imagens']: raise ValueError('Fonte retornou zero resultados. Pesquisa não concluída; revise perfil ou use materiais enviados.')
                result['empresa_id']=company
                log(provider,dict(estado='conectado',mensagem='Coleta respondeu; associação e direitos continuam sujeitos à revisão.',data=store.agora(),fingerprint=fingerprint(provider),consumo=usage,tipo_validacao='consulta_perfil_midia'))
                return result
            except ValueError:
                log(provider,dict(estado='erro',mensagem='Coleta falhou. Consulte execução; nenhuma ficha substituída.',data=store.agora(),fingerprint=fingerprint(provider)))
                raise
        return jsonify(iniciar(provider,'instagram_coleta',company,parameters,worker)),202

    @bp.get('/empresas/<company>/instagram/<jid>/imagens/<image>')
    def social_preview(company,jid,image):
        from ed_enrich import imagem_candidata
        job,item=media_job(company,jid,image)
        return send_file(imagem_candidata(job,item))

    @bp.post('/empresas/<company>/instagram/<jid>/imagens/<image>/importar')
    def social_import_media(company,jid,image):
        from ed_enrich import imagem_candidata
        data=request.get_json()
        if not isinstance(data,dict) or set(data)!={'autorizado','atribuicao'}: raise ValueError('Informe situação de uso e atribuição.')
        authorized=store.booleano(data['autorizado']); attribution=store.texto(data['atribuicao'],1000)
        if authorized and not attribution: raise ValueError('Identifique titular e autorização de uso.')
        job,item=media_job(company,jid,image)
        association=associacao(company)
        if association['estado']!='confirmado' or association['url']!=item['perfil']: raise ValueError('O vínculo do perfil mudou ou está pendente. Reveja antes de importar.')
        file=imagem_candidata(job,item)
        with lock,store.conectar() as con:
            lead=store.ler_empresa(company)
            if len(lead['materiais'])>=30: raise ValueError('Limite de trinta materiais.')
            if any(m.get('coleta_social',{}).get('url')==item['url'] for m in lead['materiais']): raise ValueError('Este arquivo já foi importado nesta empresa.')
            with Image.open(file) as im:
                ext={'PNG':'png','JPEG':'jpg','WEBP':'webp'}[im.format]; width,height=im.size
            mid=store.novo_id(); name=mid+'.'+ext; target=store.arquivo_seguro('materiais',company+'/'+name);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(file.read_bytes())
            asset=dict(arquivo=name,nome_original='instagram-'+(item['post_id'] or image)+'-'+str(item['carrossel_indice'])+'.'+ext,
                categoria='a_confirmar',origem=item['origem'],atribuicao=attribution,posicao='A confirmar; pessoas não são equipe sem evidência.',
                autorizado=authorized,selecionado=False,criado_em=store.agora(),coleta_social={**item,'largura':width,'altura':height,'empresa_id':company},
                arquivo_url=f'/api/ed/empresas/{company}/materiais/{mid}/arquivo')
            con.execute('INSERT INTO ed_materiais VALUES (?,?,?)',(mid,company,json.dumps(asset,ensure_ascii=False)))
        return jsonify(id=mid,**asset),201
