# OpenCode Phi Presidio Design

Data: 2026-05-27

## Objetivo

Criar um redator local de PHI/PII para textos clinicos em portugues brasileiro, com Microsoft Presidio como motor de deteccao, pseudonimizacao reversivel por placeholders estaveis e primeiro runtime integrado ao OpenCode.

Frase-guia:

```text
Skill for knowledge.
Hook/plugin/firewall for enforcement.
Presidio core for local PHI/PII detection.
Stable local mapping for reversible pseudonymization.
```

O primeiro produto utilizavel deve proteger o fluxo antes do texto chegar ao modelo. O usuario pode colar texto livre com prontuario em um comando especial do OpenCode ou usar a CLI diretamente no clipboard.

## Escopo Do MVP

O MVP e OpenCode-first e Presidio-first.

Inclui:

- `phi_br_core`: pacote Python local com Presidio Analyzer e recognizers brasileiros.
- `phi`: CLI publica simples.
- plugin OpenCode com comando `/phi <texto livre>`.
- mapping local temporario para restauracao reversivel.
- lifecycle de sessoes PHI com purge automatico de expirados.

Nao inclui no MVP:

- daemon permanente de clipboard.
- suporte Gemini/Codex.
- spaCy/Stanza obrigatorios.
- criptografia do mapping.
- restauracao automatica dentro do chat do OpenCode.

## UX Publica

CLI:

```bash
phi redact
phi restore
phi status
phi purge
```

OpenCode:

```text
/phi <qualquer instrucao + texto clinico colado>
```

`phi redact` le o clipboard, detecta PHI/PII localmente, substitui por placeholders, salva mapping temporario e devolve o texto redigido ao clipboard.

`phi restore` le o clipboard, identifica placeholders, encontra automaticamente as sessoes ativas donas desses placeholders, restaura o texto localmente e devolve o resultado ao clipboard. O texto restaurado nao e impresso no terminal.

`/phi <texto livre>` recebe o payload bruto localmente no plugin OpenCode, chama o core via CLI ou API local, e so envia ao modelo o texto redigido.

## Fluxo OpenCode

```text
/phi Estruture em SOAP: Paciente Joao da Silva, CPF 123.456.789-09...
  -> plugin OpenCode intercepta o comando localmente
  -> plugin chama `phi redact` ou `scrub_text` com o texto bruto local
  -> phi_br_core roda Presidio Analyzer + recognizers BR
  -> StablePlaceholderAnonymizer gera texto seguro + mapping local
  -> audit_text roda segunda passada no texto redigido
  -> plugin substitui as parts do comando por texto redigido
  -> modelo recebe apenas placeholders
```

Se scrub ou audit falhar, o plugin nao envia nada ao modelo. A falha deve ser fechada, curta e sem texto bruto.

O comportamento de substituicao por `command.execute.before` precisa de uma prova empirica no OpenCode instalado antes da integracao final. A spec assume esse caminho como alvo, mas o primeiro marco tecnico deve provar que o modelo nao recebe os argumentos brutos.

## Fluxo CLI Clipboard

`phi redact`:

```text
clipboard bruto
  -> purge --expired
  -> Presidio Analyzer
  -> pseudonimizacao estavel
  -> audit pos-scrub
  -> mapping local
  -> clipboard redigido
```

`phi restore`:

```text
clipboard redigido
  -> purge --expired
  -> escanear placeholders
  -> resolver sessoes donas via indice local
  -> carregar mappings necessarios
  -> restaurar localmente
  -> clipboard restaurado
```

O comando nao imprime PHI. Saidas JSON ou humanas mostram apenas contagens, tipos de entidade e status.

## Core Presidio

`phi_br_core` deve expor estas funcoes publicas:

```python
def build_analyzer(policy: PhiPolicy) -> AnalyzerEngine: ...
def scan_text(text: str, policy: PhiPolicy) -> PhiScanResult: ...
def scrub_text(text: str, policy: PhiPolicy) -> PhiScrubResult: ...
def audit_text(text: str, policy: PhiPolicy) -> PhiAuditResult: ...
def restore_text(text: str, mapping_path: str) -> str: ...
```

O core usa explicitamente:

```python
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
```

Decisao tecnica:

- Presidio Analyzer e a fonte canonica de deteccao.
- A pseudonimizacao reversivel fica em `StablePlaceholderAnonymizer`, nao no `AnonymizerEngine` padrao.
- Presidio Anonymizer pode existir para modos irreversiveis ou simples.
- Mapping e restauracao ficam em `phi_br_core.mapping`.

## Recognizers Brasileiros

Entidades customizadas:

```text
BR_CPF
BR_RG
BR_CNS
BR_CRM
BR_CNPJ
BR_CEP
BR_PHONE
BR_EMAIL
BR_ADDRESS
BR_HEALTH_INSURANCE
BR_CLINICAL_RECORD_ID
BR_VISIT_ID
BR_EXAM_ID
BR_AUTHORIZATION_ID
BR_DATE
BR_AGE
BR_PATIENT_NAME
BR_FAMILY_MEMBER_NAME
BR_HEALTHCARE_PROFESSIONAL_NAME
BR_INSTITUTION
BR_WORKPLACE
BR_SCHOOL
BR_CONTEXTUAL_IDENTIFIER
```

Recognizers obrigatorios no MVP:

- CPF com digito verificador.
- CNS com 15 digitos e contexto forte se validacao completa nao entrar no primeiro corte.
- CRM com UF antes ou depois do numero.
- telefone brasileiro.
- CEP.
- IDs clinicos apenas com contexto.
- datas brasileiras absolutas.
- nomes por contexto clinico.
- instituicoes por contexto.

