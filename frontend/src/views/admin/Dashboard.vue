<template>
  <v-app-bar color="primary" density="compact" elevation="2" class="py-1">
    
    <template v-slot:prepend>
        <div class="d-flex align-center ml-2">
             <img src="/brasao.png" height="40" alt="Brasão Mogi"> 
        </div>
    </template>

    <v-app-bar-title class="font-weight-bold text-uppercase" style="font-size: 1rem;">
        Gestão CIPTEA
    </v-app-bar-title>    

    <v-spacer></v-spacer>

    <v-text-field
        v-model="termoBusca"
        density="compact"
        variant="solo"
        label="Buscar Nome, CPF ou Protocolo..."
        append-inner-icon="mdi-magnify"
        single-line
        hide-details
        clearable 
        style="max-width: 300px;"
        class="mr-4"
        bg-color="white" 
        color="primary"
        @keydown.enter="carregarSolicitacoes" 
        @click:append-inner="carregarSolicitacoes"
        @click:clear="limparBusca"
    ></v-text-field>
    <v-select
      v-model="filtroOrigem"
      :items="opcoesOrigem"
      item-title="label"
      item-value="value"
      density="compact"
      variant="solo"
      hide-details
      style="max-width: 220px;"
      class="mr-4"
      bg-color="white"
      label="Origem"
      @update:model-value="carregarSolicitacoes"
    ></v-select>
    <v-switch
      v-model="somenteVencidas"
      color="deep-orange-darken-2"
      hide-details
      inset
      class="mr-4"
      :label="`Somente vencidas (${somenteVencidas ? 'ON' : 'OFF'})`"
      @update:model-value="carregarSolicitacoes"
    ></v-switch>
    <div
      class="text-caption mr-4"
      :class="somenteVencidas ? 'text-deep-orange font-weight-bold' : 'text-grey-darken-1'"
    >
      Filtro {{ somenteVencidas ? 'ativo' : 'inativo' }}
    </div>
    
    <v-btn icon="mdi-refresh" @click="carregarSolicitacoes"></v-btn>
    <v-btn icon="mdi-logout" @click="realizarLogout"></v-btn>
  </v-app-bar>
  <v-progress-linear
    v-if="loadingDetalhe"
    indeterminate
    color="primary"
  ></v-progress-linear>

  <v-container fluid class="pa-4 pb-0">
    <div class="d-flex align-center" style="gap: 8px;">
      <v-chip size="small" color="purple" variant="flat" class="cursor-pointer" @click="aplicarFiltroOrigem('LEGADO')">
        Legado (página): {{ totalLegado }}
      </v-chip>
      <v-chip size="small" color="primary" variant="flat" class="cursor-pointer" @click="aplicarFiltroOrigem('SISTEMA_NOVO')">
        Novo (página): {{ totalSistemaNovo }}
      </v-chip>
      <v-chip size="small" color="grey-darken-1" variant="tonal" class="cursor-pointer" @click="aplicarFiltroOrigem('TODOS')">
        Total (todas colunas): {{ totalSolicitacoes }}
      </v-chip>
      <v-chip
        size="small"
        color="deep-orange"
        :variant="somenteVencidas ? 'flat' : 'tonal'"
        class="cursor-pointer"
        @click="alternarSomenteVencidas"
      >
        Vencidas visíveis: {{ totalVencidasVisiveis }}
      </v-chip>
    </div>
    <v-card class="mt-3" variant="tonal" :color="corCardRollout">
      <v-card-text class="py-3">
        <div class="d-flex align-center justify-space-between" style="gap: 12px;">
          <div>
            <div class="text-subtitle-2 font-weight-bold text-grey-darken-4">Acompanhamento dos novos cadastros</div>
            <div class="text-caption text-grey-darken-1">
              Fluxo principal: {{ metricasCadastro.transacional_total }} | Plano B: {{ metricasCadastro.fallback_total }} | Total: {{ metricasCadastro.total_cadastros_medidos }}
            </div>
          </div>
          <v-btn
            size="small"
            variant="text"
            color="primary"
            prepend-icon="mdi-refresh"
            :loading="loadingMetricasCadastro"
            @click="carregarMetricasCadastro"
          >
            Atualizar dados
          </v-btn>
        </div>
        <v-progress-linear
          class="mt-2"
          height="10"
          color="success"
          bg-color="grey-lighten-2"
          :model-value="participacaoTransacionalPercentual"
          rounded
        ></v-progress-linear>
        <div class="text-caption mt-1 text-grey-darken-1">
          Uso do fluxo principal: {{ participacaoTransacionalPercentual.toFixed(1) }}%
        </div>
        <v-alert
          class="mt-2"
          density="compact"
          :type="statusRollout.type"
          variant="tonal"
          :icon="statusRollout.icon"
        >
          {{ statusRollout.texto }}
        </v-alert>
      </v-card-text>
    </v-card>
  </v-container>

  <v-container fluid class="bg-grey-lighten-3 fill-height align-start pa-8 justify-center" style="overflow-x: auto;">
    <div class="d-flex" style="gap: 16px; min-width: 1200px;">
      
      <v-sheet width="300" color="transparent">
        <div class="text-subtitle-2 text-uppercase text-grey-darken-1 mb-2 font-weight-bold pl-1">
          Novos ({{ totaisColuna.aberto }})
        </div>
        <v-card 
          v-for="item in colunasFiltradas.aberto" :key="item.id" 
          class="mb-3 cursor-pointer border-l-xl border-primary"
          :class="{ 'vencida-card': item.vencida }"
          @click="abrirAnalise(item)"
          elevation="1"
        >
          <v-card-text>
            <div v-if="item.vencida" class="vencida-badge mb-2">
              <v-icon icon="mdi-alert-octagon" size="small"></v-icon>
              CARTEIRINHA VENCIDA
            </div>
            <div class="text-caption text-grey">Protocolo: {{ item.protocolo }}</div>
            <div class="font-weight-bold text-body-1">{{ item.beneficiario.nome_completo }}</div>
            <v-chip v-if="item.origem === 'LEGADO'" size="x-small" color="purple" class="mt-2" variant="flat">
              Legado
            </v-chip>
            <div class="text-caption mt-1">
              <v-icon icon="mdi-calendar" size="x-small"></v-icon> {{ formatData(item.data_solicitacao) }}
            </div>
          </v-card-text>
        </v-card>
        <div class="d-flex justify-center mt-2" style="gap: 8px;" v-if="podeCarregarMais('aberto')">
          <v-btn size="small" variant="tonal" color="primary" :loading="loadingMais.aberto" @click="carregarMais('aberto')">Carregar mais</v-btn>
          <v-btn size="small" variant="text" color="primary" :loading="loadingTudo.aberto" @click="carregarTudo('aberto')">Carregar tudo</v-btn>
        </div>
      </v-sheet>

      <v-sheet width="300" color="transparent">
        <div class="text-subtitle-2 text-uppercase text-grey-darken-1 mb-2 font-weight-bold pl-1">
          Em Análise ({{ totaisColuna.analise }})
        </div>
        <v-card 
          v-for="item in colunasFiltradas.analise" :key="item.id" 
          class="mb-3 cursor-pointer border-l-xl border-orange"
          :class="{ 'vencida-card': item.vencida }"
          @click="abrirAnalise(item)"
          elevation="1"
        >
          <v-card-text>
            <div v-if="item.vencida" class="vencida-badge mb-2">
              <v-icon icon="mdi-alert-octagon" size="small"></v-icon>
              CARTEIRINHA VENCIDA
            </div>
            <div class="text-caption text-grey">Protocolo: {{ item.protocolo }}</div>
            <div class="font-weight-bold">{{ item.beneficiario.nome_completo }}</div>
            <v-chip v-if="item.origem === 'LEGADO'" size="x-small" color="purple" class="mt-2" variant="flat">
              Legado
            </v-chip>
          </v-card-text>
        </v-card>
        <div class="d-flex justify-center mt-2" style="gap: 8px;" v-if="podeCarregarMais('analise')">
          <v-btn size="small" variant="tonal" color="primary" :loading="loadingMais.analise" @click="carregarMais('analise')">Carregar mais</v-btn>
          <v-btn size="small" variant="text" color="primary" :loading="loadingTudo.analise" @click="carregarTudo('analise')">Carregar tudo</v-btn>
        </div>
      </v-sheet>

      <v-sheet width="300" color="transparent">
        <div class="text-subtitle-2 text-uppercase text-grey-darken-1 mb-2 font-weight-bold pl-1">
          Pendência ({{ totaisColuna.pendente }})
        </div>
        <v-card 
          v-for="item in colunasFiltradas.pendente" :key="item.id" 
          class="mb-3 cursor-pointer border-l-xl border-error"
          :class="{ 'vencida-card': item.vencida }"
          @click="abrirAnalise(item)"
          elevation="1"
        >
          <v-card-text>
            <div v-if="item.vencida" class="vencida-badge mb-2">
              <v-icon icon="mdi-alert-octagon" size="small"></v-icon>
              CARTEIRINHA VENCIDA
            </div>
            <div class="text-caption text-grey">Protocolo: {{ item.protocolo }}</div>
            <div class="font-weight-bold">{{ item.beneficiario.nome_completo }}</div>
            <v-chip v-if="item.origem === 'LEGADO'" size="x-small" color="purple" class="mt-2 mr-2" variant="flat">
              Legado
            </v-chip>
            <v-chip size="x-small" color="error" class="mt-2">Aguardando Cidadão</v-chip>
          </v-card-text>
        </v-card>
        <div class="d-flex justify-center mt-2" style="gap: 8px;" v-if="podeCarregarMais('pendente')">
          <v-btn size="small" variant="tonal" color="primary" :loading="loadingMais.pendente" @click="carregarMais('pendente')">Carregar mais</v-btn>
          <v-btn size="small" variant="text" color="primary" :loading="loadingTudo.pendente" @click="carregarTudo('pendente')">Carregar tudo</v-btn>
        </div>
      </v-sheet>

      <v-sheet width="300" color="transparent">
        <div class="text-subtitle-2 text-uppercase text-grey-darken-1 mb-2 font-weight-bold pl-1">
          Concluídos ({{ totaisColuna.aprovado }})
        </div>
        <v-card 
          v-for="item in colunasFiltradas.aprovado" :key="item.id" 
          class="mb-3 cursor-pointer border-l-xl border-success"
          :class="{ 'vencida-card': item.vencida }"
          @click="abrirAnalise(item)"
          elevation="1"
        >
          <v-card-text>
            <div v-if="item.vencida" class="vencida-badge mb-2">
              <v-icon icon="mdi-alert-octagon" size="small"></v-icon>
              CARTEIRINHA VENCIDA
            </div>
            <div class="text-caption text-grey">Protocolo: {{ item.protocolo }}</div>
            <div class="font-weight-bold">{{ item.beneficiario.nome_completo }}</div>
            <v-chip v-if="item.origem === 'LEGADO'" size="x-small" color="purple" class="mt-2 mr-2" variant="flat">
              Legado
            </v-chip>
            <v-chip v-if="item.vencida" size="x-small" color="deep-orange" class="mt-2" variant="flat">
              Vencida
            </v-chip>
            <div class="d-flex gap-2 mt-2">
                <v-btn 
                    size="x-small" 
                    variant="tonal" 
                    color="primary" 
                    prepend-icon="mdi-printer"
                    :href="`${pdfBaseUrl}/api/carteira/pdf/${item.protocolo}/`"
                    target="_blank"
                    @click.stop
                >
                    PDF
                </v-btn>
            </div>
          </v-card-text>
        </v-card>
        <div class="d-flex justify-center mt-2" style="gap: 8px;" v-if="podeCarregarMais('aprovado')">
          <v-btn size="small" variant="tonal" color="primary" :loading="loadingMais.aprovado" @click="carregarMais('aprovado')">Carregar mais</v-btn>
          <v-btn size="small" variant="text" color="primary" :loading="loadingTudo.aprovado" @click="carregarTudo('aprovado')">Carregar tudo</v-btn>
        </div>
      </v-sheet>

      <v-sheet width="300" color="transparent">
        <div class="text-subtitle-2 text-uppercase text-grey-darken-1 mb-2 font-weight-bold pl-1">
          Arquivados ({{ totaisColuna.indeferido }})
        </div>
        <v-card 
          v-for="item in colunasFiltradas.indeferido" :key="item.id" 
          class="mb-3 cursor-pointer border-l-xl"
          style="border-left-color: #616161 !important;"
          :class="{ 'vencida-card': item.vencida }"
          @click="abrirAnalise(item)"
          elevation="1"
        >
          <v-card-text>
            <div v-if="item.vencida" class="vencida-badge mb-2">
              <v-icon icon="mdi-alert-octagon" size="small"></v-icon>
              CARTEIRINHA VENCIDA
            </div>
            <div class="text-caption text-grey">Protocolo: {{ item.protocolo }}</div>
            <div class="font-weight-bold text-grey-darken-2" :class="item.status === 'INDEFERIDO' ? 'text-decoration-line-through' : ''">
                {{ item.beneficiario.nome_completo }}
            </div>
            
            <v-chip v-if="item.vencida" size="x-small" color="deep-orange" class="mt-2 mr-2" variant="flat">
                Vencida
            </v-chip>
            <v-chip size="x-small" color="grey-darken-2" class="mt-2">
                Indeferido
            </v-chip>

          </v-card-text>
        </v-card>
        <div class="d-flex justify-center mt-2" style="gap: 8px;" v-if="podeCarregarMais('indeferido')">
          <v-btn size="small" variant="tonal" color="primary" :loading="loadingMais.indeferido" @click="carregarMais('indeferido')">Carregar mais</v-btn>
          <v-btn size="small" variant="text" color="primary" :loading="loadingTudo.indeferido" @click="carregarTudo('indeferido')">Carregar tudo</v-btn>
        </div>
      </v-sheet>
      <v-sheet width="300" color="transparent">
        <div class="text-subtitle-2 text-uppercase text-grey-darken-1 mb-2 font-weight-bold pl-1">
          Legado ({{ totaisColuna.legado }})
        </div>
        <v-card
          v-for="item in colunasFiltradas.legado" :key="item.id"
          class="mb-3 cursor-pointer border-l-xl"
          style="border-left-color: #9C27B0 !important;"
          :class="{ 'vencida-card': item.vencida }"
          @click="abrirAnalise(item)"
          elevation="1"
        >
          <v-card-text>
            <div v-if="item.vencida" class="vencida-badge mb-2">
              <v-icon icon="mdi-alert-octagon" size="small"></v-icon>
              CARTEIRINHA VENCIDA
            </div>
            <div class="text-caption text-grey">Protocolo: {{ item.protocolo }}</div>
            <div class="font-weight-bold">{{ item.beneficiario.nome_completo }}</div>
            <v-chip size="x-small" color="purple" class="mt-2 mr-2" variant="flat">
              Sistema Antigo
            </v-chip>
            <v-chip size="x-small" color="grey-darken-2" class="mt-2" variant="tonal">
              Aguardando Atualização
            </v-chip>
          </v-card-text>
        </v-card>
        <div class="d-flex justify-center mt-2" style="gap: 8px;" v-if="podeCarregarMais('legado')">
          <v-btn size="small" variant="tonal" color="primary" :loading="loadingMais.legado" @click="carregarMais('legado')">Carregar mais</v-btn>
          <v-btn size="small" variant="text" color="primary" :loading="loadingTudo.legado" @click="carregarTudo('legado')">Carregar tudo</v-btn>
        </div>
      </v-sheet>

    </div>
  </v-container>

  <v-dialog v-model="dialogAnalise" fullscreen transition="dialog-bottom-transition">
    <v-card v-if="selecionado">
        <v-toolbar color="primary" density="comfortable">
            <v-btn icon="mdi-close" @click="dialogAnalise = false"></v-btn>
            <v-toolbar-title>Análise: {{ selecionado.beneficiario.nome_completo }}</v-toolbar-title>
        </v-toolbar>

        <v-container>
            <v-alert
              v-if="selecionado.vencida"
              type="warning"
              variant="tonal"
              border="start"
              color="deep-orange-darken-2"
              icon="mdi-alert-octagon"
              class="mb-4"
            >
              <strong>CARTEIRINHA VENCIDA</strong><br>
              Esta solicitação exige ação de renovação.
            </v-alert>
            <v-row>
                <v-col cols="12" md="6">
                    <v-card class="mb-4">
                        <v-card-title class="bg-grey-lighten-4 py-2 text-subtitle-1 font-weight-bold">
                            Dados Cadastrais
                        </v-card-title>
                        <v-card-text class="pt-4">
                            <v-row dense>
                                <v-col cols="12" md="4">
                                    <div class="text-caption text-grey-darken-1">CPF</div>
                                    <div class="font-weight-medium">{{ selecionado.beneficiario.cpf }}</div>
                                </v-col>
                                <v-col cols="12" md="4">
                                    <div class="text-caption text-grey-darken-1">CID</div>
                                    <div class="font-weight-medium">{{ selecionado.beneficiario.cid }}</div>
                                </v-col>
                                <v-col cols="12" md="4">
                                    <div class="text-caption text-grey-darken-1">Nascimento</div>
                                    <div class="font-weight-medium">{{ formatData(selecionado.beneficiario.data_nascimento) }}</div>
                                </v-col>
                                
                                <v-col cols="12" class="mt-2">
                                    <v-divider class="mb-2"></v-divider>
                                    <div class="text-caption text-grey-darken-1 mb-1">Responsáveis</div>
                                    
                                    <div v-if="selecionado.beneficiario.responsaveis && selecionado.beneficiario.responsaveis.length">
                                        <div 
                                            v-for="(resp, i) in selecionado.beneficiario.responsaveis" 
                                            :key="i"
                                            class="mb-1 text-body-2"
                                        >
                                            <v-icon icon="mdi-account-circle" size="small" class="mr-1 text-grey"></v-icon>
                                            <strong>{{ resp.nome }}</strong> 
                                            <span class="text-caption text-grey-darken-2">
                                                ({{ resp.perfil }}) • {{ resp.telefone }}
                                            </span>
                                        </div>
                                    </div>
                                    <div v-else class="text-caption text-error">
                                        Nenhum responsável identificado.
                                    </div>
                                </v-col>
                            </v-row>
                        </v-card-text>
                    </v-card>

                    <v-card class="mb-3">
                        <v-card-title class="bg-grey-lighten-4 py-2 text-subtitle-1 font-weight-bold">
                            Resultado da IA por Documento
                        </v-card-title>
                        <v-card-text class="pt-3">
                            <div v-if="iaStatusDocumentosLista.length" class="d-flex flex-column" style="gap: 10px;">
                                <div
                                    v-for="item in iaStatusDocumentosLista"
                                    :key="item.key"
                                    class="d-flex align-center justify-space-between flex-wrap"
                                    style="gap: 8px;"
                                >
                                    <div>
                                        <div class="text-body-2 font-weight-bold">{{ item.label }}</div>
                                        <div class="text-caption text-grey-darken-1">{{ item.motivo }}</div>
                                    </div>
                                    <v-chip
                                        size="small"
                                        :color="item.color"
                                        variant="flat"
                                    >
                                        {{ item.status }}
                                    </v-chip>
                                </div>
                            </div>
                            <v-alert v-else type="info" variant="tonal" density="compact">
                                Triagem IA ainda não disponível para esta solicitação.
                            </v-alert>
                        </v-card-text>
                    </v-card>

                    <v-card class="mb-3 border" :color="getColorCard(selecionado.beneficiario.status_foto)">
                        <v-card-title class="bg-grey-lighten-4 py-2 text-subtitle-1 font-weight-bold">
                            Foto do Perfil (Carteirinha)
                        </v-card-title>
                        <v-card-text class="d-flex flex-no-wrap justify-space-between pt-4">
                            <div>
                                <v-card-subtitle>A foto deve ser de rosto, fundo claro e sem acessórios.</v-card-subtitle>
                                
                                <v-card-actions>
                                    <v-btn-group variant="outlined" divided>
                                        <v-btn size="small" color="success" 
                                            :variant="selecionado.beneficiario.status_foto === 'APROVADO' ? 'flat' : 'outlined'"
                                            @click="selecionado.beneficiario.status_foto = 'APROVADO'">
                                            Aprovar
                                        </v-btn>
                                        <v-btn size="small" color="error" 
                                            :variant="selecionado.beneficiario.status_foto === 'REJEITADO' ? 'flat' : 'outlined'"
                                            @click="selecionado.beneficiario.status_foto = 'REJEITADO'">
                                            Rejeitar
                                        </v-btn>
                                    </v-btn-group>
                                </v-card-actions>

                                <v-expand-transition>
                                    <div v-if="selecionado.beneficiario.status_foto === 'REJEITADO'" class="px-4 pb-2">
                                        <v-textarea 
                                            v-model="selecionado.beneficiario.motivo_rejeicao_foto" 
                                            label="Motivo da Rejeição da Foto" 
                                            rows="1" auto-grow variant="underlined" color="error"
                                        ></v-textarea>
                                    </div>
                                </v-expand-transition>
                            </div>

                            <v-avatar class="ma-3" size="100" rounded="lg">
                                <v-img 
                                    :src="selecionado.beneficiario.foto" 
                                    cover 
                                    class="bg-grey-lighten-2"
                                    @click="abrirImagem(selecionado.beneficiario.foto)" 
                                    style="cursor: pointer"
                                ></v-img>
                            </v-avatar>
                        </v-card-text>
                    </v-card>

                    <h3 class="text-h6 mb-2">Documentação</h3>
                    <v-expansion-panels variant="accordion">
                        <v-expansion-panel v-for="doc in selecionado.anexos" :key="doc.id">
                            <v-expansion-panel-title>
                                <v-icon 
                                    :color="doc.status === 'APROVADO' ? 'success' : (doc.status === 'REJEITADO' ? 'error' : 'grey')"
                                    class="mr-2"
                                >
                                    {{ doc.status === 'APROVADO' ? 'mdi-check-circle' : (doc.status === 'REJEITADO' ? 'mdi-alert-circle' : 'mdi-file') }}
                                </v-icon>
                                {{ doc.descricao }} ({{ doc.tipo }})
                            </v-expansion-panel-title>
                            <v-expansion-panel-text>
                                <div class="d-flex justify-space-between align-start">
                                    <v-btn :href="doc.arquivo" target="_blank" prepend-icon="mdi-eye" size="small" color="primary">Abrir Arquivo</v-btn>
                                    
                                    <div class="d-flex flex-column" style="width: 300px;">
                                        <v-select 
                                            label="Status do Documento" 
                                            v-model="doc.status" 
                                            :items="['PENDENTE', 'APROVADO', 'REJEITADO']"
                                            density="compact"
                                            variant="outlined"
                                            @update:model-value="marcarAlteracao"
                                        ></v-select>
                                        
                                        <v-text-field 
                                            v-if="doc.status === 'REJEITADO'"
                                            label="Motivo da Rejeição" 
                                            v-model="doc.motivo_rejeicao"
                                            variant="outlined"
                                            density="compact"
                                            placeholder="Ex: Foto ilegível"
                                            @input="marcarAlteracao"
                                        ></v-text-field>
                                    </div>
                                </div>
                            </v-expansion-panel-text>
                        </v-expansion-panel>
                    </v-expansion-panels>
                </v-col>

                <v-col cols="12" md="6">
                    <v-card v-if="selecionado.vencida" class="pa-4 mb-4 contato-vencida-card">
                        <h3 class="text-subtitle-1 font-weight-bold mb-2">
                            <v-icon icon="mdi-forum-outline" class="mr-1"></v-icon>
                            Comunicação - Renovação CIPTEA
                        </h3>
                        <v-alert
                            v-if="!selecionado.vencida"
                            type="info"
                            variant="tonal"
                            density="compact"
                            class="mb-3"
                        >
                            Esta solicitação ainda não está vencida. Os templates já ficam visíveis para preparo da comunicação.
                        </v-alert>
                        <div class="text-caption text-grey-darken-1 mb-3">
                            Responsável para contato: <strong>{{ contatoResponsavelNome }}</strong>
                        </div>
                        <v-select
                            v-model="templateComunicacao"
                            :items="opcoesTemplateComunicacao"
                            item-title="label"
                            item-value="value"
                            density="compact"
                            variant="outlined"
                            label="Template de mensagem"
                            hide-details
                            class="mb-3"
                            @update:model-value="atualizarMensagemComunicacao"
                        ></v-select>
                        <div class="text-caption font-weight-bold mb-1">
                            Texto do template selecionado
                        </div>
                        <div class="template-preview-box mb-3">
                            {{ montarMensagemPorTemplate(templateComunicacao) }}
                        </div>
                        <v-textarea
                            v-model="mensagemComunicacao"
                            label="Prévia da mensagem (editável)"
                            variant="outlined"
                            rows="4"
                            auto-grow
                            class="mb-3"
                        ></v-textarea>
                        <div class="d-flex flex-wrap" style="gap: 8px;">
                            <v-btn size="small" color="primary" variant="tonal" prepend-icon="mdi-email-outline" :disabled="!contatoEmail" @click="copiarEmailContato">Copiar e-mail</v-btn>
                            <v-btn size="small" color="primary" variant="tonal" prepend-icon="mdi-phone-outline" :disabled="!contatoTelefone" @click="copiarTelefoneContato">Copiar telefone</v-btn>
                            <v-btn size="small" color="primary" variant="tonal" prepend-icon="mdi-message-text-outline" @click="copiarMensagemContato">Copiar mensagem</v-btn>
                            <v-btn size="small" color="grey-darken-2" variant="text" prepend-icon="mdi-restore" @click="restaurarMensagemTemplate">Restaurar template</v-btn>
                            <v-btn size="small" color="success" variant="flat" prepend-icon="mdi-whatsapp" :disabled="!contatoTelefoneLimpo" @click="abrirWhatsappContato">Abrir WhatsApp Web</v-btn>
                        </div>
                        <div class="text-caption text-grey-darken-1 mt-3">
                            Contato atual: {{ contatoTelefone || 'Telefone não informado' }} • {{ contatoEmail || 'E-mail não informado' }}
                        </div>
                    </v-card>
                    <v-card class="pa-4 bg-grey-lighten-4">
                        <h3 class="text-subtitle-2 font-weight-bold mb-2 text-grey-darken-2">
                            <v-icon icon="mdi-history" size="small" class="mr-1"></v-icon>
                            Histórico de Interações
                        </h3>

                        <v-timeline density="compact" side="end" truncate-line="both" align="start">
                            <v-timeline-item
                                v-for="(evento, i) in selecionado.historico"
                                :key="i"
                                :dot-color="getEventColor(evento.tipo_evento)"
                                size="x-small"
                                width="100%"
                            >
                                <div class="d-flex flex-column">
                                    <div class="text-caption font-weight-bold text-grey-darken-1">
                                        {{ new Date(evento.data).toLocaleDateString('pt-BR') }} {{ new Date(evento.data).toLocaleTimeString('pt-BR', {hour: '2-digit', minute:'2-digit'}) }}
                                    </div>
                                    <div class="font-weight-bold text-caption">{{ evento.titulo }}</div>
                                    <div v-if="evento.mensagem" class="text-caption text-grey-darken-2 bg-white pa-1 rounded mt-1 border">
                                        {{ evento.mensagem }}
                                    </div>
                                    <div class="text-caption text-grey-lighten-1 mt-1 font-italic" style="font-size: 0.6rem;">
                                        Por: {{ evento.autor }}
                                    </div>
                                </div>
                            </v-timeline-item>
                        </v-timeline>
                        
                        <div v-if="!selecionado.historico || selecionado.historico.length === 0" class="text-caption text-center text-grey">
                            Nenhum registro encontrado.
                        </div>
                    </v-card>
                    <v-card
                        v-if="selecionado?.validacao_ia?.resumo_divergencias?.length"
                        class="mt-4 pa-4"
                        color="amber-lighten-5"
                    >
                        <h3 class="text-subtitle-2 font-weight-bold mb-2 text-grey-darken-3">
                            Log de divergências da IA
                        </h3>
                        <div
                            v-for="d in selecionado.validacao_ia.resumo_divergencias"
                            :key="`${d.documento}-${d.codigo}`"
                            class="mb-2"
                        >
                            <div class="font-weight-bold">{{ d.titulo }} - {{ d.codigo }}</div>
                            <div class="text-body-2">{{ d.motivo }}</div>
                            <div
                                v-if="d?.detalhes && (d.detalhes.score || d.detalhes.score_nome || d.detalhes.data_recente_ok === false || d.detalhes.cpf_ok === false)"
                                class="text-caption text-grey-darken-2"
                            >
                                <span v-if="d.detalhes.score">score={{ d.detalhes.score }}</span>
                                <span v-if="d.detalhes.score_nome" class="ml-2">score_nome={{ d.detalhes.score_nome }}</span>
                                <span v-if="d.detalhes.data_recente_ok === false" class="ml-2">data_recente_ok=false</span>
                                <span v-if="d.detalhes.cpf_ok === false" class="ml-2">cpf_ok=false</span>
                            </div>
                        </div>
                    </v-card>

                    <v-card v-if="selecionado.status !== 'APROVADO' && selecionado.status !== 'IMPRESSO'" class="mt-4 pa-4 bg-grey-lighten-4">

                        <h3 class="text-subtitle-1 mb-2">Parecer Final</h3>
                        
                        <v-textarea 
                            label="Mensagem para o Cidadão" 
                            v-model="mensagemParecer"
                            rows="3"
                            variant="outlined"
                            bg-color="white"
                        ></v-textarea>

                        <v-alert
                            v-if="selecionado.status === 'LEGADO' || selecionado.origem === 'LEGADO'"
                            type="info"
                            variant="tonal"
                            class="mb-3"
                            density="compact"
                        >
                            Cadastro legado: para emissão digital, inicie uma nova solicitação de renovação.
                        </v-alert>

                        <div class="d-flex flex-row mt-2" style="gap: 1rem">
                            <v-btn
                                v-if="selecionado.status === 'LEGADO' || selecionado.origem === 'LEGADO'"
                                color="deep-orange-darken-1"
                                variant="flat"
                                :loading="loadingRenovacao"
                                @click="iniciarRenovacao"
                            >
                                <v-icon start>mdi-refresh-circle</v-icon> Iniciar renovação digital
                            </v-btn>
                            <template v-if="selecionado.status !== 'INDEFERIDO' && selecionado.status !== 'LEGADO' && selecionado.origem !== 'LEGADO'">
                                <v-btn color="success" @click="prepararFinalizacao('APROVAR')">
                                    <v-icon start>mdi-check-all</v-icon> Aprovar Tudo
                                </v-btn>
                                <v-btn color="warning" @click="prepararFinalizacao('PENDENCIA')">
                                    <v-icon start>mdi-alert-circle-outline</v-icon> Solicitar Correção
                                </v-btn>
                                <v-btn color="grey-darken-3" variant="flat" @click="prepararFinalizacao('INDEFERIR')">
                                    <v-icon start>mdi-close-octagon</v-icon> Indeferir Pedido
                                </v-btn>
                            </template>

                            <template v-else-if="selecionado.status === 'INDEFERIDO'">
                                <v-alert type="error" variant="tonal" class="mb-2 text-caption">
                                    Este processo está arquivado como <strong>Indeferido</strong>.
                                </v-alert>
                                <v-btn color="primary" variant="flat" @click="prepararFinalizacao('REATIVAR')">
                                    <v-icon start>mdi-restore</v-icon> Reativar Processo
                                </v-btn>
                            </template>
                            <template v-else>
                                <v-alert type="info" variant="tonal" class="mb-2 text-caption">
                                    Este cadastro legado não deve ser finalizado diretamente. Use a renovação digital.
                                </v-alert>
                            </template>
                        </div>
                        <v-alert
                            v-if="ultimaRenovacaoIniciada"
                            type="success"
                            variant="tonal"
                            density="compact"
                            class="mt-3 text-caption"
                        >
                            Renovação iniciada: <strong>{{ ultimaRenovacaoIniciada }}</strong>
                        </v-alert>
                    </v-card>

                    <v-alert v-else type="success" variant="tonal" class="mt-4" icon="mdi-check-decagram">
                        <strong>Processo Finalizado</strong><br>
                        Esta solicitação já foi aprovada e a carteirinha gerada.
                        <div class="mt-3">
                            <v-btn
                                color="deep-orange-darken-1"
                                variant="flat"
                                prepend-icon="mdi-refresh-circle"
                                :loading="loadingRenovacao"
                                :disabled="!podeIniciarRenovacao"
                                @click="iniciarRenovacao"
                            >
                                Iniciar renovação
                            </v-btn>
                        </div>
                    </v-alert>
                </v-col>
            </v-row>
        </v-container>
    </v-card>
  </v-dialog>

  <v-dialog v-model="dialogConfirmacao" max-width="450">
    <v-card class="rounded-lg">
        <v-card-title class="d-flex align-center py-4" :class="confirmacao.cor === 'success' ? 'bg-success text-white' : 'bg-warning text-white'">
            <v-icon :icon="confirmacao.icone" class="mr-3" size="small"></v-icon>
            {{ confirmacao.titulo }}
        </v-card-title>
        
        <v-card-text class="pt-6 pb-4 text-body-1">
            <div v-html="confirmacao.mensagem"></div>
            
            <v-alert v-if="confirmacao.docsAutoAprovar > 0" type="info" variant="tonal" density="compact" class="mt-4 text-caption">
                <v-icon start size="small">mdi-information</v-icon>
                {{ confirmacao.docsAutoAprovar }} documento(s) pendente(s) será(ão) marcado(s) como <strong>APROVADO(S)</strong> automaticamente.
            </v-alert>
        </v-card-text>

        <v-divider></v-divider>

        <v-card-actions class="pa-4">
            <v-btn variant="text" color="grey-darken-1" @click="dialogConfirmacao = false">Cancelar</v-btn>
            <v-spacer></v-spacer>
            <v-btn 
                :color="confirmacao.cor" 
                variant="elevated" 
                :loading="loadingConfirmacao"
                @click="executarFinalizacao"
            >
                Confirmar
            </v-btn>
        </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, onMounted, reactive, computed } from 'vue';
