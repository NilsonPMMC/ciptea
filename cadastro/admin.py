from django.contrib import admin
from django.utils.html import format_html
from .models import Beneficiario, Responsavel, Solicitacao, Documento, Historico, ValidacaoDocumentoIA

# 1. Inline de Documentos (Geral)
class DocumentoInline(admin.TabularInline):
    model = Documento
    extra = 0
    fields = ('tipo', 'arquivo', 'status', 'motivo_rejeicao')

# 2. Inline de Histórico
class HistoricoInline(admin.TabularInline):
    model = Historico
    extra = 1
    fields = ('tipo_evento', 'titulo', 'mensagem', 'autor', 'data')
    readonly_fields = ('data',)

# 3. Inline de Responsável (Agora com o Documento de Identidade)
class ResponsavelInline(admin.StackedInline):
    model = Responsavel
    extra = 0
    can_delete = True
    verbose_name_plural = 'Responsáveis'
    fk_name = 'beneficiario'
    
    # Adicionamos os campos de documento para que o fiscal valide no cadastro do beneficiário
    fields = (
        ('perfil', 'nome'),
        ('cpf', 'rg', 'data_nascimento'),
        ('telefone', 'telefone2', 'email'),
        ('documento_identidade', 'status_documento', 'motivo_rejeicao_documento')
    )

@admin.register(Beneficiario)
class BeneficiarioAdmin(admin.ModelAdmin):
    list_display = ('nome_completo', 'cpf', 'data_nascimento', 'cidade', 'status_foto')
    search_fields = ('nome_completo', 'cpf')
    list_filter = ('cidade', 'sexo', 'status_foto')
    inlines = [ResponsavelInline]

@admin.register(Solicitacao)
class SolicitacaoAdmin(admin.ModelAdmin):
    list_display = ('protocolo', 'get_beneficiario_nome', 'status', 'data_solicitacao')
    list_filter = ('status', 'data_solicitacao')
    search_fields = ('protocolo', 'beneficiario__nome_completo', 'beneficiario__cpf')
    inlines = [DocumentoInline, HistoricoInline]
    
    def get_beneficiario_nome(self, obj):
        return obj.beneficiario.nome_completo
    get_beneficiario_nome.short_description = 'Beneficiário'

@admin.register(ValidacaoDocumentoIA)
class ValidacaoDocumentoIAAdmin(admin.ModelAdmin):
    list_display = (
        'solicitacao',
        'status_validacao',
        'status_laudo',
        'status_identidade',
        'status_endereco',
        'get_status_responsaveis',
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
        'get_status_responsaveis',
        'log_ia',
    )

    fields = (
        'solicitacao',
        'status_validacao',
        'status_documentos_resumo',
        'status_laudo',
        'status_identidade',
        'status_endereco',
        'get_status_responsaveis',
        'arquivo_laudo_medico',
        'arquivo_doc_tea',
        'arquivo_comprovante_endereco',
        'atualizado_em',
        'log_ia',
    )

    def _status_doc(self, obj, key):
        log = obj.log_ia if isinstance(obj.log_ia, dict) else {}
        sd = log.get('status_documentos', {})
        if not sd:
            etapas = log.get('etapas', {})
            valid = etapas.get('validacao', {})
            row = valid.get(key, {})
            if not row: return 'PENDENTE'
            return 'VALIDADO' if row.get('ok') else 'INVALIDO'
        row = sd.get(key, {})
        return row.get('status') or 'PENDENTE'

    def status_laudo(self, obj): return self._status_doc(obj, 'laudo')
    status_laudo.short_description = 'Laudo IA'

    def status_identidade(self, obj): return self._status_doc(obj, 'identidade')
    status_identidade.short_description = 'Identidade IA'

    def status_endereco(self, obj): return self._status_doc(obj, 'endereco')
    status_endereco.short_description = 'Endereço IA'

    def get_status_responsaveis(self, obj):
        """Resume o status de todos os responsáveis da solicitação."""
        responsaveis = obj.solicitacao.beneficiario.responsaveis.all()
        if not responsaveis:
            return "N/A"
        
        resumo = []
        for r in responsaveis:
            resumo.append(f"{r.nome[:10]}: {r.status_documento}")
        return " | ".join(resumo)
    get_status_responsaveis.short_description = 'Responsaveis'

    def status_documentos_resumo(self, obj):
        return (
            f"Laudo: {self.status_laudo(obj)} | "
            f"Identidade: {self.status_identidade(obj)} | "
            f"Endereço: {self.status_endereco(obj)}"
        )
    status_documentos_resumo.short_description = 'Resumo IA'

# Registros auxiliares
admin.site.register(Historico)
admin.site.register(Documento)
@admin.register(Responsavel)
class ResponsavelAdmin(admin.ModelAdmin):
    list_display = ('nome', 'perfil', 'beneficiario', 'status_documento')
    search_fields = ('nome', 'cpf', 'beneficiario__nome_completo')
    list_filter = ('perfil', 'status_documento')