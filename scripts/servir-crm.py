"""Launcher portátil. A demonstração só grava em data-demo deste checkout."""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def configuration(demo=False):
    directory = ROOT / ('data-demo' if demo else 'data')
    return {'DATA_DIR': directory, 'PREVIEW_ROOT': directory / 'previas',
            'RUN_JOBS': not demo, 'RUN_SITE_JOBS': not demo}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--port', type=int, default=5128)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Use uma porta entre 1024 e 65535.')
    from dotenv import load_dotenv
    # A demonstração não carrega chaves de arquivo nem inicia executores.
    if not args.demo:
        load_dotenv(ROOT / '.env', override=False)
    else:
        # Isolamento só neste processo; não altera a sessão do aplicativo Codex.
        for key in list(os.environ):
            if key.startswith('ED_CRM_') or key=='OPENAI_API_KEY':
                os.environ.pop(key)
        os.environ['CODEX_HOME']=str(ROOT/'data-demo'/'codex-sem-login')
    from ed_app import criar_app
    config=configuration(args.demo)
    config['PREVIEW_FRAME_ORIGIN']=f'http://127.0.0.1:{args.port}'
    app = criar_app(config)
    if args.demo:
        from demonstracao import seed
        seed(app)
    from waitress import serve
    print(f'EDY CRM: http://127.0.0.1:{args.port} · '+('DADOS FICTÍCIOS / sem IA' if args.demo else 'banco próprio deste checkout'), flush=True)
    serve(app, host='127.0.0.1', port=args.port, threads=6)


if __name__ == '__main__':
    main()