import api from '@/services/api';
import { useAuthStore } from '@/stores/auth';
import { useToastStore } from '@/stores/toast';

const pdfBaseUrl = import.meta.env.VITE_PDF_BASE_URL || window.location.origin;

const colunas = reactive({
    aberto: [],
    analise: [],
    pendente: [],
    aprovado: [],
    indeferido: [],
    legado: []
});
const totaisColuna = reactive({
    aberto: 0,
    analise: 0,
    pendente: 0,
    aprovado: 0,
    indeferido: 0,
    legado: 0
});
const paginacaoColuna = reactive({
    aberto: { page: 1, pages: 1 },
    analise: { page: 1, pages: 1 },
    pendente: { page: 1, pages: 1 },
    aprovado: { page: 1, pages: 1 },
    indeferido: { page: 1, pages: 1 },
    legado: { page: 1, pages: 1 }
});
const loadingMais = reactive({
    aberto: false,
    analise: false,
    pendente: false,
    aprovado: false,
    indeferido: false,
    legado: false
});
const loadingTudo = reactive({
    aberto: false,
    analise: false,
    pendente: false,
    aprovado: false,
    indeferido: false,
    legado: false
});
const PAGE_SIZE_KANBAN = 100;

const getColorCard = (status) => {
    if (status === 'APROVADO') return 'green-lighten-5';
    if (status === 'REJEITADO') return 'red-lighten-5';
    return 'white';
};

