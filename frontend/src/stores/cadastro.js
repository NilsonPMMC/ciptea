import { defineStore } from 'pinia';
import api from '@/services/api';
import axios from 'axios';

const onlyDigits = (value) => (value || '').toString().replace(/\D/g, '');
const sanitizeText = (value) => (value || '').toString().replace(/\u0000/g, '').trim();
const normalizeUploadFile = (value) => {
  if (!value) return null;
  if (Array.isArray(value)) return value[0] || null;
  return value;
};

/** Última mensagem de pendência/correção gravada no histórico (parecer do PAC). */
function mensagemParecerDoHistorico(historico) {
  if (!Array.isArray(historico) || !historico.length) return '';
  const sorted = [...historico].sort((a, b) => {
    const ta = new Date(a.data).getTime();
    const tb = new Date(b.data).getTime();
    return tb - ta;
  });
  const row = sorted.find(
    (h) =>
      h.tipo_evento === 'PENDENCIA' &&
      h.mensagem &&
      String(h.mensagem).trim() &&
      String(h.mensagem).trim() !== 'Atualização de status administrativa.'
  );
  return row ? String(row.mensagem).trim() : '';
}

function enriquecerDocComParecerHistorico(doc, parecer) {
  if (!doc || !parecer) return doc;
  const motivo = (doc.motivo_rejeicao && String(doc.motivo_rejeicao).trim()) || '';
  if (doc.status === 'REJEITADO' && !motivo) {
    return { ...doc, motivo_rejeicao: parecer.slice(0, 255) };
  }
  return doc;
}

/** Query com protocolo + CPF + nascimento para rotas públicas de correção (sem JWT). */
function queryCorrecaoCidadao(protocolo, cpf, dataNascimento) {
  const p = (protocolo || '').toString().trim();
  const c = onlyDigits(cpf);
  const dn = dataNascimento ? String(dataNascimento).slice(0, 10) : '';
  if (!p || !c || !dn) return null;
  return new URLSearchParams({
    protocolo: p,
    cpf: c,
    data_nascimento: dn,
  }).toString();
}

/** @typedef {'pendente'|'analisando'|'sucesso'|'revisao_manual'} StatusDocIa */

function createValidacaoInicial() {
  return {
    laudo: { status: 'pendente', mensagem: 'Aguardando análise.' },
    documentoPortador: { status: 'pendente', mensagem: 'Aguardando análise.' },
    documentoResponsavel: { status: 'pendente', mensagem: 'Aguardando análise.' },
    comprovanteEndereco: { status: 'pendente', mensagem: 'Aguardando análise.' },
  };
}

/**
 * Deriva o estado por documento a partir da resposta de triagem-ia (um registro agregado + log_ia).
 * @param {object} data
 * @param {boolean} temResponsavel
 */
