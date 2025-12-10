<template>
  <v-dialog v-model="show" fullscreen transition="dialog-bottom-transition">
    <v-card color="grey-darken-4">
      
      <v-toolbar color="black" density="compact">
        <v-btn icon="mdi-close" @click="fechar"></v-btn>
        <v-toolbar-title class="text-subtitle-1">Carteira Digital</v-toolbar-title>
        <v-spacer></v-spacer>
        <v-btn icon="mdi-share-variant" @click="compartilhar"></v-btn>
      </v-toolbar>

      <v-container class="fill-height d-flex flex-column justify-center align-center">
        
        <div class="scene" @click="virarCartao">
          <div class="card" :class="{ 'is-flipped': isFlipped }">
            
            <div class="card-face card-front">
              <div class="front-content">
                
                <img src="/logo_infinito_colorido.png" class="logo-top animate-pulse">

                <div class="grid-info mt-2">
                    <div class="left-col">
                        <div class="foto-moldura">
                            <v-img :src="dados.foto" cover class="foto-img"></v-img>
                        </div>
                        <div class="protocolo-box">
                            <span class="label-proto">Nº </span>
                            <span class="value-proto">{{ dados.protocolo }}</span>
                        </div>
                    </div>

                    <div class="right-col pl-3">
                        <div class="name-text">{{ dados.nome }}</div>
                        
                        <div class="mt-2">
                            <div class="label-field">CPF</div>
                            <div class="value-field">{{ dados.cpf }}</div>
                        </div>

                        <div class="mt-1">
                            <div class="label-field">DATA NASCIMENTO</div>
                            <div class="value-field">{{ formatarData(dados.nascimento) }}</div>
                        </div>
                    </div>
                </div>

                <div class="footer-front">
                    <div class="d-flex align-center flex-column justify-end pb-1">
                        <div class="badge-pref">Atendimento Preferencial</div>
                        <div class="lei-txt">Lei Federal Nº 13.977/2020</div>
                    </div>
                    <div>
                        <img src="/brasao_mogi_preto.png" class="logo-pref-img">
                    </div>
                </div>
                
                <div class="touch-hint">
                    <v-icon icon="mdi-gesture-tap" size="x-small"></v-icon> Toque para virar
                </div>
              </div>
            </div>

            <div class="card-face card-back">
              
              <div class="back-body">
                  <div class="d-flex justify-space-between mb-3 border-b pb-2">
                      <div>
                          <div class="label-green">EMISSÃO</div>
                          <div class="value-small">{{ new Date().toLocaleDateString('pt-BR') }}</div>
                      </div>
                      <div class="text-right">
                          <div class="label-green">VALIDADE</div>
                          <div class="value-small">5 ANOS</div>
                      </div>
                  </div>

                  <div class="mb-2">
                      <div class="label-green badge-green mb-1">RESPONSÁVEL 1</div>
                      <div class="value-small text-uppercase">{{ dados.responsavel1_nome }}</div>
                  </div>

                  <div v-if="dados.responsavel2_nome" class="mb-2">
                      <div class="label-green badge-green mb-1">RESPONSÁVEL 2</div>
                      <div class="value-small text-uppercase">{{ dados.responsavel2_nome }}</div>
                  </div>

                  <div class="mb-2">
                      <div class="label-green badge-green mb-1">CONTATO</div>
                      <div class="value-small">{{ dados.contato_telefone }}</div>
                  </div>
                  
                  <div class="mb-2">
                      <div class="label-green badge-green mb-1">ENDEREÇO</div>
                      <div class="value-small text-uppercase" style="font-size: 0.75rem">
                        {{ dados.logradouro }}, {{ dados.numero }} - {{ dados.bairro }}
                      </div>
                  </div>
              </div>

              <div class="qr-box">
                  <QrcodeVue :value="qrValue" :size="130" level="H" background="#ffffff" foreground="#000000" />
                  <div class="text-caption mt-1 text-grey-darken-1" style="font-size: 0.6rem">Validação Digital</div>
              </div>

               <div class="footer-blue-back">
                   <img src="/logo_ciptea_branco.png" class="logo-footer-white">
               </div>
            </div>

          </div>
        </div>

        <v-btn 
            v-if="pwaInstallEvent" 
            color="white" 
            variant="text"
            class="mt-6 text-none" 
            prepend-icon="mdi-download" 
            @click="instalarApp"
        >
            Salvar Carteira no Celular
        </v-btn>

      </v-container>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed } from 'vue';
import QrcodeVue from 'qrcode.vue';

const props = defineProps(['modelValue', 'dados', 'pwaInstallEvent']);
const emit = defineEmits(['update:modelValue', 'install']);

const isFlipped = ref(false);

const show = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
});

const qrValue = computed(() => `https://ciptea.mogidascruzes.sp.gov.br/validar/${props.dados.protocolo}`);

const fechar = () => {
    show.value = false;
    setTimeout(() => { isFlipped.value = false; }, 300);
};

