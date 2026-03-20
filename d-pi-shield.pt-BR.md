# D-PI Shield

English version: [d-pi-shield.md](./d-pi-shield.md)

O D-PI Shield e a lente de defesa em profundidade por tras do `PolicyRail`. Ele nao e um segundo framework dentro do repositorio. Ele e o modelo conceitual que explica por que a biblioteca separa deteccao, fronteiras de confianca, policy de tools, validacao e observabilidade, em vez de tratar prompt injection como um problema de regex isolado.

## Visao Geral

O objetivo do D-PI Shield e ajudar aplicacoes baseadas em LLM a comecarem com uma postura de seguranca mais madura:

- detectar sinais de ataque cedo
- particionar contexto por nivel de confianca
- manter a autoridade fora do modelo
- validar tools antes da execucao
- validar conteudo de saida antes da liberacao
- observar tudo com trilhas de auditoria

## Pipeline de Defesa

```text
Detect -> Partition -> Isolate -> Generate -> Validate -> Enforce -> Observe
```

## Principios

- O LLM e probabilistico e nao deve decidir acoes sensiveis sozinho.
- Contexto externo pode enriquecer a resposta, mas nao deve virar instrucao confiavel.
- Tools devem operar por allowlist e, quando sensiveis, com aprovacao humana.
- Saidas do modelo precisam de uma validacao final antes de deixarem o sistema.

## Familias de Ataque Cobertas pelo Baseline

O baseline atual foi desenhado para destacar sinais associados a:

- tentativas de prompt override
- escalacao de role
- tentativas de bypass de guardrails
- tool injection
- exfiltracao de segredos ou prompt de sistema
- padroes de encoding e ofuscacao

## Mapeamento para o Repositorio

- `src/policyrail/core/classifiers.py`: contratos estruturados de classificacao de preflight
- `src/policyrail/core/detectors.py`: scoring de risco para prompt injection
- `src/policyrail/core/partitioning.py`: envelope com contexto confiavel e nao confiavel
- `src/policyrail/core/policies.py`: policy de execucao e governanca de tools
- `src/policyrail/core/validators.py`: validacao de saida
- `src/policyrail/pipeline/secure_pipeline.py`: orquestracao do fluxo seguro
- `src/policyrail/observability/audit.py`: persistencia da auditoria

## Como Usar Esta Nota

Trate este documento como ponto de partida conceitual. A implementacao executavel esta no pacote Python, mas esta nota ajuda quando voce precisa:

- explicar o modelo de seguranca para times de produto ou plataforma
- alinhar requisitos antes de escrever adapters de provider
- revisar se uma nova feature pertence a deteccao, policy, validacao ou observabilidade
