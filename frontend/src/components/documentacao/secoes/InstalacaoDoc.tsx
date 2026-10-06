import {
  DocSection,
  DocH2,
  DocList,
  DocCallout,
  DocCode,
} from "@/components/documentacao/DocSection"

export function InstalacaoDoc() {
  return (
    <DocSection titulo="Instalação e requisitos">
      <DocCallout variante="warning">
        Esta ferramenta faz scraping do Google Maps e do Instagram, o que
        viola os Termos de Uso das duas plataformas. Use por sua conta e
        risco — a conta pessoal usada no Instagram pode ser bloqueada.
      </DocCallout>

      <DocH2>Requisitos</DocH2>
      <DocList>
        <li>
          <strong>Windows</strong> — os scripts <DocCode>.bat</DocCode> e o
          executável do scraper são específicos para Windows.
        </li>
        <li>
          <strong>Python 3.11+</strong> — para o backend Flask.
        </li>
        <li>
          <strong>Node.js 20+</strong> — para rodar o frontend React (o
          scraper do Maps também usa Node.js internamente, via Playwright).
        </li>
      </DocList>

      <DocH2>1. Backend</DocH2>
      <DocList>
        <li>
          <DocCode>py -m pip install -r requirements.txt</DocCode>
        </li>
        <li>
          Copie <DocCode>.env.example</DocCode> para <DocCode>.env</DocCode> e
          preencha ao menos uma chave de IA gratuita (Gemini, Groq ou NVIDIA).
        </li>
        <li>
          Baixe o <DocCode>google-maps-scraper.exe</DocCode> (projeto{" "}
          <DocCode>gosom/google-maps-scraper</DocCode>) e coloque na raiz do
          backend, ao lado de <DocCode>app.py</DocCode>. Sem ele, buscas no
          Maps falham.
        </li>
        <li>
          Rode com <DocCode>py app.py</DocCode> —{" "}
          <DocCode>http://localhost:5000</DocCode>.
        </li>
      </DocList>

      <DocH2>2. Frontend</DocH2>
      <DocList>
        <li>
          Dentro de <DocCode>prospeccao-react/</DocCode>:{" "}
          <DocCode>npm install</DocCode> e depois{" "}
          <DocCode>npm run dev</DocCode>.
        </li>
        <li>
          Acessível em <DocCode>http://localhost:5173</DocCode>. O proxy da
          API já vem configurado (sem precisar mexer em CORS).
        </li>
        <li>
          Existe um atalho <DocCode>Abrir Prospecção.bat</DocCode> que sobe
          backend + frontend juntos e abre o navegador automaticamente.
        </li>
      </DocList>

      <DocH2>3. Instagram (opcional, só se for usar esse canal)</DocH2>
      <DocList>
        <li>
          Rode <DocCode>py instagram\login.py SEU_USUARIO</DocCode> uma
          única vez (pede senha e, se solicitado, código de 2FA).
        </li>
        <li>
          Isso salva a sessão em{" "}
          <DocCode>instagram/sessao/session-SEU_USUARIO.json</DocCode>. Se a
          sessão expirar, basta rodar o login de novo.
        </li>
      </DocList>
    </DocSection>
  )
}
