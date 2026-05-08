<template>
  <v-container class="fill-height align-start pa-0 pa-md-4">
    <v-card width="100%" max-width="800" class="mx-auto mt-md-5 rounded-0 rounded-md-lg" :loading="store.loading">
      
      <v-toolbar v-if="store.fasePosEnvio !== 'final'" color="primary" density="comfortable">
        <v-btn icon="mdi-arrow-left" to="/"></v-btn>
        <v-toolbar-title>
          {{ store.fasePosEnvio === 'triagem_ia' ? 'Análise automática dos documentos' : 'Solicitação CIPTEA' }}
        </v-toolbar-title>
      </v-toolbar>

      <v-fade-transition>
        <div
          v-if="store.fasePosEnvio === 'final' && store.success"
          class="fill-height d-flex flex-column justify-center align-center text-center pa-8 bg-white triagem-surface"
          style="min-height: 400px;"
        >
            
            <v-icon icon="mdi-check-decagram" color="green" size="100" class="mb-4 animate__animated animate__bounceIn"></v-icon>
            
            <h2 class="text-h4 font-weight-bold text-green-darken-2 mb-2">Solicitação Recebida!</h2>
            <p class="text-body-1 text-grey-darken-1 mb-6">
              O cadastro foi enviado para análise do PAC.<br>
              Acompanhe o status usando o protocolo abaixo:
            </p>

            <v-card variant="tonal" color="primary" class="py-4 px-8 mb-8 rounded-lg">
                <div class="text-caption text-uppercase font-weight-bold">Seu Protocolo</div>
                <div class="text-h3 font-weight-black text-primary">{{ store.protocolo }}</div>
            </v-card>

            <v-alert type="warning" variant="outlined" density="compact" class="mb-6 text-left max-width-500">
                <strong>Prazo de Análise:</strong> até 3 dias úteis.<br>
                Você receberá notificações de atualizaçoes.
            </v-alert>

            <v-btn 
                color="primary" 
                size="x-large" 
                to="/" 
                prepend-icon="mdi-home"
                @click="store.resetForm()"
            >
                Voltar para Início
            </v-btn>
        </div>
      </v-fade-transition>

      <v-expand-transition>
        <div
          v-if="store.fasePosEnvio === 'triagem_ia'"
          class="pa-4 pa-md-6 triagem-surface triagem-panel-enter"
        >
          <div class="text-center mb-6">
            <v-chip color="primary" variant="flat" size="small" class="mb-2">Etapa em tempo real</v-chip>
            <h2 class="text-h5 font-weight-bold text-primary">Status da análise por IA</h2>
            <p v-if="store.protocolo" class="text-body-2 text-medium-emphasis mb-0">
              Protocolo: <strong class="text-primary">{{ store.protocolo }}</strong>
            </p>
          </div>

          <v-card variant="tonal" color="surface-variant" class="mb-6 pa-2">
            <v-timeline align="start" side="end" density="compact" truncate-line="both">
              <v-timeline-item
                v-for="item in itensValidacaoIa"
                :key="item.key"
                :dot-color="item.dotColor"
                size="small"
              >
                <template #icon>
                  <v-progress-circular
                    v-if="item.status === 'analisando'"
                    indeterminate
                    size="20"
                    width="2"
                    color="primary"
                  />
                  <v-icon v-else-if="item.status === 'sucesso'" icon="mdi-check-circle" color="success" size="22" />
                  <v-icon v-else-if="item.status === 'revisao_manual'" icon="mdi-account-supervisor" color="warning" size="22" />
                  <v-icon v-else icon="mdi-clock-outline" color="grey" size="22" />
                </template>
                <div class="text-subtitle-2 font-weight-bold">{{ item.titulo }}</div>
                <div class="text-body-2 text-medium-emphasis">{{ item.mensagem }}</div>
              </v-timeline-item>
            </v-timeline>
          </v-card>

          <template v-if="store.iaResultadoGlobal">
            <div v-if="store.iaResultadoGlobal === 'APROVADO_IA'" class="celebration-wrap mb-6">
              <div class="confetti" aria-hidden="true">
                <span v-for="n in 12" :key="n" class="confetti-piece" :style="{ '--d': `${n * 0.08}s` }" />
              </div>
              <v-banner color="success" rounded="lg" lines="two" class="elevation-2">
                <template #prepend>
                  <v-icon icon="mdi-party-popper" size="large" />
                </template>
                <div class="text-body-1">
                  <strong>Ótimo!</strong> A triagem automática concluiu com sucesso. Você já pode seguir para a próxima etapa.
                </div>
              </v-banner>
            </div>

            <v-card
              v-else-if="store.iaResultadoGlobal === 'REVISAO_MANUAL'"
              class="mb-4"
              variant="tonal"
              color="warning"
            >
              <v-card-title class="text-subtitle-1 font-weight-bold">
                Análise inicial concluída
              </v-card-title>
              <v-card-text>
                <div class="text-body-2 mb-3">Foram identificadas divergências automáticas.</div>
                <div
                  v-for="d in divergenciasIa"
                  :key="`${d.documento}-${d.codigo}`"
                  class="mb-2"
                >
                  <div class="font-weight-bold">{{ d.titulo }} - {{ d.codigo }}</div>
                  <div class="text-body-2">{{ d.motivo }}</div>
                </div>
              </v-card-text>
            </v-card>
            <v-card
              v-if="podeReenviarDivergentes"
              class="mb-6"
              variant="flat"
              color="#455A64"
            >
              <v-card-title class="text-subtitle-2 font-weight-bold text-white">
                Reenviar apenas documentos divergentes
              </v-card-title>
              <v-card-text>
                <div
                  v-for="d in divergenciasIa"
                  :key="`${d.documento}-${d.codigo}`"
                  class="mb-3"
                >
                  <v-file-input
                    v-model="arquivosCorrecao[d.documento]"
                    :label="getLabelDivergencia(d)"
                    density="comfortable"
                    variant="outlined"
                    prepend-icon="mdi-paperclip"
                    accept=".pdf,.jpg,.jpeg,.png,.webp"
                    show-size
                    clearable
                    base-color="white"
                    color="warning"
                    theme="dark"
                  />
                </div>
                <v-btn
                  color="warning"
                  block
                  prepend-icon="mdi-upload"
                  :loading="loadingReenvioDivergente"
                  @click="reenviarDivergentes"
                >
                  REENVIAR
                </v-btn>
              </v-card-text>
            </v-card>

            <div class="d-flex flex-column flex-sm-row justify-center ga-3">
              <v-btn
                color="primary"
                size="large"
                prepend-icon="mdi-arrow-right-circle"
                @click="store.finalizarFaseTriagemVisual()"
              >
                Prosseguir
              </v-btn>
            </div>
          </template>
          <div v-else class="text-center text-medium-emphasis text-body-2">
            Aguardando retorno do servidor…
            <div class="mt-2">Você pode voltar para a tela inicial a qualquer momento.</div>
          </div>
        </div>
      </v-expand-transition>

      <div v-if="store.fasePosEnvio === 'form' && !store.success">
        <v-tabs v-if="!somenteCorrecaoAnexos" v-model="step" grow color="primary" class="mb-4">
          <v-tab :value="1">
            <v-badge :model-value="stepErrors[1]" color="error" dot>1. Dados</v-badge>
          </v-tab>
          <v-tab :value="2">
            <v-badge :model-value="stepErrors[2]" color="error" dot>2. Resp.</v-badge>
          </v-tab>
          <v-tab :value="3">
            <v-badge :model-value="stepErrors[3]" color="error" dot>3. Docs</v-badge>
          </v-tab>
        </v-tabs>
        <v-alert
          v-if="temErrosFormulario && !somenteCorrecaoAnexos"
          type="error"
          variant="tonal"
          border="start"
          density="compact"
          class="mx-4 mt-2 mb-4"
          icon="mdi-alert-circle"
        >
          <strong>Atenção:</strong> Existem campos com erro ou obrigatórios em branco. Verifique as abas sinalizadas com um ponto vermelho.
        </v-alert>

        <v-alert
          v-else-if="somenteCorrecaoAnexos"
          type="warning"
          variant="tonal"
          border="start"
          class="mx-4 mt-4 mb-0"
        >
          <strong>Correção de documentos</strong><br>
          Atualize apenas os anexos sinalizados para nova análise da IA.
        </v-alert>

        <v-card-text>
          <v-window v-model="step">
            
            <v-window-item :value="1">
              
              <v-sheet class="d-flex flex-column align-center mb-6 pt-4 pb-2 bg-transparent">
                
                <v-avatar 
                    size="130" 
                    class="mb-4 elevation-3" 
                    :style="store.beneficiario.status_foto === 'REJEITADO' ? 'border: 4px solid #FF5252' : 'border: 4px solid white'" 
                    color="grey-lighten-3"
                >
                  <v-img 
                      v-if="fotoPreview || store.beneficiario.foto" 
                      :src="fotoPreview ? fotoPreview : store.beneficiario.foto" 
                      cover
                  ></v-img>
                  <v-icon v-else icon="mdi-account" size="70" color="grey-lighten-1"></v-icon>
                </v-avatar>
                
                <v-alert 
                    v-if="store.beneficiario.status_foto === 'REJEITADO'"
                    type="error" 
                    variant="tonal" 
                    density="compact" 
                    class="mb-4 text-center w-100"
                    icon="mdi-camera-off"
                >
                    <strong>Foto Recusada:</strong> {{ store.beneficiario.motivo_rejeicao_foto }}
                    <div class="text-caption">Por favor, tire uma nova foto e envie novamente.</div>
                </v-alert>

                <div class="d-flex justify-center" style="gap: 20px">
                  <v-btn icon="mdi-camera" color="primary" size="large" elevation="2" @click="$refs.cameraInput.click()" v-tooltip:bottom="'Tirar Foto'"></v-btn>
                  <v-btn icon="mdi-image" color="primary" size="large" elevation="2" @click="$refs.fileInput.click()" v-tooltip:bottom="'Galeria'"></v-btn>
                </div>

                <input type="file" ref="cameraInput" accept="image/*" capture="user" class="d-none" @change="onFotoChange">
                <input type="file" ref="fileInput" accept="image/*" class="d-none" @change="onFotoChange">
              </v-sheet>
              
              <h3 class="text-h6 mb-2 text-primary">Identificação</h3>
              <v-row dense>
                <v-col cols="12">
                  <v-text-field 
                      label="Nome Completo*" 
                      v-model="store.beneficiario.nome_completo" 
                      variant="outlined" 
                      density="comfortable" 
                      :error-messages="getErro('nome_completo')" 
                  ></v-text-field>
                </v-col>
                <v-col cols="6">
                  <v-text-field label="Data Nasc.*" type="date" v-model="store.beneficiario.data_nascimento" variant="outlined" density="comfortable"></v-text-field>
                </v-col>
                <v-col cols="6">
                  <v-select label="Sexo" v-model="store.beneficiario.sexo" :items="['M', 'F']" variant="outlined" density="comfortable"></v-select>
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field label="CPF*" v-maska="'###.###.###-##'" v-model="store.beneficiario.cpf" variant="outlined" density="comfortable"></v-text-field>
                </v-col>
                <v-col cols="12" md="6">
                  <v-select 
                      label="CID Principal*" 
                      v-model="store.beneficiario.cid" 
                      :items="['F84.0 - Autismo Infantil', 'F84.1 - Autismo Atípico', 'F84.5 - Síndrome de Asperger', 'F84.9 - TGD Sem Outra Espec.']"
                      item-title="text"
                      item-value="value"
                      :return-object="false"
                      variant="outlined"
                      density="comfortable"
                  ></v-select>
                </v-col>
              </v-row>

              <h3 class="text-h6 mt-4 mb-2 text-primary">Endereço</h3>
              <v-row dense>
                <v-col cols="5">
                  <v-text-field 
                    label="CEP*" 
                    v-maska="'#####-###'" 
                    v-model="store.beneficiario.cep" 
                    @update:model-value="store.buscarCep"
                    :loading="store.loadingCep"
                    variant="outlined" 
                    density="comfortable"
                  ></v-text-field>
                </v-col>
                <v-col cols="7">
                  <v-text-field label="Bairro*" v-model="store.beneficiario.bairro" variant="outlined" density="comfortable"></v-text-field>
                </v-col>
                <v-col cols="9">
                  <v-text-field label="Logradouro*" v-model="store.beneficiario.logradouro" variant="outlined" density="comfortable"></v-text-field>
                </v-col>
                <v-col cols="3">
                  <v-text-field label="Nº*" id="numeroInput" v-model="store.beneficiario.numero" variant="outlined" density="comfortable"></v-text-field>
                </v-col>
                <v-col cols="12">
                  <v-text-field label="Complemento" v-model="store.beneficiario.complemento" variant="outlined" density="comfortable"></v-text-field>
                </v-col>
                <v-col cols="6">
                  <v-text-field label="Cidade" v-model="store.beneficiario.cidade" readonly variant="filled" density="comfortable"></v-text-field>
                </v-col>
                <v-col cols="6">
                  <v-text-field label="UF" v-model="store.beneficiario.estado" readonly variant="filled" density="comfortable"></v-text-field>
                </v-col>
              </v-row>
              
              <div class="d-flex justify-end mt-4">
                <v-btn color="primary" append-icon="mdi-arrow-right" @click="step++">Próximo</v-btn>
              </div>
            </v-window-item>

            <v-window-item :value="2">
              <div class="d-flex justify-space-between align-center mb-4">
                  <h3 class="text-h6 text-primary">Responsáveis</h3>
                  <v-btn 
                      size="small" 
                      variant="tonal" 
                      prepend-icon="mdi-plus" 
                      @click="store.adicionarResponsavel"
                  >
                      Adicionar
                  </v-btn>
              </div>

              <div v-for="(resp, i) in store.responsaveis" :key="i">
                  <v-card class="mb-4 pa-4 border" variant="flat">
                      
                      <v-checkbox
                          v-if="i === 0"
                          v-model="isProprioBeneficiario"
                          label="O beneficiário é o próprio responsável"
                          color="primary"
                          density="compact"
                          class="mt-n2"
                          hide-details
                      ></v-checkbox>

                      <div class="d-flex justify-space-between mb-2">
                          </div>

                      <v-row dense>
                          <v-col cols="12">
                              <v-select 
                                  label="Vínculo*" 
                                  v-model="resp.perfil"
                                  :items="listaVinculos"
                                  :disabled="isProprioBeneficiario && i === 0"
                                  variant="outlined"
                                  density="comfortable"
                              ></v-select>
                          </v-col>
                          <v-col cols="12">
                              <v-text-field 
                                  label="Nome Completo*" 
                                  v-model="resp.nome" 
                                  :disabled="isProprioBeneficiario && i === 0"
                                  variant="outlined"
                                  density="comfortable"
                              ></v-text-field>
                          </v-col>
                          <v-col cols="12" md="6">
                              <v-text-field 
                                  label="CPF*" 
                                  v-maska="'###.###.###-##'" 
                                  v-model="resp.cpf" 
                                  :disabled="isProprioBeneficiario && i === 0"
                                  variant="outlined"
                                  density="comfortable"
                              ></v-text-field>
                          </v-col>

                          <v-col cols="12" md="6">
                              <v-text-field 
                                  label="Celular/WhatsApp*" 
                                  v-maska="'(##) #####-####'" 
                                  v-model="resp.telefone" 
                                  variant="outlined"
                                  density="comfortable"
                              ></v-text-field>
                          </v-col>
                          
                          <v-col cols="12" v-if="!(isProprioBeneficiario && i === 0)">
                              <v-file-input 
                                  label="RG/CNH deste Responsável*" 
                                  variant="outlined"
                                  density="comfortable"
                                  prepend-icon="mdi-badge-account-horizontal-outline"
                                  accept="image/*, application/pdf"
                                  @update:model-value="files => resp.documento_identidade = files ? (Array.isArray(files) ? files[0] : files) : null"
                              ></v-file-input>
                          </v-col>
                          <v-col cols="12" v-else>
                              <v-alert type="success" variant="tonal" density="compact" icon="mdi-link-variant">
                                  O documento de identidade do beneficiário será utilizado como comprovação.
                              </v-alert>
                          </v-col>
                      </v-row>
                  </v-card>
              </div>

              <div class="d-flex justify-space-between mt-4">
                <v-btn variant="text" @click="step--">Voltar</v-btn>
                <v-btn color="primary" append-icon="mdi-arrow-right" @click="step++">Próximo</v-btn>
              </div>
            </v-window-item>

            <v-window-item :value="3">
              <h3 class="text-h6 mb-2 text-primary">Documentação</h3>
              <v-alert type="info" variant="tonal" class="mb-4 text-caption" density="compact">
                Arquivos aceitos: Fotos (JPG/PNG) ou PDF.
              </v-alert>
              
              <v-alert
                v-if="isRenovacaoEdicao"
                type="warning"
                variant="tonal"
                class="mb-4 text-caption"
                density="comfortable"
                icon="mdi-clipboard-check-outline"
              >
                <strong>Documentos obrigatórios para concluir a renovação:</strong><br>
                - Laudo Médico com CID<br>
                - RG/Certidão do Beneficiário<br>
                - Comprovante de Residência
              </v-alert>
              
              <v-card v-if="isRenovacaoEdicao" variant="tonal" class="mb-4">
                <v-card-text class="py-3">
                  <div class="text-subtitle-2 font-weight-bold mb-2 text-grey-darken-3">
                    Conferência rápida da renovação
                  </div>
                  <div class="d-flex flex-wrap" style="gap: 8px;">
                    <v-chip :color="checklistDocs.laudo.ok ? 'success' : 'error'" size="small" variant="flat">
                      <v-icon start :icon="checklistDocs.laudo.ok ? 'mdi-check-circle' : 'mdi-alert-circle'"></v-icon>
                      {{ checklistDocs.laudo.label }}
                    </v-chip>
                    <v-chip :color="checklistDocs.rgBenef.ok ? 'success' : 'error'" size="small" variant="flat">
                      <v-icon start :icon="checklistDocs.rgBenef.ok ? 'mdi-check-circle' : 'mdi-alert-circle'"></v-icon>
                      {{ checklistDocs.rgBenef.label }}
                    </v-chip>
                    <v-chip :color="checklistDocs.compRes.ok ? 'success' : 'error'" size="small" variant="flat">
                      <v-icon start :icon="checklistDocs.compRes.ok ? 'mdi-check-circle' : 'mdi-alert-circle'"></v-icon>
                      {{ checklistDocs.compRes.label }}
                    </v-chip>
                  </div>
                </v-card-text>
              </v-card>

              <div class="mb-4">
                  <v-file-input 
                    label="Laudo Médico (c/ CID)*" 
                    variant="outlined"
                    density="comfortable"
                    prepend-icon="mdi-doctor"
                    accept="image/*, application/pdf"
                    @update:model-value="files => store.anexos.laudo = files ? files : null"
                    :disabled="somenteCorrecaoAnexos && !campoDivergente('laudo')"
                    :color="campoDivergente('laudo') ? 'warning' : undefined"
                    :messages="campoDivergente('laudo') ? ['Documento com divergência da IA: envie uma nova versão.'] : []"
                    :error-messages="store.statusLaudo?.status === 'REJEITADO' ? 'Documento recusado' : ''"
                    :base-color="campoDivergente('laudo') ? 'warning' : (store.statusLaudo?.status === 'REJEITADO' ? 'error' : (store.statusLaudo?.status === 'APROVADO' ? 'success' : ''))"
                    :class="{ 'doc-divergente': campoDivergente('laudo') }"
                  >
                      <template v-slot:append-inner v-if="store.statusLaudo?.status === 'APROVADO'">
                          <v-icon color="success" icon="mdi-check-circle" v-tooltip:top="'Documento Aceito'"></v-icon>
                      </template>
                  </v-file-input>

                  <v-alert 
                      v-if="store.statusLaudo?.status === 'REJEITADO'"
                      type="error" variant="tonal" density="compact" class="mt-1" icon="mdi-alert-circle"
                  >
                      <strong>Motivo da Recusa:</strong> {{ store.statusLaudo.motivo_rejeicao }}
                      <div class="text-caption">Por favor, envie uma foto nova e legível.</div>
                  </v-alert>
              </div>

              <div class="mb-4">
                  <v-file-input 
                    label="RG/Certidão (Beneficiário)*" 
                    variant="outlined"
                    density="comfortable"
                    prepend-icon="mdi-card-account-details"
                    accept="image/*, application/pdf"
                    @update:model-value="files => store.anexos.rg_beneficiario = files ? files : null"
                    :disabled="somenteCorrecaoAnexos && !campoDivergente('rg_beneficiario')"
                    :color="campoDivergente('rg_beneficiario') ? 'warning' : undefined"
                    :messages="campoDivergente('rg_beneficiario') ? ['Documento com divergência da IA: envie uma nova versão.'] : []"
                    :error-messages="store.statusRgBenef?.status === 'REJEITADO' ? 'Documento recusado' : ''"
                    :base-color="campoDivergente('rg_beneficiario') ? 'warning' : (store.statusRgBenef?.status === 'REJEITADO' ? 'error' : (store.statusRgBenef?.status === 'APROVADO' ? 'success' : ''))"
                    :class="{ 'doc-divergente': campoDivergente('rg_beneficiario') }"
                  >
                      <template v-slot:append-inner v-if="store.statusRgBenef?.status === 'APROVADO'">
                          <v-icon color="success" icon="mdi-check-circle"></v-icon>
                      </template>
                  </v-file-input>

                  <v-alert 
                      v-if="store.statusRgBenef?.status === 'REJEITADO'"
                      type="error" variant="tonal" density="compact" class="mt-1" icon="mdi-alert-circle"
                  >
                      <strong>Motivo:</strong> {{ store.statusRgBenef.motivo_rejeicao }}
                  </v-alert>
              </div>

              <div class="mb-4">
                  <v-file-input 
                    label="Comp. Residência (Mogi)*" 
                    variant="outlined"
                    density="comfortable"
                    prepend-icon="mdi-home-map-marker"
                    accept="image/*, application/pdf"
                    @update:model-value="files => store.anexos.comprovante_residencia = files ? files : null"
                    :disabled="somenteCorrecaoAnexos && !campoDivergente('comprovante_residencia')"
                    :color="campoDivergente('comprovante_residencia') ? 'warning' : undefined"
                    :messages="campoDivergente('comprovante_residencia') ? ['Documento com divergência da IA: envie uma nova versão.'] : []"
                    :error-messages="store.statusCompRes?.status === 'REJEITADO' ? 'Documento recusado' : ''"
                    :base-color="campoDivergente('comprovante_residencia') ? 'warning' : (store.statusCompRes?.status === 'REJEITADO' ? 'error' : (store.statusCompRes?.status === 'APROVADO' ? 'success' : ''))"
                    :class="{ 'doc-divergente': campoDivergente('comprovante_residencia') }"
                  >
                      <template v-slot:append-inner v-if="store.statusCompRes?.status === 'APROVADO'">
                          <v-icon color="success" icon="mdi-check-circle"></v-icon>
                      </template>
                  </v-file-input>

                  <v-alert 
                      v-if="store.statusCompRes?.status === 'REJEITADO'"
                      type="error" variant="tonal" density="compact" class="mt-1" icon="mdi-alert-circle"
                  >
                      <strong>Motivo:</strong> {{ store.statusCompRes.motivo_rejeicao }}
                  </v-alert>
              </div>

              <v-divider class="my-6"></v-divider>

              <div v-if="store.error" class="text-red mb-3 text-center font-weight-bold">
                <v-icon icon="mdi-alert-circle"></v-icon> {{ store.error }}
              </div>
              
              <div class="d-flex justify-space-between mt-4">
                <v-btn v-if="!somenteCorrecaoAnexos" variant="text" @click="step--">Voltar</v-btn>
                <span v-else></span>
                <v-btn color="success" size="large" :loading="store.loading" @click="store.enviarSolicitacao()">
                  {{ isRenovacaoEdicao ? 'Enviar Renovação' : (store.modoEdicao ? 'Salvar Correções' : 'Finalizar Solicitação') }}
                </v-btn>
              </div>
            </v-window-item>

          </v-window>
        </v-card-text>
      </div>
    </v-card>
    <v-dialog v-model="dialogCropper" persistent max-width="600" class="dialog-cropper">
        <v-card class="bg-black">
            <v-toolbar color="black" density="compact">
                <v-toolbar-title class="text-white">Ajustar Foto</v-toolbar-title>
                <v-btn icon="mdi-close" color="white" @click="dialogCropper = false"></v-btn>
            </v-toolbar>
            
            <v-card-text class="pa-0 d-flex justify-center align-center" style="height: 400px; background-color: #000;">
                <img id="image-cropper-target" :src="imageSrc" style="max-width: 100%; max-height: 100%; display: block;">
            </v-card-text>

            <v-card-actions class="bg-white pa-4">
                <span class="text-caption text-grey">Arraste e use pinça para ajustar o rosto no quadrado.</span>
                <v-spacer></v-spacer>
                <v-btn variant="text" @click="dialogCropper = false">Cancelar</v-btn>
                <v-btn color="primary" variant="elevated" @click="confirmarRecorte">
                    <v-icon start>mdi-crop</v-icon> Confirmar
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, computed, onUnmounted, watch } from 'vue';
import { vMaska } from 'maska/vue'; 
import { useCadastroStore } from '@/stores/cadastro';
import { useToastStore } from '@/stores/toast';
import { useRouter } from 'vue-router';
import Cropper from 'cropperjs';
import 'cropperjs/dist/cropper.css';
import { nextTick } from 'vue';