const authStore = useAuthStore();
const toast = useToastStore();
const termoBusca = ref('');
const filtroOrigem = ref('TODOS');
const somenteVencidas = ref(false);
const dialogAnalise = ref(false);
const selecionado = ref(null);
const mensagemParecer = ref('');
const alteracoesPendentes = ref(false);
const loadingDetalhe = ref(false);
const templateComunicacao = ref('PADRAO_CURTO');
const mensagemComunicacao = ref('');
const loadingRenovacao = ref(false);
const ultimaRenovacaoIniciada = ref('');
const loadingMetricasCadastro = ref(false);
const metricasCadastro = reactive({
    transacional_total: 0,
    fallback_total: 0,
    total_cadastros_medidos: 0,
    participacao_transacional: 0,
});
const opcoesTemplateComunicacao = [
    { label: 'Padrão curto', value: 'PADRAO_CURTO' },
    { label: 'Padrão completo', value: 'PADRAO_COMPLETO' },
    { label: 'Pendência de documentação', value: 'PENDENCIA_DOC' }
];
const opcoesOrigem = [
    { label: 'Todas', value: 'TODOS' },
    { label: 'Somente Legado', value: 'LEGADO' },
    { label: 'Somente Novo', value: 'SISTEMA_NOVO' }
];

const dialogConfirmacao = ref(false);
const loadingConfirmacao = ref(false);
const acaoPendente = ref(''); // Guarda qual botão foi clicado ('APROVAR' ou 'PENDENCIA')
const confirmacao = ref({
    titulo: '',
    mensagem: '',
    cor: 'primary',
    icone: '',
    docsAutoAprovar: 0
});

