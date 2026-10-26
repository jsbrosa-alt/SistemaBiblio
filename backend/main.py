from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
from database import engine, Base, get_db
from models import Obra, Exemplar, CatalogoIsbnLocal
from schemas import ObraCreateSchema
from classificador import calcular_cdd_automatico, calcular_cutter_automatico, separar_nome_autor
from PIL import Image
from isbn_service import consultar_isbn_em_cascata, PASTA_CAPAS, baixar_e_converter_capa_webp
import os
import io


# Cria as tabelas no PostgreSQL automaticamente se ainda não existirem!
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SistemaBiblio - API de Gestão de Acervo")

# Libera o acesso para o seu frontend React (que vai rodar na porta 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(PASTA_CAPAS, exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

@app.get("/api/isbn/{isbn}")
async def buscar_metadados_isbn(isbn: str, db: Session = Depends(get_db)):
    isbn_limpo = "".join(c for c in isbn if c.isdigit() or c.upper() == "X")

    # Etapa 0 (Offline): Verifica se já temos esse ISBN salvo no nosso próprio PostgreSQL!
    existente = db.query(Obra).filter(Obra.isbn_issn == isbn_limpo).first()
    if existente:
        return {
            "ja_cadastrado": True,
            "obra_id": existente.id,
            "fonte": "Banco Local (PostgreSQL)",
            "titulo": existente.titulo,
            "subtitulo": existente.subtitulo,
            "autor_sobrenome": existente.autor_sobrenome,
            "autor_nome": existente.autor_nome,
            "editora": existente.editora,
            "ano_publicacao": existente.ano_publicacao,
            "paginas": existente.paginas,
            "capa_url": existente.capa_url,
            "cdd_oficial": existente.cdd,
            "cutter_sugerido": existente.cutter,
        }

    # Etapas 1, 2 e 3: Consulta TODAS as APIs (BrasilAPI + Open Library + Google Books) + Conversão WebP
    dados = await consultar_isbn_em_cascata(isbn_limpo)
    catalogo_local = db.query(CatalogoIsbnLocal).filter(CatalogoIsbnLocal.isbn == isbn_limpo).first()

    if dados:
        # Se algum campo ainda faltou nas APIs mas existe no catálogo local, complementa
        if catalogo_local:
            if not dados.get("autor_sobrenome") and catalogo_local.autor_completo and catalogo_local.autor_completo != "DESCONHECIDO":
                sob, nom = separar_nome_autor(catalogo_local.autor_completo)
                dados["autor_sobrenome"] = sob
                dados["autor_nome"] = nom
            if not dados.get("subtitulo") and catalogo_local.subtitulo:
                dados["subtitulo"] = catalogo_local.subtitulo
            if not dados.get("editora") and catalogo_local.editora:
                dados["editora"] = catalogo_local.editora
            if not dados.get("ano_publicacao") and catalogo_local.ano:
                dados["ano_publicacao"] = catalogo_local.ano
            if not dados.get("paginas") and catalogo_local.paginas:
                dados["paginas"] = catalogo_local.paginas

        # Alimenta/atualiza automaticamente o Catálogo Offline Local para futuras consultas sem internet
        try:
            autor_completo = f"{dados.get('autor_sobrenome', '')}, {dados.get('autor_nome', '')}".strip(", ") or "DESCONHECIDO"
            novo_cache = CatalogoIsbnLocal(
                isbn=isbn_limpo,
                titulo=dados["titulo"],
                subtitulo=dados.get("subtitulo") or None,
                autor_completo=autor_completo,
                editora=dados.get("editora") or None,
                ano=dados.get("ano_publicacao"),
                paginas=dados.get("paginas"),
            )
            db.merge(novo_cache)
            db.commit()
        except Exception:
            db.rollback()

        return {"ja_cadastrado": False, **dados}

    # Fallback Offline: Se estiver sem internet ou não achar nas APIs, usa a tabela catalogo_isbn_local
    if catalogo_local:
        sobrenome, nome = separar_nome_autor(catalogo_local.autor_completo)
        origem_padrao = "brasileira" if isbn_limpo.startswith(("97885", "97865", "85")) else "outras"
        cdd_sugerido = calcular_cdd_automatico("livro", "literatura", "romance_ficcao", origem_padrao, "adulto")
        cutter_sugerido = calcular_cutter_automatico(sobrenome, catalogo_local.titulo, "livro", nome)
        caminho_capa_local = f"/static/capas/{isbn_limpo}.webp"
        capa_local = caminho_capa_local if os.path.exists(os.path.join(PASTA_CAPAS, f"{isbn_limpo}.webp")) else None
        return {
            "ja_cadastrado": False,
            "fonte": "Catálogo Offline Local",
            "titulo": catalogo_local.titulo,
            "subtitulo": catalogo_local.subtitulo,
            "autor_sobrenome": sobrenome,
            "autor_nome": nome,
            "editora": catalogo_local.editora,
            "ano_publicacao": catalogo_local.ano,
            "paginas": catalogo_local.paginas,
            "capa_url": capa_local,
            "categoria_principal": "literatura",
            "genero_literario": "romance_ficcao",
            "origem_autor": origem_padrao,
            "publico_alvo": "adulto",
            "cdd_sugerido": cdd_sugerido,
            "cutter_sugerido": cutter_sugerido,
        }

    raise HTTPException(
        status_code=404,
        detail="ISBN não encontrado na BrasilAPI, Google Books nem Open Library. Preencha manualmente."
    )