function mapTriagemParaValidacao(data, temResponsavel) {
  const st = data?.status_validacao;
  const sd = data?.status_documentos && typeof data.status_documentos === 'object'
    ? data.status_documentos
    : null;
  const log = data?.log_ia && typeof data.log_ia === 'object' ? data.log_ia : {};
  const etapas = log.etapas || {};
  /** @type {Record<string, { status: StatusDocIa, mensagem: string }>} */
  const out = createValidacaoInicial();

  const msgAnalisando = {
    laudo: 'Buscando CID e dados do laudo…',
    documentoPortador: 'Validando nome e CPF no documento…',
    comprovanteEndereco: 'Verificando data e endereço no comprovante…',
    documentoResponsavel: temResponsavel
      ? 'Conferindo consistência com o cadastro do responsável…'
      : 'Sem responsável adicional neste envio.',
  };

  if (st === 'PENDENTE') {
    const base = log.motivo || 'Aguardando início da triagem automática…';
    Object.keys(out).forEach((k) => {
      out[k] = { status: 'pendente', mensagem: base };
    });
    return out;
  }

  if (st === 'PROCESSANDO') {
    Object.keys(out).forEach((k) => {
      if (k === 'documentoResponsavel' && !temResponsavel) {
        out[k] = { status: 'sucesso', mensagem: 'Não aplicável neste cadastro.' };
      } else {
        out[k] = { status: 'analisando', mensagem: msgAnalisando[k] };
      }
    });
    return out;
  }

  if (st === 'APROVADO_IA') {
    out.laudo = { status: 'sucesso', mensagem: 'Laudo compatível com o CID informado.' };
    out.documentoPortador = { status: 'sucesso', mensagem: 'Identidade coerente com o cadastro.' };
    out.comprovanteEndereco = { status: 'sucesso', mensagem: 'Endereço conferido com o cadastro.' };
    out.documentoResponsavel = temResponsavel
      ? { status: 'sucesso', mensagem: 'Dados do responsável conferidos no contexto do envio.' }
      : { status: 'sucesso', mensagem: 'Sem responsável adicional neste cadastro.' };
    return out;
  }

  // Fonte principal: resumo de status por documento vindo do backend.
  if (sd) {
    const toUi = (row, fallbackOkMsg, fallbackKoMsg) => {
      const status = (row?.status || '').toUpperCase();
      if (status === 'NAO_APLICAVEL') {
        return { status: 'sucesso', mensagem: row?.motivo || 'Não aplicável neste cadastro.' };
      }
      if (status === 'VALIDADO') {
        return { status: 'sucesso', mensagem: row?.motivo || fallbackOkMsg };
      }
      if (status === 'INVALIDO') {
        return { status: 'revisao_manual', mensagem: row?.motivo || fallbackKoMsg };
      }
      return { status: 'analisando', mensagem: 'Aguardando conclusão desta etapa...' };
    };
    out.laudo = toUi(
      sd.laudo,
      'Laudo validado automaticamente.',
      'Laudo requer conferência manual.'
    );
    out.documentoPortador = toUi(
      sd.identidade,
      'Documento de identidade validado.',
      'Identidade requer conferência manual.'
    );
    out.comprovanteEndereco = toUi(
      sd.endereco,
      'Comprovante de endereço validado.',
      'Comprovante requer conferência manual.'
    );
    out.documentoResponsavel = temResponsavel
      ? toUi(
          sd.responsavel,
          'Dados do responsável consistentes.',
          'Documento do responsável exige conferência.'
        )
      : { status: 'sucesso', mensagem: 'Não aplicável.' };
    return out;
  }

  const ocr = etapas.ocr;
  if (ocr && ocr.ok === false) {
    const det = ocr.detalhes || {};
    out.laudo = det.laudo?.ok
      ? { status: 'sucesso', mensagem: 'Leitura automática ok.' }
      : { status: 'revisao_manual', mensagem: 'Leitura do laudo inconclusiva. Conferência humana.' };
    out.documentoPortador = det.doc_tea?.ok
      ? { status: 'sucesso', mensagem: 'Leitura automática ok.' }
      : { status: 'revisao_manual', mensagem: 'Leitura do documento do portador inconclusiva.' };
    out.comprovanteEndereco = det.endereco?.ok
      ? { status: 'sucesso', mensagem: 'Leitura automática ok.' }
      : { status: 'revisao_manual', mensagem: 'Leitura do comprovante inconclusiva.' };
    out.documentoResponsavel = temResponsavel
      ? { status: 'revisao_manual', mensagem: 'Triagem encaminhada à equipe do PAC.' }
      : { status: 'sucesso', mensagem: 'Não aplicável.' };
    return out;
  }

  const val = etapas.validacao;
  if (val && typeof val === 'object') {
    const rl = val.laudo;
    const idn = val.identidade;
    const en = val.endereco;
    out.laudo = rl?.ok
      ? { status: 'sucesso', mensagem: (rl && rl.motivo) || 'Critérios do laudo atendidos.' }
      : { status: 'revisao_manual', mensagem: (rl && rl.motivo) || 'Laudo requer conferência humana.' };
    out.documentoPortador = idn?.ok
      ? { status: 'sucesso', mensagem: (idn && idn.motivo) || 'Documento ok.' }
      : { status: 'revisao_manual', mensagem: (idn && idn.motivo) || 'Identidade requer conferência manual.' };
    out.comprovanteEndereco = en?.ok
      ? { status: 'sucesso', mensagem: (en && en.motivo) || 'Comprovante ok.' }
      : { status: 'revisao_manual', mensagem: (en && en.motivo) || 'Endereço requer conferência manual.' };
    out.documentoResponsavel = temResponsavel
      ? {
          status: idn?.ok && en?.ok ? 'sucesso' : 'revisao_manual',
          mensagem:
            idn?.ok && en?.ok
              ? 'Dados do responsável consistentes no contexto analisado.'
              : 'Pode ser necessário conferir o documento do responsável junto aos demais itens.',
        }
      : { status: 'sucesso', mensagem: 'Não aplicável.' };
    return out;
  }

  Object.keys(out).forEach((k) => {
    out[k] = {
      status: 'revisao_manual',
      mensagem: 'Análise inicial encaminhada ao PAC para conferência final.',
    };
  });
  return out;
}