const limparBusca = () => {
    termoBusca.value = ''; // Garante que a variável zere
    carregarSolicitacoes(); // Recarrega o Kanban padrão (sem o filtro ?search=)
}

const totalLegado = computed(() => Object.values(colunas).reduce((acc, lista) => acc + lista.filter(item => item.origem === 'LEGADO').length, 0));
const totalSistemaNovo = computed(() => Object.values(colunas).reduce((acc, lista) => acc + lista.filter(item => item.origem !== 'LEGADO').length, 0));
const totalSolicitacoes = computed(() => Object.values(colunas).reduce((acc, lista) => acc + lista.length, 0));
const totalVencidasVisiveis = computed(() => Object.values(colunasFiltradas.value).reduce((acc, lista) => acc + lista.filter(item => item.vencida).length, 0));
const participacaoTransacionalPercentual = computed(() => (Number(metricasCadastro.participacao_transacional || 0) * 100));
const podeIniciarRenovacao = computed(() => {
    if (!selecionado.value) return false;
    return Boolean(selecionado.value.vencida || selecionado.value.origem === 'LEGADO');
});
const taxaFallbackPercentual = computed(() => {
    if (!metricasCadastro.total_cadastros_medidos) return 0;
    return (Number(metricasCadastro.fallback_total || 0) / Number(metricasCadastro.total_cadastros_medidos)) * 100;
});
const corCardRollout = computed(() => {
    if (taxaFallbackPercentual.value > 20) return 'red-lighten-5';
    if (taxaFallbackPercentual.value > 10) return 'amber-lighten-5';
    return 'indigo-lighten-5';
});
const statusRollout = computed(() => {
    if (metricasCadastro.total_cadastros_medidos === 0) {
        return {
            type: 'info',
            icon: 'mdi-information-outline',
            texto: 'Ainda não há cadastros suficientes para esta leitura.'
        };
    }
    if (taxaFallbackPercentual.value > 20) {
        return {
            type: 'error',
            icon: 'mdi-alert-circle',
            texto: `Plano B em ${taxaFallbackPercentual.value.toFixed(1)}% (acima de 20%). Atenção: o sistema está usando pouco o fluxo principal.`
        };
    }
    if (taxaFallbackPercentual.value > 10) {
        return {
            type: 'warning',
            icon: 'mdi-alert',
            texto: `Plano B em ${taxaFallbackPercentual.value.toFixed(1)}% (acima de 10%). Acompanhe para garantir estabilidade.`
        };
    }
    return {
        type: 'success',
        icon: 'mdi-check-circle',
        texto: `Plano B em ${taxaFallbackPercentual.value.toFixed(1)}%. Funcionamento dentro do esperado.`
    };
});

