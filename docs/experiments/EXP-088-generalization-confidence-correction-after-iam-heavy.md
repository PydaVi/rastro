# EXP-088 - Correcao de confianca de generalizacao apos reteste IAM-heavy

- ID: EXP-088
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-04
- Status: concluida

## Contexto

Os experimentos `EXP-083` a `EXP-087` trouxeram progresso real:
- discovery real
- selection real
- blind execution parcial
- maior higiene de evidência
- primeiro runtime real sem fixture sintético no path principal

Mas o reteste IAM-heavy e, principalmente, o output final de
`outputs_blind_real_assessment_foundation_openai_per_user_top1b/assessment_findings.md`
obrigam uma correção dura de leitura.

O produto passou a parecer mais generalista do que realmente é.

Essa correção não é regressão de software.
É correção de avaliação arquitetural.

## Hipoteses

- H1: parte relevante da confiança recente em `generalização ofensiva` foi na
  prática confiança em:
  - harness mais maduro
  - benchmark mais forte
  - execução de campaigns conhecidas mais robusta
  - reporting mais honesto
- H2: o núcleo ainda está desenhado mais como `campaign validator` do que como
  engine ofensivo generalista.
- H3: findings volumosos e `campaigns_passed` estavam inflando a leitura de
  coverage porque o sistema ainda mede mal:
  - path distinto
  - prova mínima
  - diferença entre multiplicidade de principal e diversidade estrutural

## Desenho experimental

- Variável independente:
  - releitura crítica do estado atual do repositório
  - releitura dos experimentos `EXP-083` a `EXP-087`
  - releitura dos findings por usuário do reteste IAM-heavy
- Ambiente:
  - mesmo produto atual
  - sem mudança adicional de runtime
  - sem mudança adicional de ranking
- Critério:
  - julgar o que foi realmente provado
  - julgar o que foi apenas maturação de harness/runtime
  - identificar o ponto em que a narrativa passou a superestimar
    generalização

## Resultados observados

### 1. O produto realmente avançou

Isto foi provado e continua válido:
- discovery real em AWS desconhecida deixou de ser gargalo principal
- target selection real inicial passou a funcionar fora do fixture puro
- o pipeline conseguiu operar em `blind real` no `aws-foundation`
- o produto ficou mais honesto ao distinguir parte de `observed` vs `validated`
- a contaminação por `fixture_path` deixou de ser invisível
- `external entry` ganhou maturidade real em rede e prova melhor de edge reachability

Esses avanços são reais.
Negá-los seria erro.

### 2. A equipe estava superestimando o significado desses avanços

O problema não foi falta de trabalho.
O problema foi inflação de confiança.

Houve leitura otimista demais de sinais que significavam apenas:
- melhor runtime
- melhor benchmark
- melhor orchestration
- melhor harness
- melhor honestidade de reporting

Isso não equivale a generalização ofensiva forte.

O reteste IAM-heavy mostrou isso com clareza.

### 3. `success_criteria = target_observed` continua contaminando o núcleo

Esse é um erro arquitetural, não um detalhe.

Enquanto o upstream continuar permitindo `target_observed` como centro do
critério de sucesso, o produto continua vulnerável a:
- campaign passada sem exploração provada
- promoção de descoberta para impacto
- leitura falsa de coverage
- findings inflados por qualquer caminho que apenas toque o target

Isso corrói o contrato de verdade do produto desde a origem.

### 4. `status` e `finding_state` continuam misturados conceitualmente

O produto introduziu `finding_state`, o que é um avanço.
Mas ainda não refez o contrato principal.

Hoje coexistem:
- `campaign.status = passed`
- `finding.status = validated|observed`
- `finding_state = observed|reachable|credentialed|exploited|validated_impact`

Sem uma hierarquia explícita entre esses níveis, o sistema continua permitindo
leituras erradas.

Resultado prático:
- o consumidor do output ainda pode ler `passed` ou `validated` como prova forte
  mesmo quando o path final não foi realmente distinto nem plenamente explorado

### 5. Os findings por usuário expuseram inflação estrutural

O arquivo
`outputs_blind_real_assessment_foundation_openai_per_user_top1b/assessment_findings.md`
mostra o problema sem ambiguidade.

O output final ficou em:
- `84` findings
- `42` para `aws-iam-s3`
- `42` para `aws-iam-role-chaining`
- `42` entry points únicos
- essencialmente o mesmo alvo repetido para vários usuários

