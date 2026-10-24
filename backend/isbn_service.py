import os
import io
import re
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
            autores = d.get("authors") or []
            autor_raw = autores[0] if autores else ""
            sobrenome, nome = separar_nome_autor(autor_raw) if autor_raw else ("", "")
            
            ano = d.get("year")
            paginas = d.get("page_count")
            assuntos = d.get("subjects") or []
            
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
                "assuntos": [str(a) for a in assuntos],
            }
    except Exception:
        pass
    return None


async def buscar_na_open_library(client: httpx.AsyncClient, isbn: str) -> Optional[Dict[str, Any]]:
    """Fonte 2: Open Library API (Extrai Dewey Decimal Class oficial se catalogado!)"""
    try:
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
        resp = await client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            chave = f"ISBN:{isbn}"
            if chave in data:
                info = data[chave]
                autores = info.get("authors") or []
                autor_raw = autores[0].get("name", "") if autores else ""
                sobrenome, nome = separar_nome_autor(autor_raw) if autor_raw else ("", "")
                
                editoras = info.get("publishers") or []
                editora = editoras[0].get("name", "") if editoras else ""
                
                data_pub = str(info.get("publish_date", ""))
                match_ano = re.search(r'\b(1[4-9]\d{2}|20\d{2})\b', data_pub)
                ano = int(match_ano.group(1)) if match_ano else None

                paginas = info.get("number_of_pages")
                capa = info.get("cover", {}).get("large") or info.get("cover", {}).get("medium")

                # EXTRAÇÃO DO CDD OFICIAL DA OPEN LIBRARY
                classificacoes = info.get("classifications") or {}
                lista_dewey = classificacoes.get("dewey_decimal_class") or []
                cdd_extraido = _limpar_cdd_api(lista_dewey[0]) if lista_dewey else None

                # Se não veio no jscmd=data, checa rápido o endpoint direto da edição (.json)
                if not cdd_extraido:
                    try:
                        resp_ed = await client.get(f"https://openlibrary.org/isbn/{isbn}.json")
                        if resp_ed.status_code == 200:
                            ed_json = resp_ed.json()
                            dewey_ed = ed_json.get("dewey_decimal_class") or []
                            if dewey_ed:
                                cdd_extraido = _limpar_cdd_api(dewey_ed[0])
                    except Exception:
                        pass

                assuntos_raw = info.get("subjects") or []
                assuntos = [s.get("name", "") if isinstance(s, dict) else str(s) for s in assuntos_raw]

                return {
                    "fonte": "Open Library",
                    "titulo": (info.get("title") or "").strip(),
                    "subtitulo": (info.get("subtitle") or "").strip(),
                    "autor_sobrenome": sobrenome,
                    "autor_nome": nome,
                    "editora": editora.strip(),
                    "ano_publicacao": ano,
                    "paginas": int(paginas) if str(paginas).isdigit() and int(paginas) > 0 else None,
                    "capa_remota": capa,
                    "cdd_oficial": cdd_extraido,
                    "assuntos": assuntos,
                }
    except Exception:
        pass
    return None


