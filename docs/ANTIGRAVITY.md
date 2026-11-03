# Como usar este MCP com o Antigravity (Gemini)

Se você utiliza o assistente **Antigravity** (baseado no Gemini), você pode integrar perfeitamente os servidores MCP deste repositório sem precisar instalar clientes externos de terceiros.

O Antigravity possui suporte nativo para ler configurações `.mcp.json` presentes na raiz do workspace (repositório) através do sistema de **Subagentes**.

## Passo a Passo (Onboarding)

1. **Configuração Padrão**: Certifique-se de que o arquivo `.mcp.json` já está na raiz do projeto, exatamente com a mesma estrutura usada pelo Claude Desktop. 
   *(Neste repositório, ele já vem configurado!)*

2. **Inicie o Workspace**: Abra a pasta do `mcp-usp` no seu editor onde o Antigravity está conectado.

3. **Invoque as Ferramentas MCP**: Peça para o Antigravity acessar o servidor MCP. Como a interface principal pode não expor os comandos diretamente para o usuário humano, basta você digitar no chat:
   
   > *"Por favor, crie um subagente com ferramentas MCP ativadas e verifique minhas notas no Moodle / qual o cardápio do Bandejão."*

4. **Como funciona "por baixo dos panos"**:
   - O Antigravity instanciará uma versão dele mesmo (um subagente) utilizando a flag `enable_mcp_tools: true`.
   - O sistema detecta automaticamente o `.mcp.json` na raiz do projeto.
   - O subagente recebe uma ferramenta chamada `call_mcp_tool`, que atua como uma ponte.
   - O subagente então consegue listar e executar nativamente todas as ferramentas (ex: `moodle`, `jupiter`, `rucard`), repassando os resultados de forma transparente para você no chat principal.

## Exemplo de prompts para usar com o Antigravity

- *"Crie um subagente com MCP ativado e veja se tenho trabalhos atrasados no Moodle."*
- *"Use o seu subagente MCP para consultar a ementa da disciplina PTC3314 no Jupiter."*
- *"Use o MCP para ver o cardápio do bandejão no almoço de hoje."*

---
**Nota técnica para o Agente**: Quando o usuário pedir para usar o MCP, utilize a tool `define_subagent` com `enable_mcp_tools: true`, e em seguida mande as instruções para ele usar a ferramenta `call_mcp_tool` para executar a ação desejada.
