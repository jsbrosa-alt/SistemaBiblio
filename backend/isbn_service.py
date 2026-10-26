import os
import io
import re
import asyncio
import httpx
from PIL import Image
from typing import Optional, Dict, Any, List
from classificador import (
    separar_nome_autor,
    calcular_cdd_automatico,
    calcular_cutter_automatico,
    inferir_classificacao_por_assuntos,
)

PASTA_CAPAS = os.path.join(os.path.dirname(__file__), "static", "capas")
os.makedirs(PASTA_CAPAS, exist_ok=True)


def _limpar_cdd_api(cdd_bruto: str) -> Optional[str]:
    """Limpa barras de segmentação da Biblioteca do Congresso (ex: '869.9/1' -> '869.91')"""
    if not cdd_bruto:
        return None
    limpo = cdd_bruto.replace("/", "").strip()
    if limpo.upper() in {"[FIC]", "FIC", "E", "[E]"} or re.match(r"^J\d*", limpo, re.IGNORECASE):
        return "028.5"
    match = re.match(r"^(B?\d{3}(?:\.\d+)?)", limpo, re.IGNORECASE)
    return match.group(1).upper() if match else None


async def baixar_e_converter_capa_webp(url_imagem: str, identificador: str) -> Optional[str]:
    if not url_imagem:
        return None

    caminho_arquivo = os.path.join(PASTA_CAPAS, f"{identificador}.webp")
    url_relativa = f"/static/capas/{identificador}.webp"

    if os.path.exists(caminho_arquivo):
        return url_relativa

    url_limpa = url_imagem.replace("http://", "https://").replace("&edge=curl", "")

    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(url_limpa)
            if resp.status_code != 200 or len(resp.content) < 1000:
                return None

            img = Image.open(io.BytesIO(resp.content))
            if img.mode in ("RGBA", "P", "CMYK"):
                img = img.convert("RGB")

            largura_max = 400
            if img.width > largura_max:
                proporcao = largura_max / float(img.width)
                nova_altura = int(float(img.height) * proporcao)
                img = img.resize((largura_max, nova_altura), Image.Resampling.LANCZOS)

            img.save(caminho_arquivo, format="WEBP", quality=80, method=6, optimize=True)
            return url_relativa
    except Exception as e:
        print(f"[Aviso] Falha ao processar capa para {identificador}: {e}")
        return None


async def buscar_na_brasil_api(client: httpx.AsyncClient, isbn: str) -> Optional[Dict[str, Any]]:
    """Fonte 1: BrasilAPI (CBL - traz sujeitos/temas em português)"""
    try:
        resp = await client.get(f"https://brasilapi.com.br/api/isbn/v1/{isbn}")
        if resp.status_code == 200:
            d = resp.json()
            autores = [str(a).strip() for a in (d.get("authors") or []) if str(a).strip()]
            autor_raw = autores[0] if autores else ""
            sobrenome, nome = separar_nome_autor(autor_raw) if autor_raw else ("", "")

            ano = d.get("year")
            paginas = d.get("page_count")
            assuntos = [str(a).strip() for a in (d.get("subjects") or []) if str(a).strip()]

            # Se a sinopse contiver marcadores claros de público infantil ou quadrinhos, adiciona como pista de assunto
            sinopse = str(d.get("synopsis") or "").lower()
            if any(k in sinopse for k in ["infantojuvenil", "infanto-juvenil", "literatura infantil", "livro infantil"]):
                assuntos.append("Literatura infantojuvenil")

            return {
                "fonte": "BrasilAPI",
                "titulo": (d.get("title") or "").strip(),
                "subtitulo": (d.get("subtitle") or "").strip(),
                "autor_sobrenome": sobrenome,
                "autor_nome": nome,
                "editora": (d.get("publisher") or "").strip(),
                "ano_publicacao": int(ano) if str(ano).isdigit() else None,
                "paginas": int(paginas) if str(paginas).isdigit() and int(paginas) > 0 else None,
                "capa_remota": d.get("cover_url"),
                "cdd_oficial": None,
                "assuntos": assuntos,
            }
    except Exception:
        pass
    return None


