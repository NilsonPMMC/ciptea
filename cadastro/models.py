import os
import uuid
from django.db import models
from django.utils import timezone

# Função para renomear arquivos e organizar pastas
def get_file_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join(f'uploads/{instance.__class__.__name__.lower()}/', filename)

# MIXIN: Reutilizável para Beneficiário e Responsável
class EnderecoMixin(models.Model):
    cep = models.CharField(max_length=9)
    logradouro = models.CharField(max_length=255)
    numero = models.CharField(max_length=20)
    complemento = models.CharField(max_length=100, blank=True, null=True)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)

    class Meta:
        abstract = True

class Beneficiario(EnderecoMixin):
    SEXO_CHOICES = [('M', 'Masculino'), ('F', 'Feminino'), ('O', 'Outro')]
    CID_CHOICES = [
        ('F84.0', 'F84.0 - Autismo Infantil'),
        ('F84.1', 'F84.1 - Autismo Atípico'),
        ('F84.5', 'F84.5 - Síndrome de Asperger'),
        ('F84.9', 'F84.9 - Transtorno global do desenvolvimento SOE'),
        # Adicione outros conforme necessidade
    ]

    # Dados Pessoais
    nome_completo = models.CharField(max_length=255)
    data_nascimento = models.DateField()
    local_nascimento = models.CharField(max_length=100, blank=True, null=True)
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES)
    escolaridade = models.CharField(max_length=100, blank=True, null=True)
    
    # Documentos
    rg = models.CharField(max_length=20, blank=True, null=True)
    cpf = models.CharField(max_length=14, unique=True) # Validar formato no Frontend/Serializer
    cns = models.CharField(max_length=20, blank=True, null=True, verbose_name="Cartão Nacional de Saúde")
    sis = models.CharField(max_length=20, blank=True, null=True)
    nis = models.CharField(max_length=20, blank=True, null=True)
    cid = models.CharField(max_length=10, choices=CID_CHOICES)
    
    # Filiação
    nome_pai = models.CharField(max_length=255, blank=True, null=True)
    nome_mae = models.CharField(max_length=255, blank=True, null=True)
    
    # Contato
    telefone = models.CharField(max_length=20)
    telefone2 = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    
    # Foto do Beneficiário (Para a carteirinha)
    foto = models.ImageField(upload_to=get_file_path, verbose_name="Foto 3x4")

    STATUS_FOTO_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('APROVADO', 'Aprovado'),
        ('REJEITADO', 'Rejeitado'),
    ]
    status_foto = models.CharField(max_length=20, choices=STATUS_FOTO_CHOICES, default='PENDENTE')
    motivo_rejeicao_foto = models.TextField(blank=True, null=True)
    
    observacao = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome_completo

class Responsavel(EnderecoMixin):
    VINCULO_CHOICES = [
        ('MAE', 'Mãe'),
        ('PAI', 'Pai'),
        ('AVO', 'Avô/Avó'),
        ('TIO', 'Tio/Tia'),
        ('TUTOR', 'Tutor/Curador'),
        ('PROPRIO', 'Próprio Beneficiário'),
        ('OUTRO', 'Outro'),
    ]

    beneficiario = models.ForeignKey(
        Beneficiario, 
        on_delete=models.CASCADE, 
        related_name='responsaveis'
    )
    perfil = models.CharField(max_length=20, choices=VINCULO_CHOICES)
    nome = models.CharField(max_length=255)
    rg = models.CharField(max_length=20, blank=True, null=True)
    cpf = models.CharField(max_length=14)
    data_nascimento = models.DateField(blank=True, null=True)
    telefone = models.CharField(max_length=20)
    telefone2 = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return f"{self.nome} ({self.perfil}) - Resp. por {self.beneficiario.nome_completo}"