O MVP nao tenta resolver NER perfeito. Nomes e instituicoes usam heuristicas contextuais e allowlist inicial de medicamentos para reduzir falso positivo.

## Placeholders E Mapping

Placeholders sao semanticamente significativos:

```text
[PACIENTE_001]
[CPF_001]
[CNS_001]
[CRM_001]
[PROFISSIONAL_001]
[DATA_001]
[INSTITUICAO_001]
```

Regras:

- O mesmo valor textual dentro da sessao recebe o mesmo placeholder.
- Valores diferentes da mesma categoria recebem indices diferentes.
- O mapping nunca e enviado ao modelo.
- O mapping nunca e impresso.
- O mapping nunca e commitado.
- O mapping fica em `.tmp/phi/<session_id>/mapping.json`.

## Multiplas Sessoes Sem Session ID Manual

O usuario nao precisa informar sessao para `phi restore`.

O CLI mantem um indice local de placeholders ativos. Enquanto houver sessoes ativas, os indices de placeholders nao reiniciam. Exemplo:

```text
sessao A: [PACIENTE_001], [CPF_001]
sessao B: [PACIENTE_002], [CPF_002]
sessao C: [PACIENTE_003], [CRM_001]
```

Indice local:

```json
{
  "PACIENTE_001": "phi-20260527-a1",
  "CPF_001": "phi-20260527-a1",
  "PACIENTE_002": "phi-20260527-b2",
  "CPF_002": "phi-20260527-b2"
}
```

`phi restore` escaneia o clipboard, identifica placeholders e carrega os mappings correspondentes. Se o texto tiver placeholders de mais de uma sessao ativa, o comando pode restaurar todos em uma unica passada.

Placeholders nao devem ser reciclados durante sessoes ativas. Reciclagem futura deve ser evitada por padrao para nao restaurar texto antigo com mapping errado.

## Lifecycle De Sessoes PHI

Cada comando `phi` executa `purge --expired` antes da acao principal.

Sequencia obrigatoria:

```text
1. adquirir lock local
2. rodar purge --expired
3. atualizar indice de sessoes ativas
4. executar comando solicitado
5. gravar estado atomicamente
```

Default:

```yaml
sessions:
  ttl_hours: 24
  purge_expired_on_start: true
  max_sessions: 20
  delete_by_default: true
```

Arquivos por sessao:

```text
.tmp/phi/<session_id>/
  mapping.json
  metadata.json
```

`metadata.json` nao contem PHI:

```json
{
  "session_id": "phi-20260527-abc123",
  "created_at": "2026-05-27T20:00:00Z",
  "expires_at": "2026-05-28T20:00:00Z",
  "placeholder_count": 8,
  "entity_types": ["BR_CPF", "BR_PATIENT_NAME", "BR_CRM"],
  "source": "opencode:/phi",
  "raw_text_saved": false
}
```

Se purge de expirados falhar, o comando falha fechado.

## Auditoria E Fail-Closed

Depois de redigir, `audit_text` roda uma segunda passada Presidio no texto redigido com threshold mais estrito.

Se restar CPF, CNS, CRM, telefone, email, CEP ou outro identificador de alta confianca, o resultado e bloqueado.

O sistema nao deve imprimir texto bruto, mapping ou texto restaurado em stdout/stderr. Erros devem conter apenas motivo seguro, contagens, entity types e caminhos de arquivos quando necessario.

## CLI Interna E Compatibilidade

A UX publica e `phi`, mas o core pode manter subcomandos internos ou aliases para teste:

```bash
phi check
phi scan --text "..."
phi redact
phi restore
phi status
phi purge
```

`phi check` verifica importacao, inicializacao do Presidio Analyzer, recognizers customizados, escrita em `.tmp/phi`, scrub simples, audit simples e purge de expirados.

## Arquivos Sensíveis E Git

`.gitignore` deve incluir:

```gitignore
.tmp/
*.mapping.json
*mapping*.json
*.phi.json
raw.txt
input.txt
patient*.txt
paciente*.txt
prontuario*.txt
prontuário*.txt
relatorio*.txt
relatório*.txt
clinical_raw/
raw_clinical/
.env
```

Testes devem usar apenas dados sinteticos.

## Marcos De Implementacao

1. Provar OpenCode `/phi` com substituicao local de mensagem, sem enviar argumentos brutos ao modelo.
2. Criar `phi_br_core` com Presidio Analyzer e recognizers brasileiros deterministicas.
3. Implementar `StablePlaceholderAnonymizer`, mapping, indice global de placeholders ativos e purge atomico.
4. Implementar `phi redact`, `phi restore`, `phi status`, `phi purge` para clipboard macOS.
5. Integrar `/phi <texto livre>` ao core via CLI ou API local.
6. Adicionar testes sinteticos para recognizers, roundtrip, audit e lifecycle.

## Criterios De Aceite

- `/phi <texto livre>` envia ao modelo apenas texto redigido.
- `phi redact` transforma clipboard bruto em clipboard redigido.
- `phi restore` restaura clipboard redigido usando mappings ativos sem pedir session id.
- Qualquer comando `phi` roda purge de expirados antes da acao principal.
- Mapping nunca e impresso, enviado ao modelo ou commitado.
- Texto restaurado nunca e impresso por padrao.
- CPF invalido nao e aceito como CPF.
- IDs clinicos nao mascaram doses, sinais vitais ou valores laboratoriais soltos.
- Audit bloqueia residual de alta confianca.
- Testes usam apenas dados sinteticos.