const step = ref(1);
const store = useCadastroStore();
const toast = useToastStore();
const router = useRouter();
const fotoPreview = ref(null);
const dialogCropper = ref(false);
const imageSrc = ref('');
let cropperInstance = null;
const loadingReenvioDivergente = ref(false);
const arquivosCorrecao = ref({
  laudo: null,
  rg_beneficiario: null,
  comprovante_residencia: null,
  rg_responsavel: null,
});

const listaVinculos = [
    { title: 'Mãe', value: 'MAE' },
    { title: 'Pai', value: 'PAI' },
    { title: 'Avô/Avó', value: 'AVO' },
    { title: 'Tio/Tia', value: 'TIO' },
    { title: 'Tutor/Curador', value: 'TUTOR' },
    { title: 'Próprio Beneficiário', value: 'PROPRIO' },
    { title: 'Outro', value: 'OUTRO' }
];
// Controle para o fluxo de "Próprio Beneficiário"
const isProprioBeneficiario = ref(false);

// Sincroniza dados do beneficiário para o primeiro responsável
watch(isProprioBeneficiario, (val) => {
    if (val) {
        // Validação de Maioridade (18+ anos)
        if (!store.beneficiario.data_nascimento) {
            toast.warning("Preencha a data de nascimento do beneficiário (Passo 1) primeiro.");
            isProprioBeneficiario.value = false;
            return;
        }
        
        const dob = new Date(store.beneficiario.data_nascimento);
        const hoje = new Date();
        let idade = hoje.getFullYear() - dob.getFullYear();
        const m = hoje.getMonth() - dob.getMonth();
        if (m < 0 || (m === 0 && hoje.getDate() < dob.getDate())) {
            idade--;
        }
        
        if (idade < 18) {
            toast.error("O beneficiário precisa ter 18 anos ou mais para ser o próprio responsável.");
            isProprioBeneficiario.value = false;
            return;
        }

        if (store.responsaveis.length > 0) {
            const resp = store.responsaveis[0];
            resp.nome = store.beneficiario.nome_completo;
            resp.cpf = store.beneficiario.cpf;
            resp.perfil = 'PROPRIO';
            resp.status_documento = 'APROVADO'; 
        }
    } else if (!val && store.responsaveis.length > 0) {
        store.responsaveis[0].perfil = null;
    }
});