class Solicitacao(models.Model):
    STATUS_CHOICES = [
        ('LEGADO', 'Sistema Antigo (Aguardando Atualização)'),
        ('ABERTO', 'Aberto'),
        ('ANALISE', 'Em Análise'),
        ('PENDENTE', 'Pendência de Documento'),
        ('APROVADO', 'Aprovado'),
        ('IMPRESSO', 'Impresso/Entregue'),
        ('INDEFERIDO', 'Indeferido'),
    ]

    beneficiario = models.ForeignKey(Beneficiario, on_delete=models.CASCADE)
    protocolo = models.CharField(max_length=20, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ABERTO')
    data_solicitacao = models.DateTimeField(auto_now_add=True)
    data_analise = models.DateTimeField(blank=True, null=True)
    analista_responsavel = models.CharField(max_length=100, blank=True, null=True)
    ORIGEM_CHOICES = [
        ('SISTEMA_NOVO', 'Sistema Novo (Digital)'),
        ('LEGADO', 'Sistema Antigo (Importado)'),
    ]
    TIPO_FLUXO_CHOICES = [
        ('PRIMEIRA_VIA', 'Primeira via'),
        ('RENOVACAO', 'Renovação'),
    ]
    origem = models.CharField(max_length=20, choices=ORIGEM_CHOICES, default='SISTEMA_NOVO')
    tipo_fluxo = models.CharField(max_length=20, choices=TIPO_FLUXO_CHOICES, default='PRIMEIRA_VIA')
    renovacao_de = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='renovacoes')
    primeira_digitalizacao = models.BooleanField(default=False)
    validade_anos = models.PositiveSmallIntegerField(default=5)

    def save(self, *args, **kwargs):
        if not self.protocolo:
            # Gera protocolo simples: ANO + 6 digitos aleatorios (ex: 2024123456)
            import random
            self.protocolo = f"{timezone.now().year}{random.randint(100000, 999999)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Protocolo {self.protocolo} - {self.status}"

class Documento(models.Model):
    TIPO_DOC_CHOICES = [
        ('LAUDO', 'Laudo Médico'),
        ('RG_BENEF', 'RG do Beneficiário'),
        ('RG_RESP', 'RG do Responsável'),
        ('COMP_RES', 'Comprovante de Residência'),
        ('OUTRO', 'Outro'),
    ]

    solicitacao = models.ForeignKey(Solicitacao, on_delete=models.CASCADE, related_name='anexos')
    arquivo = models.FileField(upload_to=get_file_path)
    tipo = models.CharField(max_length=20, choices=TIPO_DOC_CHOICES)
    descricao = models.CharField(max_length=100)
    aprovado = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, 
        choices=[('PENDENTE', 'Aguardando Análise'), ('APROVADO', 'Aprovado'), ('REJEITADO', 'Rejeitado')],
        default='PENDENTE'
    )
    motivo_rejeicao = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.solicitacao.protocolo}"


class ValidacaoDocumentoIA(models.Model):
    STATUS_VALIDACAO_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('PROCESSANDO', 'Processando'),
        ('APROVADO_IA', 'Aprovado pela IA'),
        ('REVISAO_MANUAL', 'Revisão Manual'),
    ]

    solicitacao = models.OneToOneField(Solicitacao, on_delete=models.CASCADE, related_name='validacao_ia')
    arquivo_laudo_medico = models.FileField(upload_to=get_file_path, blank=True, null=True)
    arquivo_doc_tea = models.FileField(upload_to=get_file_path, blank=True, null=True)
    arquivo_doc_responsavel = models.FileField(upload_to=get_file_path, blank=True, null=True)
    arquivo_comprovante_endereco = models.FileField(upload_to=get_file_path, blank=True, null=True)
    status_validacao = models.CharField(max_length=20, choices=STATUS_VALIDACAO_CHOICES, default='PENDENTE')
    log_ia = models.JSONField(default=dict, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Validação IA {self.solicitacao.protocolo} - {self.status_validacao}"


class Historico(models.Model):
    solicitacao = models.ForeignKey(Solicitacao, on_delete=models.CASCADE, related_name='historico')
    data = models.DateTimeField(auto_now_add=True)
    titulo = models.CharField(max_length=100)
    mensagem = models.TextField(blank=True, null=True)
    autor = models.CharField(max_length=100, default='Sistema')
    
    tipo_evento = models.CharField(
        max_length=20, 
        choices=[('CRIACAO', 'Criação'), ('ANALISE', 'Análise'), ('PENDENCIA', 'Pendência'), ('CONCLUSAO', 'Conclusão')],
        default='ANALISE'
    )

    class Meta:
        ordering = ['-data'] # Do mais recente para o mais antigo

    def __str__(self):
        return f"{self.titulo} - {self.solicitacao.protocolo}"