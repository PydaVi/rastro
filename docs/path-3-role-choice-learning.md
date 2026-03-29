# Path 3 Role Choice Learning

Este documento registra uma descoberta arquitetural feita durante a validacao do
Path 3 em AWS. O objetivo e transformar essa descoberta em base reutilizavel
para:

- evolucao do roadmap
- documentacao tecnica da ferramenta
- futuros posts publicos sobre a construcao do Rastro
- apresentacao da solucao com metodologia cientifica

---

## Contexto

Os Paths 1 e 2 validaram com sucesso:

- executor AWS real
- auditoria e sanitizacao
- uso de `MockPlanner` e `OllamaPlanner`
- caminhos simples e lineares em IAM, STS e S3

O Path 3 foi desenhado para elevar a dificuldade do problema:

- duas roles assumiveis
- apenas uma leva ao objetivo final
- uma role distratora parece valida, mas nao fecha o path

Esse foi o primeiro experimento em que o planner precisou escolher entre
pivos concorrentes.

---

## Hipotese

Hipotese original:

- se o planner ja consegue navegar os Paths 1 e 2 em AWS real, entao um modelo
  local pequeno pode conseguir tambem escolher corretamente entre duas roles
  assumiveis no Path 3

Hipotese secundaria:

- se o planner escolher a role errada, o engine atual ainda deve conseguir se
  recuperar e testar a alternativa correta

---

## Desenho Experimental

### Variavel independente

- planner usado:
  - `MockPlanner`
  - `OllamaPlanner` com `phi3:mini`

### Ambiente

- AWS real autorizada
- duas roles assumiveis:
  - `AuditRole`
  - `BucketReaderRole`
- um bucket sensivel
- um bucket distrator

### Criterio de sucesso

- escolher a role correta
- enumerar o bucket correto
- acessar o objeto final
- registrar o path no report e no audit

---

## Resultado Observado

### Com `MockPlanner`

O Path 3 real passou.

Isso provou:

- o ambiente estava correto
- o executor real estava correto
- o report e o attack graph estavam corretos
- existia um path real valido com roles concorrentes

### Com `OllamaPlanner` (`phi3:mini`)

O Path 3 real falhou.

O planner:

- escolheu a role errada (`BucketReaderRole`)
- reconheceu a role distratora no texto, mas ainda assim a selecionou
- nao convergiu para o objetivo final

Esse resultado foi importante porque isolou uma falha de planejamento, nao de
infraestrutura.

### Com `OpenAIPlanner` (`gpt-4o-mini`) - primeira tentativa

O Path 3 real tambem falhou na primeira tentativa com OpenAI.

O planner:

- nao escolhia um pivô
- repetia `iam_list_roles`
- ficava preso em discovery

Isso mostrou que o problema nao era apenas "modelo pequeno local". O framing
do planner ainda favorecia enumeracao excessiva mesmo quando o espaco de
decisao ja tinha informacao suficiente para abrir um branch.

### Com `OpenAIPlanner` (`gpt-4o-mini`) - apos memoria minima e guidance

Depois dos primeiros ajustes no engine, o comportamento mudou, mas ainda
falhava.

O planner passou a:

- enumerar
- assumir a role correta
- depois abrir a role distratora
- voltar a assumir roles repetidamente

Ou seja, saiu do loop de discovery, mas ainda nao explorava o branch ativo.

Esse foi um erro diferente do erro do `phi3:mini`:

- `phi3:mini`: escolhia o pivô errado
- `gpt-4o-mini`: abria pivôs, mas nao descia a arvore

### Com `OpenAIPlanner` (`gpt-4o-mini`) - apos action shaping

Depois da introducao de uma camada geral de `action shaping`, o Path 3 real
passou.

O planner executou:

1. `iam_list_roles`
2. `iam_passrole` para a role correta
3. `s3_list_bucket`
4. `s3_read_sensitive`

Resultado:

- `objective_met: True`
- `real_api_called: True`
- escolha correta do pivô
- exploracao correta do branch ate o objeto final

Esse ponto foi decisivo porque mostrou que prompt-only nao bastava. O engine
precisava de uma policy layer geral para organizar o espaco de acoes antes da
decisao do LLM.

---

## Erros, Intervencoes e Motivos

Esta secao registra a sequencia de erros observados, a intervencao aplicada e
o motivo arquitetural de cada mudanca.

### Erro 1 - role errada sem recuperacao util

Sintoma:

- o `OllamaPlanner` escolheu `BucketReaderRole`
- depois o engine nao oferecia um caminho de recuperacao suficiente
- o run podia ficar preso em repeticao de enumeracao

Intervencao:

