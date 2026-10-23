import unicodedata
import re
from typing import Optional, Tuple

# 1. DICIONÁRIO DE TEMAS GERAIS (Não-Ficção e Categorias Diretas)
MAPA_TEMAS_CDD = {
    # Geral e Computação
    "computacao": "004",
    "programacao": "005",
    "enciclopedia": "030",
    "jornalismo": "070",
    # Filosofia e Psicologia
    "filosofia": "100",
    "psicologia": "150",
    "autoajuda": "158.1",
    "etica": "170",
    # Religião
    "religiao": "200",
    "teologia_crista": "230",
    "espiritismo": "133.9",
    # Ciências Sociais e Direito
    "sociologia": "301",
    "politica": "320",
    "economia": "330",
    "direito": "340",
    "administracao_publica": "350",
    "educacao": "370",
    "folclore": "398",
    # Línguas
    "linguistica": "410",
    "lingua_portuguesa": "469",
    "lingua_inglesa": "420",
    # Ciências Exatas e Naturais
    "ciencias": "500",
    "matematica": "510",
    "astronomia": "520",
    "fisica": "530",
    "quimica": "540",
    "biologia": "570",
    "botanica": "580",
    "zoologia": "590",
    # Tecnologia, Saúde e Práticas
    "medicina_saude": "610",
    "engenharia": "620",
    "agricultura": "630",
    "culinaria": "641.5",
    "administracao_empresas": "658",
    # Artes, Esportes e Quadrinhos
    "artes": "700",
    "arquitetura": "720",
    "quadrinhos_mangas": "741.5",
    "musica": "780",
    "cinema_teatro": "791",
    "esportes": "796",
    # História, Geografia e Biografias
    "geografia_viagens": "910",
    "geografia_brasil": "918.1",
    "biografia": "920",
    "historia_geral": "909",
    "historia_antiga": "930",
    "historia_europa": "940",
    "historia_brasil": "981",
    "historia_rs": "981.65", # Específico para o Rio Grande do Sul / Região!
}

# 2. MATRIZ DE LITERATURA (Raiz Nacionalidade + Sufixo de Gênero Literário)
RAIZ_LITERATURA_ORIGEM = {
    "brasileira": "869",   # Na prática brasileira usa-se B869 ou 869.3
    "portuguesa": "869",
    "americana": "81",
    "inglesa": "82",
    "alema": "83",
    "francesa": "84",
    "italiana": "85",
    "espanhola": "86",
    "latino_americana": "86",
    "classica_grega_latina": "88",
    "outras": "89",
}

SUFIXO_GENERO_LITERARIO = {
    "poesia": "1",
    "teatro_drama": "2",
    "romance_ficcao": "3",
    "conto_novela": "3",
    "cronica_ensaio": "4",
    "discursos": "5",
    "cartas": "6",
    "humor_satira": "7",
    "infantojuvenil": "028.5", # Sobrepõe como Literatura Infantil/Juvenil
}

# Artigos ignorados no início do título (Português, Inglês, Espanhol, Francês)
STOPWORDS_TITULO = {
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "the", "an", "el", "la", "los", "las", "un", "una", "le", "les"
}

# Partículas ignoradas antes do sobrenome
PARTICULAS_AUTOR = {"de", "da", "do", "das", "dos", "del", "van", "von", "e"}
SUFIXOS_PARENTESCO = {"FILHO", "NETO", "SOBRINHO", "JUNIOR", "JR"}

