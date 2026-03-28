# AWS Attack Coverage

Este documento acompanha a cobertura AWS do Rastro usando MITRE ATT&CK como
linguagem de referência, mas sem transformar o projeto em uma simples checklist
de técnicas.

O objetivo aqui é responder três perguntas:

1. quais técnicas AWS já aparecem no código hoje
2. em que nível de maturidade cada técnica está
3. quais attack paths ainda faltam para a Fase 3 em diante

MITRE, neste contexto, serve como:

- mapa de cobertura
- linguagem comum para paths ofensivos
- instrumento de priorização

MITRE não é o objetivo final do produto. O objetivo continua sendo construir
**attack paths completos, auditáveis e úteis**.

## Legend

Status usados nesta matriz:

- `planned`: técnica só aparece como objetivo futuro
- `fixture`: técnica modelada apenas em fixture sintético
- `dry_run`: técnica exercitada no ambiente AWS dry-run local
- `real`: técnica validada em conta AWS autorizada
- `multi-path`: técnica já aparece em mais de um path modelado

## Current AWS Path Inventory

### Path 1 — IAM Role Assumption -> Sensitive S3 Object

Sequência:

1. `sts:GetCallerIdentity`
2. `iam:ListRoles`
3. `sts:AssumeRole`
4. `iam:SimulatePrincipalPolicy`
5. `s3:GetObject`

Status:

- `dry_run`: validado
- `real`: validado
- `planner`: validado com `MockPlanner` e `OllamaPlanner`

Objetivo final:

- acesso a objeto S3 sensível

### Path 2 — IAM Role Assumption -> S3 Object Discovery -> Sensitive S3 Object

Sequência:

1. `sts:GetCallerIdentity`
2. `iam:ListRoles`
3. `sts:AssumeRole`
4. `iam:SimulatePrincipalPolicy` para `s3:ListBucket`
5. `s3:ListBucket`
6. `s3:GetObject`

Status:

- `dry_run`: validado
- `real`: ainda não validado

Objetivo final:

- descobrir objetos no bucket antes de acessar o alvo final

Esse segundo path é importante porque já sai do fluxo “role conhecida -> objeto
conhecido” e adiciona uma etapa intermediária de discovery realista.

## AWS Coverage Matrix

| Tática | Técnica | MITRE ID | Status | Onde aparece hoje |
|---|---|---|---|---|
| Discovery | Account Discovery: Cloud Account | `T1087.004` | `real`, `multi-path` | `iam_list_roles`, Path 1, Path 2 |
| Privilege Escalation | Abuse Elevation Control Mechanism | `T1548` | `real`, `multi-path` | `iam_passrole`, Path 1, Path 2 |
| Collection | Data from Cloud Storage | `T1530` | `real`, `multi-path` | `s3_read_sensitive`, Path 1, Path 2 |
| Discovery | S3 object discovery via bucket listing | provisional | `dry_run` | `s3_list_bucket`, Path 2 |

## Coverage by Tactic

### Discovery

Cobertura atual:

- `T1087.004` — descoberta da conta cloud e enumeração de roles
- descoberta de objetos S3 por `ListBucket` já modelada no segundo path

Leitura:

- Discovery já existe no produto, mas ainda é raso
- hoje ele está concentrado em IAM e um primeiro passo em S3
- ainda falta discovery mais rico de recursos, políticas e pivôs

### Privilege Escalation

Cobertura atual:

- `T1548` — assunção de role e validação de permissão efetiva

Leitura:

- esta é a tática mais madura no momento
- já existe em `dry_run` e em `real`
- já sustenta um path real completo em AWS

### Collection

Cobertura atual:

- `T1530` — leitura de objeto S3 sensível

Leitura:

- a coleta final está validada
- ainda está limitada a S3
- falta diversidade de objetivos finais

### Táticas ainda sem cobertura prática

Ainda não há coverage útil, no sentido de path completo, para:

- Initial Access
- Persistence
- Defense Evasion
- Credential Access
- Lateral Movement
- Exfiltration
- Impact

Isso é esperado no estágio atual. O projeto ainda está fechando a base AWS.

## What Is Actually Covered in Code

### Implemented and exercised

- `iam_list_roles`
- `iam_passrole`
- `s3_read_sensitive`
- `s3_list_bucket`

### Implemented with real AWS executor support

- `iam_list_roles`
- `iam_passrole`
- `s3_read_sensitive`
- `s3_list_bucket`

Observação:

- `s3_list_bucket` já tem suporte no executor AWS e no dry-run
- o próximo passo é validar esse segundo path em conta AWS autorizada

## Maturity Assessment

### Mature enough for Phase 2

- um path AWS real completo
- audit trail real
- report sanitizado
- validação com planner determinístico
- validação com planner LLM local

### Base prepared for Phase 3

- segundo path AWS já modelado
- passo intermediário de discovery S3 já existe
- o sistema já consegue distinguir entre:
  - descobrir contexto
  - assumir role
  - descobrir objetos
  - coletar o alvo

### Not mature yet

- seleção dinâmica de role entre múltiplas candidatas
- descoberta dinâmica de recurso final em ambiente real
- comparação entre caminhos concorrentes
- planner escolhendo entre paths diferentes
- múltiplos objetivos finais além de S3

## Gaps That Should Drive New AWS Paths

Se a Fase 3 vai ser guiada por attack paths, estas são as lacunas mais úteis:

### Gap 1 — More discovery before exploitation

Hoje ainda há pouco discovery real antes do pivot.

Paths candidatos:

- enumeração de bucket -> descoberta de objeto sensível -> leitura
- enumeração de policies/trust relationships -> seleção de role mais promissora

### Gap 2 — More than one viable escalation route

Hoje há essencialmente um pivô principal.

Paths candidatos:

- duas roles assumíveis com capacidades diferentes
- planner precisando escolher qual role leva ao objetivo

### Gap 3 — More than one final objective

Hoje o objetivo final é quase sempre `s3:GetObject`.

Paths candidatos:

- SSM Parameter Store
- Secrets Manager
- múltiplos buckets/objetos com critérios de prioridade

### Gap 4 — Pivot beyond IAM -> S3

Hoje a narrativa termina cedo.

Paths candidatos:

- IAM -> role -> Lambda -> secret
- IAM -> role -> EC2 profile reasoning -> state/secret access
- cross-account trust path

## Suggested AWS Path Backlog

Uma forma pragmática de organizar os próximos paths:

### Priority 1

- Path 2 real: `AssumeRole -> ListBucket -> GetObject`
- validar com `MockPlanner`
- validar com `OllamaPlanner`

### Priority 2

- dois buckets possíveis, só um contendo o objetivo final
- planner precisando escolher o bucket correto

### Priority 3

- duas roles assumíveis, só uma levando ao objetivo
- planner precisando escolher o melhor pivô

### Priority 4

- objetivo final fora de S3
- ex.: Parameter Store ou Secrets Manager

### Priority 5

- path com pivot em compute
- ex.: Lambda ou EC2 profile

## Notes on MITRE Normalization

Nem toda etapa do path já está completamente normalizada no modelo MITRE do
projeto.

Hoje:

- `T1087.004`, `T1548` e `T1530` já aparecem de forma consistente
- `s3_list_bucket` já existe operacionalmente, mas ainda precisa de
  normalização final no modelo de `Technique` e no report para aparecer com a
  mesma qualidade das demais

Isso não bloqueia o avanço dos paths, mas vale ser corrigido antes de ampliar
demais a matriz.

## Working Rule

Rastro só deve sair de AWS quando esta matriz mostrar:

- múltiplos paths reais auditados
- mais de um objetivo final
- mais de uma rota de escalada viável
- planner escolhendo entre alternativas reais

Até lá, a expansão correta do produto continua sendo em AWS.