// Watch auxiliar para manter sincronizado caso o usuário mude o nome no Passo 1 e volte
watch(() => store.beneficiario.nome_completo, (novoNome) => {
    if (isProprioBeneficiario.value && store.responsaveis.length > 0) {
        store.responsaveis[0].nome = novoNome;
    }
});
const isRenovacaoEdicao = computed(() => store.modoEdicao && store.tipoFluxoEdicao === 'RENOVACAO');
const temResponsavel = computed(() => Array.isArray(store.responsaveis) && store.responsaveis.length > 0);
const checklistDocs = computed(() => {
    const possuiDoc = (existente, novoArquivo) => Boolean((existente && existente.id) || novoArquivo);
    return {
        laudo: {
            label: 'Laudo Médico',
            ok: possuiDoc(store.statusLaudo, store.anexos.laudo),
        },
        rgBenef: {
            label: 'RG/Certidão Beneficiário',
            ok: possuiDoc(store.statusRgBenef, store.anexos.rg_beneficiario),
        },
        compRes: {
            label: 'Comprovante Residência',
            ok: possuiDoc(store.statusCompRes, store.anexos.comprovante_residencia),
        },
    };
});

const podeReenviarDivergentes = computed(() => {
    return store.iaResultadoGlobal === 'REVISAO_MANUAL' && divergenciasIa.value.length > 0;
});

