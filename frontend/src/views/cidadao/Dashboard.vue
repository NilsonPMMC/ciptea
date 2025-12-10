<template>
  <v-container class="fill-height align-start pa-0 pa-md-4">
    <v-card width="100%" max-width="800" class="mx-auto mt-md-5 rounded-0 rounded-md-lg" :loading="store.loading">
      
      <v-toolbar v-if="!store.success" color="primary" density="comfortable">
        <v-btn icon="mdi-arrow-left" to="/"></v-btn>
        <v-toolbar-title>Solicitação CIPTEA</v-toolbar-title>
      </v-toolbar>

      <v-fade-transition>
        <div v-if="store.success" class="fill-height d-flex flex-column justify-center align-center text-center pa-8 bg-white" style="min-height: 400px;">
            
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
                Você receberá atualizações no WhatsApp informado.
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

      <div v-if="!store.success">
        <v-tabs v-model="step" grow color="primary" class="mb-4">
          <v-tab :value="1">1. Dados</v-tab>
          <v-tab :value="2">2. Resp.</v-tab>
          <v-tab :value="3">3. Docs</v-tab>
        </v-tabs>

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
                      <div class="d-flex justify-space-between mb-2">
                          <span class="text-subtitle-2 font-weight-bold text-grey-darken-1">
                              Responsável {{ i + 1 }}
                          </span>
                          <v-btn 
                              v-if="i > 0" 
                              icon="mdi-delete" 
                              size="x-small" 
                              color="error" 
                              variant="text"
                              @click="store.removerResponsavel(i)"
                          ></v-btn>
                      </div>

                      <v-row dense>
                          <v-col cols="12">
                              <v-select 
                                  label="Vínculo*" 
                                  v-model="resp.perfil"
                                  :items="listaVinculos"
                                  item-title="title"
                                  item-value="value"
                                  variant="outlined"
                                  density="comfortable"
                              ></v-select>
                          </v-col>
                          <v-col cols="12">
                              <v-text-field 
                                  label="Nome Completo*" 
                                  v-model="resp.nome" 
                                  variant="outlined"
                                  density="comfortable"
                                  :error-messages="getErro(`responsaveis[${i}].nome`)"
                              ></v-text-field>
                          </v-col>
                          <v-col cols="12" md="6">
                              <v-text-field 
                                  label="CPF*" 
                                  v-maska="'###.###.###-##'" 
                                  v-model="resp.cpf" 
                                  variant="outlined"
                                  density="comfortable"
                                  :error-messages="getErro(`responsaveis[${i}].cpf`)"
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

              <div class="mb-4">
                  <v-file-input 
                    label="Laudo Médico (c/ CID)*" 
                    variant="outlined"
                    density="comfortable"
                    prepend-icon="mdi-doctor"
                    accept="image/*, application/pdf"
                    @update:model-value="files => store.anexos.laudo = files ? files : null"
                    :error-messages="store.statusLaudo?.status === 'REJEITADO' ? 'Documento recusado' : ''"
                    :base-color="store.statusLaudo?.status === 'REJEITADO' ? 'error' : (store.statusLaudo?.status === 'APROVADO' ? 'success' : '')"
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
                    :error-messages="store.statusRgBenef?.status === 'REJEITADO' ? 'Documento recusado' : ''"
                    :base-color="store.statusRgBenef?.status === 'REJEITADO' ? 'error' : (store.statusRgBenef?.status === 'APROVADO' ? 'success' : '')"
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
                    :error-messages="store.statusCompRes?.status === 'REJEITADO' ? 'Documento recusado' : ''"
                    :base-color="store.statusCompRes?.status === 'REJEITADO' ? 'error' : (store.statusCompRes?.status === 'APROVADO' ? 'success' : '')"
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

              <div class="mb-4">
                  <v-file-input 
                    label="RG/CNH do Responsável" 
                    hint="Obrigatório se o beneficiário for menor"
                    persistent-hint
                    variant="outlined"
                    density="comfortable"
                    prepend-icon="mdi-account-box"
                    accept="image/*, application/pdf"
                    @update:model-value="files => store.anexos.rg_responsavel = files ? files : null"
                    :error-messages="store.statusRgResp?.status === 'REJEITADO' ? 'Documento recusado' : ''"
                    :base-color="store.statusRgResp?.status === 'REJEITADO' ? 'error' : (store.statusRgResp?.status === 'APROVADO' ? 'success' : '')"
                  >
                      <template v-slot:append-inner v-if="store.statusRgResp?.status === 'APROVADO'">
                          <v-icon color="success" icon="mdi-check-circle"></v-icon>
                      </template>
                  </v-file-input>

                  <v-alert 
                      v-if="store.statusRgResp?.status === 'REJEITADO'"
                      type="error" variant="tonal" density="compact" class="mt-1" icon="mdi-alert-circle"
                  >
                      <strong>Motivo:</strong> {{ store.statusRgResp.motivo_rejeicao }}
                  </v-alert>
              </div>

              <v-divider class="my-6"></v-divider>

              <div v-if="store.error" class="text-red mb-3 text-center font-weight-bold">
                <v-icon icon="mdi-alert-circle"></v-icon> {{ store.error }}
              </div>
              
              <div class="d-flex justify-space-between mt-4">
                <v-btn variant="text" @click="step--">Voltar</v-btn>
                <v-btn color="success" size="large" :loading="store.loading" @click="store.enviarSolicitacao()">
                  {{ store.modoEdicao ? 'Salvar Correções' : 'Finalizar Solicitação' }}
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
import { ref } from 'vue';
import { vMaska } from 'maska/vue'; 
import { useCadastroStore } from '@/stores/cadastro';
import Cropper from 'cropperjs';
import 'cropperjs/dist/cropper.css';
import { nextTick } from 'vue';

const step = ref(1);
const store = useCadastroStore();
const fotoPreview = ref(null);
const dialogCropper = ref(false);
const imageSrc = ref('');
let cropperInstance = null;

const listaVinculos = [
    { title: 'Mãe', value: 'MAE' },
    { title: 'Pai', value: 'PAI' },
    { title: 'Avô/Avó', value: 'AVO' },
    { title: 'Tio/Tia', value: 'TIO' },
    { title: 'Tutor/Curador', value: 'TUTOR' },
    { title: 'Próprio Beneficiário', value: 'PROPRIO' },
    { title: 'Outro', value: 'OUTRO' }
];

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

const getErro = (campo) => {
    try {
        if (!store.errosCampos) return '';
        
        // Tenta acesso direto
        if (store.errosCampos[campo]) return store.errosCampos[campo];
        
        // Se não achou, retorna vazio sem quebrar
        return '';
    } catch (e) {
        return '';
    }
}
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
</style>