const aplicarFiltroOrigem = (origem) => {
    if (filtroOrigem.value === origem) return;
    filtroOrigem.value = origem;
    carregarSolicitacoes();
};

const alternarSomenteVencidas = () => {
    somenteVencidas.value = !somenteVencidas.value;
    carregarSolicitacoes();
}

const contatoPrimario = computed(() => {
    if (!selecionado.value?.beneficiario) return null;
    const responsavel = selecionado.value.beneficiario.responsaveis?.[0] || null;
    if (responsavel) return { ...responsavel, origem: 'responsavel' };
    return { ...selecionado.value.beneficiario, origem: 'beneficiario' };
});
const contatoResponsavelNome = computed(() => contatoPrimario.value?.nome || contatoPrimario.value?.nome_completo || 'Não identificado');
const contatoTelefone = computed(() => contatoPrimario.value?.telefone || contatoPrimario.value?.telefone2 || '');
const contatoEmail = computed(() => contatoPrimario.value?.email || '');
const iaStatusDocumentos = computed(
    () => selecionado.value?.validacao_ia?.status_documentos || null
);
const iaStatusDocumentosLista = computed(() => {
    const sd = iaStatusDocumentos.value;
    if (!sd || typeof sd !== 'object') return [];
    const map = [
        { key: 'laudo', label: 'Laudo médico' },
        { key: 'identidade', label: 'Documento de identidade (TEA)' },
        { key: 'endereco', label: 'Comprovante de endereço' },
        { key: 'responsavel', label: 'Documento do responsável' },
    ];
    const toColor = (status) => {
        const st = (status || '').toUpperCase();
        if (st === 'VALIDADO') return 'success';
        if (st === 'INVALIDO') return 'error';
        return 'grey';
    };
    return map.map(({ key, label }) => {
        const row = sd[key] || {};
        const status = (row.status || 'PENDENTE').toUpperCase();
        return {
            key,
            label,
            status,
            motivo: row.motivo || (status === 'VALIDADO' ? 'Documento validado pela IA.' : 'Sem resultado consolidado.'),
            color: toColor(status),
        };
    });
});
const contatoTelefoneLimpo = computed(() => (contatoTelefone.value || '').replace(/\D/g, ''));
const numeroWhatsapp = computed(() => {
    const numero = contatoTelefoneLimpo.value;
    if (!numero) return '';
    return numero.startsWith('55') ? numero : `55${numero}`;
});

