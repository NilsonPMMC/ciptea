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
    
    <v-btn icon="mdi-refresh" @click="carregarSolicitacoes"></v-btn>
    <v-btn icon="mdi-logout" @click="realizarLogout"></v-btn>
  </v-app-bar>

  <v-container fluid class="bg-grey-lighten-3 fill-height align-start pa-8 justify-center" style="overflow-x: auto;">
    <div class="d-flex" style="gap: 16px; min-width: 1200px;">
      
      <v-sheet width="300" color="transparent">
        <div class="text-subtitle-2 text-uppercase text-grey-darken-1 mb-2 font-weight-bold pl-1">
          Novos ({{ colunas.aberto.length }})
        </div>
        <v-card 
          v-for="item in colunasFiltradas.aberto" :key="item.id" 
          class="mb-3 cursor-pointer border-l-xl border-primary"
          @click="abrirAnalise(item)"
          elevation="1"
        >
          <v-card-text>
            <div class="text-caption text-grey">Protocolo: {{ item.protocolo }}</div>
            <div class="font-weight-bold text-body-1">{{ item.beneficiario.nome_completo }}</div>
            <div class="text-caption mt-1">
              <v-icon icon="mdi-calendar" size="x-small"></v-icon> {{ formatData(item.data_solicitacao) }}
            </div>
          </v-card-text>
        </v-card>
      </v-sheet>

      <v-sheet width="300" color="transparent">
        <div class="text-subtitle-2 text-uppercase text-grey-darken-1 mb-2 font-weight-bold pl-1">
          Em Análise ({{ colunas.analise.length }})
        </div>
        <v-card 
          v-for="item in colunasFiltradas.analise" :key="item.id" 
          class="mb-3 cursor-pointer border-l-xl border-orange"
          @click="abrirAnalise(item)"
          elevation="1"
        >
          <v-card-text>
            <div class="text-caption text-grey">Protocolo: {{ item.protocolo }}</div>
            <div class="font-weight-bold">{{ item.beneficiario.nome_completo }}</div>
          </v-card-text>
        </v-card>
      </v-sheet>

      <v-sheet width="300" color="transparent">
        <div class="text-subtitle-2 text-uppercase text-grey-darken-1 mb-2 font-weight-bold pl-1">
          Pendência ({{ colunas.pendente.length }})
        </div>
        <v-card 
          v-for="item in colunasFiltradas.pendente" :key="item.id" 
          class="mb-3 cursor-pointer border-l-xl border-error"
          @click="abrirAnalise(item)"
          elevation="1"
        >
          <v-card-text>
            <div class="text-caption text-grey">Protocolo: {{ item.protocolo }}</div>
            <div class="font-weight-bold">{{ item.beneficiario.nome_completo }}</div>
            <v-chip size="x-small" color="error" class="mt-2">Aguardando Cidadão</v-chip>
          </v-card-text>
        </v-card>
      </v-sheet>

      <v-sheet width="300" color="transparent">
        <div class="text-subtitle-2 text-uppercase text-grey-darken-1 mb-2 font-weight-bold pl-1">
          Concluídos ({{ colunas.aprovado.length }})
        </div>
        <v-card 
          v-for="item in colunasFiltradas.aprovado" :key="item.id" 
          class="mb-3 cursor-pointer border-l-xl border-success"
          @click="abrirAnalise(item)"
          elevation="1"
        >
          <v-card-text>
            <div class="text-caption text-grey">Protocolo: {{ item.protocolo }}</div>
            <div class="font-weight-bold">{{ item.beneficiario.nome_completo }}</div>
            <div class="d-flex gap-2 mt-2">
                <v-btn 
                    size="x-small" 
                    variant="tonal" 
                    color="primary" 
                    prepend-icon="mdi-printer"
                    :href="`http://localhost:8010/api/carteira/pdf/${item.protocolo}/`"
                    target="_blank"
                    @click.stop
                >
                    PDF
                </v-btn>
            </div>
          </v-card-text>
        </v-card>
      </v-sheet>

      <v-sheet width="300" color="transparent">
        <div class="text-subtitle-2 text-uppercase text-grey-darken-1 mb-2 font-weight-bold pl-1">
          Arquivados ({{ colunas.indeferido.length }})
        </div>
        <v-card 
          v-for="item in colunasFiltradas.indeferido" :key="item.id" 
          class="mb-3 cursor-pointer border-l-xl"
          :style="item.status === 'LEGADO' ? 'border-left-color: #9C27B0 !important;' : 'border-left-color: #616161 !important;'" 
          @click="abrirAnalise(item)"
          elevation="1"
        >
          <v-card-text>
            <div class="text-caption text-grey">Protocolo: {{ item.protocolo }}</div>
            <div class="font-weight-bold text-grey-darken-2" :class="item.status === 'INDEFERIDO' ? 'text-decoration-line-through' : ''">
                {{ item.beneficiario.nome_completo }}
            </div>
            
            <v-chip v-if="item.status === 'LEGADO'" size="x-small" color="purple" class="mt-2" variant="flat">
                Sistema Antigo
            </v-chip>
            <v-chip v-else size="x-small" color="grey-darken-2" class="mt-2">
                Indeferido
            </v-chip>

          </v-card-text>
        </v-card>
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

                    <v-card v-if="selecionado.status !== 'APROVADO' && selecionado.status !== 'IMPRESSO'" class="mt-4 pa-4 bg-grey-lighten-4">

                        <h3 class="text-subtitle-1 mb-2">Parecer Final</h3>
                        
                        <v-textarea 
                            label="Mensagem para o Cidadão" 
                            v-model="mensagemParecer"
                            rows="3"
                            variant="outlined"
                            bg-color="white"
                        ></v-textarea>

                        <div class="d-flex flex-row mt-2" style="gap: 1rem">
                            <template v-if="selecionado.status !== 'INDEFERIDO'">
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

                            <template v-else>
                                <v-alert type="error" variant="tonal" class="mb-2 text-caption">
                                    Este processo está arquivado como <strong>Indeferido</strong>.
                                </v-alert>
                                <v-btn color="primary" variant="flat" @click="prepararFinalizacao('REATIVAR')">
                                    <v-icon start>mdi-restore</v-icon> Reativar Processo
                                </v-btn>
                            </template>
                        </div>
                    </v-card>

                    <v-alert v-else type="success" variant="tonal" class="mt-4" icon="mdi-check-decagram">
                        <strong>Processo Finalizado</strong><br>
                        Esta solicitação já foi aprovada e a carteirinha gerada.
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