async def buscar_no_google_books(client: httpx.AsyncClient, isbn: str) -> Optional[Dict[str, Any]]:
    """Fonte 3: Google Books API (Extrai categories para inferência de CDD)"""
    try:
        resp = await client.get(f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("totalItems", 0) > 0:
                info = data["items"][0].get("volumeInfo", {})
                autores = info.get("authors") or []
                autor_raw = autores[0] if autores else ""
                sobrenome, nome = separar_nome_autor(autor_raw) if autor_raw else ("", "")
                
                ano_str = str(info.get("publishedDate", ""))[:4]
                paginas = info.get("pageCount")
                imagens = info.get("imageLinks") or {}
                capa = imagens.get("thumbnail") or imagens.get("smallThumbnail")
                categorias = info.get("categories") or []
                
                return {
                    "fonte": "Google Books",
                    "titulo": (info.get("title") or "").strip(),
                    "subtitulo": (info.get("subtitle") or "").strip(),
                    "autor_sobrenome": sobrenome,
                    "autor_nome": nome,
                    "editora": (info.get("publisher") or "").strip(),
                    "ano_publicacao": int(ano_str) if ano_str.isdigit() else None,
                    "paginas": int(paginas) if str(paginas).isdigit() and int(paginas) > 0 else None,
                    "capa_remota": capa,
                    "cdd_oficial": None,
                    "assuntos": [str(c) for c in categorias],
                }
    except Exception:
        pass
    return None


def _dados_completos(d: Dict[str, Any]) -> bool:
    campos_obrigatorios = ["titulo", "autor_sobrenome", "editora", "ano_publicacao", "paginas", "capa_remota", "cdd_oficial"]
    return all(bool(d.get(campo)) for campo in campos_obrigatorios)


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

    buscadores = [
        buscar_na_brasil_api,
        buscar_na_open_library,
        buscar_no_google_books,
    ]

    async with httpx.AsyncClient(timeout=6.0, headers=headers, follow_redirects=True) as client:
        for buscador in buscadores:
            parcial = await buscador(client, isbn)
            if not parcial:
                continue

            contribuiu = False
            for chave in acumulado.keys():
                if not acumulado.get(chave) and parcial.get(chave):
                    acumulado[chave] = parcial[chave]
                    contribuiu = True

            if parcial.get("autor_sobrenome") == acumulado["autor_sobrenome"] and not acumulado["autor_nome"]:
                acumulado["autor_nome"] = parcial.get("autor_nome", "")

            if parcial.get("assuntos"):
                todos_assuntos.extend(parcial["assuntos"])
                contribuiu = True

            if contribuiu:
                fontes_utilizadas.append(parcial["fonte"])

            if _dados_completos(acumulado):
                break

        if not acumulado["titulo"]:
            return None

        # 1. Infere Categoria, Gênero e Origem a partir dos assuntos retornados pelas APIs
        inferencia = inferir_classificacao_por_assuntos(todos_assuntos)
        # Se o ISBN começa com 97885 ou 97865 (Brasil) e não veio origem definida, assume brasileira
        if isbn.startswith(("97885", "97865", "85")) and "origem_autor" not in inferencia:
            inferencia["origem_autor"] = "brasileira"

        cat = inferencia.get("categoria_principal", "literatura")
        gen = inferencia.get("genero_literario", "romance_ficcao")
        orig = inferencia.get("origem_autor", "brasileira")
        pub = inferencia.get("publico_alvo", "adulto")

        # 2. Define o CDD: Prioriza o CDD oficial da API (se existir), senão calcula com a inferência!
        cdd_sugerido = acumulado["cdd_oficial"] or calcular_cdd_automatico("livro", cat, gen, orig, pub)
        cutter_sugerido = calcular_cutter_automatico(acumulado["autor_sobrenome"], acumulado["titulo"], "livro")

        # 3. Baixa e converte a capa em WebP
        caminho_webp = None
        if acumulado["capa_remota"]:
            caminho_webp = await baixar_e_converter_capa_webp(acumulado["capa_remota"], isbn)

        if not caminho_webp:
            url_openlib_cover = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"
            caminho_webp = await baixar_e_converter_capa_webp(url_openlib_cover, isbn)

        return {
            **acumulado,
            "categoria_principal": cat,
            "genero_literario": gen,
            "origem_autor": orig,
            "publico_alvo": pub,
            "cdd_sugerido": cdd_sugerido,
            "cutter_sugerido": cutter_sugerido,
            "assuntos_detectados": list(dict.fromkeys(todos_assuntos))[:5],
            "capa_url": caminho_webp,
            "isbn_limpo": isbn,
            "fonte": " + ".join(fontes_utilizadas) if fontes_utilizadas else "Base Online",
        }