const virarCartao = () => {
    isFlipped.value = !isFlipped.value;
}

const compartilhar = () => {
  if (navigator.share) {
    navigator.share({
      title: 'CIPTEA Digital',
      text: `Carteira CIPTEA de ${props.dados.nome}`,
      url: window.location.href
    });
  }
};

const instalarApp = () => emit('install');

const formatarData = (data) => {
    if(!data) return '';
    const [ano, mes, dia] = data.split('-');
    return `${dia}/${mes}/${ano}`;
}
</script>

<style scoped>
/* =========================================
   CENA 3D
   ========================================= */
.scene {
  height: 68vh; 
  max-height: 580px; 
  aspect-ratio: 0.63; /* Proporção ~54/86mm */
  margin: 0 auto;
  perspective: 1200px;
  cursor: pointer;
}

.card {
  width: 100%;
  height: 100%;
  position: relative;
  transition: transform 0.8s cubic-bezier(0.175, 0.885, 0.32, 1.275); /* Efeito elástico suave */
  transform-style: preserve-3d;
}

.card.is-flipped { transform: rotateY(180deg); }

.card-face {
  position: absolute;
  width: 100%;
  height: 100%;
  -webkit-backface-visibility: hidden;
  backface-visibility: hidden;
  border-radius: 14px;
  background: white;
  overflow: hidden;
  /* BORDA AZUL CIANO - IDENTIDADE VISUAL */
  border: 4px solid #1ba0da; 
  box-shadow: 0 15px 35px rgba(0,0,0,0.2);
  display: flex;
  flex-direction: column;
}

.card-back { transform: rotateY(180deg); }

/* =========================================
   ESTILOS INTERNOS (FRENTE)
   ========================================= */
.front-content {
    padding: 12px;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    position: relative;
}

.logo-top { width: 190px; margin-top: 5px; margin-bottom: 25px }

.title-main {
    font-size: 1.8rem;
    font-weight: 900;
    line-height: 1;
    margin-top: 5px;
    letter-spacing: -1px;
    color: #000;
}

.subtitle-main {
    font-size: 0.65rem;
    line-height: 1.1;
    color: #444;
    margin-bottom: 15px;
    padding: 0 5px;
}

/* Grid Foto x Dados */
.grid-info { display: flex; width: 100%; flex: 1; }
.left-col { width: 40%; display: flex; flex-direction: column; align-items: center; }
.right-col { width: 60%; display: flex; flex-direction: column; text-align: left; }

.foto-moldura {
    width: 100%;
    aspect-ratio: 3/4;
    background: #f0f0f0;
    border: 1px solid #ddd;
    border-radius: 6px;
    overflow: hidden;
    margin-bottom: 4px;
}

.foto-img { width: 100%; height: 100%; }

.protocolo-box { text-align: center; }
.label-proto { font-size: 0.6rem; font-weight: bold; color: #666; }
.value-proto { font-size: 0.8rem; font-weight: 900; color: #1ba0da; }

.name-text {
    font-size: 1rem;
    font-weight: 800;
    line-height: 1.1;
    color: #000;
    text-transform: capitalize;
    margin-bottom: 10px;
}

.label-field { font-size: 0.6rem; color: #666; font-weight: 700; text-transform: uppercase; }
.value-field { font-size: 0.9rem; font-weight: 800; color: #000; }

.footer-front {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-top: auto;
    margin-bottom: 5px;
}

.badge-pref {
    background: #1ba0da;
    color: white;
    font-weight: bold;
    font-size: 0.8rem;
    padding: 3px 6px;
    border-radius: 4px;
    margin-bottom: 2px;
    display: inline-block;
}

.lei-txt { font-size: 0.7rem; font-weight: bold; color: #000000; }
.logo-pref-img { height: 60px; }

/* =========================================
   ESTILOS INTERNOS (VERSO)
   ========================================= */
.header-green {
    color: white;
    width: 100%;
    padding: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.back-body {
    padding: 15px;
    text-align: left;
    width: 100%;
}

.label-green { font-size: 0.6rem; color: #1ba0da; font-weight: 800; }
.badge-green { 
    background: #1ba0da; 
    color: white; 
    padding: 2px 6px; 
    border-radius: 4px; 
    display: inline-block;
}

.value-small { font-size: 0.8rem; font-weight: 700; color: #222; }

.qr-box {
    margin-top: auto;
    margin-bottom: 10px;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.footer-blue-back {
    background: #1ba0da;
    width: 100%;
    height: 80px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.logo-footer-white { height: 40px; }

/* Dica de toque */
.touch-hint {
    position: absolute;
    bottom: 5px;
    right: 5px;
    font-size: 0.6rem;
    color: #1ba0da;
    opacity: 0.8;
    animation: pulse 2s infinite;
}

.animate-pulse { animation: pulse 3s infinite; }
@keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.05); } 100% { transform: scale(1); } }
</style>