# Escopo e Roadmap: CIPTEA - Onboarding Conversacional IA

Este documento define a arquitetura, as fases e o fluxo de evolução do CIPTEA para um modelo de atendimento público automatizado e conversacional via LLM.

## Visão Geral
Transformar a ingestão de dados e documentos da CIPTEA de um formulário estático tradicional para um assistente virtual conversacional. O objetivo é reduzir a carga cognitiva do cidadão, automatizar a extração de dados via Visão Computacional e garantir a higienização dos dados de entrada (Custo Zero).

## Fluxo de Atendimento (State Machine)

A interação seguirá um funil de 8 etapas estritas. A IA terá um limite de **3 tentativas** por etapa de envio de documento. Em caso de falha contínua (ilegibilidade, documento errado), o usuário será roteado para o formulário manual de fallback.

1. **Identificação Base:** Coleta de CPF e Data de Nascimento. *(Futuro: Integração gov.br)*
2. **Ingestão do Laudo Médico:** 
   - Usuário envia foto/PDF do laudo no chat.
   - IA analisa a legibilidade e pertinência.
3. **Parametrização de Dados Clínicos:** IA extrai os dados do laudo validado e persiste na base de dados (CID, médico, data).
4. **Ingestão de Identidade do Beneficiário:** 
   - Usuário envia foto do documento pessoal.
   - IA extrai JSON com dados (CPF, Nome, Nascimento).
   - Backend cruza os dados **exclusivamente com bases internas do município** (Saúde, Social, Educação) para validação a custo zero.
5. **Ingestão de Identidade dos Responsáveis:** 
   - Coleta de até 3 documentos de responsáveis.
   - Processo de extração (IA) e validação em bases internas idêntico ao passo 4.
6. **Coleta e Higienização de Contato:** 
   - Coleta conversacional de WhatsApp/Telefone.
   - IA aplica validação sintática (Regex formato BR).
   - IA solicita confirmação humana explícita no chat para garantir precisão e viabilizar envios futuros no SIGA.
7. **Validação de Endereço (Regras de Negócio):** 
   - Usuário envia comprovante.
   - IA aplica regras restritas: Pertencer a Mogi das Cruzes E data de emissão < 90 dias.
8. **Revisão e Protocolo:** 
   - IA apresenta resumo dos dados extraídos para confirmação final.
   - Geração de número de protocolo e encaminhamento para fila de análise interna.

## Roadmap de Implementação

### Fase 1: Estabilização e PAC (Atual)
- [x] Correção do Delta de reprocessamento no `cadastro/tasks.py` (Arquivos blindados por orquestração na raiz).
- [x] Concluir isolamento de filas do Celery (separação de Redis DBs e disable de Gossip/Mingle entre SIGA e CIPTEA).
- [ ] Homologação em ambiente real: Uso assistido presencialmente no PAC.
- [ ] Coleta de métricas de rejeição do docTR para calibrar os thresholds da IA.

### Fase 2: Motor Conversacional (Backend)
- [ ] Desenvolver máquina de estado no Django (Model `SessaoAtendimentoIA`).
- [ ] Integrar modelo LLM Multimodal (Vision) via API para extração estruturada (JSON) de documentos.
- [ ] Construir funções de cruzamento de dados de identidade com as bases locais do município.
- [ ] Criar prompts de sistema restritos (System Prompts) para cada etapa do funil.

### Fase 3: Interface e UX (Frontend)
- [ ] Criar componente de Chat Interface no Vue.js.
- [ ] Implementar lógica de "Fallback": Roteamento dinâmico para o formulário clássico após 3 erros de IA no chat.
- [ ] Componente de "Revisão Final" renderizado no chat antes do submit.

### Fase 4: Integrações Avançadas (Futuro)
- [ ] Login único Gov.br (Single Sign-On).
- [ ] Emissão de carteira 100% digital e offline-first (PWA) no app municipal.