// 1. PREPARA O TERRENO (Valida e Abre Dialog)
const prepararFinalizacao = (acao) => {
    acaoPendente.value = acao;
    confirmacao.value.docsAutoAprovar = 0;

    // === CENÁRIO A: APROVAÇÃO ===
    if (acao === 'APROVAR') {
        // 1. Bloqueio Rígido: FOTO REJEITADA
        if (selecionado.value.beneficiario.status_foto === 'REJEITADO') {
            toast.warning("Bloqueado: A Foto do Perfil foi REJEITADA.");
            return;
        }

        // 2. Bloqueio Rígido: DOCUMENTOS REJEITADOS
        const temRejeicao = selecionado.value.anexos.some(doc => doc.status === 'REJEITADO');
        if (temRejeicao) {
            toast.warning("Bloqueado: Existem documentos REJEITADOS. Remova a rejeição ou solicite correção.");
            return;
        }

        // 3. Contagem de itens que serão aprovados automaticamente (Docs + Foto)
        let contagemPendentes = selecionado.value.anexos.filter(doc => doc.status === 'PENDENTE').length;
        if (selecionado.value.beneficiario.status_foto === 'PENDENTE') {
            contagemPendentes++;
        }
        
        confirmacao.value.docsAutoAprovar = contagemPendentes;

        // Configura o Dialog
        confirmacao.value.titulo = 'Confirmar Aprovação';
        confirmacao.value.cor = 'success';
        confirmacao.value.icone = 'mdi-check-all';
        confirmacao.value.mensagem = `
            Tem certeza que deseja <strong>APROVAR</strong> o cadastro de <br>
            <span class="text-primary font-weight-bold text-uppercase">${selecionado.value.beneficiario.nome_completo}</span>?
            <br><br>
            Isso irá gerar a Carteirinha Digital e liberar a impressão.
        `;
    }

    // === CENÁRIO B: PENDÊNCIA ===
    if (acao === 'PENDENCIA') {
        const temRejeicaoDocs = selecionado.value.anexos.some(doc => doc.status === 'REJEITADO');
        const temRejeicaoFoto = selecionado.value.beneficiario.status_foto === 'REJEITADO';
        
        // Alerta de precaução se não rejeitou nada
        if (!temRejeicaoDocs && !temRejeicaoFoto && !mensagemParecer.value) {
             toast.warning("Atenção: Você não rejeitou nenhum item e não escreveu parecer.");
             // Pode deixar passar ou bloquear, aqui deixamos passar mas avisamos
        }

        confirmacao.value.titulo = 'Solicitar Correção';
        confirmacao.value.cor = 'warning';
        confirmacao.value.icone = 'mdi-alert-circle';
        confirmacao.value.mensagem = `
            O protocolo será devolvido para o status <strong>PENDENTE</strong> (Correção) e o cidadão será notificado.
        `;
    }

    // === NOVO CENÁRIO: INDEFERIMENTO ===
    if (acao === 'INDEFERIR') {
        if (!mensagemParecer.value) {
            toast.warning("Para indeferir, é OBRIGATÓRIO escrever o motivo no Parecer Final.");
            return;
        }

        confirmacao.value.titulo = 'Indeferir Solicitação';
        confirmacao.value.cor = 'grey-darken-3';
        confirmacao.value.icone = 'mdi-gavel'; // Ícone de martelo/juiz
        confirmacao.value.mensagem = `
            Tem certeza que deseja <strong>INDEFERIR</strong> este pedido?<br><br>
            Isso significa que o cidadão <strong>NÃO atende aos requisitos legais</strong>.<br>
            O processo será arquivado e o cidadão notificado do encerramento.
        `;
    }

    // === NOVO CENÁRIO: REATIVAR ===
    if (acao === 'REATIVAR') {
        confirmacao.value.titulo = 'Reativar Processo';
        confirmacao.value.cor = 'primary';
        confirmacao.value.icone = 'mdi-restore';
        confirmacao.value.mensagem = `
            Deseja trazer este processo de volta para <strong>EM ANÁLISE</strong>?<br><br>
            Isso permitirá que você edite, aprove ou solicite novas correções ao cidadão.
        `;
        // Opcional: Obrigar a escrever justificativa
        if (!mensagemParecer.value) {
             toast.warning("Escreva no parecer o motivo da reativação (ex: Recurso aceito).");
             return;
        }
    }

    dialogConfirmacao.value = true;
}

// 2. EXECUTA A AÇÃO (Chamado pelo botão Confirmar do Dialog)
const executarFinalizacao = async () => {
    loadingConfirmacao.value = true;
    
    try {
        // Passo A: Auto-aprovar itens pendentes se a ação for APROVAR
        if (acaoPendente.value === 'APROVAR') {
            
            // 1. Auto-aprovar FOTO se estiver pendente
            if (selecionado.value.beneficiario.status_foto === 'PENDENTE') {
                await api.patch(`beneficiarios/${selecionado.value.beneficiario.id}/`, { 
                    status_foto: 'APROVADO',
                    motivo_rejeicao_foto: ''
                });
            }

            // 2. Auto-aprovar DOCUMENTOS se estiverem pendentes
            for (const doc of selecionado.value.anexos) {
                if (doc.status === 'PENDENTE') {
                    await api.patch(`documentos/${doc.id}/`, { status: 'APROVADO', motivo_rejeicao: '' });
                }
            }
        } 
        
        // Passo B: Garantir gravação de rejeições (redundância de segurança)
        // Isso vale tanto para PENDENCIA quanto para INDEFERIR (se houver rejeições manuais)
        if (acaoPendente.value === 'PENDENCIA' || acaoPendente.value === 'INDEFERIR') {
             // Salva foto se rejeitada
             if (selecionado.value.beneficiario.status_foto === 'REJEITADO') {
                 await api.patch(`beneficiarios/${selecionado.value.beneficiario.id}/`, {
                    status_foto: 'REJEITADO',
                    motivo_rejeicao_foto: selecionado.value.beneficiario.motivo_rejeicao_foto
                });
             }
             // Salva docs rejeitados (parecer global preenche motivo se o fiscal não digitou por documento)
             const parecerExec = (mensagemParecer.value || '').trim();
             for (const doc of selecionado.value.anexos) {
                if (doc.status === 'REJEITADO') {
                    let motivo = (doc.motivo_rejeicao && String(doc.motivo_rejeicao).trim()) || '';
                    if (!motivo && parecerExec) motivo = parecerExec.slice(0, 255);
                    await api.patch(`documentos/${doc.id}/`, { 
                        status: 'REJEITADO', 
                        motivo_rejeicao: motivo
                    });
                }
            }
        }

        // --- CORREÇÃO AQUI (Passo C) ---
        // Agora tratamos os 3 status possíveis
        let novoStatus = '';
        
        if (acaoPendente.value === 'APROVAR') novoStatus = 'APROVADO';
        else if (acaoPendente.value === 'PENDENCIA') novoStatus = 'PENDENTE';
        else if (acaoPendente.value === 'INDEFERIR') novoStatus = 'INDEFERIDO';
        else if (acaoPendente.value === 'REATIVAR') novoStatus = 'ANALISE';

        // Envia para o Backend
        await api.patch(`solicitacoes/${selecionado.value.id}/`, { 
            status: novoStatus,
            parecer_final: mensagemParecer.value 
        });

        // Feedback Visual (Toast)
        if (acaoPendente.value === 'APROVAR') toast.success("Cadastro Aprovado!");
        else if (acaoPendente.value === 'REATIVAR') toast.success("Processo reaberto com sucesso!");
        else if (acaoPendente.value === 'INDEFERIR') toast.error("Indeferido.");
        else toast.info("Devolvido para correção.");

        dialogConfirmacao.value = false;
        dialogAnalise.value = false;
        await carregarSolicitacoes(); // Atualiza Kanban

    } catch (e) {
        console.error(e);
        toast.error("Erro ao finalizar processo.");
    } finally {
        loadingConfirmacao.value = false;
    }
}

