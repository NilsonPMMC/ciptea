import qrcode
import os
import datetime
from io import BytesIO
import base64
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.conf import settings
from weasyprint import HTML
from rest_framework import filters
from rest_framework import viewsets, parsers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Q
from django.shortcuts import get_object_or_404
from .models import Beneficiario, Solicitacao, Documento, Historico
from .serializers import BeneficiarioSerializer, SolicitacaoSerializer, DocumentoSerializer
from cadastro.models import Documento
from cadastro.serializers import DocumentoSerializer

class BeneficiarioViewSet(viewsets.ModelViewSet):
    queryset = Beneficiario.objects.all().order_by('-created_at')
    serializer_class = BeneficiarioSerializer
    parser_classes = (parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser)

    def get_permissions(self):
        if self.action in ['create', 'partial_update', 'update']: 
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def perform_update(self, serializer):
        if 'foto' in serializer.validated_data:
            serializer.save(status_foto='PENDENTE', motivo_rejeicao_foto='')
        else:
            serializer.save()

class SolicitacaoViewSet(viewsets.ModelViewSet):
    queryset = Solicitacao.objects.all().order_by('-data_solicitacao')
    serializer_class = SolicitacaoSerializer
    parser_classes = (parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser)
    filter_backends = [filters.SearchFilter]
    search_fields = ['protocolo', 'beneficiario__nome_completo', 'beneficiario__cpf']

    def get_permissions(self):
        if self.action in ['create', 'consultar_status', 'dados_carteira', 'retomar_edicao', 'partial_update', 'update', 'buscar_completo', 'verificar_acesso']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Solicitacao.objects.all().order_by('-data_solicitacao')
        
        if self.action == 'list':
            termo = self.request.query_params.get('search', None)
            
            # --- DEBUG NO TERMINAL ---
            print(f"=== DEBUG KANBAN ===")
            print(f"Termo de busca recebido: '{termo}'")
            
            if termo:
                print("-> Modo Busca Ativo: Retornando TUDO (incluindo LEGADO)")
                # Retorna tudo e deixa o filter_backends filtrar o texto
                return queryset 
            
            print("-> Modo Padrão: Escondendo LEGADO")
            return queryset.exclude(status='LEGADO')

        return queryset
    
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
        solicitacao = Solicitacao.objects.filter(beneficiario=beneficiario).first()

        if not solicitacao:
            # Caso raro: tem beneficiário mas sem solicitação (erro de migração?)
            # Tratamos como novo para garantir
            return Response({'tipo': 'NAO_ENCONTRADO'}, status=200)

        # Monta resposta base
        dados_retorno = {
            'nome': beneficiario.nome_completo,
            'protocolo': solicitacao.protocolo,
            'status': solicitacao.status,
            'foto': request.build_absolute_uri(beneficiario.foto.url) if beneficiario.foto else None
        }

        # CENÁRIO B: Usuário do Sistema Antigo
        if solicitacao.origem == 'LEGADO':
            dados_retorno['tipo'] = 'LEGADO'
            dados_retorno['mensagem'] = 'Cadastro encontrado no sistema antigo.'
            return Response(dados_retorno, status=200)

        # CENÁRIO A: Usuário do Sistema Novo (Logado)
        dados_retorno['tipo'] = 'SISTEMA_NOVO'
        return Response(dados_retorno, status=200)
    
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
            status='APROVADO'
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
            'validade': '5 anos',
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
    
def gerar_carteira_pdf(request, protocolo):  
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
    
    # Gera o PDF
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

    def perform_update(self, serializer):
        if 'arquivo' in serializer.validated_data:
            serializer.save(status='PENDENTE', motivo_rejeicao='')
        else:
            serializer.save()