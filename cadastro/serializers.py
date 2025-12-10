from rest_framework import serializers
from .models import Beneficiario, Responsavel, Solicitacao, Documento, Historico

class ResponsavelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Responsavel
        fields = ['id', 'nome', 'cpf', 'telefone', 'perfil']

class BeneficiarioSerializer(serializers.ModelSerializer):
    responsaveis = ResponsavelSerializer(many=True)

    class Meta:
        model = Beneficiario
        fields = '__all__'

    def create(self, validated_data):
        responsaveis_data = validated_data.pop('responsaveis', [])
        
        beneficiario = Beneficiario.objects.create(**validated_data)
        
        for resp_data in responsaveis_data:
            Responsavel.objects.create(beneficiario=beneficiario, **resp_data)
            
        return beneficiario

    def update(self, instance, validated_data):
            # 1. Separa a lista de responsáveis
            responsaveis_data = validated_data.pop('responsaveis', None)

            # 2. Atualiza os campos do Beneficiário (incluindo a foto)
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            instance.save()

            # 3. Atualiza os Responsáveis (Apaga antigos e cria novos)
            if responsaveis_data is not None:
                instance.responsaveis.all().delete()
                for resp_data in responsaveis_data:
                    Responsavel.objects.create(beneficiario=instance, **resp_data)

            return instance

class DocumentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Documento
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

    class Meta:
        model = Solicitacao
        fields = '__all__'

    def update(self, instance, validated_data):
        parecer = validated_data.pop('parecer_final', None)
        status_novo = validated_data.get('status')
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