async def buscar_na_open_library(client: httpx.AsyncClient, isbn: str) -> Optional[Dict[str, Any]]:
    """Fonte 2: Open Library API (Extrai dados da Edição + Work para máximo de categorias e autor)"""
    try:
        titulo = ""
        subtitulo = ""
        autor_raw = ""
        editora = ""
        ano = None
        paginas = None
        capa = None
        cdd_extraido = None
        assuntos: List[str] = []

        # 1. Consulta jscmd=data
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
        resp = await client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            chave = f"ISBN:{isbn}"
            if chave in data:
                info = data[chave]
                titulo = (info.get("title") or "").strip()
                subtitulo = (info.get("subtitle") or "").strip()

                autores = info.get("authors") or []
                if autores:
                    autor_raw = autores[0].get("name", "") if isinstance(autores[0], dict) else str(autores[0])
                if not autor_raw and info.get("by_statement"):
                    autor_raw = str(info.get("by_statement")).strip().rstrip(".")

                editoras = info.get("publishers") or []
                if editoras:
                    editora = (editoras[0].get("name", "") if isinstance(editoras[0], dict) else str(editoras[0])).strip()

                data_pub = str(info.get("publish_date", ""))
                match_ano = re.search(r"\b(1[4-9]\d{2}|20\d{2})\b", data_pub)
                ano = int(match_ano.group(1)) if match_ano else None

                pg = info.get("number_of_pages")
                if str(pg).isdigit() and int(pg) > 0:
                    paginas = int(pg)

                capa = info.get("cover", {}).get("large") or info.get("cover", {}).get("medium")

                classificacoes = info.get("classifications") or {}
                lista_dewey = classificacoes.get("dewey_decimal_class") or []
                for dw in lista_dewey:
                    cdd_extraido = _limpar_cdd_api(str(dw))
                    if cdd_extraido:
                        break

                for campo_assunto in ("subjects", "subject_places", "subject_times"):
                    itens = info.get(campo_assunto) or []
                    for s in itens:
                        nome_s = s.get("name", "") if isinstance(s, dict) else str(s)
                        if nome_s.strip():
                            assuntos.append(nome_s.strip())

        # 2. Consulta o endpoint direto da Edição (/isbn/{isbn}.json) e da Obra (/works/OL...W.json)
        # para buscar categorias completas, CDD oficial ou autor caso faltem
        try:
            resp_ed = await client.get(f"https://openlibrary.org/isbn/{isbn}.json")
            if resp_ed.status_code == 200:
                ed_json = resp_ed.json()
                if not titulo:
                    titulo = (ed_json.get("title") or "").strip()
                if not subtitulo:
                    subtitulo = (ed_json.get("subtitle") or "").strip()
                if not editora and ed_json.get("publishers"):
                    editora = str(ed_json["publishers"][0]).strip()
                if not paginas:
                    pg_ed = ed_json.get("number_of_pages")
                    if str(pg_ed).isdigit() and int(pg_ed) > 0:
                        paginas = int(pg_ed)
                if not ano and ed_json.get("publish_date"):
                    m_ano = re.search(r"\b(1[4-9]\d{2}|20\d{2})\b", str(ed_json.get("publish_date")))
                    if m_ano:
                        ano = int(m_ano.group(1))
                if not cdd_extraido:
                    for dw in (ed_json.get("dewey_decimal_class") or []):
                        cdd_extraido = _limpar_cdd_api(str(dw))
                        if cdd_extraido:
                            break
                for s in (ed_json.get("subjects") or []):
                    if str(s).strip():
                        assuntos.append(str(s).strip())

                # Busca na Work vinculada (onde ficam os assuntos detalhados e autores na Open Library)
                works = ed_json.get("works") or []
                if works and isinstance(works[0], dict) and works[0].get("key"):
                    work_key = works[0]["key"]
                    resp_work = await client.get(f"https://openlibrary.org{work_key}.json")
                    if resp_work.status_code == 200:
                        work_json = resp_work.json()
                        for s in (work_json.get("subjects") or []):
                            if str(s).strip():
                                assuntos.append(str(s).strip())
                        if not cdd_extraido:
                            for dw in (work_json.get("dewey_number") or []):
                                cdd_extraido = _limpar_cdd_api(str(dw))
                                if cdd_extraido:
                                    break
                        if not autor_raw:
                            work_authors = work_json.get("authors") or []
                            if work_authors and isinstance(work_authors[0], dict):
                                author_obj = work_authors[0].get("author") or work_authors[0]
                                author_key = author_obj.get("key") if isinstance(author_obj, dict) else None
                                if author_key:
                                    resp_aut = await client.get(f"https://openlibrary.org{author_key}.json")
                                    if resp_aut.status_code == 200:
                                        autor_raw = (resp_aut.json().get("name") or "").strip()

                if not autor_raw and ed_json.get("by_statement"):
                    autor_raw = str(ed_json.get("by_statement")).strip().rstrip(".")
        except Exception:
            pass

        if not (titulo or autor_raw or assuntos or cdd_extraido):
            return None

        sobrenome, nome = separar_nome_autor(autor_raw) if autor_raw else ("", "")

        return {
            "fonte": "Open Library",
            "titulo": titulo,
            "subtitulo": subtitulo,
            "autor_sobrenome": sobrenome,
            "autor_nome": nome,
            "editora": editora,
            "ano_publicacao": ano,
            "paginas": paginas,
            "capa_remota": capa,
            "cdd_oficial": cdd_extraido,
            "assuntos": assuntos,
        }
    except Exception:
        pass
    return None


