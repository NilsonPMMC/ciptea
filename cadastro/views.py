import os
import datetime
import json
import logging
from datetime import date
from io import BytesIO
import base64
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.conf import settings
from rest_framework import filters
from rest_framework import viewsets, parsers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from django.core.cache import cache
from .models import Beneficiario, Solicitacao, Documento, Historico, ValidacaoDocumentoIA
from .serializers import (
    BeneficiarioSerializer,
    SolicitacaoSerializer,
    SolicitacaoListSerializer,
    DocumentoSerializer,
    ValidacaoDocumentoIASerializer,
)

logger = logging.getLogger(__name__)
METRICA_CADASTRO_TRANSACIONAL = 'cadastro_fluxo_transacional_total'
METRICA_CADASTRO_FALLBACK = 'cadastro_fluxo_fallback_total'


def _incrementar_metrica_cadastro(chave):
    valor_atual = cache.get(chave)
    if valor_atual is None:
        cache.set(chave, 1, timeout=None)
        return 1
    try:
        return cache.incr(chave)
    except ValueError:
        cache.set(chave, int(valor_atual) + 1, timeout=None)
        return int(valor_atual) + 1


def _obter_metricas_cadastro():
    return {
        'transacional_total': int(cache.get(METRICA_CADASTRO_TRANSACIONAL, 0) or 0),
        'fallback_total': int(cache.get(METRICA_CADASTRO_FALLBACK, 0) or 0),
    }


def _pode_disparar_triagem_ia(solicitacao):
    tipos_presentes = set(solicitacao.anexos.values_list('tipo', flat=True))
    obrigatorios = {'LAUDO', 'RG_BENEF', 'COMP_RES'}
    if not obrigatorios.issubset(tipos_presentes):
        return False
    if solicitacao.beneficiario.responsaveis.exists() and 'RG_RESP' not in tipos_presentes:
        return False
    return True


def _disparar_triagem_ia_async(solicitacao):
    if not _pode_disparar_triagem_ia(solicitacao):
        return
    validacao, _ = ValidacaoDocumentoIA.objects.get_or_create(solicitacao=solicitacao)
    if validacao.status_validacao == 'PROCESSANDO':
        return
    try:
        from .tasks import process_ciptea_documents
        process_ciptea_documents.delay(solicitacao.id)
    except Exception as exc:
        logger.warning(
            'Falha ao enfileirar triagem IA; mantendo revisão manual. solicitacao=%s erro=%s',
            solicitacao.id,
            exc,
        )
        log_atual = validacao.log_ia if isinstance(validacao.log_ia, dict) else {}
        log_atual['enqueue_error'] = str(exc)
        validacao.status_validacao = 'REVISAO_MANUAL'
        validacao.log_ia = log_atual
        validacao.save(update_fields=['status_validacao', 'log_ia', 'atualizado_em'])


def _enqueue_triagem_ia_apos_commit(solicitacao_id: int):
    """Roda após commit: evita race com o worker e mantém a view HTTP mais leve."""
    try:
        solicitacao = Solicitacao.objects.get(pk=solicitacao_id)
    except Solicitacao.DoesNotExist:
        logger.warning('triagem_ia: solicitacao_id=%s não encontrada após commit', solicitacao_id)
        return
    _disparar_triagem_ia_async(solicitacao)


# Status em que o cidadão pode reenviar dados/documentos sem JWT (mesma prova de posse de buscar-completo).
CIDADAO_PODE_ATUALIZAR_STATUS = frozenset({'PENDENTE', 'ABERTO', 'ANALISE'})


def _solicitacao_cidadao_por_credenciais(protocolo, cpf, data_nascimento):
    """
    Localiza a solicitação com a mesma combinação usada em buscar-completo / retomar-edicao.
    Retorna None se faltar parâmetro ou não houver correspondência.
    """
    if not protocolo or not cpf or not data_nascimento:
        return None
    cpf_limpo = ''.join(filter(str.isdigit, str(cpf)))
    return (
        Solicitacao.objects.filter(protocolo=protocolo.strip())
        .filter(Q(beneficiario__cpf=cpf) | Q(beneficiario__cpf=cpf_limpo))
        .filter(beneficiario__data_nascimento=data_nascimento)
        .select_related('beneficiario')
        .first()
    )