const somenteCorrecaoAnexos = computed(() => store.modoCorrecaoSomenteAnexos);

const campoDivergente = (campo) => {
    return divergenciasIa.value.some(d => d.documento === campo);
};

const normalizarArquivoInput = (file) => {
    return Array.isArray(file) ? file[0] : file;
};

const dotPorStatus = (status) => {
  if (status === 'analisando') return 'primary';
  if (status === 'sucesso') return 'success';
  if (status === 'revisao_manual') return 'warning';
  return 'grey';
};

// Leitor seguro do Log da IA (resolve o problema do Django devolver JSON como String)
const logIa = computed(() => {
    let log = store.triagemResposta?.log_ia;
    if (typeof log === 'string') {
        try { return JSON.parse(log); } catch(e) { return {}; }
    }
    return log || {};
});

// 1. Timeline Dinâmica e Blindada
const itensValidacaoIa = computed(() => {
  const orq = logIa.value?.etapas?.orquestracao || {};
  const val = logIa.value?.etapas?.validacao || {};
  const docsOrquestrados = orq.documentos || [];

  const pick = (key, titulo) => {
    let statusFront = 'pendente';
    let msg = '';
    
    if (val[key]) {
        statusFront = val[key].ok ? 'sucesso' : 'revisao_manual';
        msg = val[key].motivo || '';
    } else if (store.validacao && store.validacao[key]) {
        statusFront = store.validacao[key].status === 'VALIDADO' ? 'sucesso' : 
                      store.validacao[key].status === 'INVALIDO' ? 'revisao_manual' : 'pendente';
        msg = store.validacao[key].motivo || '';
    }
    
    if (statusFront === 'pendente' && (store.iaResultadoGlobal === 'PROCESSANDO' || store.iaResultadoGlobal === 'PENDENTE')) {
        statusFront = 'analisando';
    }

    return { key, titulo, status: statusFront, mensagem: msg, dotColor: dotPorStatus(statusFront) };
  };

  const rows = [];
  const responsaveisAtuais = store.responsaveis || [];
  
  docsOrquestrados.forEach(doc => {
      const keyStr = doc.toLowerCase();
      if (keyStr === 'laudo') rows.push(pick('laudo', 'Laudo Médico'));
      else if (keyStr === 'identidade') rows.push(pick('identidade', 'RG/CNH do portador (TEA)'));
      else if (keyStr === 'endereco') rows.push(pick('endereco', 'Comprovante de endereço'));
      else if (keyStr.startsWith('responsavel_')) {
          const idx = parseInt(keyStr.split('_')[1]);
          const nome = responsaveisAtuais[idx] ? responsaveisAtuais[idx].nome : `Responsável ${idx+1}`;
          rows.push(pick(keyStr, `RG: ${nome}`));
      }
  });
  
  if (rows.length === 0) {
      rows.push(pick('laudo', 'Laudo Médico'));
      rows.push(pick('identidade', 'RG/CNH do portador (TEA)'));
      rows.push(pick('endereco', 'Comprovante de endereço'));
      responsaveisAtuais.forEach((resp, i) => {
          rows.push(pick(`responsavel_${i}`, `RG: ${resp.nome || 'Responsável ' + (i+1)}`));
      });
  }

  return rows;
});

