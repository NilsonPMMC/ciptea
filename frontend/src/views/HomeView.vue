<template>
  <v-container fluid class="fill-height align-start justify-center mogi-bg pa-0">
    
    <div v-if="store.perfilSalvo" class="logout-pos">
        <v-btn variant="text" color="white" prepend-icon="mdi-logout" @click="store.esquecerDispositivo">Sair</v-btn>
    </div>

    <v-col cols="12" sm="8" md="6" lg="4" class="d-flex flex-column align-center text-center px-6 py-10 fill-height">
        
        <div class="mb-8 mt-10 w-100">
            <img src="/logo_infinito_colorido.png" class="logo-main mb-2 animate-float">
        </div>

        <v-fade-transition mode="out-in">
            
            <div v-if="store.perfilSalvo" class="w-100 d-flex flex-column align-center">
                
                <div class="avatar-circle mb-6 elevation-5 overflow-hidden">
                    <v-img v-if="store.perfilSalvo.foto" :src="store.perfilSalvo.foto" cover width="100%" height="100%">
                        <template v-slot:placeholder>
                            <div class="d-flex align-center justify-center fill-height bg-grey-lighten-2">
                                <v-progress-circular indeterminate color="primary"></v-progress-circular>
                            </div>
                        </template>
                    </v-img>
                    <span v-else class="text-h2 font-weight-black text-primary">{{ getIniciais(store.perfilSalvo.nome) }}</span>
                </div>

                <v-sheet class="rounded-pill px-8 py-3 mb-6 elevation-2" color="white" width="100%">
                    <h3 class="text-h6 font-weight-bold text-primary text-truncate">Olá, {{ getPrimeiroNome(store.perfilSalvo.nome) }}</h3>
                </v-sheet>

                <div v-if="store.perfilSalvo.tipo === 'LEGADO'" class="w-100">
                    <v-alert type="info" variant="tonal" class="mb-4 text-left" border="start" density="compact">
                        <strong>Atualização Necessária</strong><br>
                        Localizamos seu cadastro antigo. Atualize os dados para obter a Carteira Digital.
                    </v-alert>
                    
                    <v-btn block color="primary" height="60" rounded="xl" class="mb-3 elevation-4" prepend-icon="mdi-account-convert" @click="atualizarCadastroLegado">
                        ATUALIZAR CADASTRO
                    </v-btn>
                </div>

                <div v-else class="w-100">
                    <v-btn 
                        v-if="estadoAtual === 'APROVADO'"
                        block color="#1A237E" height="60" rounded="xl" 
                        class="text-white mb-4 elevation-4 text-h6"
                        prepend-icon="mdi-card-account-details-outline"
                        @click="abrirCarteiraRapida"
                        :loading="store.consulta.loading"
                    >
                        CARTEIRINHA
                    </v-btn>

                    <v-btn 
                        v-else-if="estadoAtual === 'CORRIGIR'"
                        block color="warning" height="60" rounded="xl" 
                        class="text-white mb-4 elevation-4 text-h6"
                        style="color: white !important"
                        prepend-icon="mdi-file-document-edit-outline"
                        @click="resolverPendenciasRapido"
                        :loading="store.loading"
                    >
                        RESOLVER PENDÊNCIA
                    </v-btn>

                    <v-btn 
                        v-else-if="estadoAtual === 'INDEFERIDO'"
                        block color="error" height="60" rounded="xl" 
                        class="text-white mb-4 elevation-4 text-h6"
                        prepend-icon="mdi-close-octagon-outline"
                        @click="verStatusCompleto"
                    >
                        SOLICITAÇÃO INDEFERIDA
                    </v-btn>

                    <v-btn 
                        v-else
                        block color="#00C0F3" height="60" rounded="xl" 
                        class="text-white mb-4 elevation-4 text-h6"
                        prepend-icon="mdi-clock-outline"
                        @click="verStatusCompleto"
                    >
                        EM ANÁLISE
                    </v-btn>

                    <div class="text-center mb-2">
                        <a @click="verStatusCompleto" class="text-primary-darken-1 text-decoration-none font-weight-bold cursor-pointer">
                            <span v-if="estadoAtual === 'CORRIGIR'" class="text-warning">
                                <v-icon icon="mdi-alert-circle" size="small"></v-icon> Ação necessária
                            </span>
                            <span v-else-if="estadoAtual === 'INDEFERIDO'" class="text-error">
                                <v-icon icon="mdi-information" size="small"></v-icon> Ver motivo
                            </span>
                            <span v-else>ver detalhes / histórico</span>
                        </a>
                    </div>
                </div>

            </div>

            <div v-else class="w-100">
                <div style="height: 40px;"></div>
                
                <v-btn 
                    block 
                    color="#1A237E" 
                    height="70" 
                    rounded="xl" 
                    class="text-white mb-4 elevation-6 font-weight-bold text-h6 animate__animated animate__pulse animate__infinite"
                    prepend-icon="mdi-login"
                    @click="dialogAcesso = true"
                >
                    INICIAR / ACESSAR
                </v-btn>

                <p class="text-body-2 text-grey-darken-2 px-4 mt-4">
                    Já tem cadastro ou quer fazer um novo?<br>Clique em iniciar.
                </p>
            </div>
        </v-fade-transition>

        <div class="mt-auto w-100 pt-8">
            <div class="d-flex justify-center align-center gap-4">
                <div class="d-flex align-center">
                    <img src="/brasao_mogi_preto.png" height="45">
                </div>
            </div>
            <div class="text-caption text-grey mt-4">CIPTEA - Versão 1.0</div>
        </div>

    </v-col>

    <v-dialog v-model="dialogAcesso" max-width="400">
        <v-card class="rounded-lg">
            <v-card-title class="bg-primary text-white py-3">Identificação</v-card-title>
            <v-card-text class="pt-6">
                <p class="mb-4 text-body-2">Informe os dados do <strong>Beneficiário</strong> para entrar ou iniciar um novo cadastro.</p>
                
                <v-text-field 
                    label="CPF do Beneficiário" 
                    v-maska="'###.###.###-##'" 
                    v-model="formAcesso.cpf" 
                    variant="outlined"
                    prepend-inner-icon="mdi-card-account-details"
                ></v-text-field>

                <v-text-field 
                    label="Data de Nascimento" 
                    type="date" 
                    v-model="formAcesso.data_nascimento" 
                    variant="outlined"
                    prepend-inner-icon="mdi-calendar"
                ></v-text-field>
            </v-card-text>
            <v-card-actions class="pa-4">
                <v-spacer></v-spacer>
                <v-btn variant="text" @click="dialogAcesso = false">Cancelar</v-btn>
                <v-btn color="primary" variant="elevated" @click="verificarAcesso" :loading="loadingAcesso">
                    Continuar
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>

    <v-dialog v-model="dialogConsulta" max-width="500">
        <v-card class="rounded-lg">
            <v-toolbar color="primary" density="compact">
                <v-toolbar-title class="text-subtitle-1">Detalhes da Solicitação</v-toolbar-title>
                <v-btn icon="mdi-close" variant="text" @click="dialogConsulta = false"></v-btn>
            </v-toolbar>
            
            <v-card-text class="pt-6">
                <div v-if="store.consulta.resultado">
                    <div class="text-center bg-grey-lighten-4 pa-4 rounded-lg mb-4 border">
                        <div class="text-caption text-grey-darken-1">Beneficiário</div>
                        <div class="text-h6 font-weight-bold text-primary mb-1">{{ store.consulta.resultado.nome }}</div>
                        <v-chip :color="getStatusColor(store.consulta.resultado.status)" size="small">{{ store.consulta.resultado.status }}</v-chip>
                    </div>

                    <div v-if="store.consulta.resultado.historico && store.consulta.resultado.historico.length" class="mt-4 pt-2 border-t">
                        <h4 class="text-subtitle-2 font-weight-bold text-grey-darken-2 mb-3">
                            <v-icon start size="small">mdi-history</v-icon> Histórico
                        </h4>
                        
                        <v-timeline density="compact" side="end" align="start" truncate-line="start" class="timeline-custom">
                            <v-timeline-item
                                v-for="(evento, i) in store.consulta.resultado.historico"
                                :key="i"
                                :dot-color="getCorEvento(evento.tipo_evento)"
                                size="x-small"
                            >
                                <div class="d-flex flex-column">
                                    <div class="text-caption font-weight-bold text-grey-darken-1">
                                        {{ formatarDataHora(evento.data) }}
                                    </div>
                                    <div class="text-body-2 font-weight-bold text-primary">
                                        {{ evento.titulo }}
                                    </div>
                                    <div v-if="evento.mensagem" class="text-caption text-grey-darken-2 bg-grey-lighten-4 pa-2 rounded mt-1">
                                        {{ evento.mensagem }}
                                    </div>
                                </div>
                            </v-timeline-item>
                        </v-timeline>
                    </div>
                </div>
                <div v-else class="text-center py-4">
                    <v-progress-circular indeterminate color="primary"></v-progress-circular>
                </div>
            </v-card-text>
        </v-card>
    </v-dialog>

    <CarteiraDigital 
        v-model="showCarteira" 
        :dados="dadosCarteira"
        :pwa-install-event="deferredPrompt"
        @install="installPwa"
    />

  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import api from '@/services/api';