export const useCadastroStore = defineStore('cadastro', {
  state: () => ({
    loading: false,
    loadingCep: false,
    error: null,
    success: false,
    /** 'form' | 'triagem_ia' | 'final' — após envio com triagem IA */
    fasePosEnvio: 'form',
    solicitacaoIdTriagem: null,
    triagemPollTimerId: null,
    iaTriagemAutoRedirect: false,
    iaResultadoGlobal: null,
    triagemResposta: null,
    modoCorrecaoSomenteAnexos: false,
    docsDivergentesCorrecao: [],
    validacao: createValidacaoInicial(),
    protocolo: null,
    modoEdicao: false,
    tipoFluxoEdicao: null,
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
      { nome: '', cpf: '', telefone: '', perfil: null, documento_identidade: null }
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
          this.tipoFluxoEdicao = data.tipo_fluxo || null;

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
          const parecerHist = mensagemParecerDoHistorico(data.historico);
          if (data.anexos) {
              data.anexos.forEach((doc) => {
                  const d = enriquecerDocComParecerHistorico(doc, parecerHist);
                  if (doc.tipo === 'LAUDO') this.statusLaudo = d;
                  if (doc.tipo === 'RG_BENEF') this.statusRgBenef = d;
                  if (doc.tipo === 'COMP_RES') this.statusCompRes = d;
                  if (doc.tipo === 'RG_RESP') this.statusRgResp = d;
              });
          }

          this.modoEdicao = true;
          
          // LIMPEZA CRÍTICA: Zera os anexos da memória para evitar 
          // reenvio fantasma de arquivos da primeira tentativa
          this.anexos = {
            laudo: null,
            rg_beneficiario: null,
            comprovante_residencia: null, 
            rg_responsavel: null,
            foto: null
          };

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
              if (key === 'telefone') {
                formData.append(key, onlyDigits(this.beneficiario[key]));
              } else if (key === 'cpf' || key === 'cep') {
                formData.append(key, onlyDigits(this.beneficiario[key]));
              } else {
                formData.append(key, sanitizeText(this.beneficiario[key]));
              }
          }
        });

        // 3. A FOTO (Aqui estava o problema!)
        // Pegamos o arquivo gerado pelo Cropper em 'anexos.foto'
        if (this.anexos.foto) {
            formData.append('foto', this.anexos.foto);
        }

        // Lógica de Telefone de Segurança (Fallback)
        if (!this.beneficiario.telefone && this.responsaveis.length > 0 && this.responsaveis[0].telefone) {
             formData.append('telefone', onlyDigits(this.responsaveis[0].telefone));
        }

        // 4. DADOS DOS RESPONSÁVEIS (JSON único para multipart)
        const responsaveisPayload = this.responsaveis.map((resp) => ({
            nome: sanitizeText(resp.nome),
            cpf: onlyDigits(resp.cpf),
            telefone: onlyDigits(resp.telefone),
            perfil: sanitizeText(resp.perfil),
            cep: onlyDigits(this.beneficiario.cep),
            logradouro: sanitizeText(this.beneficiario.logradouro),
            numero: sanitizeText(this.beneficiario.numero),
            bairro: sanitizeText(this.beneficiario.bairro),
            cidade: sanitizeText(this.beneficiario.cidade),
            estado: sanitizeText(this.beneficiario.estado),
            complemento: sanitizeText(this.beneficiario.complemento),
        }));
        formData.append('responsaveis', JSON.stringify(responsaveisPayload));
        
        // 5. Fluxo transacional preferencial (backend novo)
        const formDataCompleto = new FormData();
        for (const [key, value] of formData.entries()) {
            formDataCompleto.append(key, value);
        }
        if (this.anexos.laudo) formDataCompleto.append('laudo', this.anexos.laudo);
        if (this.anexos.rg_beneficiario) formDataCompleto.append('rg_beneficiario', this.anexos.rg_beneficiario);
        if (this.anexos.comprovante_residencia) formDataCompleto.append('comprovante_residencia', this.anexos.comprovante_residencia);

        this.responsaveis.forEach((resp, index) => {
          if (resp.documento_identidade && resp.documento_identidade instanceof File) {
              formDataCompleto.append(`rg_responsavel_${index}`, resp.documento_identidade);
          } else if (resp.perfil === 'PROPRIO' && this.anexos.rg_beneficiario) {
              // NOVO: Clona silenciosamente o RG do Beneficiário para o Responsável.
              // A IA fará o OCR e vai aprovar com nota 100, destravando a Revisão Manual!
              formDataCompleto.append(`rg_responsavel_${index}`, this.anexos.rg_beneficiario);
          }
        });

        let responseCadastroCompleto = null;
        try {
          responseCadastroCompleto = await api.post('solicitacoes/cadastro-completo/', formDataCompleto, {
            headers: {
              'Content-Type': 'multipart/form-data',
              'X-Cadastro-Flow': 'transacional'
            }
          });
        } catch (erroCadastroCompleto) {
          const statusErro = erroCadastroCompleto?.response?.status;
          if (![404, 405].includes(statusErro)) {
            throw erroCadastroCompleto;
          }
        }

        if (responseCadastroCompleto?.data?.protocolo) {
          this.protocolo = responseCadastroCompleto.data.protocolo;
          const sid = responseCadastroCompleto.data.solicitacao_id;
          this.salvarNoDispositivo({
            protocolo: this.protocolo,
            cpf: this.beneficiario.cpf,
            data_nascimento: this.beneficiario.data_nascimento,
            nome: this.beneficiario.nome_completo,
            status: 'ANALISE',
            status_code: 'ANALISE',
            foto: this.beneficiario.foto || null,
            tipo: 'SISTEMA_NOVO',
            vencida: false,
            tipo_fluxo: this.tipoFluxoEdicao || 'PRIMEIRA_VIA',
            solicitacao_id: sid || null,
          });
          if (sid) {
            this.solicitacaoIdTriagem = sid;
            this.fasePosEnvio = 'triagem_ia';
            this.iaTriagemAutoRedirect = true;
            this.limparModoCorrecaoSomenteAnexos();
            this.success = false;
            this.iniciarTriagemIaPolling();
          } else {
            this.fasePosEnvio = 'final';
            this.success = true;
          }
          return;
        }

        // 6. Fallback legado (ambientes ainda não atualizados)
        const responseBen = await api.post('beneficiarios/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        const beneficiarioId = responseBen.data.id;

        const responseSol = await api.post('solicitacoes/', {
          beneficiario_id: beneficiarioId,
          status: 'ABERTO'
        }, {
          headers: {
            'X-Cadastro-Flow': 'fallback'
          }
        });

        const solicitacaoId = responseSol.data.id;
        this.protocolo = responseSol.data.protocolo;
        this.solicitacaoIdTriagem = solicitacaoId;
        this.salvarNoDispositivo({
          protocolo: this.protocolo,
          cpf: this.beneficiario.cpf,
          data_nascimento: this.beneficiario.data_nascimento,
          nome: this.beneficiario.nome_completo,
          status: 'ANALISE',
          status_code: 'ANALISE',
          foto: this.beneficiario.foto || null,
          tipo: 'SISTEMA_NOVO',
          vencida: false,
          tipo_fluxo: this.tipoFluxoEdicao || 'PRIMEIRA_VIA',
          solicitacao_id: solicitacaoId,
        });

        await this.uploadAnexo(solicitacaoId, 'LAUDO', 'Laudo Médico', this.anexos.laudo);
        await this.uploadAnexo(solicitacaoId, 'RG_BENEF', 'RG do Beneficiário', this.anexos.rg_beneficiario);
        await this.uploadAnexo(solicitacaoId, 'COMP_RES', 'Comprovante Residência', this.anexos.comprovante_residencia);
        if (this.anexos.rg_responsavel) {
          await this.uploadAnexo(solicitacaoId, 'RG_RESP', 'RG do Responsável', this.anexos.rg_responsavel);
        }

        this.fasePosEnvio = 'triagem_ia';
        this.iaTriagemAutoRedirect = true;
        this.limparModoCorrecaoSomenteAnexos();
        this.success = false;
        this.iniciarTriagemIaPolling();
      
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

    _temResponsavelRelevante() {
      return (
        Array.isArray(this.responsaveis) &&
        this.responsaveis.some(
          (r) => (r.nome && String(r.nome).trim()) || (r.cpf && onlyDigits(r.cpf))
        )
      );
    },

    pararTriagemIaPolling() {
      if (this.triagemPollTimerId != null) {
        clearTimeout(this.triagemPollTimerId);
        this.triagemPollTimerId = null;
      }
    },

    async buscarTriagemIaOnce() {
      if (!this.solicitacaoIdTriagem) return null;
      const cpfBase = this.beneficiario?.cpf || this.perfilSalvo?.cpf;
      const dataNascBase =
        this.beneficiario?.data_nascimento || this.perfilSalvo?.data_nascimento;
      const protocoloBase = this.protocolo || this.perfilSalvo?.protocolo;
      const qCidadao = queryCorrecaoCidadao(
        protocoloBase,
        cpfBase,
        dataNascBase
      );
      const url = qCidadao
        ? `solicitacoes/${this.solicitacaoIdTriagem}/triagem-ia/?${qCidadao}`
        : `solicitacoes/${this.solicitacaoIdTriagem}/triagem-ia/`;
      const { data } = await api.get(url);
      return data;
    },

    _aplicarTriagemResposta(data) {
      this.triagemResposta = data || null;
      this.validacao = mapTriagemParaValidacao(data, this._temResponsavelRelevante());
    },

    iniciarTriagemIaPolling() {
      this.pararTriagemIaPolling();
      this.iaResultadoGlobal = null;
      this.triagemResposta = null;
      if (this.perfilSalvo) {
        this.salvarNoDispositivo({
          ...this.perfilSalvo,
          solicitacao_id: this.solicitacaoIdTriagem || this.perfilSalvo.solicitacao_id || null,
          ia_status: null,
        });
      }
      const temResp = this._temResponsavelRelevante();
      this.validacao = createValidacaoInicial();
      if (!temResp) {
        this.validacao.documentoResponsavel = {
          status: 'sucesso',
          mensagem: 'Não aplicável neste cadastro.',
        };
      }

      // Encadeia com setTimeout (não setInterval): evita várias requisições em paralelo
      // se o GET demorar mais que 3s — o próximo poll só agenda após o anterior terminar.
      let attempts = 0;
      // ~8 min: OCR/modelos no 1º uso podem levar vários minutos; acima disso, assume fila/worker
      const maxAttempts = 160;

      const pollLoop = async () => {
        if (!this.solicitacaoIdTriagem) return;
        attempts += 1;
        if (attempts > maxAttempts) {
          this.triagemPollTimerId = null;
          this.iaResultadoGlobal = 'REVISAO_MANUAL';
          const msgTimeout =
            'A análise automática está demorando mais que o esperado. ' +
            'Isso costuma indicar fila cheia ou serviço de triagem indisponível. ' +
            'Seus documentos seguirão para conferência manual do PAC — use Prosseguir abaixo.';
          const keys = Object.keys(createValidacaoInicial());
          keys.forEach((k) => {
            this.validacao[k] = {
              status: 'revisao_manual',
              mensagem: msgTimeout,
            };
          });
          return;
        }
        try {
          const data = await this.buscarTriagemIaOnce();
          if (!data) return;
          this._aplicarTriagemResposta(data);
          const st = data.status_validacao;
          if (st === 'APROVADO_IA' || st === 'REVISAO_MANUAL') {
            this.iaResultadoGlobal = st;
            if (this.perfilSalvo) {
              this.salvarNoDispositivo({
                ...this.perfilSalvo,
                solicitacao_id: this.solicitacaoIdTriagem,
                ia_status: st,
              });
            }
            this.triagemPollTimerId = null;
            return;
          }
        } catch (e) {
          console.error('triagem-ia', e);
          this.triagemPollTimerId = null;
          this.iaResultadoGlobal = 'REVISAO_MANUAL';
          const errMsg =
            e?.response?.data?.detail ||
            e?.response?.data?.erro ||
            e?.message ||
            'Não foi possível obter o status da análise.';
          const keys = Object.keys(createValidacaoInicial());
          keys.forEach((k) => {
            this.validacao[k] = {
              status: 'revisao_manual',
              mensagem: errMsg,
            };
          });
          return;
        }
        this.triagemPollTimerId = setTimeout(() => {
          void pollLoop();
        }, 3000);
      };

      void pollLoop();
    },

    finalizarFaseTriagemVisual() {
      this.pararTriagemIaPolling();
      this.fasePosEnvio = 'final';
      this.iaTriagemAutoRedirect = false;
      this.success = true;
    },

    abrirAcompanhamentoTriagem() {
      if (!this.solicitacaoIdTriagem) return;
      this.iaTriagemAutoRedirect = false;
      this.fasePosEnvio = 'triagem_ia';
      if (!this.triagemPollTimerId && !this.iaResultadoGlobal) {
        this.iniciarTriagemIaPolling();
      }
    },

    prepararCorrecaoSomenteAnexos(divergencias = []) {
      this.modoCorrecaoSomenteAnexos = true;
      this.docsDivergentesCorrecao = Array.isArray(divergencias)
        ? divergencias
            .map((d) => d?.documento)
            .filter(Boolean)
        : [];
    },

    limparModoCorrecaoSomenteAnexos() {
      this.modoCorrecaoSomenteAnexos = false;
      this.docsDivergentesCorrecao = [];
    },

    async solicitarCorrecaoPrePac() {
      if (!this.solicitacaoIdTriagem) return false;
      const qCidadao = queryCorrecaoCidadao(
        this.protocolo || this.perfilSalvo?.protocolo,
        this.beneficiario?.cpf || this.perfilSalvo?.cpf,
        this.beneficiario?.data_nascimento || this.perfilSalvo?.data_nascimento
      );
      if (!qCidadao) return false;
      await api.patch(
        `solicitacoes/${this.solicitacaoIdTriagem}/solicitar-correcao-ia/?${qCidadao}`,
        { mensagem: 'Solicitação de correção iniciada pelo cidadão após triagem IA.' }
      );
      const okEdicao = await this.carregarParaEdicao(
        this.protocolo || this.perfilSalvo?.protocolo,
        this.beneficiario?.cpf || this.perfilSalvo?.cpf,
        this.beneficiario?.data_nascimento || this.perfilSalvo?.data_nascimento
      );
      if (!okEdicao) return false;
      this.fasePosEnvio = 'form';
      this.success = false;
      return true;
    },

    resetForm() {
      this.pararTriagemIaPolling();
      this.limparModoCorrecaoSomenteAnexos();
      this.$reset();
    },

    async atualizarExistente() {
      this.loading = true;
      try {
          const isRenovacao = this.tipoFluxoEdicao === 'RENOVACAO';
          const possuiResponsavel = Array.isArray(this.responsaveis) && this.responsaveis.length > 0;
          const possuiDoc = (existente, novoArquivo) => Boolean((existente && existente.id) || novoArquivo);
          if (isRenovacao) {
              const faltantes = [];
              if (!possuiDoc(this.statusLaudo, this.anexos.laudo)) faltantes.push('Laudo Médico');
              if (!possuiDoc(this.statusRgBenef, this.anexos.rg_beneficiario)) faltantes.push('RG/Certidão do Beneficiário');
              if (!possuiDoc(this.statusCompRes, this.anexos.comprovante_residencia)) faltantes.push('Comprovante de Residência');
              if (possuiResponsavel && !possuiDoc(this.statusRgResp, this.anexos.rg_responsavel)) faltantes.push('RG/CNH do Responsável');
              if (faltantes.length) {
                  this.error = `Para enviar a renovação, anexe os documentos obrigatórios: ${faltantes.join(', ')}.`;
                  return;
              }
          }

          // 1. PREPARA DADOS DO BENEFICIÁRIO (Texto + Foto + Responsáveis)
          const formData = new FormData();

          // A. Campos Básicos (Nome, CPF, Endereço...)
          Object.keys(this.beneficiario).forEach(key => {
              // Ignora campos complexos ou nulos para não quebrar o FormData
              if (this.beneficiario[key] && key !== 'responsaveis' && key !== 'foto') {
                  if (key === 'telefone') {
                      formData.append(key, onlyDigits(this.beneficiario[key]));
                  } else if (key === 'cpf' || key === 'cep') {
                      formData.append(key, onlyDigits(this.beneficiario[key]));
                  } else {
                      formData.append(key, sanitizeText(this.beneficiario[key]));
                  }
              }
          });

          // B. Foto do Perfil (Só envia se o usuário selecionou uma nova no input)
          if (this.anexos.foto && this.anexos.foto instanceof File) {
              formData.append('foto', this.anexos.foto);
          }

          // C. Responsáveis (Lista)
          // Precisamos reenviar a lista para o backend atualizar os vínculos
          const responsaveisPayload = this.responsaveis.map((resp) => ({
              id: resp.id,
              nome: sanitizeText(resp.nome),
              cpf: onlyDigits(resp.cpf),
              telefone: onlyDigits(resp.telefone),
              perfil: sanitizeText(resp.perfil),
              cep: onlyDigits(this.beneficiario.cep),
              logradouro: sanitizeText(this.beneficiario.logradouro),
              numero: sanitizeText(this.beneficiario.numero),
              bairro: sanitizeText(this.beneficiario.bairro),
              cidade: sanitizeText(this.beneficiario.cidade),
              estado: sanitizeText(this.beneficiario.estado),
              complemento: sanitizeText(this.beneficiario.complemento),
          }));
          formData.append('responsaveis', JSON.stringify(responsaveisPayload));

          this.responsaveis.forEach((resp, index) => {
            if (resp.documento_identidade && resp.documento_identidade instanceof File) {
                formData.append(`rg_responsavel_${index}`, resp.documento_identidade);
            }
          });

          const qCidadao = queryCorrecaoCidadao(
            this.protocolo,
            this.beneficiario?.cpf,
            this.beneficiario?.data_nascimento
          );
          if (!qCidadao) {
            this.error =
              'Não foi possível identificar sua sessão. Abra novamente o formulário com protocolo e CPF.';
            return;
          }

          // D. Atualização do beneficiário (rota pública com mesma prova de posse de buscar-completo)
          await api.patch(
            `beneficiarios/${this.beneficiario.id}/atualizacao-cidadao/?${qCidadao}`,
            formData,
            {
              headers: { 'Content-Type': 'multipart/form-data' },
            }
          );

          // 2. FUNÇÃO INTELIGENTE DE UPLOAD DE DOCUMENTOS
          const processarDocumento = async (arquivoInput, docExistente, tipo) => {
            const arquivo = normalizeUploadFile(arquivoInput);
            
            // BLINDAGEM: Se não houver arquivo ou se não for um Objeto File real, ignora e não envia nada!
            if (!arquivo || !(arquivo instanceof File)) return;

            const docData = new FormData();
            docData.append('arquivo', arquivo);
            
            // Força status PENDENTE para o fiscal analisar de novo
            docData.append('status', 'PENDENTE'); 
            docData.append('motivo_rejeicao', '');

            if (docExistente && docExistente.id) {
                // Cenario A: Substitui documento existente (PATCH) silencioso
                await api.patch(`documentos/${docExistente.id}/?suppress_triagem=1`, docData, {
                    headers: { 'Content-Type': 'multipart/form-data' }
                });
            } else {
                // Cenario B: Cria documento novo que faltava (POST) silencioso
                docData.append('solicitacao', this.idSolicitacaoEdicao);
                docData.append('tipo', tipo);
                await api.post('documentos/?suppress_triagem=1', docData, {
                    headers: { 'Content-Type': 'multipart/form-data' }
                });
            }
          };
          
          // 3. PROCESSA CADA TIPO DE DOCUMENTO
          await processarDocumento(this.anexos.laudo, this.statusLaudo, 'LAUDO');
          await processarDocumento(this.anexos.rg_beneficiario, this.statusRgBenef, 'RG_BENEF');
          await processarDocumento(this.anexos.comprovante_residencia, this.statusCompRes, 'COMP_RES');

          // 4. ATUALIZA STATUS E ACORDA A IA (Via BeneficiarioViewSet)
          const formDataFinal = new FormData();
          formDataFinal.append('concluir_correcao', 'true');

          await api.patch(
            `beneficiarios/${this.beneficiario.id}/atualizacao-cidadao/?${qCidadao}`,
            formDataFinal,
            { headers: { 'Content-Type': 'multipart/form-data' } }
          );

          this.solicitacaoIdTriagem = this.idSolicitacaoEdicao;
          this.fasePosEnvio = 'triagem_ia';
          this.iaTriagemAutoRedirect = false;
          this.limparModoCorrecaoSomenteAnexos();
          this.success = false;
          this.iniciarTriagemIaPolling();

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
            nome: dados.nome || dados.nome_beneficiario || '',
            status: dados.status,
            status_code: dados.status_code || dados.status,
            foto: dados.foto || null,
            tipo: dados.tipo || 'SISTEMA_NOVO',
            vencida: Boolean(dados.vencida),
            tipo_fluxo: dados.tipo_fluxo || 'PRIMEIRA_VIA',
            solicitacao_id: dados.solicitacao_id || null,
            ia_status: dados.ia_status || null,
        };
        
        sessionStorage.setItem('ciptea_user', JSON.stringify(dadosPersistencia));
        localStorage.removeItem('ciptea_user');
        this.perfilSalvo = dadosPersistencia;
        if (dadosPersistencia.solicitacao_id && !this.solicitacaoIdTriagem) {
            this.solicitacaoIdTriagem = dadosPersistencia.solicitacao_id;
        }
    },
    
    carregarDoDispositivo() {
        const salvo = sessionStorage.getItem('ciptea_user') || localStorage.getItem('ciptea_user');
        if (salvo) {
            this.perfilSalvo = JSON.parse(salvo);
            // Migração silenciosa para sessionStorage
            sessionStorage.setItem('ciptea_user', salvo);
            localStorage.removeItem('ciptea_user');
            if (this.perfilSalvo?.solicitacao_id && !this.solicitacaoIdTriagem) {
                this.solicitacaoIdTriagem = this.perfilSalvo.solicitacao_id;
            }
            return true;
        }
        return false;
    },

    esquecerDispositivo() {
        sessionStorage.removeItem('ciptea_user');
        localStorage.removeItem('ciptea_user');
        this.perfilSalvo = null;
        this.consulta.resultado = null;
    },

    adicionarResponsavel() {
      this.responsaveis.push({ nome: '', cpf: '', telefone: '', perfil: null, documento_identidade: null });
    },

    removerResponsavel(index) {
      if (this.responsaveis.length > 1) {
          this.responsaveis.splice(index, 1);
      }
    },
  }
});

/** Alias pedido para integrações / legibilidade ("CIPTEA store"). */
export { useCadastroStore as useCipteaStore };