// 2. Caçador Universal de Divergências
const divergenciasIa = computed(() => {
    const divs = [...(store.triagemResposta?.resumo_divergencias || [])];
    const val = logIa.value?.etapas?.validacao || {};
    
    const nomesPadrao = { laudo: 'Laudo Médico', identidade: 'RG/CNH do portador (TEA)', endereco: 'Comprovante de Endereço' };
    const responsaveisAtuais = store.responsaveis || [];

    // Varre TODOS os documentos na validação, garantindo que o frontend caça os erros sozinho
    Object.keys(val).forEach(key => {
        if (val[key].ok === false) {
            if (!divs.find(d => d.documento === key)) {
                let tituloDoc = nomesPadrao[key] || 'Documento';
                if (key.startsWith('responsavel_')) {
                    const idx = parseInt(key.split('_')[1]);
                    const nome = responsaveisAtuais[idx] ? responsaveisAtuais[idx].nome : `Responsável ${idx+1}`;
                    tituloDoc = `RG/CNH - ${nome}`;
                }
                divs.push({
                    documento: key,
                    titulo: tituloDoc,
                    codigo: 'DIVERGENCIA_DOCUMENTO',
                    motivo: val[key].motivo || 'Documento recusado ou ilegível pela IA.'
                });
            }
        }
    });
    
    return divs;
});