const carregarSolicitacoes = async () => {
    try {
        const baseParams = { page: 1, page_size: PAGE_SIZE_KANBAN };
        if (termoBusca.value) baseParams.search = termoBusca.value;
        if (filtroOrigem.value !== 'TODOS') baseParams.origem = filtroOrigem.value;
        if (somenteVencidas.value) baseParams.vencida = 1;

        const colunasKanban = ['aberto', 'analise', 'pendente', 'aprovado', 'indeferido', 'legado'];
        const respostas = await Promise.all(
            colunasKanban.map(coluna =>
                api.get('solicitacoes/kanban/', { params: { ...baseParams, coluna } })
            )
        );

        respostas.forEach(({ data }) => {
            colunas[data.coluna] = data.results.map(item => ({ ...item, vencida: item.vencida ?? isSolicitacaoVencida(item) }));
            totaisColuna[data.coluna] = data.total;
            paginacaoColuna[data.coluna] = { page: data.page, pages: data.pages };
        });

    } catch (e) {
        toast.error("Erro na comunicação com o servidor.");
    }
}

const carregarMetricasCadastro = async () => {
    loadingMetricasCadastro.value = true;
    try {
        const { data } = await api.get('solicitacoes/metricas-cadastro/');
        metricasCadastro.transacional_total = Number(data.transacional_total || 0);
        metricasCadastro.fallback_total = Number(data.fallback_total || 0);
        metricasCadastro.total_cadastros_medidos = Number(data.total_cadastros_medidos || 0);
        metricasCadastro.participacao_transacional = Number(data.participacao_transacional || 0);
    } catch (e) {
        toast.error("Erro ao carregar métrica de rollout.");
    } finally {
        loadingMetricasCadastro.value = false;
    }
};

const iniciarRenovacao = async () => {
    if (!selecionado.value?.protocolo || !selecionado.value?.beneficiario?.cpf || !selecionado.value?.beneficiario?.data_nascimento) {
        toast.warning("Dados insuficientes para iniciar renovação.");
        return;
    }
    loadingRenovacao.value = true;
    try {
        const { data } = await api.post('solicitacoes/iniciar-renovacao/', {
            protocolo: selecionado.value.protocolo,
            cpf: selecionado.value.beneficiario.cpf,
            data_nascimento: selecionado.value.beneficiario.data_nascimento,
        });
        ultimaRenovacaoIniciada.value = data?.protocolo || '';
        dialogAnalise.value = false;
        await carregarSolicitacoes();
        toast.success(`Renovação iniciada com protocolo ${data.protocolo}.`);
    } catch (e) {
        const mensagem = e?.response?.data?.erro || "Não foi possível iniciar a renovação.";
        toast.error(mensagem);
    } finally {
        loadingRenovacao.value = false;
    }
};

const podeCarregarMais = (coluna) => paginacaoColuna[coluna].page < paginacaoColuna[coluna].pages;

const carregarMais = async (coluna) => {
    if (!podeCarregarMais(coluna) || loadingMais[coluna]) return;
    loadingMais[coluna] = true;
    try {
        const params = {
            coluna,
            page: paginacaoColuna[coluna].page + 1,
            page_size: PAGE_SIZE_KANBAN
        };
        if (termoBusca.value) params.search = termoBusca.value;
        if (filtroOrigem.value !== 'TODOS') params.origem = filtroOrigem.value;
        if (somenteVencidas.value) params.vencida = 1;

        const { data } = await api.get('solicitacoes/kanban/', { params });
        colunas[coluna] = [...colunas[coluna], ...data.results.map(item => ({ ...item, vencida: item.vencida ?? isSolicitacaoVencida(item) }))];
        paginacaoColuna[coluna] = { page: data.page, pages: data.pages };
        totaisColuna[coluna] = data.total;
    } catch (e) {
        toast.error("Erro ao carregar mais itens.");
    } finally {
        loadingMais[coluna] = false;
    }
};

const carregarTudo = async (coluna) => {
    if (!podeCarregarMais(coluna) || loadingTudo[coluna]) return;
    loadingTudo[coluna] = true;
    try {
        while (podeCarregarMais(coluna)) {
            // eslint-disable-next-line no-await-in-loop
            await carregarMais(coluna);
        }
    } finally {
        loadingTudo[coluna] = false;
    }
};

const abrirAnalise = async (item) => {
    // 1. Se for novo, tenta mudar status antes de abrir
    if (item.status === 'ABERTO') {
        try {
            // Tenta atualizar no Backend
            await api.patch(`solicitacoes/${item.id}/`, { status: 'ANALISE' });
            
            // Se deu certo, atualiza o item local
            item.status = 'ANALISE';
            
            // AGORA VAI FUNCIONAR (pois criamos a função info na store)
            toast.info(`Iniciando análise: ${item.protocolo}`);
            
            // Atualiza o painel no fundo
            carregarSolicitacoes();

        } catch (error) {
            console.error("ERRO COMPLETO:", error);
            // ... tratamento de erro ...
            return; 
        }
    }

    // 2. Busca detalhes completos sob demanda
    loadingDetalhe.value = true;
    try {
        const { data } = await api.get(`solicitacoes/${item.id}/detalhe/`);
        selecionado.value = data;
        selecionado.value.vencida = data.vencida ?? isSolicitacaoVencida(data);
        ultimaRenovacaoIniciada.value = '';
        atualizarMensagemComunicacao();
        mensagemParecer.value = '';
        dialogAnalise.value = true;
    } catch (e) {
        toast.error("Erro ao carregar detalhes da solicitação.");
    } finally {
        loadingDetalhe.value = false;
    }
}

const formatData = (dataStr) => {
    if (!dataStr) return '';
    if (/^\d{4}-\d{2}-\d{2}$/.test(dataStr)) {
        const [ano, mes, dia] = dataStr.split('-');
        return `${dia}/${mes}/${ano}`;
    }
    const data = new Date(dataStr);
    if (Number.isNaN(data.getTime())) return dataStr;
    return data.toLocaleDateString('pt-BR');
}

const marcarAlteracao = () => {
    alteracoesPendentes.value = true;
}

// Salva alterações parciais (nos documentos)
const salvarAnaliseInterno = async () => {
    try {
        // 1. SALVA O STATUS DA FOTO (NO BENEFICIÁRIO)
        await api.patch(`beneficiarios/${selecionado.value.beneficiario.id}/`, {
            status_foto: selecionado.value.beneficiario.status_foto,
            motivo_rejeicao_foto: selecionado.value.beneficiario.motivo_rejeicao_foto
        });

        // 2. SALVA OS OUTROS DOCUMENTOS
        const parecer = (mensagemParecer.value || '').trim();
        for (const doc of selecionado.value.anexos) {
            let motivo = (doc.motivo_rejeicao && String(doc.motivo_rejeicao).trim()) || '';
            if (doc.status === 'REJEITADO' && !motivo && parecer) {
                motivo = parecer.slice(0, 255);
            }
            await api.patch(`documentos/${doc.id}/`, {
                status: doc.status,
                motivo_rejeicao: motivo,
            });
        }
        return true;
    } catch (e) {
        console.error(e);
        toast.error("Erro ao salvar avaliações.");
        return false;
    }
}

