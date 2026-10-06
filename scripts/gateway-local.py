"""Gerencia o gateway oficial isolado. Segredos próprios em DPAPI, nenhum token Codex."""
import argparse,json,os,secrets,subprocess,sys,time
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from ed_app import criar_app
import ed_secrets
from ed_visual_providers import catalog,record
CONFIG=json.loads((ROOT/'config/gateway-runtime.json').read_text())
SOURCE=(ROOT/CONFIG['codigo']).resolve();DATA=(ROOT/CONFIG['dados']).resolve();BASE='http://127.0.0.1:'+str(CONFIG['porta'])
for path in (SOURCE,DATA):
    if not path.is_relative_to(ROOT):raise ValueError('Gateway fora do projeto.')
parser=argparse.ArgumentParser();parser.add_argument('acao',choices=['iniciar','parar','saude','preparar-chave']);args=parser.parse_args()
DATA.mkdir(parents=True,exist_ok=True);pid_file=DATA/'processo.json'
app=criar_app({'RUN_JOBS':False,'RECOVER_JOBS':False})
with app.app_context():
    password=ed_secrets.get('gateway_dashboard')
    if args.acao=='iniciar':
        if not (SOURCE/'.next/standalone/custom-server.js').is_file():raise SystemExit('Execute scripts/preparar-gateway.ps1 antes de iniciar.')
        try:
            if requests.get(BASE+'/api/health',timeout=2).status_code==200:raise SystemExit('Já há um serviço nesta porta. Nenhum processo adicional iniciado.')
        except requests.RequestException:pass
        if not password:password=secrets.token_urlsafe(32);ed_secrets.put('gateway_dashboard',password)
        home=ROOT/'.cache/gateway-home';home.mkdir(parents=True,exist_ok=True)
        temp=ROOT/'.cache/gateway-tmp';temp.mkdir(parents=True,exist_ok=True)
        env={**os.environ,'DATA_DIR':str(DATA),'USERPROFILE':str(home),'APPDATA':str(home/'AppData/Roaming'),'LOCALAPPDATA':str(home/'AppData/Local'),'TEMP':str(temp),'TMP':str(temp),'HOSTNAME':'127.0.0.1','PORT':str(CONFIG['porta']),'NEXT_TELEMETRY_DISABLED':'1','INITIAL_PASSWORD':password}
        with (ROOT/'logs/gateway.stdout.log').open('ab') as out,(ROOT/'logs/gateway.stderr.log').open('ab') as err:
            p=subprocess.Popen(['node',str(SOURCE/'.next/standalone/custom-server.js')],cwd=SOURCE,env=env,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        pid_file.write_text(json.dumps({'pid':p.pid,'cwd':str(SOURCE),'commit':CONFIG['commit'],'porta':CONFIG['porta']}))
        print('Gateway iniciado em loopback, PID '+str(p.pid)+'. Autenticação própria protegida no cofre. Nenhum upstream importado.')
    elif args.acao=='parar':
        if not pid_file.is_file():raise SystemExit('Sem processo registrado.')
        saved=json.loads(pid_file.read_text());pid=saved['pid']
        # Comprovar processo correto antes de terminá-lo; não matar pelo número de porta.
        check=subprocess.run(['powershell','-NoProfile','-Command',f'(Get-CimInstance Win32_Process -Filter "ProcessId = {int(pid)}").CommandLine'],capture_output=True,text=True)
        if str(SOURCE/'.next/standalone/custom-server.js').lower() not in check.stdout.lower():raise SystemExit('PID não corresponde ao gateway registrado; nenhum processo terminado.')
        subprocess.run(['powershell','-NoProfile','-Command',f'Stop-Process -Id {int(pid)}'],check=True);pid_file.unlink();print('Gateway registrado parado; dados preservados.')
    elif args.acao=='saude':
        r=requests.get(BASE+'/api/health',timeout=5);print(json.dumps({'http':r.status_code,'saude':r.json(),'porta':CONFIG['porta'],'inferência_validada':False},ensure_ascii=False))
    elif args.acao=='preparar-chave':
        if not password:raise SystemExit('Inicie o gateway para preparar sua senha própria.')
        with requests.Session() as s:
            s.trust_env=False
            r=s.post(BASE+'/api/auth/login',json={'password':password},timeout=10);r.raise_for_status()
            r=s.patch(BASE+'/api/settings',json={'requireLogin':True,'requireApiKey':True,'cloudEnabled':False,'tunnelEnabled':False,'tailscaleEnabled':False,'pxpipeAutoInstall':False,'rtkEnabled':False,'capacityAdapter':{'vision':{'enabled':False,'models':[]},'audioInput':{'enabled':False,'models':[]}}},timeout=10);r.raise_for_status()
            if not ed_secrets.get('gateway'):
                r=s.post(BASE+'/api/keys',json={'name':'EDY CRM · loopback'},timeout=10);r.raise_for_status();ed_secrets.put('gateway',r.json()['key'])
        models=catalog('gateway');record('gateway',{'estado':'limitado','data':__import__('ed_store').agora(),'operacao':'catalogo_autenticado','mensagem':'Gateway local autenticado e catálogo consultado. Configure um upstream próprio autorizado; inferência de texto/visão/imagem ainda não validada.','quantidade_modelos':len(models)})
        report={'host':'127.0.0.1','porta':CONFIG['porta'],'runtime':CONFIG,'saude_real':True,'autenticacao_gateway_real':True,'catalogo_real':len(models),'inferencia_real':False,'upstream_configurado':False,'sessao_codex_reutilizada':False}
        (ROOT/'examples/estudio-visual/gateway-real.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False))