// 2. Mapeamento de chaves para suportar indices (ex: responsavel_0)
const mapDocumentoParaAnexo = (docKey) => {
  if (docKey === 'laudo') return 'laudo';
  if (docKey === 'identidade') return 'rg_beneficiario';
  if (docKey === 'endereco') return 'comprovante_residencia';
  if (docKey.startsWith('responsavel')) return docKey; // Mantém responsavel_0, responsavel_1...
  return 'laudo';
};

// 3. Função para gerar o Label amigável no Reenvio
const getLabelDivergencia = (d) => {
    if (d.documento.startsWith('responsavel_')) {
        const idx = parseInt(d.documento.split('_')[1]);
        const nome = store.responsaveis[idx]?.nome || `Responsável ${idx + 1}`;
        return `Novo RG - ${nome}`;
    }
    return `Novo arquivo - ${d.titulo}`;
};

// 4. Ajuste no Reenvio para injetar o arquivo no lugar certo (Anexos ou Responsáveis)
const reenviarDivergentes = async () => {
  loadingReenvioDivergente.value = true;
  try {
    const divergentes = divergenciasIa.value;
    const chavesParaProcessar = divergentes.map(d => d.documento);
    
    const possuiArquivo = chavesParaProcessar.some(k => arquivosCorrecao.value[k]);
    if (!possuiArquivo) {
      toast.warning('Anexe ao menos um documento divergente para reenviar.');
      return;
    }
    
    const protocolo = store.protocolo || store.perfilSalvo?.protocolo;
    const cpf = store.beneficiario?.cpf || store.perfilSalvo?.cpf;
    const dataNascimento = store.beneficiario?.data_nascimento || store.perfilSalvo?.data_nascimento;
    
    await store.solicitarCorrecaoPrePac();
    const ok = await store.carregarParaEdicao(protocolo, cpf, dataNascimento);
    if (!ok) return;

    // Reset de segurança
    store.anexos = { laudo: null, rg_beneficiario: null, comprovante_residencia: null, foto: null };

    // Distribuição inteligente dos arquivos
    chavesParaProcessar.forEach((k) => {
      const file = normalizarArquivoInput(arquivosCorrecao.value[k]);
      if (!file) return;

      if (k.startsWith('responsavel_')) {
          const idx = parseInt(k.split('_')[1]);
          if (store.responsaveis[idx]) {
              store.responsaveis[idx].documento_identidade = file;
          }
      } else {
          const anexoKey = mapDocumentoParaAnexo(k);
          store.anexos[anexoKey] = file;
      }
    });

    await store.atualizarExistente();
    toast.success('Documentos reenviados para reprocessamento da IA.');
    store.fasePosEnvio = 'triagem_ia';

  } catch (e) {
    toast.error(e?.response?.data?.erro || 'Falha ao reenviar.');
  } finally {
    loadingReenvioDivergente.value = false;
  }
};