@app.post("/api/upload-capa")
async def upload_capa_manual(arquivo: UploadFile = File(...)):
    """Se a pessoa enviar uma foto/imagem do computador, converte para WebP super leve e devolve a URL."""
    try:
        conteudo = await arquivo.read()
        img = Image.open(io.BytesIO(conteudo))
        if img.mode in ("RGBA", "P", "CMYK"):
            img = img.convert("RGB")

        if img.width > 400:
            proporcao = 400 / float(img.width)
            img = img.resize((400, int(img.height * proporcao)), Image.Resampling.LANCZOS)

        import uuid
        nome_arquivo = f"manual_{uuid.uuid4().hex[:10]}.webp"
        caminho_completo = os.path.join(PASTA_CAPAS, nome_arquivo)
        img.save(caminho_completo, format="WEBP", quality=80, method=6, optimize=True)

        return {"capa_url": f"/static/capas/{nome_arquivo}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Imagem inválida: {e}")


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
        dados.publico_alvo,
        dados.subdivisao_literaria,
    )
    cutter_final = dados.cutter_manual or calcular_cutter_automatico(
        sobrenome_limpo,
        dados.titulo,
        dados.tipo_acervo,
        nome_limpo
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

    # 5. Cria automaticamente os Exemplares Físicos (Números de Tombo sequenciais à prova de exclusões)
    ultimo_id = db.query(func.max(Exemplar.id)).scalar() or 0
    tombos_gerados = []
    
    for i in range(1, dados.quantidade_exemplares + 1):
        novo_tombo = f"TOMBO-{(ultimo_id + i):05d}"
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
    titulo: str = "",
    autor_sobrenome: str = "",
    autor_nome: str = "",
    tipo_acervo: str = "livro",
    subdivisao_literaria: str = "",
    categoria_principal: str = "literatura",
    genero_literario: str = "romance_ficcao",
    origem_autor: str = "brasileira",
    publico_alvo: str = "adulto"
):
    cdd = calcular_cdd_automatico(
        tipo_acervo,
        categoria_principal,
        genero_literario,
        origem_autor,
        publico_alvo,
        subdivisao_literaria,
    )
    if titulo.strip() or autor_sobrenome.strip():
        cutter = calcular_cutter_automatico(autor_sobrenome, titulo, tipo_acervo, autor_nome)
    else:
        cutter = "---"
    return {
        "cdd_gerado": cdd,
        "cutter_gerado": cutter,
        "etiqueta_lombada": f"{cdd} {cutter}"
    }