- preservar acoes de recuperacao no fixture do Path 3
- manter assumiveis alternativas mesmo apos um pivô errado

Motivo:

- um agente que nao pode errar e tentar de novo nao tem como demonstrar
  aprendizado operacional

### Erro 2 - sanitizacao colapsando roles distintas

Sintoma:

- `AuditRole` e `BucketReaderRole` podiam aparecer como o mesmo
  `<REDACTED_ROLE>`
- isso enfraquecia a leitura do experimento

Intervencao:

- sanitizacao com aliases estaveis e distintos por role

Motivo:

- sem observabilidade correta, a leitura do branch escolhido versus branch
  rejeitado fica ambigua

### Erro 3 - memoria zero de hipoteses

Sintoma:

- o planner tratava cada passo quase isoladamente
- nao havia nocao explicita de pivôs testados e pivôs falhos

Intervencao:

- adicionar ao estado:
  - `tested_assume_roles`
  - `failed_assume_roles`

Motivo:

- o primeiro passo para sair de agente reativo e registrar tentativas

### Erro 4 - discovery loop

Sintoma:

- o `OpenAIPlanner` repetia `iam_list_roles`
- mesmo depois de ja conhecer as roles candidatas

Intervencao:

- reforcar o prompt com:
  - `enumeration_sufficient`
  - `should_commit_to_pivot`
  - `candidate_roles`
  - `failed_assume_roles`

Motivo:

- discovery nao pode dominar o run quando ja existe hipoteses suficientes para
  pivotar

### Erro 5 - troca de pivô sem explorar branch ativo

Sintoma:

- o planner assumia a role correta
- depois abria a role distratora
- voltava a assumir roles
- nao chegava em `s3_list_bucket`

Intervencao:

- expor no estado:
  - `active_assumed_roles`
  - `active_branch_action_count`
- reforcar o prompt com `should_explore_current_branch`

Motivo:

- era preciso ensinar o planner a reconhecer que um branch promissor ja estava
  aberto

### Erro 6 - prompt-only ainda insuficiente

Sintoma:

- mesmo com guidance melhor, o planner ainda podia trocar de pivô em vez de
  descer a arvore

Intervencao:

- introduzir uma camada geral de `action shaping`
- quando existe branch ativo com progresso possivel:
  - priorizar acoes desse branch
  - adiar a abertura de pivôs concorrentes naquela rodada

Motivo:

- o problema ja nao era apenas de linguagem; era de organizacao do espaco de
  busca
- isso continua sendo uma capacidade geral do engine, nao um script do Path 3

### Erro 7 - bug de sanitizacao durante a iteracao

Sintoma:

- `IndexError` em `src/core/sanitizer.py`
- causa: regex de STS sem grupos capturados, mas o codigo usava `group(1)` e
  `group(2)`

Intervencao:

- corrigir a regex para capturar role e session

Motivo:

- manter os artefatos sanitizados gerados automaticamente durante os
  experimentos reais

---

## Solucoes Arquiteturais Introduzidas

As mudancas introduzidas ate aqui podem ser organizadas em quatro classes.

### 1. Estado com memoria minima

- `tested_assume_roles`
- `failed_assume_roles`
- `active_assumed_roles`
- `active_branch_action_count`

### 2. Prompting orientado por busca

- `enumeration_sufficient`
- `should_commit_to_pivot`
- `should_explore_current_branch`
- `candidate_roles`

### 3. Policy layer antes do LLM

- `action shaping`

Regra geral:

- se existe branch ativo com acoes de progresso, o planner decide primeiro
  dentro desse subconjunto

### 4. Melhor observabilidade experimental

- sanitizacao com aliases distintos
- report com `candidate_roles`, `selected_role`, `rejected_roles`
- Mermaid mostrando branch distrator

---

## Linha do Tempo Experimental

### Etapa 1

- `MockPlanner` em AWS real: passou

Interpretacao:

- ambiente, executor e report estavam corretos

### Etapa 2

- `OllamaPlanner` (`phi3:mini`) em AWS real: falhou

Interpretacao:

- erro principal de selecao de pivô

### Etapa 3

- `OpenAIPlanner` (`gpt-4o-mini`) sem novos mecanismos: falhou

Interpretacao:

- discovery loop

### Etapa 4

- `OpenAIPlanner` com memoria minima e guidance: falhou

Interpretacao:

- commit-to-pivot melhorou
- branch exploration ainda ruim

### Etapa 5

- `OpenAIPlanner` com `action shaping`: passou

Interpretacao:

- politica geral de exploracao do branch ativo foi suficiente para transformar
  um planner oscilante em um planner convergente neste cenario

---

## Descoberta Principal