def separar_nome_autor(sobrenome_ou_completo: str, prenome_atual: str = "") -> Tuple[str, str]:
    """
    Destrincha o nome caso o usuário tenha digitado o nome completo num campo só.
    Trata casos especiais da ABNT (Filho, Neto, Sobrinho, Júnior).
    Ex: ("João Cabral de Melo Neto", "") -> ("MELO NETO", "João Cabral de")
    Ex: ("Machado de Assis", "")         -> ("ASSIS", "Machado de")
    Ex: ("ASSIS", "Machado de")          -> ("ASSIS", "Machado de")
    """
    texto = sobrenome_ou_completo.strip()
    prenome = prenome_atual.strip()

    # 1. Se o usuário digitou com vírgula ("ASSIS, Machado de")
    if "," in texto:
        partes = texto.split(",", 1)
        novo_sobrenome = partes[0].strip().upper()
        resto_nome = partes[1].strip()
        novo_prenome = f"{resto_nome} {prenome}".strip() if prenome else resto_nome
        return novo_sobrenome, novo_prenome

    palavras = texto.split()

    # 2. Se só tem 1 palavra (ex: "ASSIS" ou "ZIRALDO"), já está separado!
    if len(palavras) <= 1:
        return texto.upper(), prenome

    # 3. Verifica se é um sobrenome composto com parentesco (ex: "Melo Neto")
    ultima = limpar_texto(palavras[-1]).upper()
    penultima = palavras[-2]

    if ultima in SUFIXOS_PARENTESCO:
        # Se tem apenas 2 palavras ("Melo Neto") e o prenome já veio preenchido ("João Cabral de")
        if len(palavras) == 2 and prenome:
            return f"{limpar_texto(penultima).upper()} {ultima}", prenome
        # Se colou o nome inteiro ("João Cabral de Melo Neto")
        sobrenome_final = f"{limpar_texto(penultima).upper()} {ultima}"
        extraido_prenome = " ".join(palavras[:-2])
    else:
        # Caso normal ("Machado de Assis" -> tira "Assis" e joga "Machado de" pro prenome)
        sobrenome_final = limpar_texto(palavras[-1]).upper()
        extraido_prenome = " ".join(palavras[:-1])

    # Junta o que foi extraído com o que já estava no campo de nome (se houver)
    prenome_final = f"{prenome} {extraido_prenome}".strip() if prenome else extraido_prenome
    return sobrenome_final, prenome_final

def limpar_texto(texto: str) -> str:
    """Remove acentos, caracteres especiais e espaços extras."""
    sem_acento = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return re.sub(r'[^a-zA-Z0-9\s]', '', sem_acento).strip()


def calcular_cdd_automatico(
    tipo_acervo: str,
    categoria_principal: str,
    genero_literario: Optional[str] = None,
    origem_autor: Optional[str] = "brasileira",
    publico_alvo: Optional[str] = "adulto"
) -> str:
    """
    Calcula o código CDD cruzando os campos amigáveis do formulário.
    """
    # Regra 1: Se for público infantil/juvenil, bibliotecas municipais usam 028.5
    if publico_alvo == "infantil":
        return "028.5"

    # Regra 2: Se for Quadrinhos / Gibis / Mangás
    if tipo_acervo == "quadrinho" or categoria_principal == "quadrinhos_mangas":
        return "741.5"

    # Regra 3: Se for Literatura (combina Origem + Formato Literário)
    if categoria_principal == "literatura":
        if genero_literario == "infantojuvenil":
            return "028.5"
        
        raiz = RAIZ_LITERATURA_ORIGEM.get(origem_autor or "outras", "89")
        sufixo = SUFIXO_GENERO_LITERARIO.get(genero_literario or "romance_ficcao", "3")
        
        # Se a raiz tem 3 dígitos (ex: 869), usa ponto (869.3). Se tem 2 (ex: 81), junta direto (813)
        cdd_base = f"{raiz}.{sufixo}" if len(raiz) == 3 else f"{raiz}{sufixo}"
    else:
        # Regra 4: Não-Ficção (Busca direta no dicionário de temas)
        cdd_base = MAPA_TEMAS_CDD.get(categoria_principal, "000")

    # Regra 5: Se for Periódico/Revista, adiciona a subdivisão padrão (.05) se não for geral
    if tipo_acervo == "periodico":
        if cdd_base == "000":
            return "050"
        return f"{cdd_base.split('.')[0]}.05"

    return cdd_base