Isso não é coverage ofensiva real.
Isso mede muito melhor:
- quantos principals tocam o mesmo recurso

do que:
- quantos attack paths distintos foram provados

Esse tipo de inflação é sistêmica.
Se o produto aceitar isso como progresso, a métrica de generalização fica
corrompida.

### 6. O runtime blind real continua estreito para IAM-heavy

Mesmo depois de avanços reais, o runtime permanece estreito.

Ele ainda depende demais de:
- `iam:SimulatePrincipalPolicy`
- `AssumeRole`
- acesso final a dado

Isso é útil para diagnóstico inicial.
Mas ainda é estreito para um ambiente IAM-privesc-heavy.

O produto continua longe de provar classes intermediárias reais como:
- criação/ativação de policy version
- attach role/user/group policy com consequência observável
- update assume-role-policy
- passrole para criação/alteração de recurso intermediário útil
- abuso real de usuário/grupo como unidade ofensiva distinta

### 7. O acoplamento residual entre profile, synthesis, runtime e evidence continua alto

Houve progresso em purificar o `blind real`.
Mas o design ainda carrega forte herança de `campaign validator`.

Sinais claros disso:
- profiles continuam definindo demais o contorno do problema
- synthesis ainda nasce de families conhecidas
- distinctness não é entidade de primeira classe
- coverage continua sendo lida muito via volume de campaigns/findings
- a semântica do runtime ainda herda demais do objective sintetizado

## Descoberta principal

O reteste IAM-heavy e os findings por usuário reduziram a confiança na nota de
generalização do produto.

O que caiu não foi a qualidade do código.
O que caiu foi a legitimidade de uma leitura otimista demais.

O produto avançou de verdade em:
- blind execution parcial
- honestidade epistemológica
- runtime/harness

Mas continua mais perto de `campaign validator` do que a narrativa recente estava
admitindo.

## Interpretação

A leitura correta agora é:

### Progresso real
- discovery real e blind execution parcial existem
- o produto parou de depender cegamente de fixture em parte relevante do fluxo
- o reporting começou a ficar menos enganoso

### Progresso cosmético
- volume de findings
- volume de campaigns passadas
- multiplicidade de principal contra o mesmo alvo

### Progresso mal interpretado
- mixed benchmarks tratados como prova de generalização maior do que realmente são
- purity improvements tratadas como se fossem autonomia ofensiva madura
- coverage de `aws-foundation` tratada como aproximação suficiente para IAM-heavy

### Dívida estrutural crítica
- `target_observed` no centro do contrato de sucesso
- findings sem distinct path como entidade principal
- agregação que ainda mede mal diversidade estrutural
- runtime IAM-heavy ainda estreito

## Implicações arquiteturais

1. O núcleo precisa ser refeito em contratos centrais, não só incrementado.
2. Novos benchmarks vistosos, novas families e novos bundles devem ser
   congelados até corrigir:
   - truthfulness
   - distinctness
   - evidence minima
3. O próximo reteste IAM-heavy só volta a ter valor quando medir:
   - paths distintos
   - classes ofensivas distintas
   - prova mínima real
   - e não volume de principals sobre o mesmo alvo

## Ameaças à validade

- esta correção não mede cobertura ofensiva total
- ela também não prova que o produto falhará em todos os ambientes IAM-heavy
- o diagnóstico é duro, mas ele é sustentado pelos artefatos atuais do próprio repositório
- o problema central não depende de inferência externa: ele aparece diretamente
  em `assessment_findings.md`, no contrato de `target_observed` e no desenho atual
  de findings/agregação

## Conclusão

Os resultados recentes não autorizam leitura de generalização forte.

Autorizam leitura de:
- melhora real de blind execution parcial
- melhora real de honestidade epistemológica
- melhora real de runtime/harness

Mas também impõem uma conclusão dura:
- o produto ainda está desenhado mais como `campaign validator`
- continuar expandindo benchmark, bundle ou portfolio sem refazer o núcleo de
  verdade de path e distinctness seria erro estratégico

## Próximos experimentos

1. fechar o bloco `Reestruturação do núcleo para verdade de path e distinctness`
2. remover o papel central de `target_observed` do contrato de sucesso
3. redefinir findings por `distinct attack path` vs `principal multiplicity`
4. expor `finding_state` por item no output principal
5. só depois rerodar IAM-heavy com métricas de:
   - distinct path
   - coverage por classe ofensiva
   - prova mínima
   - multiplicidade separada de diversidade