async def buscar_no_google_books(client: httpx.AsyncClient, isbn: str) -> Optional[Dict[str, Any]]:
    """Fonte 3: Google Books API (Inspeciona todos os volumes retornados para o ISBN)"""
    try:
        resp = await client.get(f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}")
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items") or []
            if not items:
                return None

            titulo = ""
            subtitulo = ""
            sobrenome = ""
            nome = ""
            editora = ""
            ano = None
            paginas = None
            capa = None
            assuntos: List[str] = []

            for item in items:
                info = item.get("volumeInfo", {})
                if not titulo and info.get("title"):
                    titulo = str(info["title"]).strip()
                if not subtitulo and info.get("subtitle"):
                    subtitulo = str(info["subtitle"]).strip()

                autores = [str(a).strip() for a in (info.get("authors") or []) if str(a).strip()]
                if autores:
                    cand_sob, cand_nome = separar_nome_autor(autores[0])
                    if not sobrenome:
                        sobrenome, nome = cand_sob, cand_nome
                    elif cand_sob == sobrenome and len(cand_nome) > len(nome):
                        nome = cand_nome

                if not editora and info.get("publisher"):
                    editora = str(info["publisher"]).strip()

                if not ano and info.get("publishedDate"):
                    m_ano = re.search(r"\b(1[4-9]\d{2}|20\d{2})\b", str(info["publishedDate"]))
                    if m_ano:
                        ano = int(m_ano.group(1))

                if not paginas:
                    pg = info.get("pageCount")
                    if str(pg).isdigit() and int(pg) > 0:
                        paginas = int(pg)

                if not capa:
                    imagens = info.get("imageLinks") or {}
                    capa = imagens.get("thumbnail") or imagens.get("smallThumbnail")

                if info.get("mainCategory"):
                    assuntos.append(str(info["mainCategory"]).strip())
                for cat in (info.get("categories") or []):
                    for parte in str(cat).split("/"):
                        if parte.strip():
                            assuntos.append(parte.strip())

                desc = str(info.get("description") or "").lower()
                if any(k in desc for k in ["infantojuvenil", "infanto-juvenil", "literatura infantil", "livro infantil"]):
                    assuntos.append("Literatura infantojuvenil")

            # Se o endpoint de busca não trouxe categorias ou autor, consulta o selfLink do 1º volume
            if (not assuntos or not sobrenome) and items[0].get("selfLink"):
                try:
                    resp_self = await client.get(items[0]["selfLink"])
                    if resp_self.status_code == 200:
                        v_info = resp_self.json().get("volumeInfo", {})
                        if not sobrenome and v_info.get("authors"):
                            sobrenome, nome = separar_nome_autor(str(v_info["authors"][0]))
                        if not editora and v_info.get("publisher"):
                            editora = str(v_info["publisher"]).strip()
                        if v_info.get("mainCategory"):
                            assuntos.append(str(v_info["mainCategory"]).strip())
                        for cat in (v_info.get("categories") or []):
                            for parte in str(cat).split("/"):
                                if parte.strip():
                                    assuntos.append(parte.strip())
                except Exception:
                    pass

            return {
                "fonte": "Google Books",
                "titulo": titulo,
                "subtitulo": subtitulo,
                "autor_sobrenome": sobrenome,
                "autor_nome": nome,
                "editora": editora,
                "ano_publicacao": ano,
                "paginas": paginas,
                "capa_remota": capa,
                "cdd_oficial": None,
                "assuntos": assuntos,
            }
    except Exception:
        pass
    return None