watch(
  () => store.fasePosEnvio,
  (fase) => {
    if (fase === 'triagem_ia' && store.iaTriagemAutoRedirect) {
      store.iaTriagemAutoRedirect = false;
      router.push('/');
    }
  },
  { immediate: true }
);

watch(
  () => store.modoCorrecaoSomenteAnexos,
  (ativo) => {
    if (ativo) {
      step.value = 3;
    }
  },
  { immediate: true }
);

onUnmounted(() => {
  // sem ações pendentes aqui
});

const iniciarCropper = () => {
    // Limpa instância anterior se existir
    if (cropperInstance) {
        cropperInstance.destroy();
        cropperInstance = null;
    }

    // Pega a imagem do DOM (que está dentro do Dialog)
    const image = document.getElementById('image-cropper-target');
    
    if (image) {
        cropperInstance = new Cropper(image, {
            aspectRatio: 1, // Quadrado 1:1
            viewMode: 1, // A imagem não sai da área de corte
            dragMode: 'move', // Permite arrastar a imagem com o dedo
            autoCropArea: 0.8,
            guides: true,
            center: true,
            background: false, // Fundo preto do modal
            responsive: true,
        });
    }
};

const onFotoChange = (event) => {
    const file = event.target.files[0];
    
    // Reseta o input para permitir selecionar a mesma foto se errar
    event.target.value = '';

    if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            // 1. Define a imagem na tela
            imageSrc.value = e.target.result;
            
            // 2. Abre o Modal
            dialogCropper.value = true;
            
            // 3. Espera o Modal renderizar e inicia o Cropper
            nextTick(() => {
                iniciarCropper(); // <--- Agora ela existe!
            });
        };
        reader.readAsDataURL(file);
    }
};

