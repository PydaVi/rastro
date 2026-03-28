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