// Finaliza o processo (Aprova ou Rejeita)
const finalizar = async (acao) => {
    if(!selecionado.value) return;

    // --- REGRA 1: NÃO PODE APROVAR COM REJEIÇÃO ---
    if (acao === 'APROVAR') {
        // Verifica se tem algum documento marcado como REJEITADO
        const temRejeicao = selecionado.value.anexos.some(doc => doc.status === 'REJEITADO');
        
        if (temRejeicao) {
            toast.warning("Bloqueado: Existem documentos REJEITADOS. Utilize o botão 'Solicitar Correção'.");
            return; // Para tudo aqui
        }

        // Verifica se tem documentos PENDENTES (Opcional: obriga o fiscal a marcar todos como Aprovado?)
        // Se quiser ser rigoroso, descomente abaixo:
        /*
        const temPendente = selecionado.value.anexos.some(doc => doc.status === 'PENDENTE');
        if (temPendente) {
            toast.warning("Por favor, avalie todos os documentos (Aprovar ou Rejeitar) antes de finalizar.");
            return;
        }
        */

        // --- REGRA 2: CONFIRMAÇÃO DE SEGURANÇA ---
        if (!confirm(`Tem certeza que deseja APROVAR o cadastro de ${selecionado.value.beneficiario.nome_completo}?\n\nEsta ação irá gerar a Carteirinha Digital e liberar a impressão.`)) {
            return; // Usuário cancelou
        }
    }

    // Se a ação for "PENDENCIA", também podemos confirmar para evitar clique acidental
    if (acao === 'PENDENCIA') {
        const temRejeicao = selecionado.value.anexos.some(doc => doc.status === 'REJEITADO');
        if (!temRejeicao) {
             if(!confirm("Nenhum documento foi rejeitado. Deseja devolver com pendência mesmo assim (apenas com o parecer)?")) {
                 return;
             }
        }
    }

    // 1. Salva o estado dos documentos primeiro (usando a função interna)
    const salvouDocs = await salvarAnaliseInterno();
    if (!salvouDocs) return;

    // 2. Define o novo status geral
    let novoStatus = '';
    if (acao === 'APROVAR') novoStatus = 'APROVADO';
    if (acao === 'PENDENCIA') novoStatus = 'PENDENTE';

    try {
        // 3. Envia Status + Parecer para o Backend
        await api.patch(`solicitacoes/${selecionado.value.id}/`, { 
            status: novoStatus,
            parecer_final: mensagemParecer.value 
        });

        dialogAnalise.value = false;
        await carregarSolicitacoes(); // Recarrega o Kanban
        
        if (acao === 'APROVAR') toast.success("Cadastro Aprovado! Carteirinha Gerada.");
        else toast.info("Solicitação devolvida para correção.");

    } catch (e) {
        toast.error("Erro ao atualizar status final.");
    }
}

const colunasFiltradas = computed(() => {
    const termo = termoBusca.value.toLowerCase();
    const filtrarItem = (item) => {
        if (filtroOrigem.value === 'LEGADO' && item.origem !== 'LEGADO') return false;
        if (filtroOrigem.value === 'SISTEMA_NOVO' && item.origem === 'LEGADO') return false;
        if (somenteVencidas.value && !item.vencida) return false;
        if (!termo) return true;
        const nome = item.beneficiario?.nome_completo?.toLowerCase() || '';
        const protocolo = item.protocolo || '';
        const cpf = item.beneficiario?.cpf || '';
        const cpfLimpo = cpf.replace(/\D/g, '');
        return nome.includes(termo) || 
               protocolo.includes(termo) || 
               cpf.includes(termo) || 
               cpfLimpo.includes(termo);
    };

    return {
        aberto: colunas.aberto.filter(filtrarItem),
        analise: colunas.analise.filter(filtrarItem),
        pendente: colunas.pendente.filter(filtrarItem),
        aprovado: colunas.aprovado.filter(filtrarItem),
        indeferido: colunas.indeferido.filter(filtrarItem),
        legado: colunas.legado.filter(filtrarItem),
    };
});

const isSolicitacaoVencida = (item) => {
    if (!item?.data_solicitacao) return false;
    const base = new Date(item.data_solicitacao);
    if (Number.isNaN(base.getTime())) return false;
    const validadeAnos = Number(item.validade_anos || 5);
    const validade = new Date(base);
    validade.setFullYear(validade.getFullYear() + validadeAnos);
    return validade < new Date();
};

const copiarTexto = async (texto, sucesso, erro) => {
    if (!texto) {
        toast.warning("Contato indisponível.");
        return;
    }
    try {
        await navigator.clipboard.writeText(texto);
        toast.success(sucesso);
    } catch {
        toast.error(erro);
    }
};

const copiarEmailContato = () => copiarTexto(contatoEmail.value, "E-mail copiado para a área de transferência.", "Não foi possível copiar o e-mail.");
const copiarTelefoneContato = () => copiarTexto(contatoTelefone.value, "Telefone copiado para a área de transferência.", "Não foi possível copiar o telefone.");

const montarMensagemPorTemplate = (template) => {
    if (!selecionado.value?.beneficiario) return '';
    const nomeBeneficiario = selecionado.value.beneficiario.nome_completo;
    const nomeContato = contatoResponsavelNome.value;
    const protocolo = selecionado.value.protocolo;
    const dataValidade = formatData(selecionado.value.data_validade || selecionado.value.data_solicitacao);
    const templates = {
        PADRAO_CURTO: `Olá, ${nomeContato}. A carteirinha CIPTEA de ${nomeBeneficiario} (protocolo ${protocolo}) está vencida desde ${dataValidade}. Por favor, realize a renovação no app CIPTEA.`,
        PADRAO_COMPLETO: `Olá, ${nomeContato}. Identificamos que a carteirinha CIPTEA de ${nomeBeneficiario} (protocolo ${protocolo}) está vencida desde ${dataValidade}. Para renovar, acesse o app CIPTEA, revise os dados cadastrais e atualize a documentação necessária. Se precisar, posso enviar o passo a passo completo.`,
        PENDENCIA_DOC: `Olá, ${nomeContato}. A carteirinha CIPTEA de ${nomeBeneficiario} (protocolo ${protocolo}) está vencida desde ${dataValidade}. Na renovação, será importante conferir e anexar os documentos atualizados no app CIPTEA. Posso orientar o envio, se desejar.`
    };
    return templates[template] || templates.PADRAO_CURTO;
};
const atualizarMensagemComunicacao = () => { mensagemComunicacao.value = montarMensagemPorTemplate(templateComunicacao.value); };
const restaurarMensagemTemplate = () => { atualizarMensagemComunicacao(); toast.info("Mensagem restaurada para o template selecionado."); };
const copiarMensagemContato = () => copiarTexto(mensagemComunicacao.value || montarMensagemPorTemplate(templateComunicacao.value), "Mensagem copiada para a área de transferência.", "Não foi possível copiar a mensagem.");
const abrirWhatsappContato = () => {
    if (!numeroWhatsapp.value) {
        toast.warning("Telefone não disponível para WhatsApp.");
        return;
    }
    const mensagem = encodeURIComponent(mensagemComunicacao.value || montarMensagemPorTemplate(templateComunicacao.value));
    window.open(`https://wa.me/${numeroWhatsapp.value}?text=${mensagem}`, '_blank', 'noopener');
};

const getEventColor = (tipo) => {
    const map = {
        'CRIACAO': 'blue',
        'ANALISE': 'orange',
        'PENDENCIA': 'red',
        'CONCLUSAO': 'green'
    };
    return map[tipo] || 'grey';
};

const realizarLogout = () => {
    authStore.logout();
    toast.info("Logout realizado com sucesso.");
}

onMounted(() => {
    carregarSolicitacoes();
    carregarMetricasCadastro();
});
</script>

<style scoped>
.vencida-card {
  border: 2px solid #e65100 !important;
  box-shadow: 0 0 0 2px rgba(230, 81, 0, 0.28);
  background: linear-gradient(180deg, rgba(255, 243, 224, 0.75) 0%, #ffffff 38%);
}

.vencida-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #ffccbc;
  color: #e65100;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.35px;
}

.contato-vencida-card {
  border: 2px solid #ffb74d;
  background: linear-gradient(180deg, rgba(255, 243, 224, 0.65) 0%, #ffffff 45%);
}

.template-preview-box {
  border: 1px solid rgba(0, 0, 0, 0.14);
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.02);
  padding: 8px 10px;
  font-size: 0.78rem;
  color: rgba(0, 0, 0, 0.75);
  white-space: pre-line;
}
</style>