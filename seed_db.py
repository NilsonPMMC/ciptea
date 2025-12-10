import os
import django
import random
from io import BytesIO
from PIL import Image, ImageDraw
from django.core.files.base import ContentFile

# Configuração do Django para rodar script avulso
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from faker import Faker
from cadastro.models import Beneficiario, Responsavel, Solicitacao, Documento, Historico

# Inicializa o Faker pt-BR
fake = Faker('pt_BR')

# Bairros reais de Mogi para dar contexto
BAIRROS_MOGI = [
    'Centro', 'Bras Cubas', 'Cezar de Souza', 'Jundiapeba', 
    'Mogilar', 'Alto do Ipiranga', 'Vila Oliveira', 'Sabaúna', 
    'Biritiba Ussu', 'Taiaçupeba'
]

def generate_dummy_image(color='blue', name='imagem.jpg'):
    """Gera uma imagem simples de uma cor sólida para teste"""
    img = Image.new('RGB', (200, 200), color=color)
    d = ImageDraw.Draw(img)
    d.text((10,10), "TESTE", fill=(255,255,255))
    
    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    return ContentFile(buffer.getvalue(), name)

def seed(qtd=10):
    print(f"🌱 Criando {qtd} registros de teste...")
    
    for i in range(qtd):
        # 1. Criar Beneficiário
        sexo = random.choice(['M', 'F'])
        primeiro_nome = fake.first_name_male() if sexo == 'M' else fake.first_name_female()
        
        beneficiario = Beneficiario(
            nome_completo=f"{primeiro_nome} {fake.last_name()} {fake.last_name()}",
            data_nascimento=fake.date_of_birth(minimum_age=2, maximum_age=18),
            local_nascimento="Mogi das Cruzes",
            sexo=sexo,
            escolaridade="Ensino Fundamental Incompleto",
            rg=fake.rg(),
            cpf=fake.cpf(),
            cns=fake.bothify(text='7###############'), # Formato CNS
            cid=random.choice(['F84.0', 'F84.1', 'F84.5']),
            nome_pai=fake.name_male(),
            nome_mae=fake.name_female(),
            telefone=fake.cellphone_number(),
            email=fake.email(),
            cep="08700-000", # Genérico de Mogi
            logradouro=fake.street_name(),
            numero=fake.building_number(),
            bairro=random.choice(BAIRROS_MOGI),
            cidade="Mogi das Cruzes",
            estado="SP",
            observacao="Cadastro gerado automaticamente via seed."
        )
        
        # Salva a foto 3x4 fake
        foto_blob = generate_dummy_image(color='green', name=f'foto_{i}.jpg')
        beneficiario.foto.save(f'foto_{i}.jpg', foto_blob, save=False)
        beneficiario.save()

        # 2. Criar Responsável
        resp = Responsavel(
            beneficiario=beneficiario,
            perfil=random.choice(['MAE', 'PAI']),
            nome=beneficiario.nome_mae if random.choice([True, False]) else beneficiario.nome_pai,
            cpf=fake.cpf(),
            rg=fake.rg(),
            telefone=beneficiario.telefone,
            cep=beneficiario.cep,
            logradouro=beneficiario.logradouro,
            numero=beneficiario.numero,
            bairro=beneficiario.bairro,
            cidade=beneficiario.cidade,
            estado=beneficiario.estado
        )
        resp.save()

        # 3. Criar Solicitação (Aleatória)
        status_random = random.choice(['ABERTO', 'ANALISE', 'PENDENTE', 'APROVADO'])
        solicitacao = Solicitacao(
            beneficiario=beneficiario,
            status=status_random
        )
        solicitacao.save() # Gera protocolo auto

        # 4. Criar Documentos Anexos
        # Cria um Laudo
        doc_laudo = Documento(
            solicitacao=solicitacao,
            tipo='LAUDO',
            descricao='Laudo Médico Neuro',
            aprovado=(status_random == 'APROVADO')
        )
        file_laudo = generate_dummy_image(color='red', name='laudo.jpg')
        doc_laudo.arquivo.save('laudo.jpg', file_laudo)
        
        # Cria um RG
        doc_rg = Documento(
            solicitacao=solicitacao,
            tipo='RG_BENEF',
            descricao='RG Frente e Verso',
            aprovado=(status_random == 'APROVADO')
        )
        file_rg = generate_dummy_image(color='gray', name='rg.jpg')
        doc_rg.arquivo.save('rg.jpg', file_rg)

        Historico.objects.create(
            solicitacao=solicitacao,
            titulo="Solicitação Recebida",
            mensagem="Cadastro realizado com sucesso. Aguardando análise.",
            tipo_evento='CRIACAO'
        )
        
        if solicitacao.status == 'PENDENTE':
            Historico.objects.create(
                solicitacao=solicitacao,
                titulo="Análise Realizada",
                mensagem="Identificamos problemas na documentação. Verifique os itens rejeitados.",
                tipo_evento='PENDENCIA',
                autor="Fiscal PAC"
            )
            # Rejeita o Laudo para teste
            doc_laudo.status = 'REJEITADO'
            doc_laudo.motivo_rejeicao = "Documento ilegível ou data vencida."
            doc_laudo.save()

        print(f"   [{i+1}/{qtd}] Gerado: {beneficiario.nome_completo} - Protocolo: {solicitacao.protocolo}")

    print("✅ Seed concluído com sucesso!")

if __name__ == '__main__':
    seed(15) # Gera 15 registros