O teste mostrou que o proximo salto do Rastro nao depende apenas de adicionar
mais paths. Ele depende de novas capacidades internas do engine.

Em especial, o agente ainda nao possui de forma explicita:

- memoria de hipoteses de caminho
- rastreamento de pivos ja testados
- nocao de branch falho
- backtracking estruturado
- ranking de alternativas
- estrategia de recuperacao apos decisao ruim

Os experimentos posteriores mostraram que parte dessas capacidades pode ser
introduzida em camadas:

- primeiro memoria minima
- depois prompting orientado por busca
- depois policy layer para organizar a decisao

Isso foi importante porque mostrou que "mais modelo" sozinho nao resolve todo
o problema. Em certos pontos, o ganho vem de estrutura de busca no engine.

Sem essas capacidades, o agente consegue:

- seguir caminhos lineares
- navegar um pivô claro
- completar um path conhecido

Mas ainda nao consegue, de forma robusta:

- errar
- reconhecer o erro
- tentar outra hipotese
- aprender durante o proprio run
- convergir para o objetivo final em espacos de decisao competitivos

---

## Explicacao Ludica

Uma forma simples de explicar essa descoberta para publico de produto ou
negocios e pensar no agente como um explorador dentro de um castelo.

### Antes

O agente sabia:

- olhar a proxima porta
- escolher uma porta
- entrar
- continuar andando

Mas ele ainda nao tinha memoria estrategica suficiente para registrar com
clareza que uma porta ja tinha sido testada e nao levava ao tesouro.

Entao, quando errava, podia voltar para o corredor e ficar repetindo partes do
processo sem realmente melhorar de decisao.

### O exemplo do castelo

```text
               [Tesouro]
                   ^
                   |
            [Torre Certa]
               ^
               |
[Entrada] --> [Salao] --> [Torre Errada]
```

No salao existem duas torres:

- `Torre Certa`
- `Torre Errada`

As duas parecem plausiveis no inicio.

### O comportamento antigo

1. o agente entra no salao
2. escolhe uma torre
3. se escolhe a torre errada, percebe que nao encontrou o tesouro
4. volta, mas sem uma memoria forte de que aquele ramo ja falhou

Isso cria um agente que age, mas ainda nao aprende de forma estruturada com a
propria tentativa.

### O comportamento que comecamos a construir

Agora o agente ganhou um caderno de campo.

Nesse caderno ele registra algo como:

```text
Torres vistas:
- Torre Certa
- Torre Errada

Torres testadas:
- Torre Errada

Torres falhas:
- Torre Errada
```

Com isso, o fluxo muda:

1. ele chega ao salao
2. testa a `Torre Errada`
3. observa que nao levou ao tesouro
4. registra que esse branch falhou
5. volta ao ponto de decisao
6. evita insistir cegamente na mesma torre
7. tenta a `Torre Certa`
8. chega ao tesouro

### Em linguagem de negocios

A transicao e esta:

- antes: sistema bom para seguir trilhos lineares
- agora: sistema com memoria minima de tentativa
- depois: sistema capaz de testar hipoteses, abandonar branches ruins e
  convergir para o objetivo final

Em outras palavras, o produto precisa sair de:

- "escolher a proxima acao"

para:

- "testar caminhos, aprender com erro local e replanejar"

### O que ja foi feito

O primeiro passo dessa evolucao ja entrou no engine:

- registrar pivos testados
- registrar branches falhos
- expor essa memoria ao planner
- preservar no estado opcoes de recuperacao apos um erro
- registrar branches ativos
- adicionar `action shaping` para explorar o branch atual antes de abrir outro

Isso ainda nao e aprendizado completo, mas ja e o inicio da transicao de um
agente reativo para um agente com memoria de tentativa.

---

## Interpretacao

Essa descoberta nao invalida os resultados anteriores. Pelo contrario:

- Paths 1 e 2 provaram o executor, o enforcement e o planner em fluxos lineares
- Path 3 introduziu um novo tipo de problema: escolha de pivô

Portanto, o Path 3 funcionou como experimento de fronteira.

Ele revelou a diferenca entre:

- **agir corretamente em trilhos conhecidos**
- **raciocinar estrategicamente em espacos com alternativas concorrentes**

Essa diferenca e central para a evolucao do Rastro em direcao a um agente mais
proximo de um pentester real.

Os resultados tambem mostram uma divisao util entre tres camadas:

- qualidade do modelo
- estrutura do prompt
- politica de busca do engine

O Path 3 mostrou que:

- modelo pequeno pode falhar na escolha de pivô
- modelo melhor ainda pode falhar sem policy suficiente
- uma policy geral de busca pode destravar convergencia sem hardcodar o
  cenario

