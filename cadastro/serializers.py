from rest_framework import serializers
import json
from datetime import date
from .models import Beneficiario, Responsavel, Solicitacao, Documento, Historico, ValidacaoDocumentoIA

class ResponsavelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Responsavel
        fields = [
            'id',
            'nome',
            'cpf',
            'telefone',
            'telefone2',
            'email',
            'rg',
            'data_nascimento',
            'perfil',
            'cep',
            'logradouro',
            'numero',
            'complemento',
            'bairro',
            'cidade',
            'estado',
        ]

class BeneficiarioSerializer(serializers.ModelSerializer):
    responsaveis = ResponsavelSerializer(many=True)

    class Meta:
        model = Beneficiario
        fields = '__all__'

    # NOVO: Trava de Maioridade na API
    def validate(self, data):
        responsaveis_data = data.get('responsaveis') or []
        
        # Pega a data da requisição ou do banco de dados (se for edição)
        data_nascimento = data.get('data_nascimento')
        if not data_nascimento and self.instance:
            data_nascimento = self.instance.data_nascimento

        # Verifica se algum responsável declarou ser o próprio beneficiário
        has_proprio = any(isinstance(r, dict) and r.get('perfil') == 'PROPRIO' for r in responsaveis_data)

        if has_proprio and data_nascimento:
            hoje = date.today()
            idade = hoje.year - data_nascimento.year - ((hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day))
            if idade < 18:
                raise serializers.ValidationError({
                    "data_nascimento": "O beneficiário deve ter 18 anos ou mais para ser o próprio responsável."
                })
                
        return super().validate(data)

    def to_internal_value(self, data):
        # multipart/form-data vem como QueryDict: não dá para usar setlist() com lista de dicts
        # (vira string inválida / some o campo) → "responsaveis: Este campo é obrigatório."
        if hasattr(data, 'getlist'):
            combined = {}
            raw_responsaveis = data.get('responsaveis')
            for key in data.keys():
                if key == 'responsaveis':
                    continue
                vals = data.getlist(key)
                combined[key] = vals[0] if len(vals) == 1 else vals
        else:
            combined = dict(data)
            raw_responsaveis = combined.pop('responsaveis', None)

        if isinstance(raw_responsaveis, str) and raw_responsaveis.strip():
            try:
                parsed = json.loads(raw_responsaveis)
                if isinstance(parsed, list):
                    combined['responsaveis'] = parsed
            except (TypeError, json.JSONDecodeError):
                pass
        elif isinstance(raw_responsaveis, list):
            combined['responsaveis'] = raw_responsaveis

        return super().to_internal_value(combined)

    def create(self, validated_data):
        responsaveis_data = validated_data.pop('responsaveis', [])
        beneficiario = Beneficiario.objects.create(**validated_data)
        
        for resp_data in responsaveis_data:
            # AUTO-APROVAÇÃO: Se for o próprio, o documento já foi validado como RG do Beneficiário
            if resp_data.get('perfil') == 'PROPRIO':
                resp_data['status_documento'] = 'APROVADO'
                
            Responsavel.objects.create(beneficiario=beneficiario, **resp_data)
            
        return beneficiario

    def update(self, instance, validated_data):
        responsaveis_data = validated_data.pop('responsaveis', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if responsaveis_data is not None:
            instance.responsaveis.all().delete()
            for resp_data in responsaveis_data:
                # AUTO-APROVAÇÃO: Mantém a coerência nas edições/reenvios
                if resp_data.get('perfil') == 'PROPRIO':
                    resp_data['status_documento'] = 'APROVADO'
                    
                Responsavel.objects.create(beneficiario=instance, **resp_data)

        return instance

class DocumentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Documento
        fields = '__all__'


class ValidacaoDocumentoIASerializer(serializers.ModelSerializer):
    status_documentos = serializers.SerializerMethodField()
    resumo_divergencias = serializers.SerializerMethodField()
    pode_correcao_cidadao = serializers.SerializerMethodField()

    def get_status_documentos(self, obj):
        log = obj.log_ia if isinstance(obj.log_ia, dict) else {}
        etapas = log.get('etapas') if isinstance(log.get('etapas'), dict) else {}
        valid = etapas.get('validacao') if isinstance(etapas.get('validacao'), dict) else {}
        ocr = etapas.get('ocr') if isinstance(etapas.get('ocr'), dict) else {}
        ocr_det = ocr.get('detalhes') if isinstance(ocr.get('detalhes'), dict) else {}

        def _doc_status(valid_key, ocr_key):
            item = valid.get(valid_key) if isinstance(valid.get(valid_key), dict) else {}
            if item:
                ok = item.get('ok')
                return {
                    'status': 'VALIDADO' if ok else 'INVALIDO',
                    'ok': bool(ok),
                    'motivo': item.get('motivo') or '',
                }
            ocr_item = ocr_det.get(ocr_key) if isinstance(ocr_det.get(ocr_key), dict) else {}
            if ocr_item:
                ok = ocr_item.get('ok')
                return {
                    'status': 'VALIDADO' if ok else 'INVALIDO',
                    'ok': bool(ok),
                    'motivo': ocr_item.get('motivo') or '',
                }
            return {'status': 'PENDENTE', 'ok': None, 'motivo': ''}

        out = {
            'laudo': _doc_status('laudo', 'laudo'),
            'identidade': _doc_status('identidade', 'identidade'),
            'endereco': _doc_status('endereco', 'endereco'),
        }
        # Responsável não deve herdar inválido de outros documentos.
        # Se não houver arquivo, é não aplicável. Se houver arquivo, fica pendente
        # até termos regra dedicada de validação IA para RG_RESP.
        if not getattr(obj, 'arquivo_doc_responsavel', None):
            out['responsavel'] = {
                'status': 'NAO_APLICAVEL',
                'ok': None,
                'motivo': 'Documento do responsável não exigido neste cadastro.',
            }
        else:
            item_resp = valid.get('responsavel') if isinstance(valid.get('responsavel'), dict) else {}
            if item_resp:
                ok = item_resp.get('ok')
                out['responsavel'] = {
                    'status': 'VALIDADO' if ok else 'INVALIDO',
                    'ok': bool(ok),
                    'motivo': item_resp.get('motivo') or '',
                }
            else:
                out['responsavel'] = {
                    'status': 'PENDENTE',
                    'ok': None,
                    'motivo': 'Documento do responsável recebido; aguardando regra dedicada de validação IA.',
                }
        return out

    def get_resumo_divergencias(self, obj):
        log = obj.log_ia if isinstance(obj.log_ia, dict) else {}
        etapas = log.get('etapas') if isinstance(log.get('etapas'), dict) else {}
        valid = etapas.get('validacao') if isinstance(etapas.get('validacao'), dict) else {}
        docs_label = {
            'laudo': 'Laudo médico',
            'identidade': 'Documento de identidade',
            'endereco': 'Comprovante de endereço',
            'responsavel': 'Documento do responsável',
        }
        out = []
        for key in ('laudo', 'identidade', 'endereco', 'responsavel'):
            row = valid.get(key) if isinstance(valid.get(key), dict) else {}
            if not row or row.get('ok') is True:
                continue
            codigo = 'DIVERGENCIA_GERAL'
            if key == 'endereco' and row.get('data_recente_ok') is False:
                codigo = 'ENDERECO_DATA_FORA_VALIDADE'
            elif key == 'identidade' and row.get('cpf_ok') is False:
                codigo = 'IDENTIDADE_CPF_BAIXA_CONFIANCA'
            elif key == 'laudo':
                motivo = (row.get('motivo') or '').upper()
                if 'SOFTTIMELIMITEXCEEDED' in motivo or 'TIMEOUT' in motivo:
                    codigo = 'LAUDO_TIMEOUT_OCR'
                else:
                    codigo = 'LAUDO_CID_NAO_CONFIRMADO'
            out.append({
                'documento': key,
                'titulo': docs_label.get(key, key),
                'codigo': codigo,
                'motivo': row.get('motivo') or 'Divergência detectada na validação automática.',
                'detalhes': {
                    'score': row.get('score'),
                    'score_nome': row.get('score_nome'),
                    'data_recente_ok': row.get('data_recente_ok'),
                    'cpf_ok': row.get('cpf_ok'),
                },
            })
        return out

    def get_pode_correcao_cidadao(self, obj):
        solicitacao = getattr(obj, 'solicitacao', None)
        if not solicitacao or solicitacao.status != 'ABERTO':
            return False
        # Quando o PAC já interagiu (parecer/finalização), bloqueia correção direta.
        return not solicitacao.historico.exclude(autor='Portal CIPTEA').filter(
            tipo_evento__in=['ANALISE', 'PENDENCIA', 'CONCLUSAO', 'INDEFERIDO']
        ).exists()

    class Meta:
        model = ValidacaoDocumentoIA
        fields = '__all__'

class HistoricoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Historico
        fields = ['data', 'titulo', 'mensagem', 'autor', 'tipo_evento']

class SolicitacaoSerializer(serializers.ModelSerializer):
    beneficiario = BeneficiarioSerializer(read_only=True)
    beneficiario_id = serializers.PrimaryKeyRelatedField(
        queryset=Beneficiario.objects.all(), 
        source='beneficiario', 
        write_only=True,
        required=False,
        allow_null=True
    )
    
    anexos = DocumentoSerializer(many=True, read_only=True)
    historico = HistoricoSerializer(many=True, read_only=True)
    parecer_final = serializers.CharField(write_only=True, required=False, allow_blank=True)
    data_validade = serializers.SerializerMethodField()
    vencida = serializers.SerializerMethodField()
    validacao_ia = serializers.SerializerMethodField()

    class Meta:
        model = Solicitacao
        fields = '__all__'

    def get_validacao_ia(self, obj):
        validacao = getattr(obj, 'validacao_ia', None)
        if not validacao:
            return None
        return ValidacaoDocumentoIASerializer(validacao).data

    def update(self, instance, validated_data):
        parecer = validated_data.pop('parecer_final', None)
        status_novo = validated_data.get('status')

        if instance.status == 'LEGADO' and status_novo and status_novo != instance.status:
            raise serializers.ValidationError({
                'status': 'Cadastro legado deve seguir por renovação digital. Inicie uma nova solicitação de renovação.'
            })

        if instance.tipo_fluxo == 'RENOVACAO' and status_novo == 'ANALISE':
            tipos_presentes = set(instance.anexos.values_list('tipo', flat=True))
            obrigatorios = {'LAUDO', 'RG_BENEF', 'COMP_RES'}
            faltantes = sorted(obrigatorios - tipos_presentes)

            # RG do responsável permanece obrigatório quando há responsável cadastrado.
            if instance.beneficiario.responsaveis.exists() and 'RG_RESP' not in tipos_presentes:
                faltantes.append('RG_RESP')

            if faltantes:
                nomes = {
                    'LAUDO': 'Laudo Médico',
                    'RG_BENEF': 'RG do Beneficiário',
                    'COMP_RES': 'Comprovante de Residência',
                    'RG_RESP': 'RG do Responsável',
                }
                faltantes_txt = ', '.join(nomes.get(tipo, tipo) for tipo in faltantes)
                raise serializers.ValidationError({
                    'status': f'Para enviar a renovação, anexe os documentos obrigatórios: {faltantes_txt}.'
                })

        instance = super().update(instance, validated_data)

        if parecer or status_novo:
            titulo = f"Status alterado para {instance.get_status_display()}"
            tipo = 'ANALISE'
            
            if status_novo == 'APROVADO': tipo = 'CONCLUSAO'
            elif status_novo == 'PENDENTE': tipo = 'PENDENCIA'
            elif status_novo == 'INDEFERIDO': tipo = 'INDEFERIDO'

            Historico.objects.create(
                solicitacao=instance,
                titulo=titulo,
                mensagem=parecer if parecer else "Atualização de status administrativa.",
                autor="Gestão PAC",
                tipo_evento=tipo
            )
        
        return instance

    def _validade_data(self, instance):
        if not instance.data_solicitacao:
            return None
        base_date = instance.data_solicitacao.date()
        validade_anos = int(getattr(instance, 'validade_anos', 5) or 5)
        try:
            return base_date.replace(year=base_date.year + validade_anos)
        except ValueError:
            return base_date.replace(month=2, day=28, year=base_date.year + validade_anos)

    def get_data_validade(self, instance):
        data_validade = self._validade_data(instance)
        return data_validade.isoformat() if data_validade else None

    def get_vencida(self, instance):
        data_validade = self._validade_data(instance)
        return bool(data_validade and data_validade < date.today())


class BeneficiarioResumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Beneficiario
        fields = ['id', 'nome_completo', 'cpf']


class SolicitacaoListSerializer(serializers.ModelSerializer):
    beneficiario = BeneficiarioResumoSerializer(read_only=True)
    data_validade = serializers.SerializerMethodField()
    vencida = serializers.SerializerMethodField()

    class Meta:
        model = Solicitacao
        fields = [
            'id',
            'protocolo',
            'status',
            'origem',
            'tipo_fluxo',
            'renovacao_de',
            'primeira_digitalizacao',
            'data_solicitacao',
            'beneficiario',
            'data_validade',
            'vencida',
        ]

    def _validade_data(self, instance):
        if not instance.data_solicitacao:
            return None
        base_date = instance.data_solicitacao.date()
        validade_anos = int(getattr(instance, 'validade_anos', 5) or 5)
        try:
            return base_date.replace(year=base_date.year + validade_anos)
        except ValueError:
            return base_date.replace(month=2, day=28, year=base_date.year + validade_anos)

    def get_data_validade(self, instance):
        data_validade = self._validade_data(instance)
        return data_validade.isoformat() if data_validade else None

    def get_vencida(self, instance):
        data_validade = self._validade_data(instance)
        return bool(data_validade and data_validade < date.today())