# Âncoras reais da Tabela Cutter-Sanborn para interpolação exata (3 algarismos)
ANCORAS_CUTTER = {
    # Vogais e S usam 2 dígitos na tabela original, mas padronizamos em 3 dígitos proporcionais
    "A": [("AA", 111), ("AB", 116), ("AC", 168), ("AD", 191), ("AL", 316), ("AM", 479), ("AN", 532), ("AR", 658), ("AS", 844), ("AT", 862), ("AV", 945), ("AZ", 993)],
    "B": [("BA", 111), ("BE", 365), ("BI", 576), ("BL", 627), ("BO", 662), ("BR", 794), ("BU", 917), ("BZ", 999)],
    "C": [("CA", 111), ("CE", 387), ("CH", 426), ("CI", 567), ("CL", 585), ("CO", 652), ("CR", 883), ("CU", 961), ("CZ", 998)],
    "F": [("FA", 111), ("FE", 297), ("FI", 438), ("FL", 571), ("FO", 649), ("FR", 797), ("FU", 949), ("FZ", 999)],
    "G": [("GA", 111), ("GE", 289), ("GI", 436), ("GL", 541), ("GO", 573), ("GR", 726), ("GU", 896), ("GZ", 999)],
    "M": [("MA", 111), ("MC", 119), ("ME", 479), ("MI", 618), ("MO", 687), ("MU", 941), ("MZ", 999)],
    "P": [("PA", 111), ("PE", 348), ("PH", 534), ("PI", 579), ("PL", 698), ("PO", 739), ("PR", 895), ("PU", 974), ("PZ", 999)],
    "R": [("RA", 111), ("RE", 281), ("RI", 481), ("RO", 628), ("RU", 888), ("RZ", 999)],
    "S": [("SA", 111), ("SC", 289), ("SE", 438), ("SH", 524), ("SI", 565), ("SL", 631), ("SM", 635), ("SO", 676), ("SP", 732), ("ST", 774), ("SU", 939), ("SZ", 996)],
}

def calcular_cutter_automatico(sobrenome: str, titulo: str, tipo_acervo: str = "livro") -> str:
    """
    Gera o código Cutter-Sanborn mantendo ordem alfabética estrita + inicial do título.
    """
    if tipo_acervo == "periodico":
        # Revistas não usam Cutter de autor; usam as 3 primeiras letras do título em maiúsculo
        palavras = [p for p in limpar_texto(titulo).split() if p.lower() not in STOPWORDS_TITULO]
        base_rev = palavras[0] if palavras else "REV"
        return base_rev[:3].upper()

    # 1. Limpa partículas ("de Assis" -> "ASSIS")
    sobrenome_extraido, _ = separar_nome_autor(sobrenome)
    sobrenome_limpo = limpar_texto(sobrenome_extraido.split()[0]).upper() if sobrenome_extraido else "AUTOR"
    if not sobrenome_limpo:
        sobrenome_limpo = "AUTOR"

    letra_inicial = sobrenome_limpo[0]
    resto = (sobrenome_limpo + "AAAA")[1:5] # Pega as próximas 4 letras para cálculo proporcional

    # 2. Interpolação Alfabética Estrita (Garante que "ASSIS" < "AZEVEDO" sempre!)
    # Converte as 4 letras seguintes em uma fração entre 0.0 e 1.0 na base 26
    valor_base26 = sum((ord(c) - ord('A')) * (26 ** (3 - idx)) for idx, c in enumerate(resto))
    fator_alfabetico = valor_base26 / (26 ** 4 - 1)

    # Mapeia na escala oficial Cutter (111 a 999)
    numero_cutter = int(111 + fator_alfabetico * (999 - 111))

    # 3. Extrai a letra do Título (ignorando artigos "O", "A", "Um"...)
    palavras_titulo = limpar_texto(titulo).split()
    if len(palavras_titulo) > 1 and palavras_titulo[0].lower() in STOPWORDS_TITULO:
        primeira_palavra_util = palavras_titulo[1]
    elif palavras_titulo:
        primeira_palavra_util = palavras_titulo[0]
    else:
        primeira_palavra_util = "a"

    letra_titulo = primeira_palavra_util[0].lower()

    return f"{letra_inicial}{numero_cutter}{letra_titulo}"