import { useCadastroStore } from '@/stores/cadastro';
import { vMaska } from 'maska/vue';
import CarteiraDigital from '@/components/CarteiraDigital.vue';
import { useToastStore } from '@/stores/toast';

const toast = useToastStore();
const store = useCadastroStore();
const router = useRouter();

// --- ESTADOS DO NOVO FLUXO ---
const dialogAcesso = ref(false);
const loadingAcesso = ref(false);
const formAcesso = ref({ cpf: '', data_nascimento: '' });

// Estados antigos mantidos para funcionalidades internas
const dialogConsulta = ref(false);
const showCarteira = ref(false);
const dadosCarteira = ref({});
const deferredPrompt = ref(null);

// --- 1. FUNÇÃO CENTRAL: VERIFICAR ACESSO (Login) ---
const verificarAcesso = async () => {
    if (!formAcesso.value.cpf || !formAcesso.value.data_nascimento) {
        toast.warning("Preencha todos os campos.");
        return;
    }

    loadingAcesso.value = true;
    try {
        const { data } = await api.post('solicitacoes/verificar-acesso/', formAcesso.value);

        // CASO C: NÃO ENCONTRADO -> CADASTRO NOVO
        if (data.tipo === 'NAO_ENCONTRADO') {
            dialogAcesso.value = false;
            store.resetForm();
            // Pré-preenche para facilitar
            store.beneficiario.cpf = formAcesso.value.cpf;
            store.beneficiario.data_nascimento = formAcesso.value.data_nascimento;
            
            toast.info("Iniciando nova solicitação...");
            router.push('/cidadao'); 
            return;
        }

        // CASO A ou B: ENCONTRADO -> LOGIN
        const dadosParaSalvar = {
            nome: data.nome,
            protocolo: data.protocolo,
            status: data.status,
            status_code: data.status_code, // Importante para as cores
            foto: data.foto,
            cpf: formAcesso.value.cpf,
            data_nascimento: formAcesso.value.data_nascimento,
            tipo: data.tipo // 'SISTEMA_NOVO' ou 'LEGADO'
        };
        
        store.salvarNoDispositivo(dadosParaSalvar);
        store.perfilSalvo = dadosParaSalvar; 
        
        dialogAcesso.value = false;
        
        if (data.tipo === 'LEGADO') toast.info("Cadastro antigo localizado.");
        else toast.success(`Bem-vindo de volta!`);

    } catch (e) {
        console.error(e);
        toast.error("Erro ao verificar acesso. Verifique os dados.");
    } finally {
        loadingAcesso.value = false;
    }
};