const colunas = reactive({
    aberto: [],
    analise: [],
    pendente: [],
    aprovado: [],
    indeferido: []
});

const getColorCard = (status) => {
    if (status === 'APROVADO') return 'green-lighten-5';
    if (status === 'REJEITADO') return 'red-lighten-5';
    return 'white';
};

const authStore = useAuthStore();
const toast = useToastStore();
const termoBusca = ref('');
const dialogAnalise = ref(false);
const selecionado = ref(null);
const mensagemParecer = ref('');
const alteracoesPendentes = ref(false);

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
             // Salva docs rejeitados
             for (const doc of selecionado.value.anexos) {
                if (doc.status === 'REJEITADO') {
                    await api.patch(`documentos/${doc.id}/`, { 
                        status: 'REJEITADO', 
                        motivo_rejeicao: doc.motivo_rejeicao 
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
        const params = {};
        if (termoBusca.value) params.search = termoBusca.value;

        console.log("Enviando busca:", params);

        // DEBUG: Vamos ver o que volta da API
        const { data } = await api.get('solicitacoes/', { params });
        console.log("Recebido do servidor:", data.length, "registros");

        // Limpa colunas
        colunas.aberto = []; colunas.analise = []; colunas.pendente = []; 
        colunas.aprovado = []; colunas.indeferido = [];
        
        data.forEach(s => {
            if (s.status === 'ABERTO') colunas.aberto.push(s);
            else if (s.status === 'ANALISE') colunas.analise.push(s);
            else if (s.status === 'PENDENTE') colunas.pendente.push(s);
            else if (['APROVADO', 'IMPRESSO'].includes(s.status)) colunas.aprovado.push(s);
            
            // AQUI: Joga tanto INDEFERIDO quanto LEGADO na última coluna
            else if (s.status === 'INDEFERIDO' || s.status === 'LEGADO') {
                colunas.indeferido.push(s);
            }
        });

    } catch (e) {
        console.error("Erro ao carregar dashboard", e);
        toast.error("Erro na comunicação com o servidor.");
    }
}

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

    // 2. Abre o Modal
    selecionado.value = JSON.parse(JSON.stringify(item));
    mensagemParecer.value = '';
    dialogAnalise.value = true;
}

const formatData = (dataStr) => {
    if(!dataStr) return '';
    return new Date(dataStr).toLocaleDateString('pt-BR');
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
        for (const doc of selecionado.value.anexos) {
            await api.patch(`documentos/${doc.id}/`, {
                status: doc.status,
                motivo_rejeicao: doc.motivo_rejeicao
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
    // Se não tiver busca, retorna tudo original
    if (!termoBusca.value) return colunas;

    const termo = termoBusca.value.toLowerCase();

    // Função auxiliar que verifica se o item bate com a busca
    const filtrarItem = (item) => {
        const nome = item.beneficiario?.nome_completo?.toLowerCase() || '';
        const protocolo = item.protocolo || '';
        const cpf = item.beneficiario?.cpf || '';
        const cpfLimpo = cpf.replace(/\D/g, ''); // Permite buscar sem pontos/traços

        return nome.includes(termo) || 
               protocolo.includes(termo) || 
               cpf.includes(termo) || 
               cpfLimpo.includes(termo);
    };

    // Retorna a mesma estrutura, mas filtrada
    return {
        aberto: colunas.aberto.filter(filtrarItem),
        analise: colunas.analise.filter(filtrarItem),
        pendente: colunas.pendente.filter(filtrarItem),
        aprovado: colunas.aprovado.filter(filtrarItem),
        indeferido: colunas.indeferido.filter(filtrarItem)
    };
});

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
});
</script>