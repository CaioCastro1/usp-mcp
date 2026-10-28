# Handoff: Fujita, site no molde do Polishare e conector MCP — 27/10/2026

Substitui `2026-10-20-fujita-v0.md`. Spec: `docs/superpowers/specs/2026-10-19-acervo-de-questoes-v0-design.md`
(ver a seção "Mudança de direção (23/10/2026): o site é o produto").

## Onde as coisas estão

| O quê | Onde |
|---|---|
| Dados (JSON) | `polos-e-zeros/acervo`, privado; clone `~/Padrao/GitHub/Pessoal/acervo` |
| Código (validador, Worker, site, conector) | `polos-e-zeros/fujita`, privado; clone `~/Padrao/GitHub/Pessoal/fujita` |
| Produção | `https://fujita.polos-e-zeros.workers.dev`, conta Cloudflare polos-e-zeros; deploy manual com o token em `fujita/worker/.env` (`set -a; . ./.env; set +a; pnpm exec wrangler deploy`) |
| Login | Google restrito a `@usp.br`, app OAuth em modo "Testando" (até 100 usuários de teste); funcionou com a conta do Caio |
| Dev local | `fujita/worker`: `cp .dev.vars.example .dev.vars && pnpm dev` (sem login em localhost); gerar o pacote antes com `uv run scripts/publicar.py ../acervo` |

## Estado (tudo no branch `conector-mcp` do fujita, PR fujita#1 aberta, publicado em produção a partir do branch)

- **Site = explorador de pastas igual ao Polishare** (pedido explícito do Caio em 26/10, depois de rejeitar
  uma versão em cartões): barra com "1º…6º Semestre" do curso escolhido, tabela Nome | Descrição | Questões,
  disciplina com pastas (Provas, Listas, Testes, Por tema, Temas por prova, O que mais cai), Provas → P1/P2…
  → uma linha por prova (procedência do gabarito) → prova inteira; home com busca e "Adicionadas
  recentemente"; favoritos e curso em localStorage. O Caio ainda não comparou lado a lado.
- **Grade curricular**: contrato `acervo.cursos/v1`, `acervo/usp/cursos.json` com os 11 cursos de entrada da
  Poli (Jupiter, `fujita/scripts/importar/cursos_jupiter.py`), PR acervo#6 aberta. Elétrica = `3033-0`.
- **Views/API**: `/api/cursos`, `/api/matriz`, `/api/ranking`, `/api/cobertura`, `/api/documentos/{id}`, exportação
  `.md` por tema e por prova. 60 testes no validador, 43 no Worker.
- **Conector MCP** em `/mcp` (createMcpHandler + OAuth do próprio Fujita, endpoints `/oauth/*`, KV `OAUTH_KV`).
  Testado por protocolo em localhost e metadados em produção; **o fluxo com login nunca foi testado ponta a
  ponta** (a conta claude.ai da Lastro bloqueia conector personalizado; Gemini só aceita nos EUA).
- Acervo: 318 questões em 5 disciplinas (4323204, PEA3301, PEA3306, PTC3314, PTC3361).

## Armadilha de deploy (ler antes de qualquer merge no acervo)

O CI do acervo publica com `polos-e-zeros/fujita@v0.1.0`, que é o código **antigo** (sem views, sem cursos, sem
o site novo). Mergear qualquer PR no acervo republica o site antigo. Ordem segura:
1. mergear fujita#1 → `git tag -a v0.2.0 && git push origin v0.2.0`;
2. em acervo#6, trocar `fujita@v0.1.0` por `fujita@v0.2.0` em `.github/workflows/acervo.yml`;
3. mergear acervo#6.

## Pendências

- Caio comparar o site com o Polishare e dizer o que destoa (tema claro fixo? ver abaixo).
- Fazer a sequência de merge acima.
- Catálogo de provas conhecidas (`acervo.catalogo/v1`) e contribuição pelo site (bot que abre PR) — são os
  próximos itens do spec; "Enviar questões" já aparece desabilitado no site.
- Reetiquetar temas por item nas 4 disciplinas importadas (o banco antigo marcava por questão inteira; o
  conversor cortou em 3). P3 de Física IV não transcritas (PDFs em `~/Downloads/claude_downloads/4323204_site`).
- Grade da Elétrica no Jupiter para no 6º semestre; os códigos das ênfases (7º em diante) não foram achados.
- Enunciados com `**negrito**` Markdown aparecem literais no site.
- `fujita/.claude/launch.json` ficou untracked (criado por subagente para o preview); decidir se versiona.
- Publicar o app OAuth no Google (Branding com `/` e `/privacidade`) quando for abrir para todos.
- Diretório de conectores do Claude: exige conta Pro/Max/Team para submeter; ferramentas já têm `readOnlyHint`.
- Renomear o repositório `acervo` (não precisa mais: dados e código já são repositórios separados).
