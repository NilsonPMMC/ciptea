import { defineStore } from 'pinia';
import api from '@/services/api';
import axios from 'axios';

export const useCadastroStore = defineStore('cadastro', {
  state: () => ({
    loading: false,
    loadingCep: false,
    error: null,
    success: false,
    protocolo: null,
    modoEdicao: false,
    idSolicitacaoEdicao: null,
    statusLaudo: null,
    statusRgBenef: null,
    statusCompRes: null,
    statusRgResp: null,
    perfilSalvo: null,
    
    beneficiario: {
      nome_completo: '',
      data_nascimento: '',
      sexo: 'M',
      cpf: '',
      rg: '',
      cid: 'F84.0',
      nome_mae: '',
      nome_pai: '',
      telefone: '',
      email: '',
      cep: '',
      logradouro: '',
      numero: '',
      complemento: '',
      bairro: '',
      cidade: 'Mogi das Cruzes',
      estado: 'SP',
      foto: null 
    },

    responsaveis: [
      { nome: '', cpf: '', telefone: '', perfil: null }
    ],

    anexos: {
      laudo: null,
      rg_beneficiario: null,
      comprovante_residencia: null, 
      rg_responsavel: null 
    },

    consulta: {
      loading: false,
      resultado: null,
      erro: null
    }
  }),

  actions: {
    async buscarCep(valor) {
      const cepLimpo = valor.replace(/\D/g, '');

      if (cepLimpo.length === 8) {
        this.loadingCep = true;
        try {
          const { data } = await axios.get(`https://viacep.com.br/ws/${cepLimpo}/json/`);
          
          if (!data.erro) {
            this.beneficiario.logradouro = data.logradouro;
            this.beneficiario.bairro = data.bairro;
            this.beneficiario.cidade = data.localidade;
            this.beneficiario.estado = data.uf;
            
          } else {
            this.error = "CEP não encontrado.";
          }
        } catch (e) {
          console.error("Erro ViaCEP", e);
        } finally {
          this.loadingCep = false;
        }
      }
    },

    async carregarParaEdicao(protocolo, cpf, dataNascimento) {
      this.loading = true;
      try {
          // 1. MUDANÇA DA URL: Aponta para a nova rota que aceita status PENDENTE
          const { data } = await api.get(`solicitacoes/buscar-completo/?protocolo=${protocolo}&cpf=${cpf}&data_nascimento=${dataNascimento}`);
          
          if (!data) throw new Error("Dados não encontrados");

          // Guarda ID e Protocolo para o PATCH posterior
          this.idSolicitacaoEdicao = data.id; 
          this.protocolo = protocolo;

          // 2. PREENCHE BENEFICIÁRIO
          // O Serializer retorna o objeto completo em 'beneficiario'
          this.beneficiario = {
              id: data.beneficiario.id, 
              nome_completo: data.beneficiario.nome_completo,
              cpf: data.beneficiario.cpf,
              data_nascimento: data.beneficiario.data_nascimento,
              sexo: data.beneficiario.sexo,
              cid: data.beneficiario.cid,
              cep: data.beneficiario.cep,
              logradouro: data.beneficiario.logradouro,
              numero: data.beneficiario.numero,
              bairro: data.beneficiario.bairro,
              cidade: data.beneficiario.cidade,
              estado: data.beneficiario.estado,
              complemento: data.beneficiario.complemento,
              telefone: data.beneficiario.telefone || '',
              foto: data.beneficiario.foto,
                status_foto: data.beneficiario.status_foto,
                motivo_rejeicao_foto: data.beneficiario.motivo_rejeicao_foto
          };

          // 3. PREENCHE RESPONSÁVEIS (Lista)
          if (data.beneficiario.responsaveis && data.beneficiario.responsaveis.length > 0) {
              this.responsaveis = data.beneficiario.responsaveis.map(resp => ({
                  id: resp.id,
                  nome: resp.nome,
                  cpf: resp.cpf,
                  telefone: resp.telefone,
                  perfil: resp.perfil
              }));
          } else {
              this.responsaveis = [{ nome: '', cpf: '', telefone: '', perfil: null }];
          }

          // 4. PREENCHE STATUS DOS DOCUMENTOS
          // O Serializer retorna a lista em 'anexos'
          if (data.anexos) {
              data.anexos.forEach(doc => {
                  if (doc.tipo === 'LAUDO') this.statusLaudo = doc;
                  if (doc.tipo === 'RG_BENEF') this.statusRgBenef = doc;
                  if (doc.tipo === 'COMP_RES') this.statusCompRes = doc;
                  if (doc.tipo === 'RG_RESP') this.statusRgResp = doc;
              });
          }

          this.modoEdicao = true;
          return true;

      } catch (e) {
          console.error("Erro ao carregar edição:", e);
          // toast.error("Erro ao carregar dados."); // Opcional, já que retorna false
          return false;
      } finally {
          this.loading = false;
      }
    },

    async enviarSolicitacao() {
      this.loading = true;
      this.error = null;

      try {
        // 1. SE FOR EDIÇÃO, REDIRECIONA PARA A OUTRA FUNÇÃO
        if (this.modoEdicao) {
            await this.atualizarExistente();
            return;
        }

        const formData = new FormData();

        // 2. DADOS DO BENEFICIÁRIO (Texto)
        Object.keys(this.beneficiario).forEach(key => {
          // Ignora campos complexos ou nulos para não quebrar o FormData
          // Também ignoramos 'foto' aqui porque vamos adicionar manualmente abaixo
          if (this.beneficiario[key] && key !== 'responsaveis' && key !== 'foto') {
              formData.append(key, this.beneficiario[key]);
          }
        });

        // 3. A FOTO (Aqui estava o problema!)
        // Pegamos o arquivo gerado pelo Cropper em 'anexos.foto'
        if (this.anexos.foto) {
            formData.append('foto', this.anexos.foto);
        }

        // Lógica de Telefone de Segurança (Fallback)
        if (!this.beneficiario.telefone && this.responsaveis.length > 0 && this.responsaveis[0].telefone) {
             formData.append('telefone', this.responsaveis[0].telefone);
        }

        // 4. DADOS DOS RESPONSÁVEIS (Lista)
        this.responsaveis.forEach((resp, index) => {
            formData.append(`responsaveis[${index}]nome`, resp.nome);
            formData.append(`responsaveis[${index}]cpf`, resp.cpf);
            formData.append(`responsaveis[${index}]telefone`, resp.telefone);
            formData.append(`responsaveis[${index}]perfil`, resp.perfil);
            
            // Endereço do responsável (copia do beneficiário)
            formData.append(`responsaveis[${index}]cep`, this.beneficiario.cep);
            formData.append(`responsaveis[${index}]logradouro`, this.beneficiario.logradouro);
            formData.append(`responsaveis[${index}]numero`, this.beneficiario.numero);
            formData.append(`responsaveis[${index}]bairro`, this.beneficiario.bairro);
            formData.append(`responsaveis[${index}]cidade`, this.beneficiario.cidade);
            formData.append(`responsaveis[${index}]estado`, this.beneficiario.estado);
            if(this.beneficiario.complemento) {
                formData.append(`responsaveis[${index}]complemento`, this.beneficiario.complemento);
            }
        });

        // 5. ENVIA PARA A API (Cria Beneficiário + Responsáveis)
        const responseBen = await api.post('beneficiarios/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        
        const beneficiarioId = responseBen.data.id;

        // 6. CRIA A SOLICITAÇÃO
        const responseSol = await api.post('solicitacoes/', {
          beneficiario_id: beneficiarioId,
          status: 'ABERTO'
        });

        const solicitacaoId = responseSol.data.id;
        this.protocolo = responseSol.data.protocolo;

        // 7. UPLOAD DOS ANEXOS
        await this.uploadAnexo(solicitacaoId, 'LAUDO', 'Laudo Médico', this.anexos.laudo);
        await this.uploadAnexo(solicitacaoId, 'RG_BENEF', 'RG do Beneficiário', this.anexos.rg_beneficiario);
        await this.uploadAnexo(solicitacaoId, 'COMP_RES', 'Comprovante Residência', this.anexos.comprovante_residencia);
        
        if (this.anexos.rg_responsavel) {
            await this.uploadAnexo(solicitacaoId, 'RG_RESP', 'RG do Responsável', this.anexos.rg_responsavel);
        }
        
        this.success = true;
      
      } catch (err) {
        console.error("Erro API Detalhado:", err.response?.data);
        
        if (err.response?.data) {
             const dadosErro = err.response.data;
             // Trata erro de foto especificamente
             if (dadosErro.foto) {
                 this.error = "Erro na Foto: O arquivo é inválido ou não foi enviado.";
             }
             else if (dadosErro.cpf || (dadosErro.beneficiario && dadosErro.beneficiario.cpf)) {
                 this.error = "Erro: Já existe um cadastro com este CPF.";
             } else {
                 this.error = "Verifique os campos obrigatórios.";
             }
             this.errosCampos = dadosErro;
        } else {
            this.error = "Erro ao enviar solicitação. Tente novamente.";
        }
      } finally {
        this.loading = false;
      }
    },

    async uploadAnexo(solicitacaoId, tipo, descricao, arquivo) {
        if (!arquivo) return;
        const form = new FormData();
        form.append('solicitacao', solicitacaoId);
        form.append('tipo', tipo);
        form.append('descricao', descricao);
        form.append('arquivo', arquivo);
        
        await api.post('documentos/', form, {
             headers: { 'Content-Type': 'multipart/form-data' }
        });
    },

    async consultarProtocolo(dadosBusca) {
        this.consulta.loading = true;
        this.consulta.erro = null;
        this.consulta.resultado = null;
        
        try {
            // Monta a Query String dinâmica
            let params = '';
            if (dadosBusca.tipo === 'protocolo') {
                params = `protocolo=${dadosBusca.valor}`;
            } else {
                params = `cpf=${dadosBusca.cpf}&data_nascimento=${dadosBusca.data_nascimento}`;
            }

            const { data } = await api.get(`solicitacoes/consultar-status/?${params}`);
            this.consulta.resultado = data;
        } catch (err) {
            if (err.response?.status === 404) {
                this.consulta.erro = "Cadastro não localizado. Verifique os dados.";
            } else {
                this.consulta.erro = "Erro ao consultar sistema.";
            }
        } finally {
            this.consulta.loading = false;
        }
    },

    resetForm() {
      this.$reset();
    },

    async atualizarExistente() {
      this.loading = true;
      try {
          // 1. PREPARA DADOS DO BENEFICIÁRIO (Texto + Foto + Responsáveis)
          const formData = new FormData();

          // A. Campos Básicos (Nome, CPF, Endereço...)
          Object.keys(this.beneficiario).forEach(key => {
              // Ignora campos complexos ou nulos para não quebrar o FormData
              if (this.beneficiario[key] && key !== 'responsaveis' && key !== 'foto') {
                  formData.append(key, this.beneficiario[key]);
              }
          });

          // B. Foto do Perfil (Só envia se o usuário selecionou uma nova no input)
          // Nota: this.anexos.foto guarda o arquivo 'File' novo. 
          if (this.anexos.foto) {
              console.log("Anexando nova foto ao envio:", this.anexos.foto.name); // <--- DEBUG
              formData.append('foto', this.anexos.foto);
          } else {
              console.log("Nenhuma foto nova selecionada. Mantendo a antiga.");
          }

          // C. Responsáveis (Lista)
          // Precisamos reenviar a lista para o backend atualizar os vínculos
          this.responsaveis.forEach((resp, index) => {
              formData.append(`responsaveis[${index}]nome`, resp.nome);
              formData.append(`responsaveis[${index}]cpf`, resp.cpf);
              formData.append(`responsaveis[${index}]telefone`, resp.telefone);
              formData.append(`responsaveis[${index}]perfil`, resp.perfil);
              
              // Se necessário reenviar endereço dos responsáveis (caso seu backend exija):
              // formData.append(`responsaveis[${index}]cep`, this.beneficiario.cep);
              // ... outros campos de endereço
          });

          // D. Envia atualização do Beneficiário
          await api.patch(`beneficiarios/${this.beneficiario.id}/`, formData, {
              headers: { 'Content-Type': 'multipart/form-data' }
          });

          // 2. FUNÇÃO INTELIGENTE DE UPLOAD DE DOCUMENTOS
          const processarDocumento = async (arquivoInput, docExistente, tipo) => {
              // Se o usuário não selecionou arquivo novo, ignora
              if (!arquivoInput) return;

              const docData = new FormData();
              docData.append('arquivo', arquivoInput);
              
              // Força status PENDENTE para o fiscal analisar de novo
              docData.append('status', 'PENDENTE'); 
              docData.append('motivo_rejeicao', '');

              if (docExistente && docExistente.id) {
                  // Cenario A: Substitui documento existente (PATCH)
                  console.log(`Atualizando doc ${tipo} ID: ${docExistente.id}`);
                  await api.patch(`documentos/${docExistente.id}/`, docData, {
                      headers: { 'Content-Type': 'multipart/form-data' }
                  });
              } else {
                  // Cenario B: Cria documento novo que faltava (POST)
                  docData.append('solicitacao', this.idSolicitacaoEdicao);
                  docData.append('tipo', tipo);
                  await api.post('documentos/', docData, {
                      headers: { 'Content-Type': 'multipart/form-data' }
                  });
              }
          };

          // 3. PROCESSA CADA TIPO DE DOCUMENTO
          await processarDocumento(this.anexos.laudo, this.statusLaudo, 'LAUDO');
          await processarDocumento(this.anexos.rg_beneficiario, this.statusRgBenef, 'RG_BENEF');
          await processarDocumento(this.anexos.comprovante_residencia, this.statusCompRes, 'COMP_RES');
          await processarDocumento(this.anexos.rg_responsavel, this.statusRgResp, 'RG_RESP');

          // 4. ATUALIZA STATUS DA SOLICITAÇÃO
          // Move de 'PENDENTE' (Vermelho) para 'ANALISE' (Amarelo) no Kanban
          await api.patch(`solicitacoes/${this.idSolicitacaoEdicao}/`, { 
               status: 'ANALISE'
          });
          
          this.success = true; // Ativa a tela de sucesso

      } catch (error) {
          console.error(error);
          this.error = "Erro ao enviar correções. Verifique os dados.";
          
          // Captura erros de validação do backend para pintar os campos de vermelho
          if (error.response && error.response.data) {
              this.errosCampos = error.response.data;
          }
      } finally {
          this.loading = false;
      }
    },

    salvarNoDispositivo(dados) {
        // Salvamos apenas o necessário para refazer a chamada da API
        const dadosPersistencia = {
            protocolo: dados.protocolo,
            cpf: dados.cpf,             // Atenção: Em produção real, ideal seria encriptar
            data_nascimento: dados.data_nascimento,
            nome: dados.nome_beneficiario,
            status: dados.status
        };
        
        localStorage.setItem('ciptea_user', JSON.stringify(dadosPersistencia));
        this.perfilSalvo = dadosPersistencia;
    },
    
    carregarDoDispositivo() {
        const salvo = localStorage.getItem('ciptea_user');
        if (salvo) {
            this.perfilSalvo = JSON.parse(salvo);
            return true;
        }
        return false;
    },

    esquecerDispositivo() {
        localStorage.removeItem('ciptea_user');
        this.perfilSalvo = null;
        this.consulta.resultado = null;
    },

    adicionarResponsavel() {
      this.responsaveis.push({ nome: '', cpf: '', telefone: '', perfil: null });
    },

    removerResponsavel(index) {
      if (this.responsaveis.length > 1) {
          this.responsaveis.splice(index, 1);
      }
    },
  }
});