# Muro de arrimo — aplicativo Android

O mesmo núcleo de cálculo do aplicativo de computador (`core/`) rodando **dentro do celular**, sem servidor e
sem internet depois de instalado. A interface é uma página feita para tela de celular; o Python roda no
aparelho com o [Pyodide](https://pyodide.org) (Python em WebAssembly). Nenhuma fórmula foi reescrita:
`montar.py` empacota a pasta `core/` inteira.

## O que tem

- **Dados**: as seções 1 a 9 da entrada, com os mesmos rótulos, limites, padrões e textos de ajuda.
- **Resultado**: vereditos, os quatro fatores, avisos, croqui, tabela de verificações e tabela de forças.
- **Armaduras**: materiais, bitolas e espaçamentos, verificações da NBR 6118 e notas do dimensionamento.
- **Solo**: parâmetros por tipo de solo e NSPT, com botão para aplicar ao aterro ou à fundação.
- **Projeto**: salvar e abrir o arquivo `.json` (o mesmo do aplicativo de computador), compartilhar o resumo.

Ficaram de fora desta versão: leitura de sondagem em PDF, memorial em PDF, exportação para Excel, desenho
das armaduras e as ferramentas (base mínima, estudo paramétrico).

## Como obter o APK

O repositório tem um fluxo automático (`.github/workflows/android.yml`). A cada alteração em `android/` ou
`core/` o GitHub monta o aplicativo e gera o APK:

1. No GitHub, abra a aba **Actions** e a execução mais recente de **Aplicativo Android**.
2. Em **Artifacts**, baixe **MuroDeArrimo-apk** e extraia o `app-debug.apk`.
3. Copie o APK para o celular e abra-o. O Android pede para permitir a instalação de fonte desconhecida.

É um APK de depuração, assinado com a chave padrão de testes: serve para instalar direto no aparelho, não
para publicar na Play Store.

## Alternativa sem APK (PWA)

O artefato **MuroDeArrimo-web** (ou a pasta `android/www` montada no computador) é um site estático. Publicado
em qualquer hospedagem com HTTPS, abre no Chrome do celular e pode ser instalado por **Adicionar à tela
inicial**; depois da primeira abertura funciona sem internet.

## Montar e testar no computador

```bash
cd android
npm install
python montar.py
python -m http.server 8600 --directory www
```

Abra `http://localhost:8600` no navegador (no Chrome, F12 e o modo de celular).

## Arquivos

| Arquivo | Papel |
|---|---|
| `ponte.py` | Liga o núcleo à interface: formulário, validação e resultados em JSON |
| `src/` | Interface (`index.html`, `app.js`, `estilo.css`), motor em segundo plano (`motor.js`), uso offline (`sw.js`) |
| `montar.py` | Monta `www/`: interface, `programa.zip` (núcleo + ponte), Pyodide, numpy, pydantic e ícones |
| `capacitor.config.json` | Empacotamento em APK com o Capacitor |
| `../tests/test_android.py` | Testes da ponte |
