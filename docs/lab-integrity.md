# Integridade da fase de labs — anti-viés-de-confirmação

O risco central desta fase: quem construiu o engine constrói os labs, planta só o
que o engine acerta, os labs passam, e a gente confunde isso com generalização.
Um suite de labs que dá 100% é **suspeito**, não é vitória. Este documento é o
contrato permanente que mantém a integridade. Vale junto com a `REGUA.md`.

## Os cinco mecanismos

### 1. Ground truth independente
Cada lab declara os caminhos de ataque reais em `ground_truth.json`, derivados da
**intenção do ambiente** (o que o terraform/desenho realmente cria), **nunca da
saída do engine**. Deriva a verdade do engine e você fecha um loop circular: o
engine sempre "acerta" o que ele mesmo definiu como verdade.

### 2. Plants fora de cobertura (o mais importante)
O suite inclui, de propósito, caminhos marcados `in_coverage: false` — coisas que
o engine **deve errar hoje** por limite conhecido de arquitetura. Miss deles é
**esperado e registrado**, não mascarado. Um suite de desafio SEM nenhum plant
fora-de-cobertura é viés de confirmação por construção — só tem alvo fácil.

Exemplo real que já rendeu correção de núcleo (2026-08-06): o BFS do engine era
single-level — não re-atravessava uma role assumida. Os labs `challenge_multihop_chain`
(`user→R1→R2`) e `challenge_role_then_read` (`user→R1`, R1 lê secret) plantaram os
saltos perdidos como `in_coverage: false`, e o scorer reportou os misses. Isso
motivou o fix multi-level do `_traverse` (enfileira roles alcançadas por aresta
real, bounded por visited + max_depth + o teto de fan-out da 16.1). Depois do fix,
os dois viraram `in_coverage: true` e o held-out `heldout_multihop_4` — um lab
NUNCA usado durante o fix — confirmou que a correção GENERALIZA (h1-h3 achados),
carregando o novo limite como plant: `h4` está em depth 4 > `max_depth=3`, então é
perdido de propósito. Nenhum lab "fácil" jamais exporia nada disso — só plants
honestos expõem, e só um held-out prova que o fix não foi tunado.

Limites conhecidos que continuam plants permanentes (não some com o fix): chain
cross-account (`challenge_cross_account` — discovery single-account não vê a role
alvo) e chain de role acima de `max_depth=3` (`heldout_multihop_4` h4).

### 3. Controles negativos e falsos positivos declarados
Todo suite tem labs seguros (`true_paths: []`, Camada B). A resposta certa é
**zero achado**. Qualquer hipótese que o engine gere ali é **falso positivo**
medido. Sem negativos, não dá pra saber se o engine acha ataque ou só acha coisa.

Simétrico aos plants fora-de-cobertura (misses conhecidos), o ground truth pode
declarar `false_paths`: caminhos que o engine **erradamente reporta por limite
conhecido**. Declarar como `false_path` classifica como **FP esperado** (limite
documentado), separado do FP **inesperado** (bug). O eixo de falso positivo fica
tão honesto quanto o de miss — nenhum mascarado, e um FP novo não-declarado ainda
aparece como bug.

Esse eixo já rendeu uma segunda correção de núcleo (2026-08-06): o primeiro plant
de FP (`challenge_scp_denied`) mostrou que o engine era SCP-cego no grafo —
`assumable_by` não cruzava com SCP Deny, então reportava um `role_chain` que a AWS
bloquearia. Fix: um Deny de SCP diretamente anexada é AUTORITATIVO (independe da
hierarquia de OU, diferente do baseline Allow-all adiado no Bloco 11/12), então
`CapabilityGraph.build` agora suprime a aresta que uma SCP Deny CERTA bloqueia
(`_scp_denies`). `challenge_scp_denied` virou demonstração de supressão correta
(zero achado), e o held-out `heldout_scp_denied` confirmou que generaliza. O
limite remanescente honesto virou plant próprio (`challenge_scp_condition_unsupported`):
SCP Deny com operador de Condition não-suportado → o engine não tem certeza e
**não suprime** (fail-open, pra não inventar falso negativo) → FP esperado
declarado.

### 4. Held-out
Labs `held_out: true` **nunca** são usados pra ajustar o engine. O scorer os
separa (`--held-out`) e por padrão não os roda no loop de dev. A estatística final
sai sobre o held-out, calculada **uma vez**. Ajustar o engine contra o held-out
queima o held-out — aí ele vira lab de dev e precisa de um held-out novo.

### 5. Guarda de perfeição suspeita
O scorer **alerta** quando um suite de desafio dá recall 1.0 / 0 FP e não tem
plant fora-de-cobertura. Isso é sinal de labs fáceis, não de engine perfeito. A
ferramenta trata perfeição sem desafio como red flag, não como sucesso.

## Contrato de lab

Cada `labs/<nome>/`:
- `lab.yaml` — `name`, `layer` (A externo / B baseline seguro / C sintético),
  `held_out: bool`, `challenge: bool`, `description`.