const confirmarRecorte = () => {
    if (!cropperInstance) return;

    // Gera o arquivo recortado (600x600px)
    cropperInstance.getCroppedCanvas({
        width: 600,
        height: 600,
        fillColor: '#fff',
        imageSmoothingEnabled: true,
        imageSmoothingQuality: 'high',
    }).toBlob((blob) => {
        if (!blob) return;

        // Cria arquivo final
        const arquivoFinal = new File([blob], "perfil_recortado.jpg", { type: "image/jpeg" });
        
        // Salva na Store
        store.anexos.foto = arquivoFinal;
        
        // Atualiza Preview
        fotoPreview.value = URL.createObjectURL(blob);
        
        // Fecha tudo
        dialogCropper.value = false;
        cropperInstance.destroy();
        cropperInstance = null;
        
    }, 'image/jpeg', 0.9);
};

// --- VALIDAÇÃO VISUAL DE ERROS ---

const temErrosFormulario = computed(() => Object.keys(store.errosCampos || {}).length > 0);

// Descobre em qual aba estão os erros baseados nas chaves retornadas pelo Django
const stepErrors = computed(() => {
    const errs = store.errosCampos || {};
    const keys = Object.keys(errs);
    return {
        1: keys.some(k => ['nome_completo', 'data_nascimento', 'cpf', 'cid', 'cep', 'bairro', 'logradouro', 'numero', 'foto'].includes(k)),
        2: keys.some(k => k === 'responsaveis'), // O Django agrupa erros da lista nesta chave
        3: keys.some(k => ['laudo', 'rg_beneficiario', 'comprovante_residencia', 'rg_responsavel'].includes(k))
    };
});

// Leitor profundo: consegue ler 'nome_completo' ou 'responsaveis[0].nome'
const getErro = (campoPath) => {
    try {
        if (!store.errosCampos) return '';
        
        // Converte a string 'responsaveis[0].nome' num array de chaves: ['responsaveis', '0', 'nome']
        const parts = campoPath.replace(/\[(\d+)\]/g, '.$1').split('.');
        let current = store.errosCampos;
        
        for (let part of parts) {
            if (current[part] === undefined) return '';
            current = current[part];
        }
        
        // O Django REST geralmente devolve as mensagens dentro de um array ["Este campo é obrigatório."]
        return Array.isArray(current) ? current[0] : current;
    } catch (e) {
        return '';
    }
};
</script>

<style scoped>
/* Garante que a imagem do cropper não ultrapasse o container */
img {
  max-width: 100%; 
}

/* Opcional: Ajuste para o container do cropper ficar escuro */
.cropper-modal {
    background-color: rgba(0, 0, 0, 0.8);
}

/* Transição suave entre formulário e painel de triagem (substitui utilitários Tailwind) */
.triagem-surface {
  transition: opacity 0.35s ease, transform 0.35s ease;
}
.triagem-panel-enter {
  opacity: 1;
  transform: translateY(0);
}
@media (max-width: 600px) {
  .triagem-panel-enter {
    padding-left: 12px;
    padding-right: 12px;
  }
}

.celebration-wrap {
  position: relative;
  overflow: hidden;
  border-radius: 12px;
}
.confetti {
  pointer-events: none;
  position: absolute;
  inset: 0;
  z-index: 0;
}
.confetti-piece {
  position: absolute;
  top: -12px;
  width: 6px;
  height: 10px;
  opacity: 0.85;
  animation: confetti-fall 2.2s ease-in infinite;
  animation-delay: var(--d, 0s);
  left: calc(8% + (var(--n, 0) * 7%));
}
.confetti-piece:nth-child(odd) {
  background: #43a047;
}
.confetti-piece:nth-child(even) {
  background: #1e88e5;
}
.confetti-piece:nth-child(1) { left: 5%; }
.confetti-piece:nth-child(2) { left: 15%; }
.confetti-piece:nth-child(3) { left: 25%; }
.confetti-piece:nth-child(4) { left: 35%; }
.confetti-piece:nth-child(5) { left: 45%; }
.confetti-piece:nth-child(6) { left: 55%; }
.confetti-piece:nth-child(7) { left: 65%; }
.confetti-piece:nth-child(8) { left: 75%; }
.confetti-piece:nth-child(9) { left: 85%; }
.confetti-piece:nth-child(10) { left: 92%; }
.confetti-piece:nth-child(11) { left: 50%; }
.confetti-piece:nth-child(12) { left: 30%; }

@keyframes confetti-fall {
  0% {
    transform: translateY(0) rotate(0deg);
    opacity: 1;
  }
  100% {
    transform: translateY(140px) rotate(260deg);
    opacity: 0;
  }
}
.celebration-wrap :deep(.v-banner) {
  position: relative;
  z-index: 1;
}

.doc-divergente :deep(.v-field) {
  border: 2px solid rgb(var(--v-theme-warning));
  background-color: rgba(var(--v-theme-warning), 0.08);
}

.doc-divergente :deep(.v-label),
.doc-divergente :deep(.v-field__prepend-inner .v-icon) {
  color: rgb(var(--v-theme-warning)) !important;
}
</style>