"""Entrada local do EDY CRM; rotas e automações legadas ficam desativadas."""
import logging
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

import ed_store as store


def criar_app(config=None):
    app = Flask(__name__)
    app.config.update(DATA_DIR=Path(__file__).resolve().parent.parent / 'data',
                      RUN_JOBS=True, MAX_CONTENT_LENGTH=9 * 1024 * 1024)
    if config:
        app.config.update(config)
    from ed_routes import bp
    app.register_blueprint(bp)
    with app.app_context():
        store.preparar()
    from ed_access import setup
    setup(app)
    from ed_workflows import start_scheduler
    start_scheduler(app)
    from ed_batches import scheduler
    scheduler(app)

    @app.before_request
    def proteger_origem():
        if request.path.startswith('/api/') and not (request.endpoint or '').startswith(('ed.','ed_acesso_')):
            abort(404)
        if request.host.split(':')[0] not in ('127.0.0.1', 'localhost', '[::1]'):
            abort(403)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('Origin')
            if origin and origin not in (request.host_url.rstrip('/'), 'http://127.0.0.1:5128', 'http://localhost:5128',
                                         'http://localhost:5178', 'http://127.0.0.1:5178'):
                abort(403)
            if request.headers.get('Sec-Fetch-Site') == 'cross-site':
                abort(403)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        frames=' '.join('http://127.0.0.1:'+str(port) for port in range(5131,5191))
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; frame-src "+frames+"; frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(Exception)
    def erro(exc):
        if isinstance(exc, ValueError):
            return jsonify(erro=str(exc)), 400
        if isinstance(exc, LookupError):
            return jsonify(erro=str(exc)), 404
        if isinstance(exc, HTTPException):
            messages = {413: 'Arquivo muito grande. Use imagens de até 8 MB.',
                        403: exc.description if exc.description!='You don\'t have the permission to access the requested resource. It is either read-protected or not readable by the server.' else 'Origem não autorizada.', 404: 'Recurso não encontrado.',
                        415: 'Envie os dados em JSON.'}
            return jsonify(erro=messages.get(exc.code, exc.description)), exc.code
        logging.exception('Erro interno no EDY CRM')
        return jsonify(erro='Erro interno. Consulte o log local do servidor.'), 500

    dist = Path(__file__).resolve().parent.parent / 'frontend' / 'dist'

    @app.get('/', defaults={'path': 'index.html'})
    @app.get('/<path:path>')
    def frontend(path):
        if path.startswith('api/'):
            abort(404)
        resolved = (dist / path).resolve()
        if not resolved.is_relative_to(dist.resolve()):
            abort(404)
        if not (dist / 'index.html').exists():
            return jsonify(erro='Execute npm run build na pasta frontend.'), 503
        return send_from_directory(dist, path if resolved.is_file() else 'index.html')

    return app


if __name__ == '__main__':
    from waitress import serve
    application = criar_app()
    print('EDY CRM: http://127.0.0.1:5128', flush=True)
    serve(application, host='127.0.0.1', port=5128, threads=6)