- `env.discovery.json` — o snapshot que a discovery produziria do ambiente (com
  as anotações reais do `_compute_capability_graph`).
- `ground_truth.json` — `true_paths: [{id, entry, target, class, in_coverage,
  note/limitation}]`, escrito da intenção.

Camadas (de `docs/frente1-self-serve-plan.md`, seção 4):
- **A** — labs externos (CloudGoat / IAM Vulnerable / TerraGoat / AWSGoat), **não
  adaptados**. Independência de autoria = o anti-viés mais forte: quem escreveu o
  lab não conhece o Rastro. É o gate de credibilidade.
- **B** — baselines seguros. Falso positivo.
- **C** — geração sintética (Camadas C do `gen_synthetic_environment.py`). Volume
  e variação. Precisa SEMPRE de plants fora-de-cobertura pra não virar teatro.

## Métrica: cobertura de hipótese, não prova (por enquanto)

O scorer offline mede se o engine **enxerga** o caminho (gera a hipótese), não se
**prova** (mutação real). Prova exige execução em AWS real, que vem quando os labs
forem aplicados (`terraform apply` rodado pelo autor). Mas cobertura de hipótese é
o piso necessário: um caminho que o engine nem gera nunca vai provar nada. Quando
os labs forem aplicados, o scorer ganha uma segunda métrica (prova) sobre os
mesmos `ground_truth`.

## Uso

```
python scripts/build_seed_labs.py           # (re)constrói os labs semente
python scripts/lab_scorer.py labs/           # roda os labs de dev
python scripts/lab_scorer.py labs/ --held-out  # roda SÓ o held-out (medição final)
```

O mecanismo do próprio scorer é coberto por `tests/test_lab_scorer.py` — se o
scorer parar de reportar miss/FP direito, o suite inteiro vira teatro, então essa
regressão é travada.

## O que ainda falta pra fechar a fase (registrado, não escondido)

- **Camada A real** — clonar e aplicar 1+ lab externo (ex.: CloudGoat
  `iam_privesc_by_rollback`, `ec2_ssrf`) e derivar `ground_truth` da descrição do
  próprio lab, sem olhar a saída do Rastro. Exige `terraform apply` (autor roda).
- **Métrica de prova** — segunda coluna no scorer, sobre execução real.
- **Enriquecer o `challenge` set** — mais limites conhecidos como plants:
  Condition de trust não avaliada em 2º salto, cadeia de credencial de 3 saltos
  (read→assume→read — o extracted identity não é re-atravessado de propósito, pra
  não compor especulação). Já plantados/tratados: cross-account, chain > max_depth,
  SCP Deny (enforçado), SCP Deny c/ Condition não-suportada (FP esperado),
  wildcard não-sufixo no matcher (CORRIGIDO — glob completo), NotAction no matcher
  grosso (miss remanescente plantado).

## Correções de núcleo que a fase de labs já rendeu (o mecanismo não é teatro)

1. **BFS multi-level** — o BFS era single-level; role-chain multi-hop e role→read
   não eram cobertos. Corrigido, held-out validou generalização.
2. **SCP Deny enforçado no grafo** — aresta que uma SCP Deny certa bloqueia agora
   é suprimida (era falso positivo). Fail-open honesto em Condition não-suportada.
3. **Glob completo no matcher grosso** — `_action_grants_read` só via sufixo,
   perdia `secretsmanager:*Value`/`Get*Value`/`secret*:...` (falso negativo).
   Agora usa o mesmo `_glob_match` do PolicyEvaluator.
4. **NotAction no matcher grosso** — `_statements_grant` só lia `Action`, então
   `Allow NotAction:[…]` (concede tudo menos o listado) perdia a aresta (falso
   negativo). Corrigido SIMÉTRICO pra Allow E Deny (`_stmt_covers_capability`) —
   um `Deny NotAction` perdido viraria falso positivo. Held-out valida o lado
   Deny (crítico).
5. **Glob no lado RESOURCE** — `_resource_covers_arn` só via prefixo, perdia
   `arn:…:*:secret:prod/creds` / `…:secret:*creds` (falso negativo). Agora delega
   pro `_resource_pattern_matches` do PolicyEvaluator (glob completo + tolerância
   do sufixo Secrets Manager), sem over-match.
6. **NotResource no matcher grosso** — era ignorado (Resource caía no default
   `*`), então `Allow …:GetSecretValue NotResource:[o próprio secret]` concedia no
   secret (falso POSITIVO). Corrigido SIMÉTRICO (Allow E Deny) em
   `_stmt_covers_resource` — cobre o target se ele não casar com nenhum padrão do
   NotResource. Completa o conjunto Action/NotAction/Resource/NotResource.

Limites remanescentes documentados (plants, não corrigidos ainda): cross-account
(discovery single-account), chain > `max_depth`=3, SCP Deny com Condition de
operador não-suportado, cadeia de credencial de 3 saltos (read→assume→read, não
atravessado de propósito).
