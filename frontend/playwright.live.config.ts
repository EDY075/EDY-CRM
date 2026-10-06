import { defineConfig } from '@playwright/test'

// Verificação explícita, somente leitura de dados, da aplicação realmente servida.
// Não inicia nem substitui servidor/banco do usuário.
export default defineConfig({
  testDir: './live-tests', workers: 1, timeout: 45000,
  outputDir: '../.cache/live-browser-results', reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5128', channel: 'chrome', viewport: { width: 1440, height: 900 }, screenshot: 'only-on-failure' },
})