// --- 2. HELPERS E ESTADOS ---
const getIniciais = (nome) => nome ? nome.substring(0, 2).toUpperCase() : '??';
const getPrimeiroNome = (nome) => nome ? nome.split(' ')[0] : '';

const estadoAtual = computed(() => {
    const perfil = store.perfilSalvo;
    if (!perfil) return null;
    const statusRaw = (perfil.status_code || perfil.status || '').toUpperCase();

    if (['APROVADO', 'IMPRESSO'].includes(statusRaw)) return 'APROVADO';
    if (['PENDENTE', 'REJEITADO', 'CORREÇÃO'].some(s => statusRaw.includes(s))) return 'CORRIGIR';
    if (statusRaw.includes('INDEFERIDO')) return 'INDEFERIDO';
    return 'AGUARDANDO';
});

// --- 3. AÇÕES DO PAINEL ---

const abrirCarteiraRapida = async () => {
    const perfil = store.perfilSalvo;
    if(!perfil) return;
    
    store.consulta.loading = true;
    try {
        const { data } = await api.get(`solicitacoes/dados-carteira/?protocolo=${perfil.protocolo}&cpf=${perfil.cpf}&data_nascimento=${perfil.data_nascimento}`);
        dadosCarteira.value = data;
        showCarteira.value = true;
    } catch (e) {
        toast.error("Erro ao abrir carteira.");
    } finally {
        store.consulta.loading = false;
    }
};

