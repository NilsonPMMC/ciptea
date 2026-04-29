from django.contrib import admin
from .models import Beneficiario, Responsavel, Solicitacao, Documento, Historico, ValidacaoDocumentoIA

# 1. Inline de Documentos (Agora com Status e Motivo)
class DocumentoInline(admin.TabularInline):
    model = Documento
    extra = 0
    fields = ('tipo', 'arquivo', 'status', 'motivo_rejeicao')
    # Opcional: deixar o link do arquivo clicável se quiser, mas o padrão já resolve.

# 2. Inline de Histórico (A Timeline)
class HistoricoInline(admin.TabularInline):
    model = Historico
    extra = 1 # Já deixa uma linha em branco para adicionar uma nova interação
    fields = ('tipo_evento', 'titulo', 'mensagem', 'autor', 'data')
    readonly_fields = ('data',) # Data é automática, então deixamos apenas leitura

# 3. Inline de Responsável (Visualização Compacta)
class ResponsavelInline(admin.StackedInline):
    model = Responsavel
    can_delete = False
    verbose_name_plural = 'Responsável'
    fk_name = 'beneficiario'

@admin.register(Beneficiario)
class BeneficiarioAdmin(admin.ModelAdmin):
    list_display = ('nome_completo', 'cpf', 'data_nascimento', 'cidade')
    search_fields = ('nome_completo', 'cpf')
    list_filter = ('cidade', 'sexo')
    inlines = [ResponsavelInline]

@admin.register(Solicitacao)
class SolicitacaoAdmin(admin.ModelAdmin):
    list_display = ('protocolo', 'get_beneficiario_nome', 'status', 'data_solicitacao')
    list_filter = ('status', 'data_solicitacao')
    search_fields = ('protocolo', 'beneficiario__nome_completo', 'beneficiario__cpf')
    
    # Aqui conectamos tudo na mesma tela
    inlines = [DocumentoInline, HistoricoInline]
    
    def get_beneficiario_nome(self, obj):
        return obj.beneficiario.nome_completo
    get_beneficiario_nome.short_description = 'Beneficiário'

# Registro avulso caso queira consultar tabelas isoladas
admin.site.register(Historico)
admin.site.register(Documento) # Já está inline na Solicitação
admin.site.register(Responsavel) # Já está inline no Beneficiário


@admin.register(ValidacaoDocumentoIA)
class ValidacaoDocumentoIAAdmin(admin.ModelAdmin):
    list_display = (
        'solicitacao',
        'status_validacao',
        'status_laudo',
        'status_identidade',
        'status_endereco',
        'status_responsavel',
        'atualizado_em',
    )
    list_filter = ('status_validacao', 'atualizado_em')
    search_fields = ('solicitacao__protocolo', 'solicitacao__beneficiario__nome_completo')
    readonly_fields = (
        'atualizado_em',
        'status_documentos_resumo',
        'status_laudo',
        'status_identidade',
        'status_endereco',
        'status_responsavel',
        'log_ia',
    )

    fields = (
        'solicitacao',
        'status_validacao',
        'status_documentos_resumo',
        'status_laudo',
        'status_identidade',
        'status_endereco',
        'status_responsavel',
        'arquivo_laudo_medico',
        'arquivo_doc_tea',
        'arquivo_doc_responsavel',
        'arquivo_comprovante_endereco',
        'atualizado_em',
        'log_ia',
    )

    def _status_doc(self, obj, key):
        log = obj.log_ia if isinstance(obj.log_ia, dict) else {}
        sd = log.get('status_documentos') if isinstance(log.get('status_documentos'), dict) else None
        if not sd:
            # fallback quando status_documentos é exposto no serializer mas ainda não persistido no log
            etapas = log.get('etapas') if isinstance(log.get('etapas'), dict) else {}
            valid = etapas.get('validacao') if isinstance(etapas.get('validacao'), dict) else {}
            row = valid.get(key) if isinstance(valid.get(key), dict) else {}
            if not row:
                return 'PENDENTE'
            return 'VALIDADO' if row.get('ok') else 'INVALIDO'
        row = sd.get(key) if isinstance(sd.get(key), dict) else {}
        return row.get('status') or 'PENDENTE'

    def status_laudo(self, obj):
        return self._status_doc(obj, 'laudo')
    status_laudo.short_description = 'Laudo IA'

    def status_identidade(self, obj):
        return self._status_doc(obj, 'identidade')
    status_identidade.short_description = 'Identidade IA'

    def status_endereco(self, obj):
        return self._status_doc(obj, 'endereco')
    status_endereco.short_description = 'Endereço IA'

    def status_responsavel(self, obj):
        log = obj.log_ia if isinstance(obj.log_ia, dict) else {}
        etapas = log.get('etapas') if isinstance(log.get('etapas'), dict) else {}
        valid = etapas.get('validacao') if isinstance(etapas.get('validacao'), dict) else {}
        row = valid.get('responsavel') if isinstance(valid.get('responsavel'), dict) else {}
        if row:
            return 'VALIDADO' if row.get('ok') else 'INVALIDO'
        if obj.arquivo_doc_responsavel:
            return 'PENDENTE'
        return 'NAO_APLICAVEL'
    status_responsavel.short_description = 'Responsável IA'

    def status_documentos_resumo(self, obj):
        return (
            f"Laudo: {self.status_laudo(obj)} | "
            f"Identidade: {self.status_identidade(obj)} | "
            f"Endereço: {self.status_endereco(obj)} | "
            f"Responsável: {self.status_responsavel(obj)}"
        )
    status_documentos_resumo.short_description = 'Resumo por documento'