async def consultar_isbn_em_cascata(isbn_sujo: str) -> Optional[Dict[str, Any]]:
    isbn = "".join(c for c in isbn_sujo if c.isdigit() or c.upper() == "X")
    if len(isbn) not in (10, 13):
        return None

    headers = {"User-Agent": "SistemaBiblio/1.0 (Gestao de Acervo Bibliografico)"}

    acumulado: Dict[str, Any] = {
        "titulo": "",
        "subtitulo": "",
        "autor_sobrenome": "",
        "autor_nome": "",
        "editora": "",
        "ano_publicacao": None,
        "paginas": None,
        "capa_remota": None,
        "cdd_oficial": None,
    }
    todos_assuntos: List[str] = []
    fontes_utilizadas: List[str] = []

    async with httpx.AsyncClient(timeout=6.0, headers=headers, follow_redirects=True) as client:
        # Consulta TODAS as 3 APIs simultaneamente para garantir o máximo de metadados e categorias
        resultados = await asyncio.gather(
            buscar_na_brasil_api(client, isbn),
            buscar_na_open_library(client, isbn),
            buscar_no_google_books(client, isbn),
            return_exceptions=True,
        )

        for parcial in resultados:
            if not isinstance(parcial, dict) or not parcial:
                continue

            contribuiu = False

            # Se ainda não tinha autor, ou tinha só sobrenome sem prenome (ou abreviado), complementa da próxima API
            if not acumulado["autor_sobrenome"] and parcial.get("autor_sobrenome"):
                acumulado["autor_sobrenome"] = parcial["autor_sobrenome"]
                acumulado["autor_nome"] = parcial.get("autor_nome", "")
                contribuiu = True
            elif (
                parcial.get("autor_sobrenome") == acumulado["autor_sobrenome"]
                and len(parcial.get("autor_nome", "")) > len(acumulado.get("autor_nome", ""))
            ):
                acumulado["autor_nome"] = parcial["autor_nome"]
                contribuiu = True

            for chave in ("titulo", "subtitulo", "editora", "ano_publicacao", "paginas", "capa_remota", "cdd_oficial"):
                if not acumulado.get(chave) and parcial.get(chave):
                    acumulado[chave] = parcial[chave]
                    contribuiu = True

            if parcial.get("assuntos"):
                todos_assuntos.extend(parcial["assuntos"])
                contribuiu = True

            if contribuiu:
                fontes_utilizadas.append(parcial["fonte"])

        if not acumulado["titulo"]:
            return None

        # Também inclui título e subtítulo como contexto auxiliar caso as APIs tragam termos explícitos neles
        assuntos_para_inferencia = list(todos_assuntos)
        for texto_extra in (acumulado["titulo"], acumulado["subtitulo"]):
            if texto_extra and any(
                termo in texto_extra.lower()
                for termo in ("infantil", "infantojuvenil", "quadrinhos", "mangá", "manga", "poesia", "poemas", "contos", "crônicas", "biografia")
            ):
                assuntos_para_inferencia.append(texto_extra)

        # 1. Infere Categoria, Gênero, Origem, Público-Alvo e Período a partir de todos os assuntos + CDD oficial
        inferencia = inferir_classificacao_por_assuntos(assuntos_para_inferencia, acumulado["cdd_oficial"])

        # Se o ISBN começa com 97885 ou 97865 (Brasil) e não veio origem definida, assume brasileira
        if isbn.startswith(("97885", "97865", "85")) and "origem_autor" not in inferencia:
            inferencia["origem_autor"] = "brasileira"

        tipo_acervo = inferencia.get("tipo_acervo", "livro")
        cat = inferencia.get("categoria_principal", "literatura")
        gen = inferencia.get("genero_literario", "romance_ficcao")
        orig = inferencia.get("origem_autor", "brasileira")
        pub = inferencia.get("publico_alvo", "adulto")
        subdiv = inferencia.get("subdivisao_literaria", "")

        # 2. Define o CDD: Se for infantojuvenil é 028.5; senão prioriza CDD oficial da API ou calcula com a inferência
        if pub == "infantil":
            cdd_sugerido = "028.5"
        else:
            cdd_sugerido = acumulado["cdd_oficial"] or calcular_cdd_automatico(tipo_acervo, cat, gen, orig, pub, subdiv)

        cutter_sugerido = calcular_cutter_automatico(
            acumulado["autor_sobrenome"],
            acumulado["titulo"],
            tipo_acervo,
            acumulado["autor_nome"],
        )

        # 3. Baixa e converte a capa em WebP
        caminho_webp = None
        if acumulado["capa_remota"]:
            caminho_webp = await baixar_e_converter_capa_webp(acumulado["capa_remota"], isbn)

        if not caminho_webp:
            url_openlib_cover = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"
            caminho_webp = await baixar_e_converter_capa_webp(url_openlib_cover, isbn)

        return {
            **acumulado,
            "tipo_acervo": tipo_acervo,
            "categoria_principal": cat,
            "genero_literario": gen,
            "origem_autor": orig,
            "publico_alvo": pub,
            "subdivisao_literaria": subdiv,
            "cdd_sugerido": cdd_sugerido,
            "cutter_sugerido": cutter_sugerido,
            "assuntos_detectados": list(dict.fromkeys(todos_assuntos))[:10],
            "capa_url": caminho_webp,
            "isbn_limpo": isbn,
            "fonte": " + ".join(fontes_utilizadas) if fontes_utilizadas else "Base Online",
        }