def _pode_correcao_ia_pre_pac(solicitacao):
    # Regra de negócio: correção IA pelo cidadão só é permitida enquanto
    # a solicitação ainda estiver em ABERTO (antes de entrar em análise do PAC).
    if not solicitacao or solicitacao.status != 'ABERTO':
        return False
    return not solicitacao.historico.exclude(autor='Portal CIPTEA').filter(
        tipo_evento__in=['ANALISE', 'PENDENCIA', 'CONCLUSAO', 'INDEFERIDO']
    ).exists()


class BeneficiarioViewSet(viewsets.ModelViewSet):
    queryset = Beneficiario.objects.all().order_by('-created_at')
    serializer_class = BeneficiarioSerializer
    parser_classes = (parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser)

    def get_permissions(self):
        # Nota: @action(permission_classes=...) é ignorado quando get_permissions() é sobrescrito;
        # incluir aqui toda action pública do viewset.
        if self.action in ['create', 'atualizacao_cidadao']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def _normalize_responsaveis_payload(self, data):
        """
        Aceita os dois formatos no multipart:
        1) responsaveis='[{"nome": ...}]' (JSON string)
        2) responsaveis[0]nome=... / responsaveis[0]cpf=...
        """
        normalized = {}
        for key in data.keys():
            normalized[key] = data.get(key)
        parsed = []

        raw_json = data.get('responsaveis')
        if raw_json:
            try:
                decoded = json.loads(raw_json)
                if isinstance(decoded, list):
                    parsed = decoded
            except (TypeError, json.JSONDecodeError):
                parsed = []

        if not parsed:
            by_index = {}
            for key in data.keys():
                if not (key.startswith('responsaveis[') and ']' in key):
                    continue
                index_part, field = key.split(']', 1)
                field = field.lstrip('.')
                if field.startswith('['):
                    # Ex.: responsaveis[0][nome]
                    field = field.strip('[]')
                if field.startswith('.'):
                    field = field[1:]
                if field == '':
                    # Ex.: responsaveis[0]nome
                    field = key.split(']', 1)[1]
                try:
                    idx = int(index_part.replace('responsaveis[', ''))
                except ValueError:
                    continue
                by_index.setdefault(idx, {})[field] = data.get(key)

            if by_index:
                parsed = [by_index[i] for i in sorted(by_index.keys())]

        if parsed:
            normalized['responsaveis'] = parsed
        return normalized

    def create(self, request, *args, **kwargs):
        data = self._normalize_responsaveis_payload(request.data)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        data = self._normalize_responsaveis_payload(request.data)
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
    
    def perform_update(self, serializer):
        if 'foto' in serializer.validated_data:
            serializer.save(status_foto='PENDENTE', motivo_rejeicao_foto='')
        else:
            serializer.save()

    @action(detail=True, methods=['patch'], permission_classes=[AllowAny], url_path='atualizacao-cidadao')
    def atualizacao_cidadao(self, request, pk=None):
        """
        Atualização do beneficiário pelo fluxo público (correção / renovação), sem JWT.
        Exige query: protocolo, cpf, data_nascimento — mesma prova de posse de buscar-completo.
        """
        protocolo = request.query_params.get('protocolo')
        cpf = request.query_params.get('cpf')
        data_nascimento = request.query_params.get('data_nascimento')
        solicitacao = _solicitacao_cidadao_por_credenciais(protocolo, cpf, data_nascimento)
        if not solicitacao or solicitacao.beneficiario_id != int(pk):
            return Response(
                {'erro': 'Solicitação não encontrada ou dados não conferem com o beneficiário.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if solicitacao.status not in CIDADAO_PODE_ATUALIZAR_STATUS:
            return Response(
                {'erro': 'Esta solicitação não aceita atualização pelo formulário público no status atual.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = self.get_object()
        data = self._normalize_responsaveis_payload(request.data)
        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


class SolicitacaoViewSet(viewsets.ModelViewSet):
    queryset = Solicitacao.objects.all().order_by('-data_solicitacao')
    serializer_class = SolicitacaoSerializer
    parser_classes = (parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser)
    filter_backends = [filters.SearchFilter]
    search_fields = ['protocolo', 'beneficiario__nome_completo', 'beneficiario__cpf']

    def get_permissions(self):
        if self.action in [
            'create',
            'cadastro_completo',
            'consultar_status',
            'dados_carteira',
            'retomar_edicao',
            'buscar_completo',
            'verificar_acesso',
            'iniciar_renovacao',
            'triagem_ia',
            'atualizacao_cidadao',
            'solicitar_correcao_ia',
        ]:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def _data_validade(self, solicitacao):
        if not solicitacao.data_solicitacao:
            return None
        base_date = solicitacao.data_solicitacao.date()
        validade_anos = int(getattr(solicitacao, 'validade_anos', 5) or 5)
        try:
            return base_date.replace(year=base_date.year + validade_anos)
        except ValueError:
            return base_date.replace(month=2, day=28, year=base_date.year + validade_anos)

    def _is_vencida(self, solicitacao):
        data_validade = self._data_validade(solicitacao)
        return bool(data_validade and data_validade < date.today())

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        fluxo = (request.headers.get('X-Cadastro-Flow') or '').strip().lower()
        if fluxo == 'fallback' and response.status_code == status.HTTP_201_CREATED:
            total = _incrementar_metrica_cadastro(METRICA_CADASTRO_FALLBACK)
            logger.info('cadastro_flow=fallback total=%s protocolo=%s', total, response.data.get('protocolo'))
        return response

    def get_serializer_class(self):
        if self.action == 'list':
            return SolicitacaoListSerializer
        return SolicitacaoSerializer
    
    def get_queryset(self):
        queryset = Solicitacao.objects.select_related('beneficiario').order_by('-data_solicitacao')
        origem = (self.request.query_params.get('origem') or '').strip().upper()
        
        if self.action == 'list':
            termo = self.request.query_params.get('search', None)
            if origem in ('LEGADO', 'SISTEMA_NOVO'):
                queryset = queryset.filter(origem=origem)
            if termo:
                return queryset 
            return queryset.exclude(status='LEGADO')

        if self.action in ['retrieve', 'detalhe', 'buscar_completo']:
            return queryset.select_related('validacao_ia').prefetch_related('beneficiario__responsaveis', 'anexos', 'historico')

        return queryset

    @action(detail=True, methods=['get'], url_path='detalhe')
    def detalhe(self, request, pk=None):
        solicitacao = self.get_object()
        serializer = SolicitacaoSerializer(solicitacao)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='kanban')
    def kanban(self, request):
        coluna = (request.query_params.get('coluna') or '').strip().lower()
        termo = (request.query_params.get('search') or '').strip()
        origem = (request.query_params.get('origem') or '').strip().upper()
        apenas_vencida = (request.query_params.get('vencida') or '').strip().lower() in ('1', 'true', 'yes', 'on')
        try:
            page = max(int(request.query_params.get('page', 1)), 1)
            page_size = max(min(int(request.query_params.get('page_size', 50)), 200), 1)
        except (TypeError, ValueError):
            return Response({'erro': "Parâmetros 'page' e 'page_size' devem ser numéricos."}, status=status.HTTP_400_BAD_REQUEST)

        mapa_colunas = {
            'aberto': ['ABERTO'],
            'analise': ['ANALISE'],
            'pendente': ['PENDENTE'],
            'aprovado': ['APROVADO', 'IMPRESSO'],
            'indeferido': ['INDEFERIDO'],
            'legado': ['LEGADO'],
        }
        if coluna not in mapa_colunas:
            return Response({'erro': "Parâmetro 'coluna' inválido."}, status=status.HTTP_400_BAD_REQUEST)

        queryset = Solicitacao.objects.select_related('beneficiario').filter(status__in=mapa_colunas[coluna]).order_by('-data_solicitacao')

        if origem in ('LEGADO', 'SISTEMA_NOVO'):
            queryset = queryset.filter(origem=origem)

        if termo:
            queryset = queryset.filter(
                Q(protocolo__icontains=termo)
                | Q(beneficiario__nome_completo__icontains=termo)
                | Q(beneficiario__cpf__icontains=termo)
            )

        lista = list(queryset)
        if apenas_vencida:
            lista = [s for s in lista if self._is_vencida(s)]
        lista.sort(key=lambda s: (not self._is_vencida(s), s.data_solicitacao))

        paginator = Paginator(lista, page_size)
        page_obj = paginator.get_page(page)
        serializer = SolicitacaoListSerializer(page_obj.object_list, many=True)
        return Response({
            'coluna': coluna,
            'page': page_obj.number,
            'page_size': page_size,
            'pages': paginator.num_pages,
            'total': paginator.count,
            'results': serializer.data,
        })
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny], url_path='verificar-acesso')
    def verificar_acesso(self, request):
        cpf = request.data.get('cpf')
        data_nascimento = request.data.get('data_nascimento')

        if not cpf or not data_nascimento:
            return Response({'erro': 'CPF e Data de Nascimento obrigatórios'}, status=400)

        # Limpa CPF
        cpf_limpo = ''.join(filter(str.isdigit, cpf))

        # Busca Beneficiário
        try:
            beneficiario = Beneficiario.objects.get(
                Q(cpf=cpf) | Q(cpf=cpf_limpo),
                data_nascimento=data_nascimento
            )
        except Beneficiario.DoesNotExist:
            # CENÁRIO C: Não existe -> Vai para Cadastro Novo
            return Response({'tipo': 'NAO_ENCONTRADO'}, status=200)

        # Busca a solicitação associada
        solicitacao = Solicitacao.objects.filter(beneficiario=beneficiario).order_by('-data_solicitacao').first()

        if not solicitacao:
            # Caso raro: tem beneficiário mas sem solicitação (erro de migração?)
            # Tratamos como novo para garantir
            return Response({'tipo': 'NAO_ENCONTRADO'}, status=200)

        # Monta resposta base
        dados_retorno = {
            'nome': beneficiario.nome_completo,
            'solicitacao_id': solicitacao.id,
            'protocolo': solicitacao.protocolo,
            'status': solicitacao.status,
            'foto': request.build_absolute_uri(beneficiario.foto.url) if beneficiario.foto else None,
            'vencida': self._is_vencida(solicitacao),
            'tipo_fluxo': solicitacao.tipo_fluxo,
        }

        # CENÁRIO B: Usuário do Sistema Antigo
        if solicitacao.origem == 'LEGADO':
            dados_retorno['tipo'] = 'LEGADO'
            dados_retorno['mensagem'] = 'Cadastro encontrado no sistema antigo.'
            return Response(dados_retorno, status=200)

        # CENÁRIO A: Usuário do Sistema Novo (Logado)
        dados_retorno['tipo'] = 'SISTEMA_NOVO'
        return Response(dados_retorno, status=200)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny], url_path='iniciar-renovacao')
    def iniciar_renovacao(self, request):
        protocolo = request.data.get('protocolo')
        cpf = request.data.get('cpf')
        data_nascimento = request.data.get('data_nascimento')

        if not protocolo or not cpf or not data_nascimento:
            return Response({'erro': 'Protocolo, CPF e Data de Nascimento são obrigatórios.'}, status=status.HTTP_400_BAD_REQUEST)

        cpf_limpo = ''.join(filter(str.isdigit, cpf))
        solicitacao_base = Solicitacao.objects.filter(
            protocolo=protocolo,
            beneficiario__data_nascimento=data_nascimento
        ).filter(
            Q(beneficiario__cpf=cpf) | Q(beneficiario__cpf=cpf_limpo)
        ).select_related('beneficiario').first()

        if not solicitacao_base:
            return Response({'erro': 'Solicitação base não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        elegivel_renovacao = solicitacao_base.origem == 'LEGADO' or self._is_vencida(solicitacao_base)
        if not elegivel_renovacao:
            return Response({'erro': 'Renovação disponível apenas para cadastros legados ou carteirinhas vencidas.'}, status=status.HTTP_400_BAD_REQUEST)

        renovacao_existente = Solicitacao.objects.filter(
            renovacao_de=solicitacao_base,
            status__in=['ABERTO', 'ANALISE', 'PENDENTE']
        ).order_by('-data_solicitacao').first()
        if renovacao_existente:
            return Response({
                'id': renovacao_existente.id,
                'protocolo': renovacao_existente.protocolo,
                'status': renovacao_existente.status,
                'tipo_fluxo': renovacao_existente.tipo_fluxo,
                'primeira_digitalizacao': renovacao_existente.primeira_digitalizacao,
                'mensagem': 'Já existe renovação em andamento para este cadastro.',
            }, status=status.HTTP_200_OK)

        primeira_digitalizacao = bool(
            solicitacao_base.origem == 'LEGADO'
            and not Documento.objects.filter(solicitacao=solicitacao_base).exists()
        )

        with transaction.atomic():
            renovacao = Solicitacao.objects.create(
                beneficiario=solicitacao_base.beneficiario,
                status='ABERTO',
                origem='SISTEMA_NOVO',
                tipo_fluxo='RENOVACAO',
                renovacao_de=solicitacao_base,
                primeira_digitalizacao=primeira_digitalizacao,
            )
            Historico.objects.create(
                solicitacao=renovacao,
                titulo='Renovação iniciada',
                mensagem=f'Renovação iniciada a partir do protocolo {solicitacao_base.protocolo}.',
                autor='Portal CIPTEA',
                tipo_evento='CRIACAO',
            )

        return Response({
            'id': renovacao.id,
            'protocolo': renovacao.protocolo,
            'status': renovacao.status,
            'tipo_fluxo': renovacao.tipo_fluxo,
            'primeira_digitalizacao': renovacao.primeira_digitalizacao,
            'renovacao_de': solicitacao_base.protocolo,
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny], url_path='cadastro-completo')
    def cadastro_completo(self, request):
        dados_beneficiario = request.data.copy()
        for campo_anexo in ('laudo', 'rg_beneficiario', 'comprovante_residencia', 'rg_responsavel'):
            dados_beneficiario.pop(campo_anexo, None)

        with transaction.atomic():
            serializer_beneficiario = BeneficiarioSerializer(data=dados_beneficiario)
            serializer_beneficiario.is_valid(raise_exception=True)
            beneficiario = serializer_beneficiario.save()

            solicitacao = Solicitacao.objects.create(
                beneficiario=beneficiario,
                status='ABERTO',
            )

            Historico.objects.create(
                solicitacao=solicitacao,
                titulo='Solicitação criada',
                mensagem='Cadastro inicial realizado pelo cidadão.',
                autor='Portal CIPTEA',
                tipo_evento='CRIACAO',
            )

            anexos_map = (
                ('laudo', 'LAUDO', 'Laudo Médico'),
                ('rg_beneficiario', 'RG_BENEF', 'RG do Beneficiário'),
                ('comprovante_residencia', 'COMP_RES', 'Comprovante Residência'),
                ('rg_responsavel', 'RG_RESP', 'RG do Responsável'),
            )
            for campo, tipo, descricao in anexos_map:
                arquivo = request.FILES.get(campo)
                if arquivo:
                    Documento.objects.create(
                        solicitacao=solicitacao,
                        arquivo=arquivo,
                        tipo=tipo,
                        descricao=descricao,
                        status='PENDENTE',
                    )

        total = _incrementar_metrica_cadastro(METRICA_CADASTRO_TRANSACIONAL)
        logger.info('cadastro_flow=transacional total=%s protocolo=%s', total, solicitacao.protocolo)
        solicitacao_pk = solicitacao.id
        transaction.on_commit(lambda pk=solicitacao_pk: _enqueue_triagem_ia_apos_commit(pk))

        return Response({
            'beneficiario_id': beneficiario.id,
            'solicitacao_id': solicitacao.id,
            'protocolo': solicitacao.protocolo,
            'status': solicitacao.status,
            'pipeline': {
                'status': 'PROCESSANDO',
                'mensagem': 'Triagem automática enfileirada. Acompanhe pelo endpoint de triagem.',
            },
        }, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=['get'], url_path='metricas-cadastro')
    def metricas_cadastro(self, request):
        metricas = _obter_metricas_cadastro()
        total = metricas['transacional_total'] + metricas['fallback_total']
        participacao_transacional = (metricas['transacional_total'] / total) if total else 0
        return Response({
            **metricas,
            'total_cadastros_medidos': total,
            'participacao_transacional': round(participacao_transacional, 4),
        })
    
    @action(detail=False, methods=['get'], url_path='consultar-status')
    def consultar_status(self, request):
        protocolo = request.query_params.get('protocolo')
        cpf = request.query_params.get('cpf')
        data_nascimento = request.query_params.get('data_nascimento')
        
        solicitacao = None

        # 1. Busca por Protocolo
        if protocolo:
            solicitacao = Solicitacao.objects.filter(protocolo=protocolo).first()
        
        # 2. Busca por CPF + Data Nasc
        elif cpf and data_nascimento:
            # --- DEFINIÇÃO DAS VARIÁVEIS ---
            cpf_com_mascara = cpf  # <--- LINHA QUE FALTOU (ou estava indentada errado)
            cpf_limpo = ''.join(filter(str.isdigit, cpf))
            # -------------------------------
            
            # Busca: (CPF igual ao mascarado OU CPF igual ao limpo) E Data Nasc bate
            solicitacao = Solicitacao.objects.filter(
                Q(beneficiario__cpf=cpf_com_mascara) | Q(beneficiario__cpf=cpf_limpo),
                beneficiario__data_nascimento=data_nascimento
            ).order_by('-data_solicitacao').first()

        if not solicitacao:
            return Response(
                {'erro': 'Cadastro não localizado. Verifique se o CPF e a Data de Nascimento estão corretos.'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        foto_url = None
        if solicitacao.beneficiario.foto:
            foto_url = request.build_absolute_uri(solicitacao.beneficiario.foto.url)

        # Monta a Timeline
        historico_data = []
        # Ordena do mais recente para o mais antigo
        for h in solicitacao.historico.all().order_by('-data'):
            historico_data.append({
                'data': h.data,
                'titulo': h.titulo,
                'mensagem': h.mensagem,
                'tipo_evento': h.tipo_evento
            })
            
        # Verifica documentos rejeitados
        docs_pendentes = []
        for doc in solicitacao.anexos.filter(status='REJEITADO'):
            docs_pendentes.append({
                'tipo': doc.get_tipo_display(),
                'motivo': doc.motivo_rejeicao
            })

        dados = {
            'protocolo': solicitacao.protocolo,
            'status': solicitacao.get_status_display(),
            'status_code': solicitacao.status,
            'data': solicitacao.data_solicitacao,
            'nome': solicitacao.beneficiario.nome_completo,
            'nome_beneficiario': solicitacao.beneficiario.nome_completo.split()[0] + ' ***',
            'timeline': historico_data,
            'pendencias': docs_pendentes,
            'foto': foto_url,
            'historico': historico_data
        }
        return Response(dados)
    
    @action(detail=False, methods=['get'], url_path='retomar-edicao')
    def retomar_edicao(self, request):
        protocolo = request.query_params.get('protocolo')
        cpf = request.query_params.get('cpf') # Espera CPF limpo ou sujo, vamos tratar
        data_nascimento = request.query_params.get('data_nascimento')
        
        if not protocolo or not cpf or not data_nascimento:
             return Response({'erro': 'Dados insuficientes para autenticação.'}, status=status.HTTP_400_BAD_REQUEST)

        # Lógica de busca segura (mesma da consulta)
        cpf_limpo = ''.join(filter(str.isdigit, cpf))
        
        solicitacao = Solicitacao.objects.filter(
            protocolo=protocolo,
            beneficiario__data_nascimento=data_nascimento
        ).filter(
            Q(beneficiario__cpf=cpf) | Q(beneficiario__cpf=cpf_limpo)
        ).first()

        if not solicitacao:
            return Response({'erro': 'Solicitação não encontrada ou dados incorretos.'}, status=status.HTTP_404_NOT_FOUND)

        # Serializa tudo para devolver ao front
        serializer = self.get_serializer(solicitacao)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='dados-carteira')
    def dados_carteira(self, request):
        protocolo = request.query_params.get('protocolo')
        cpf = request.query_params.get('cpf') 
        data_nascimento = request.query_params.get('data_nascimento')
        
        if not protocolo:
            return Response(status=400)

        cpf_limpo = ''.join(filter(str.isdigit, cpf)) if cpf else ''
      
        solicitacao = Solicitacao.objects.filter(
            protocolo=protocolo,
            status__in=['APROVADO', 'IMPRESSO']
        ).filter(
            Q(beneficiario__cpf=cpf) | Q(beneficiario__cpf=cpf_limpo),
            beneficiario__data_nascimento=data_nascimento
        ).first()

        if not solicitacao:
            return Response({'erro': 'Carteira não disponível.'}, status=404)

        foto_url = None
        if solicitacao.beneficiario.foto:
            foto_url = request.build_absolute_uri(solicitacao.beneficiario.foto.url)

        responsaveis_qs = solicitacao.beneficiario.responsaveis.all().order_by('id')[:2]
        
        resp1 = responsaveis_qs[0] if len(responsaveis_qs) > 0 else None
        resp2 = responsaveis_qs[1] if len(responsaveis_qs) > 1 else None

        contato_tel = resp1.telefone if resp1 else ''
        data_emissao = solicitacao.data_solicitacao.date()
        validade_anos = int(getattr(solicitacao, 'validade_anos', 5) or 5)
        try:
            data_validade = data_emissao.replace(year=data_emissao.year + validade_anos)
        except ValueError:
            data_validade = data_emissao.replace(month=2, day=28, year=data_emissao.year + validade_anos)

        dados = {
            'nome': solicitacao.beneficiario.nome_completo,
            'rg': solicitacao.beneficiario.rg,
            'cpf': solicitacao.beneficiario.cpf,
            'nascimento': solicitacao.beneficiario.data_nascimento,
            'cid': solicitacao.beneficiario.cid,
            'foto': foto_url,
            'responsavel1_nome': resp1.nome if resp1 else '',
            'responsavel1_cpf': resp1.cpf if resp1 else '',
            'responsavel2_nome': resp2.nome if resp2 else '',
            'responsavel2_cpf': resp2.cpf if resp2 else '',
            'contato_telefone': contato_tel,
            'protocolo': solicitacao.protocolo,
            'validade': f'{validade_anos} anos',
            'validade_anos': validade_anos,
            'data_emissao': data_emissao,
            'data_validade': data_validade,
            'logradouro': solicitacao.beneficiario.logradouro,
            'numero': solicitacao.beneficiario.numero,
            'bairro': solicitacao.beneficiario.bairro,
            'cidade': solicitacao.beneficiario.cidade,
            'estado': solicitacao.beneficiario.estado,
        }
        return Response(dados)
    
    @action(detail=False, methods=['get'], url_path='buscar-completo')
    def buscar_completo(self, request):
        protocolo = request.query_params.get('protocolo')
        cpf = request.query_params.get('cpf')
        data_nascimento = request.query_params.get('data_nascimento')
        
        # Validação básica
        if not protocolo or not cpf:
            return Response({'erro': 'Protocolo e CPF obrigatórios'}, status=400)

        # Limpeza do CPF para garantir match
        cpf_limpo = ''.join(filter(str.isdigit, cpf))

        # Busca segura: Protocolo + (CPF formatado OU CPF limpo)
        # NOTA: Removemos o filtro status='APROVADO'
        solicitacao = Solicitacao.objects.filter(
            protocolo=protocolo
        ).filter(
            Q(beneficiario__cpf=cpf) | Q(beneficiario__cpf=cpf_limpo)
        ).first()
        
        # Validação extra de Data de Nascimento (opcional, mas bom pra segurança)
        if solicitacao and data_nascimento:
            if str(solicitacao.beneficiario.data_nascimento) != data_nascimento:
                 return Response({'erro': 'Data de nascimento não confere'}, status=404)

        if not solicitacao:
            return Response({'erro': 'Solicitação não encontrada.'}, status=404)
            
        # Serializa com todos os dados (beneficiário aninhado, responsáveis, anexos)
        serializer = self.get_serializer(solicitacao)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], permission_classes=[AllowAny], url_path='atualizacao-cidadao')
    def atualizacao_cidadao(self, request, pk=None):
        """
        Atualização limitada da solicitação pelo cidadão (ex.: status ANALISE após correções).
        Query: protocolo, cpf, data_nascimento — mesma prova de posse de buscar-completo.
        """
        protocolo = request.query_params.get('protocolo')
        cpf = request.query_params.get('cpf')
        data_nascimento = request.query_params.get('data_nascimento')
        solicitacao = _solicitacao_cidadao_por_credenciais(protocolo, cpf, data_nascimento)
        if not solicitacao or solicitacao.id != int(pk):
            return Response(
                {'erro': 'Solicitação não encontrada ou dados não conferem.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if solicitacao.status not in CIDADAO_PODE_ATUALIZAR_STATUS:
            return Response(
                {'erro': 'Esta solicitação não aceita atualização pelo formulário público no status atual.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        novo_status = request.data.get('status')
        if novo_status != 'ANALISE':
            return Response(
                {'erro': "Por esta rota só é permitido reenviar à análise (status 'ANALISE')."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(solicitacao, data={'status': 'ANALISE'}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='triagem-ia')
    def triagem_ia(self, request, pk=None):
        # PAC autenticado acessa por id; cidadão sem JWT precisa provar posse
        # com protocolo + CPF + data_nascimento (mesmo padrão de buscar-completo).
        if request.user and request.user.is_authenticated:
            solicitacao = self.get_object()
        else:
            protocolo = request.query_params.get('protocolo')
            cpf = request.query_params.get('cpf')
            data_nascimento = request.query_params.get('data_nascimento')
            solicitacao = _solicitacao_cidadao_por_credenciais(protocolo, cpf, data_nascimento)
            try:
                solicitacao_id = int(pk)
            except (TypeError, ValueError):
                solicitacao_id = None
            if not solicitacao or solicitacao.id != solicitacao_id:
                return Response(
                    {'erro': 'Solicitação não encontrada ou dados não conferem.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        validacao = getattr(solicitacao, 'validacao_ia', None)
        if not validacao:
            return Response({
                'status_validacao': 'PENDENTE',
                'log_ia': {'motivo': 'Triagem ainda não iniciada.'},
            })
        serializer = ValidacaoDocumentoIASerializer(validacao)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], permission_classes=[AllowAny], url_path='solicitar-correcao-ia')
    def solicitar_correcao_ia(self, request, pk=None):
        protocolo = request.query_params.get('protocolo')
        cpf = request.query_params.get('cpf')
        data_nascimento = request.query_params.get('data_nascimento')
        solicitacao = _solicitacao_cidadao_por_credenciais(protocolo, cpf, data_nascimento)
        if not solicitacao or solicitacao.id != int(pk):
            return Response(
                {'erro': 'Solicitação não encontrada ou dados não conferem.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not _pode_correcao_ia_pre_pac(solicitacao):
            return Response(
                {'erro': "Correção prévia indisponível: só é permitida enquanto a solicitação estiver em 'ABERTO'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        solicitacao.status = 'PENDENTE'
        solicitacao.save(update_fields=['status'])
        mensagem = (request.data.get('mensagem') or '').strip() or (
            'Cidadão solicitou correção após divergências identificadas na triagem de IA.'
        )
        Historico.objects.create(
            solicitacao=solicitacao,
            titulo='Correção solicitada pelo cidadão',
            mensagem=mensagem,
            autor='Portal CIPTEA',
            tipo_evento='PENDENCIA',
        )
        return Response({'ok': True, 'status': solicitacao.status})
    
def gerar_carteira_pdf(request, protocolo):  
    try:
        import qrcode
    except ModuleNotFoundError:
        return HttpResponse(
            "Dependencia 'qrcode' nao instalada no servidor. Instale com: pip install 'qrcode[pil]'",
            status=500,
        )

    # 1. Busca a solicitação APROVADA
    try:
        solicitacao = Solicitacao.objects.get(protocolo=protocolo, status='APROVADO')
    except Solicitacao.DoesNotExist:
        return HttpResponse("Carteirinha não encontrada ou ainda não aprovada.", status=404)

    # 2. Gera o QR Code em memória
    # O QR aponta para uma URL de validação (fictícia por enquanto)
    qr_url = f"https://ciptea.mogidascruzes.sp.gov.br/validar/{protocolo}" 
    img = qrcode.make(qr_url)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    static_img_path = os.path.join(settings.BASE_DIR, 'static', 'img')
    foto_path = None
    if solicitacao.beneficiario.foto:
        foto_path = solicitacao.beneficiario.foto.path

    responsaveis_qs = solicitacao.beneficiario.responsaveis.all().order_by('id')[:2]
    
    resp1 = responsaveis_qs[0] if len(responsaveis_qs) > 0 else None
    resp2 = responsaveis_qs[1] if len(responsaveis_qs) > 1 else None

    # 3. Prepara dados para o Template
    context = {
        'solicitacao': solicitacao,
        'beneficiario': solicitacao.beneficiario,
        'responsavel1': resp1,
        'responsavel2': resp2,
        'qr_code': qr_base64,
        'hoje': datetime.date.today(),
        'MEDIA_URL': request.build_absolute_uri(settings.MEDIA_URL), # Para carregar a foto do perfil
        'base_url': request.build_absolute_uri('/'), # Para carregar logos estáticos se tiver
        'img_dir': static_img_path, # Caminho da pasta static/img
        'foto_path': foto_path,
    }

    # 4. Renderiza HTML e Converte para PDF
    html_string = render_to_string('cadastro/carteira_pdf.html', context)
    
    # Gera o PDF (import local: WeasyPrint é pesado e não deve carregar em toda importação de views)
    from weasyprint import HTML

    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    pdf_file = html.write_pdf()

    # 5. Retorna o arquivo para download
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="CIPTEA_{protocolo}.pdf"'
    return response

class DocumentoViewSet(viewsets.ModelViewSet):
    queryset = Documento.objects.all()
    serializer_class = DocumentoSerializer
    parser_classes = (parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser)

    def get_permissions(self):
        if self.action in ['create', 'partial_update', 'update']: 
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        documento = serializer.save()
        sid = documento.solicitacao_id
        transaction.on_commit(lambda pk=sid: _enqueue_triagem_ia_apos_commit(pk))

    def perform_update(self, serializer):
        if 'arquivo' in serializer.validated_data:
            documento = serializer.save(status='PENDENTE', motivo_rejeicao='')
        else:
            documento = serializer.save()
        sid = documento.solicitacao_id
        transaction.on_commit(lambda pk=sid: _enqueue_triagem_ia_apos_commit(pk))