from django.contrib import admin
from .models import Beneficiario, Responsavel, Solicitacao, Documento, Historico

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