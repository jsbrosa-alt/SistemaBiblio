from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import unicodedata

from database import engine, Base, get_db
from models import Obra, Exemplar
from schemas import ObraCreateSchema
from classificador import calcular_cdd_automatico, calcular_cutter_automatico, separar_nome_autor

# Cria as tabelas no PostgreSQL automaticamente se ainda não existirem!
Base.metadata.create_all(bind=engine)

app = FastAPI(title="API Biblioteca Pública de São Marcos")

# Libera o acesso para o seu frontend React (que vai rodar na porta 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def gerar_cutter_simplificado(sobrenome: str, titulo: str) -> str:
    """Remove acentos e gera a estrutura base do Cutter (Ex: ASSIS + Dom Casmurro -> A848d)"""
    limpo = ''.join(c for c in unicodedata.normalize('NFD', sobrenome) if unicodedata.category(c) != 'Mn')
    letra_autor = limpo[0].upper()
    
    # Ignora artigos iniciais do título (Stopwords de biblioteconomia)
    palavras = titulo.strip().split()
    artigos = {"o", "a", "os", "as", "um", "uma", "de", "da", "do"}
    primeira_palavra = palavras[1] if (len(palavras) > 1 and palavras[0].lower() in artigos) else palavras[0]
    letra_titulo = primeira_palavra[0].lower()
    
    # (No próximo passo plugamos o dicionário completo da tabela Cutter-Sanborn aqui)
    codigo_numerico = sum(ord(c) for c in limpo[:4]) % 900 + 100
    return f"{letra_autor}{codigo_numerico}{letra_titulo}"


@app.post("/api/obras", status_code=201)
def cadastrar_obra(dados: ObraCreateSchema, db: Session = Depends(get_db)):
    # 1. Guardrail Anti-Clone: Verifica se o ISBN já existe na base de dados
    if dados.isbn_issn:
        existente = db.query(Obra).filter(Obra.isbn_issn == dados.isbn_issn).first()
        if existente:
            raise HTTPException(
                status_code=409,
                detail=f"Este ISBN já está registado como '{existente.titulo}' (ID {existente.id}). Adicione apenas um novo exemplar!"
            )

    # 2. Destrincha o nome caso tenham digitado o nome completo num campo só
    sobrenome_limpo, nome_limpo = separar_nome_autor(
        dados.autor_sobrenome, 
        dados.autor_nome or ""
    )

    # 3. Gera o código CDD e Cutter automaticamente
    cdd_final = dados.cdd_manual or calcular_cdd_automatico(
        dados.tipo_acervo,
        dados.categoria_principal,
        dados.genero_literario,
        dados.origem_autor,
        dados.publico_alvo
    )
    cutter_final = dados.cutter_manual or calcular_cutter_automatico(
        sobrenome_limpo,
        dados.titulo,
        dados.tipo_acervo
    )

    # 4. Monta o objeto SQLAlchemy (Obra) completo e fecha o parêntese!
    nova_obra = Obra(
        tipo_acervo=dados.tipo_acervo,
        isbn_issn=dados.isbn_issn,
        titulo=dados.titulo,
        subtitulo=dados.subtitulo,
        autor_sobrenome=sobrenome_limpo,
        autor_nome=nome_limpo,
        editora=dados.editora,
        ano_publicacao=dados.ano_publicacao,
        edicao=dados.edicao,
        paginas=dados.paginas,
        idioma=dados.idioma,
        capa_url=dados.capa_url,
        cdd=cdd_final,
        cutter=cutter_final,
        colecao=dados.colecao,
        marc21_extras=dados.marc21_extras
    )
    db.add(nova_obra)
    db.flush()  # Gera o ID da nova_obra antes de fechar a transação

    # 5. Cria automaticamente os Exemplares Físicos (Números de Tombo)
    total_atual = db.query(Exemplar).count()
    tombos_gerados = []
    
    for i in range(1, dados.quantidade_exemplares + 1):
        novo_tombo = f"SM-{(total_atual + i):05d}"
        exemplar = Exemplar(
            obra_id=nova_obra.id,
            codigo_tombo=novo_tombo,
            numero_exemplar=i,
            status="DISPONIVEL"
        )
        db.add(exemplar)
        tombos_gerados.append(novo_tombo)

    # 6. Grava tudo em definitivo no PostgreSQL
    db.commit()
    db.refresh(nova_obra)

    return {
        "mensagem": "Obra e exemplares registados com sucesso!",
        "obra_id": nova_obra.id,
        "autor_formatado": f"{nova_obra.autor_sobrenome}, {nova_obra.autor_nome}".strip(", "),
        "etiqueta_chamada": f"{nova_obra.cdd} {nova_obra.cutter}",
        "tombos_gerados": tombos_gerados
    }

@app.get("/api/classificar-preview")
def preview_classificacao(
    titulo: str,
    autor_sobrenome: str,
    tipo_acervo: str = "livro",
    categoria_principal: str = "literatura",
    genero_literario: str = "romance_ficcao",
    origem_autor: str = "brasileira",
    publico_alvo: str = "adulto"
):
    cdd = calcular_cdd_automatico(tipo_acervo, categoria_principal, genero_literario, origem_autor, publico_alvo)
    cutter = calcular_cutter_automatico(autor_sobrenome, titulo, tipo_acervo)
    return {
        "cdd_gerado": cdd,
        "cutter_gerado": cutter,
        "etiqueta_lombada": f"{cdd} {cutter}"
    }