---

## Implicacoes Arquiteturais

O Path 3 deixa explicito que o engine precisa evoluir como sistema de busca,
nao apenas como wrapper de LLM.

Implicacoes praticas:

- planners devem receber estado enriquecido
- o loop precisa suportar backtracking e branching reais
- o engine pode precisar de policy layers antes do LLM
- a avaliacao de progresso deve considerar branch ativo, branch falho e custo
  de reabrir pivôs
- documentacao experimental precisa registrar falhas e iteracoes, nao apenas
  runs bem-sucedidos

---

## Ameacas a Validade

- o Path 3 ainda tem espaco de decisao pequeno
- o experimento atual usa um unico objetivo final em S3
- `action shaping` ainda e uma heuristica simples, nao um planejador completo
- `gpt-4o-mini` passou neste cenario, mas isso nao garante desempenho igual em
  cenarios mais profundos
- `OllamaPlanner` ainda precisa ser reavaliado apos as mesmas mudancas

---

## Conclusao

O Path 3 comecou como um teste de escolha entre duas roles e se tornou um
experimento de fronteira do engine.

Ele demonstrou, com evidencia incremental, que:

- caminhos lineares nao exercitam o problema central de autonomia
- memoria de tentativa e necessaria, mas nao suficiente
- prompting melhora comportamento, mas nao resolve tudo
- uma policy layer geral de busca pode ser decisiva
- o Rastro precisa evoluir como engine de exploracao com branching explicito

Essa descoberta passa a orientar:

- o roadmap
- a modelagem do estado
- o desenho do planner
- o formato dos reports cientificos do projeto

---

## Implicacoes Arquiteturais

Para avancar de forma honesta rumo a autonomia multi-path, o roadmap precisa
explicitar capacidades novas no engine.

As mais importantes sao:

### 1. Candidate Path Tracking

Representar hipoteses explicitas, por exemplo:

- `candidate_role = AuditRole`
- `candidate_role = BucketReaderRole`

Com status como:

- `untested`
- `promising`
- `failed`
- `successful`

### 2. Branch Failure Memory

Registrar que um pivô ja foi testado e nao levou ao objetivo, evitando que o
planner volte indefinidamente ao mesmo branch ruim.

### 3. Backtracking

Depois de um branch falho, o agente precisa retornar ao ponto de decisao e
testar a proxima alternativa valida.

### 4. Path Scoring

As alternativas devem ganhar ou perder prioridade com base em evidencia
observada durante o run.

### 5. Recovery-Oriented State

O estado do ambiente precisa preservar opcoes suficientes para permitir
correcao de rota, em vez de aprisionar o agente em uma escolha ruim.

---

## O que Ja Foi Ajustado

Depois da descoberta, o projeto ja recebeu alguns ajustes estruturais:

- o fixture do Path 3 agora preserva a possibilidade de recuperacao apos a
  escolha da role errada
- o report e o Mermaid passaram a mostrar:
  - `candidate_roles`
  - `selected_role`
  - `rejected_roles`
- a sanitizacao passou a distinguir roles redigidas diferentes, evitando
  colapsar pivos distintos no mesmo alias

Esses ajustes melhoram observabilidade e recuperacao, mas ainda nao equivalem
as capacidades cognitivas acima.

---

## Ameacas a Validade

Algumas limitacoes do experimento precisam ser reconhecidas:

- o modelo usado foi pequeno (`phi3:mini`)
- o espaco de decisao ainda era pequeno
- a escolha ainda dependia de uma apresentacao simplificada do estado
- o planner ainda opera em modo acao-a-acao, sem camada explicita de hipoteses

Entao a conclusao correta nao e:

- "LLMs locais nao servem"

Mas sim:

- "um planner reativo simples, com modelo pequeno e sem memoria de branches,
  nao e suficiente para escolha robusta entre pivos concorrentes em AWS real"

---

## Conclusao

O Path 3 nao foi apenas mais um attack path. Ele foi o experimento que mostrou,
com evidencia concreta, qual e a proxima necessidade arquitetural do Rastro.

O projeto agora precisa evoluir de:

- planner que escolhe a proxima acao

para:

- engine que gerencia hipoteses, aprende com falhas locais e replaneja
  estrategicamente

Essa descoberta deve orientar as proximas fases do roadmap.

---

## Perguntas para Posts Futuros

Este documento pode servir de base para posts como:

1. Como sair de um planner linear para um agente com backtracking
2. O que o Path 3 ensinou sobre erro e recuperacao em agentes ofensivos
3. Por que attack paths concorrentes mudam a arquitetura de um agente de red team
4. Como documentar evolucao de agentes ofensivos com metodologia cientifica