const resolverPendenciasRapido = async () => {
    const perfil = store.perfilSalvo;
    const sucesso = await store.carregarParaEdicao(perfil.protocolo, perfil.cpf, perfil.data_nascimento);
    if (sucesso) router.push('/cidadao');
    else toast.error("Erro ao carregar edição.");
};

const atualizarCadastroLegado = async () => {
    const perfil = store.perfilSalvo;
    // O endpoint 'buscar-completo' deve saber lidar com legado ou retornar o básico
    const sucesso = await store.carregarParaEdicao(perfil.protocolo, perfil.cpf, perfil.data_nascimento);
    if(sucesso) router.push('/cidadao'); 
    else {
        // Fallback: se não carregar nada, reseta e vai pro form limpo mas com CPF
        store.resetForm();
        store.beneficiario.cpf = perfil.cpf;
        store.beneficiario.data_nascimento = perfil.data_nascimento;
        router.push('/cidadao');
    }
};

const verStatusCompleto = async () => {
     const perfil = store.perfilSalvo;
     if (perfil) {
         // Consulta silenciosa para pegar histórico atualizado
         await store.consultarProtocolo({ 
            tipo: 'cpf', 
            cpf: perfil.cpf, 
            data_nascimento: perfil.data_nascimento 
         });
     }
     dialogConsulta.value = true;
}

// --- 4. UTILITÁRIOS ---
const getStatusColor = (status) => {
    const s = status ? status.toUpperCase() : '';
    if (s.includes('APROVADO')) return 'success';
    if (s.includes('PENDENTE')) return 'warning';
    if (s.includes('INDEFERIDO')) return 'error';
    return 'primary';
};

const getCorEvento = (tipo) => {
    if (tipo === 'CONCLUSAO') return 'success';
    if (tipo === 'PENDENCIA') return 'warning';
    if (tipo === 'INDEFERIDO') return 'error';
    if (tipo === 'ANALISE') return 'info';
    return 'grey';
};

const formatarDataHora = (dataISO) => {
    if (!dataISO) return '';
    const data = new Date(dataISO);
    return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }).format(data);
};

// Lifecycle: Atualização Silenciosa
onMounted(async () => {
    store.carregarDoDispositivo();
    if (store.perfilSalvo && store.perfilSalvo.cpf) {
        try {
            // Tenta atualizar status/foto no fundo
            const { data } = await api.post('solicitacoes/verificar-acesso/', {
                cpf: store.perfilSalvo.cpf,
                data_nascimento: store.perfilSalvo.data_nascimento
            });
            // Atualiza local se encontrou
            if (data.tipo !== 'NAO_ENCONTRADO') {
                const atualizado = { ...store.perfilSalvo, ...data };
                store.salvarNoDispositivo(atualizado);
                store.perfilSalvo = atualizado;
            }
        } catch (e) { console.error("Sync error", e); }
    }
});

// PWA
window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferredPrompt.value = e; });
const installPwa = () => { if (deferredPrompt.value) deferredPrompt.value.prompt(); }
</script>

<style scoped>
.mogi-bg { background: linear-gradient(180deg, #00C0F3 0%, #FFFFFF 60%); min-height: 100vh; }
.logo-main { width: 160px; height: auto; filter: drop-shadow(0 4px 6px rgba(0,0,0,0.1)); }
.logout-pos { position: absolute; top: 20px; right: 20px; z-index: 10; }
.avatar-circle { width: 140px; height: 140px; background: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 4px solid white; overflow: hidden; position: relative; }
.animate-float { animation: float 6s ease-in-out infinite; }
@keyframes float { 0% { transform: translateY(0px); } 50% { transform: translateY(-10px); } 100% { transform: translateY(0px); } }
.cursor-pointer { cursor: pointer; }
.timeline-custom :deep(.v-timeline-item__body) { padding-left: 10px !important; width: 100%; }
</style>