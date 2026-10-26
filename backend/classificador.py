import os
import re
import bisect
import unicodedata
from typing import Optional, Tuple, List, Dict

# ==============================================================================
# 1. DICIONÁRIOS DE CLASSIFICAÇÃO TEMÁTICA (CDD)
# ==============================================================================

MAPA_TEMAS_CDD: Dict[str, str] = {
    "computacao": "004",
    "programacao": "005",
    "enciclopedia": "030",
    "jornalismo": "070",
    "filosofia": "100",
    "psicologia": "150",
    "autoajuda": "158.1",
    "etica": "170",
    "religiao": "200",
    "teologia_crista": "230",
    "espiritismo": "133.9",
    "sociologia": "301",
    "politica": "320",
    "economia": "330",
    "direito": "340",
    "administracao_publica": "350",
    "educacao": "370",
    "folclore": "398",
    "linguistica": "410",
    "lingua_portuguesa": "469",
    "lingua_inglesa": "420",
    "ciencias": "500",
    "matematica": "510",
    "astronomia": "520",
    "fisica": "530",
    "quimica": "540",
    "biologia": "570",
    "botanica": "580",
    "zoologia": "590",
    "medicina_saude": "610",
    "engenharia": "620",
    "agricultura": "630",
    "culinaria": "641.5",
    "administracao_empresas": "658",
    "artes": "700",
    "arquitetura": "720",
    "quadrinhos_mangas": "741.5",
    "musica": "780",
    "cinema_teatro": "791",
    "esportes": "796",
    "geografia_viagens": "910",
    "geografia_brasil": "918.1",
    "biografia": "920",
    "historia_geral": "909",
    "historia_antiga": "930",
    "historia_europa": "940",
    "historia_brasil": "981",
    "historia_rs": "981.65",
}

RAIZ_LITERATURA_ORIGEM: Dict[str, str] = {
    "brasileira": "869.9",           # Ex: 869.91 (Poesia), 869.98 (Miscelânea)
    "portuguesa": "869",             # Ex: 869.1 (Poesia), 869.8 (Miscelânea), 869.87
    "angolana_mocambicana": "869.89",# Literaturas Africanas de Língua Portuguesa
    "americana": "81",               # Ex: 811..818
    "canadense": "819",              # Ex: 819.1..819.8
    "inglesa": "82",                 # Ex: 821..828
    "alema": "83",                   # Ex: 831..838
    "nordica_escandinava": "839.5",  # Dinamarquesa, Norueguesa, Sueca
    "francesa": "84",                # Ex: 841..848
    "italiana": "85",                # Ex: 851..858
    "espanhola": "86",               # Ex: 861..868
    "latino_americana": "868.99",    # Hispano-Americana
    "classica_latina": "87",         # Literatura Latina Clássica (871..878)
    "classica_grega": "88",          # Literatura Grega Clássica (881..888)
    "russa_eslava": "891.7",         # Ex: 891.73 (Dostoiévski, Tolstói)
    "polonesa_tcheca": "891.8",      # Ex: 891.853
    "hebraica_judaica": "892.4",
    "arabe": "892.7",
    "chinesa": "895.1",
    "japonesa": "895.6",
    "africana": "896",
    "outras": "89",
}

SUFIXO_GENERO_LITERARIO: Dict[str, str] = {
    "antologia_colecao": "08",       # Coletâneas de vários autores (.08)
    "historia_critica": "09",        # História e crítica literária (.09)
    "poesia": "1",                   # Poesia (.1)
    "teatro_drama": "2",             # Teatro / Drama (.2)
    "romance_ficcao": "3",           # Ficção / Romance (.3)
    "conto_novela": "3",             # Conto / Novela (.3)
    "cronica_ensaio": "4",           # Ensaios / Crônicas (.4)
    "discursos": "5",                # Discursos / Oratória (.5)
    "cartas": "6",                   # Cartas / Epistolografia (.6)
    "humor_satira": "7",             # Humor e Sátira (.7)
    "miscelanea": "8",               # Miscelânea, Diários, Fragmentos, Prosa Poética, Obras Completas (.8)
    "infantojuvenil": "028.5",
}

# ==============================================================================
# 2. CONSTANTES E REGRAS CUTTER-SANBORN (METODOLOGIA TABELACUTTER.COM / ABNT)
# ==============================================================================

# ABNT NBR 6033:2022 (item 3.4 e Anexo A): Artigos em PT, EN, ES, FR, IT e DE
# Nota da Metodologia: "Das" e "Die" NÃO são removidos por serem palavras em português.
ARTIGOS_TITULO = {
    # Português
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    # Inglês
    "the", "an",
    # Espanhol
    "el", "la", "los", "las", "un", "unos", "unas",
    # Francês
    "le", "les", "une", "des", "du",
    # Italiano
    "il", "lo", "gli", "i", "uno",
    # Alemão (exceto 'das' e 'die')
    "der", "ein", "eine",
}

ARTIGOS_ENTRADA_PRINCIPAL = {"o", "a", "os", "as", "um", "uma", "uns", "umas", "the", "an"}
SUFIXOS_PARENTESCO = {"FILHO", "NETO", "SOBRINHO", "JUNIOR", "JR"}

# Linhas oficiais completas das letras Q e X (Swanson-Swift 1969 - 9 linhas cada, 1 dígito)
LINHAS_OFICIAIS_CURTAS: Dict[str, List[Tuple[Tuple[str, ...], str]]] = {
    "Q": [
        (("QUA",), "1"), (("QUAT",), "2"), (("QUE",), "3"),
        (("QUER",), "4"), (("QUES",), "5"), (("QUI",), "6"),
        (("QUIN",), "7"), (("QUIR",), "8"), (("QUO",), "9"),
    ],
    "X": [
        (("XA",), "1"), (("XAN",), "2"), (("XAV",), "3"),
        (("XE",), "4"), (("XEN",), "5"), (("XER",), "6"),
        (("XL",), "7"), (("XU",), "8"), (("XY",), "9"),
    ],
}

# Quantidade de algarismos por letra na Cutter-Sanborn 1969:
# Q, X -> 1 algarismo (9 linhas: 1 a 9)
# E, I, J, K, O, U, Y, Z -> 2 algarismos (81 linhas: 11 a 99, sem zero)
# Demais -> 3 algarismos (729 linhas: 111 a 999, sem zero)
LETRAS_1_DIGITO = {"Q", "X"}
LETRAS_2_DIGITOS = {"E", "I", "J", "K", "O", "U", "Y", "Z"}

# Cache em memória da tabela TSV completa (Letra -> Lista ordenada de (tupla_palavras, numero_str))
_TABELA_CUTTER_TSV: Dict[str, List[Tuple[Tuple[str, ...], str]]] = {}
CAMINHO_TSV_LOCAL = os.path.join(os.path.dirname(__file__), "tabela-cutter-sanborn-1969-even3-1.0.tsv")


# ==============================================================================
# 3. FUNÇÕES DE NORMALIZAÇÃO (ABNT NBR 6033:2022 + CONVENÇÕES EVEN3)
# ==============================================================================

def _remover_acentos_e_ligaduras(texto: str) -> str:
    """
    ABNT NBR 6033:2022, item 3.1: Letras com acento ou sinal valem pela letra base.
    Expande ligaduras (æ -> ae, œ -> oe, ß -> ss).
    """
    if not texto:
        return ""
    t = (
        texto.replace("æ", "ae").replace("Æ", "AE")
        .replace("œ", "oe").replace("Œ", "OE")
        .replace("ß", "ss")
    )
    return "".join(
        c for c in unicodedata.normalize("NFD", t)
        if unicodedata.category(c) != "Mn"
    )


def limpar_texto(texto: str) -> str:
    """Limpeza geral mantendo apenas letras, números e espaços."""
    sem_acento = _remover_acentos_e_ligaduras(texto)
    return re.sub(r"[^a-zA-Z0-9\s]", "", sem_acento).strip()


def normalizar_para_busca_cutter(entrada: str) -> Tuple[str, ...]:
    """
    Aplica rigorosamente as regras de normalização da Metodologia Tabela Cutter:
    1. Desconsidera sinais não alfabéticos no início (ABNT NBR 6033, 3.6.1).
    2. Junta partes separadas por apóstrofo: O'Neill -> Oneill (Lehnus, 1980).
    3. Trata hífen e vírgula como separação de palavras: Saint-Exupéry -> Saint Exupery (OCLC / Even3).
    4. Converte Mc, M' e M'c no início da 1ª palavra para Mac (Regra 7, Cutter 1969).
    5. Devolve a tupla de palavras em maiúsculas para comparação palavra por palavra.
    """
    if not entrada:
        return ("A",)

    texto = _remover_acentos_e_ligaduras(entrada).strip()

    # Trata Mc, M' e M'c no início como Mac ANTES de remover apóstrofo (Regra 7)
    texto = re.sub(r"^[Mm](?:'c|c|')(?=[A-Za-z])", "Mac", texto)

    # Apóstrofo junta as partes sem espaço (O'Neill -> Oneill)
    texto = re.sub(r"['’`´]", "", texto)

    # Hífen, vírgula, ponto e barra separam palavras (Saint-Exupéry -> Saint Exupery; Assis, M. -> Assis M)
    texto = re.sub(r"[-,/.;:()\[\]\"“”?!]+", " ", texto)

    # Mantém apenas letras e espaços
    texto = re.sub(r"[^a-zA-Z\s]", "", texto).upper()
    palavras = tuple(p for p in texto.split() if p)

    return palavras if palavras else ("A",)


def _converter_numero_inicial_titulo(palavra: str) -> str:
    """
    Convenção Even3: Converte ordinais (1º, 2ª) e números iniciais no título por extenso
    para extrair a letra da obra corretamente.
    """
    p = palavra.lower().strip()
    ordinais_f = {"1ª": "primeira", "2ª": "segunda", "3ª": "terceira", "4ª": "quarta", "5ª": "quinta"}
    ordinais_m = {"1º": "primeiro", "2º": "segundo", "3º": "terceiro", "4º": "quarto", "5º": "quinto"}
    if p in ordinais_f:
        return ordinais_f[p]
    if p in ordinais_m:
        return ordinais_m[p]

    cardinais = {
        "1": "um", "2": "dois", "3": "tres", "4": "quatro", "5": "cinco",
        "6": "seis", "7": "sete", "8": "oito", "9": "nove", "10": "dez",
        "11": "onze", "12": "doze", "13": "treze", "14": "quatorze", "15": "quinze",
        "16": "dezesseis", "17": "dezessete", "18": "dezoito", "19": "dezenove",
        "20": "vinte", "30": "trinta", "40": "quarenta", "50": "cinquenta",
        "80": "oitenta", "100": "cem", "1000": "mil", "1984": "mil", "2001": "dois",
    }
    return cardinais.get(p, p)


def extrair_letra_obra(titulo: str) -> str:
    """
    Regra 5 (Cutter, 1969) + ABNT NBR 6033:2022 (item 3.4 e Anexo A):
    Extrai a primeira letra da primeira palavra significativa do título em minúscula,
    desconsiderando artigos iniciais (inclusive elididos como L') e sinais.
    """
    if not titulo:
        return ""

    t = _remover_acentos_e_ligaduras(titulo).strip()
    # Remove sinais de pontuação/aspas no início (ABNT 3.6.1)
    t = re.sub(r"^[^a-zA-Z0-9]+", "", t)

    # Remove artigo elidido francês/italiano no início (ex: "L'Étranger" -> "Étranger")
    t = re.sub(r"^[lL]['’`´]\s*", "", t)

    palavras = t.split()
    if not palavras:
        return ""

    primeira_limpa = re.sub(r"[^a-zA-Z0-9ªº]", "", palavras[0]).lower()

    # Se a primeira palavra for um artigo (e houver mais palavras depois), pula o artigo
    if len(palavras) > 1 and primeira_limpa in ARTIGOS_TITULO:
        palavra_alvo = re.sub(r"[^a-zA-Z0-9ªº]", "", palavras[1]).lower()
    else:
        palavra_alvo = primeira_limpa

    palavra_alvo = _converter_numero_inicial_titulo(palavra_alvo)
    letras = re.sub(r"[^a-z]", "", palavra_alvo)
    return letras[0] if letras else ""


def separar_nome_autor(sobrenome_ou_completo: str, prenome_atual: str = "") -> Tuple[str, str]:
    """
    Destrincha o nome caso o usuário tenha digitado o nome completo num campo só.
    Respeita Filho, Neto, Sobrinho e Júnior junto ao sobrenome.
    """
    texto = re.sub(r"\s*\([^)]*\)\s*", " ", sobrenome_ou_completo).strip()
    prenome = prenome_atual.strip()

    if "," in texto:
        partes = texto.split(",", 1)
        novo_sobrenome = partes[0].strip().upper()
        resto_nome = partes[1].strip()
        novo_prenome = f"{resto_nome} {prenome}".strip() if prenome else resto_nome
        return novo_sobrenome, novo_prenome

    palavras = texto.split()
    if len(palavras) <= 1:
        return texto.upper(), prenome

    ultima = limpar_texto(palavras[-1]).upper()
    penultima = palavras[-2]

    if ultima in SUFIXOS_PARENTESCO:
        if len(palavras) == 2 and prenome:
            return f"{ penultima.upper() } {ultima}", prenome
        sobrenome_final = f"{penultima.upper()} {ultima}"
        extraido_prenome = " ".join(palavras[:-2])
    else:
        sobrenome_final = palavras[-1].upper()
        extraido_prenome = " ".join(palavras[:-1])

    prenome_final = f"{prenome} {extraido_prenome}".strip() if prenome else extraido_prenome
    return sobrenome_final, prenome_final


# ==============================================================================
# 4. CARREGADOR DA TABELA TSV OFICIAL (OFFLINE-FIRST) + BUSCA PALAVRA POR PALAVRA
# ==============================================================================

def _carregar_tabela_tsv_se_disponivel() -> None:
    """
    Carrega em memória o arquivo oficial tabela-cutter-sanborn-1969-even3-1.0.tsv.
    Se ainda não existir no disco, tenta baixá-lo uma única vez do site tabelacutter.com.
    """
    global _TABELA_CUTTER_TSV
    if _TABELA_CUTTER_TSV:
        return

    # Se não existe localmente, tenta baixar uma única vez e salvar para uso 100% offline
    if not os.path.exists(CAMINHO_TSV_LOCAL):
        urls_tentativa = [
            "https://www.tabelacutter.com/tabela-cutter-sanborn-1969-even3-1.0.tsv",
            "https://tabelacutter.com/tabela-cutter-sanborn-1969-even3-1.0.tsv",
        ]
        try:
            import urllib.request
            for url in urls_tentativa:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "SistemaBiblio/1.0"})
                    with urllib.request.urlopen(req, timeout=4.0) as resp:
                        conteudo = resp.read().decode("utf-8")
                        if "111" in conteudo and "\t" in conteudo:
                            with open(CAMINHO_TSV_LOCAL, "w", encoding="utf-8") as f:
                                f.write(conteudo)
                            break
                except Exception:
                    continue
        except Exception:
            pass

    if os.path.exists(CAMINHO_TSV_LOCAL):
        try:
            with open(CAMINHO_TSV_LOCAL, "r", encoding="utf-8") as f:
                for linha in f:
                    partes = linha.strip().split("\t")
                    if len(partes) < 3 or partes[0].lower() == "letra":
                        continue
                    letra = partes[0].strip().upper()
                    numero = partes[1].strip()
                    entrada_str = partes[2].strip()
                    chave_palavras = normalizar_para_busca_cutter(entrada_str)
                    _TABELA_CUTTER_TSV.setdefault(letra, []).append((chave_palavras, numero))

            for letra in _TABELA_CUTTER_TSV:
                _TABELA_CUTTER_TSV[letra].sort(key=lambda item: item[0])
        except Exception as e:
            print(f"[Aviso] Erro ao ler TSV Cutter local: {e}")


def _converter_indice_para_digitos_sem_zero(indice: int, qtd_digitos: int) -> str:
    """
    Regra 6 (Cutter, 1969): A tabela Cutter-Sanborn nunca usa o algarismo zero!
    Converte um índice de base 9 para os dígitos de 1 a 9 (ex: 11..99 ou 111..999).
    """
    max_itens = 9 ** qtd_digitos
    idx = max(0, min(indice, max_itens - 1))
    digitos = []
    for _ in range(qtd_digitos):
        digitos.append(str((idx % 9) + 1))
        idx //= 9
    return "".join(reversed(digitos))


def _buscar_numero_cutter(palavras_busca: Tuple[str, ...]) -> Tuple[str, str]:
    """
    Executa a busca exata palavra por palavra conforme a metodologia da Even3 / OCLC:
    1. Usa a tabela TSV completa (12.312 linhas) se presente em disco.
    2. Usa a tabela oficial exata de 1 dígito para Q e X (Ex: Quintana -> Quin -> Q7).
    3. Fallback algorítmico em base 9 (sem zero!) respeitando 2 dígitos (E,I,J,K,O,U,Y,Z) ou 3 dígitos.
    """
    _carregar_tabela_tsv_se_disponivel()

    primeira_palavra = palavras_busca[0]
    letra_inicial = primeira_palavra[0]

    # 1. Busca na tabela TSV oficial ou nas tabelas exatas de Q e X
    linhas_letra = _TABELA_CUTTER_TSV.get(letra_inicial) or LINHAS_OFICIAIS_CURTAS.get(letra_inicial)
    if linhas_letra:
        chaves = [item[0] for item in linhas_letra]
        pos = bisect.bisect_right(chaves, palavras_busca)
        if pos == 0:
            # Convenção Even3: Entrada anterior à 1ª linha da letra usa a 1ª linha
            return letra_inicial, linhas_letra[0][1]
        return letra_inicial, linhas_letra[pos - 1][1]

    # 2. Fallback caso o TSV ainda não tenha sido baixado (respeitando 2 ou 3 dígitos e Regra 6 sem zero!)
    qtd_digitos = 2 if letra_inicial in LETRAS_2_DIGITOS else 3
    total_linhas = 9 ** qtd_digitos  # 81 para vogais/Y/Z, 729 para consoantes

    resto = (primeira_palavra + "AAAA")[1:5]
    valor_base26 = sum((ord(c) - ord("A")) * (26 ** (3 - idx)) for idx, c in enumerate(resto))
    fator = valor_base26 / (26 ** 4 - 1)
    indice_base9 = int(fator * (total_linhas - 1))

    return letra_inicial, _converter_indice_para_digitos_sem_zero(indice_base9, qtd_digitos)


def calcular_cutter_automatico(
    sobrenome: str,
    titulo: str,
    tipo_acervo: str = "livro",
    prenome: str = ""
) -> str:
    """
    Gera o código Cutter-Sanborn completo seguindo a metodologia oficial (tabelacutter.com/metodologia):
    - Monta a entrada principal "Sobrenome, Prenome" (ou usa o Título na ausência de autor - Regra 9).
    - Compara palavra por palavra (ignorando a vírgula, tratando Mc->Mac, hífen->espaço e juntando apóstrofo).
    - Adiciona a inicial da primeira palavra significativa do título em minúscula (Regra 5).
    """
    if tipo_acervo == "periodico":
        letra_rev = extrair_letra_obra(titulo)
        palavras = [p for p in limpar_texto(titulo).split() if p.lower() not in ARTIGOS_TITULO]
        base_rev = palavras[0] if palavras else (letra_rev or "REV")
        return base_rev[:3].upper()

    sobrenome_limpo, prenome_extraido = separar_nome_autor(sobrenome, prenome)

    # Regra 9: Se não houver autor (ou for anônimo), a entrada principal é o próprio título (sem letra da obra no fim)
    if not sobrenome_limpo or sobrenome_limpo in {"ANONIMO", "DESCONHECIDO", "SEM AUTOR"}:
        palavras_titulo = limpar_texto(titulo).split()
        if len(palavras_titulo) > 1 and palavras_titulo[0].lower() in ARTIGOS_ENTRADA_PRINCIPAL:
            palavras_titulo = palavras_titulo[1:]
        entrada_principal = " ".join(palavras_titulo) if palavras_titulo else "A"
        palavras_busca = normalizar_para_busca_cutter(entrada_principal)
        letra, numero = _buscar_numero_cutter(palavras_busca)
        return f"{letra}{numero}"

    # Entrada normal por autor: "Sobrenome, Prenome"
    entrada_autor = f"{sobrenome_limpo}, {prenome_extraido}" if prenome_extraido else sobrenome_limpo
    palavras_busca = normalizar_para_busca_cutter(entrada_autor)
    letra, numero = _buscar_numero_cutter(palavras_busca)
    letra_obra = extrair_letra_obra(titulo)

    return f"{letra}{numero}{letra_obra}"


# ==============================================================================
# 5. MOTOR DE CLASSIFICAÇÃO CDD E INFERÊNCIA DE ASSUNTOS
# ==============================================================================

def calcular_cdd_automatico(
    tipo_acervo: str,
    categoria_principal: str,
    genero_literario: Optional[str] = None,
    origem_autor: Optional[str] = "brasileira",
    publico_alvo: Optional[str] = "adulto",
    subdivisao_literaria: Optional[str] = ""
) -> str:
    """
    Calcula o código CDD completo para Literatura (incluindo .8 Miscelânea e dígito
    de período/subdivisão como .87 para Fernando Pessoa) e todas as classes de Não-Ficção.
    """
    if publico_alvo == "infantil":
        return "028.5"

    if tipo_acervo == "quadrinho" or categoria_principal == "quadrinhos_mangas":
        return "741.5"

    if categoria_principal == "literatura":
        if genero_literario == "infantojuvenil":
            return "028.5"

        raiz = RAIZ_LITERATURA_ORIGEM.get(origem_autor or "brasileira", "89")
        sufixo = SUFIXO_GENERO_LITERARIO.get(genero_literario or "romance_ficcao", "3")
        digito_extra = re.sub(r"[^0-9]", "", subdivisao_literaria or "")

        if "." in raiz:
            cdd_base = f"{raiz}{sufixo}{digito_extra}"
        elif len(raiz) == 3:
            cdd_base = f"{raiz}.{sufixo}{digito_extra}"
        else:
            # Raízes de 2 dígitos (ex: "81" + "8" -> "818", e com período "7" -> "818.7")
            if len(sufixo) == 1:
                cdd_base = f"{raiz}{sufixo}.{digito_extra}" if digito_extra else f"{raiz}{sufixo}"
            else:
                cdd_base = f"{raiz}0.{sufixo}{digito_extra}"
    else:
        cdd_base = MAPA_TEMAS_CDD.get(categoria_principal, "000")

    if tipo_acervo == "periodico":
        if cdd_base == "000":
            return "050"
        return f"{cdd_base.split('.')[0]}.05"

    return cdd_base


def _inferir_por_cdd_oficial(cdd_oficial: str, resultado: dict) -> None:
    """Mapeia um CDD oficial vindo de API (ex: Open Library) para os campos do formulário."""
    if not cdd_oficial:
        return
    cdd = cdd_oficial.strip().upper()

    if cdd.startswith("028.5") or cdd in {"E", "FIC"} or cdd.startswith("J"):
        resultado.setdefault("publico_alvo", "infantil")
        return

    if cdd.startswith("741.5"):
        resultado.setdefault("categoria_principal", "quadrinhos_mangas")
        resultado.setdefault("tipo_acervo", "quadrinho")
        return

    # Verifica correspondência exata ou por prefixo com MAPA_TEMAS_CDD
    for cat, codigo in sorted(MAPA_TEMAS_CDD.items(), key=lambda x: len(x[1]), reverse=True):
        if cdd == codigo or cdd.startswith(codigo + "."):
            resultado.setdefault("categoria_principal", cat)
            return

    prefixos_temas = [
        ("004", "computacao"), ("005", "programacao"), ("006", "programacao"),
        ("03", "enciclopedia"), ("07", "jornalismo"),
        ("133.9", "espiritismo"), ("158", "autoajuda"), ("15", "psicologia"),
        ("17", "etica"), ("1", "filosofia"),
        ("23", "teologia_crista"), ("24", "teologia_crista"), ("2", "religiao"),
        ("30", "sociologia"), ("32", "politica"), ("33", "economia"),
        ("34", "direito"), ("35", "administracao_publica"), ("37", "educacao"),
        ("398", "folclore"), ("41", "linguistica"), ("42", "lingua_inglesa"),
        ("469", "lingua_portuguesa"), ("51", "matematica"), ("52", "astronomia"),
        ("53", "fisica"), ("54", "quimica"), ("57", "biologia"),
        ("58", "botanica"), ("59", "zoologia"), ("5", "ciencias"),
        ("61", "medicina_saude"), ("62", "engenharia"), ("63", "agricultura"),
        ("641", "culinaria"), ("65", "administracao_empresas"),
        ("72", "arquitetura"), ("78", "musica"), ("791", "cinema_teatro"),
        ("792", "cinema_teatro"), ("796", "esportes"), ("7", "artes"),
        ("918.1", "geografia_brasil"), ("91", "geografia_viagens"),
        ("92", "biografia"), ("93", "historia_antiga"), ("94", "historia_europa"),
        ("981.65", "historia_rs"), ("981", "historia_brasil"), ("90", "historia_geral"),
    ]
    for pref, cat in prefixos_temas:
        if cdd.startswith(pref):
            resultado.setdefault("categoria_principal", cat)
            return

    # Classe 800 (Literatura)
    cdd_num = cdd.lstrip("B")
    if cdd_num.startswith("8"):
        resultado.setdefault("categoria_principal", "literatura")
        if cdd.startswith("B869") or cdd_num.startswith("869.9"):
            resultado.setdefault("origem_autor", "brasileira")
        else:
            for orig, raiz in sorted(RAIZ_LITERATURA_ORIGEM.items(), key=lambda x: len(x[1]), reverse=True):
                if cdd_num.startswith(raiz):
                    resultado.setdefault("origem_autor", orig)
                    break


def inferir_classificacao_por_assuntos(assuntos: List[str], cdd_oficial: Optional[str] = None) -> dict:
    texto_limpo = " | ".join(limpar_texto(a).lower() for a in assuntos if a)
    resultado: Dict[str, str] = {}

    # 1. Detecção automática de Público-Alvo (Adulto vs Infantojuvenil 028.5)
    palavras_infantojuvenil = [
        "infantojuvenil", "infanto juvenil", "literatura infantil", "literatura juvenil",
        "infantil", "juvenil", "juvenile", "children", "childrens", "young adult",
        "ya fiction", "kids", "contos de fadas", "fairy tales", "fairy tale",
        "fabulas", "fables", "picture book", "livros ilustrados", "livro ilustrado",
        "bedtime", "para criancas", "para jovens", "leitura infantil", "ensino fundamental",
        "historias infantis", "poesia infantil", "teatro infantil",
    ]
    if any(k in texto_limpo for k in palavras_infantojuvenil):
        resultado["publico_alvo"] = "infantil"

    # 2. Detecção de Quadrinhos / Mangás / Graphic Novels (741.5)
    palavras_quadrinhos = [
        "quadrinhos", "historias em quadrinhos", "historia em quadrinhos",
        "comics", "comic books", "graphic novel", "graphic novels",
        "manga", "mangas", "bande dessinee", "hq", "tirinhas", "gibis",
    ]
    if any(k in texto_limpo for k in palavras_quadrinhos):
        resultado["categoria_principal"] = "quadrinhos_mangas"
        resultado["tipo_acervo"] = "quadrinho"

    # 3. Identificação de Origem Literária / Nacionalidade do Autor
    mapa_origens = [
        (["brasileir", "brazil", "brasil"], "brasileira"),
        (["angola", "mocambic", "cabo verde", "guine bissau", "sao tome"], "angolana_mocambicana"),
        (["portugues", "portugal", "lusitan", "fernando pessoa", "saramago", "camoes", "eca de queiros"], "portuguesa"),
        (["latinoamerican", "hispanoamerican", "latin american", "argentin", "chilena", "uruguaia", "colombian", "mexican", "peruana", "venezuelan", "cuban"], "latino_americana"),
        (["espanhol", "spanish", "espanha", "spain"], "espanhola"),
        (["canadense", "canadian", "canada"], "canadense"),
        (["american", "estados unidos", "united states", "norteamerican", "usa"], "americana"),
        (["ingles", "english", "british", "britanic", "uk", "irlandes", "irish", "escoces", "scottish", "australian"], "inglesa"),
        (["nordic", "escandinav", "scandinavian", "suec", "swedish", "norueg", "norwegian", "dinamarq", "danish", "islandes"], "nordica_escandinava"),
        (["alema", "german", "alemanha", "germany", "austriac", "austrian", "suic"], "alema"),
        (["frances", "french", "franca", "france", "belga", "belgian"], "francesa"),
        (["italian", "italia", "italy"], "italiana"),
        (["latina", "romana", "latin literature", "ovidio", "virgilio", "cicero", "seneca", "horacio"], "classica_latina"),
        (["grega", "grego", "greek", "homero", "sofocles", "euripides", "esquilo", "aristofanes"], "classica_grega"),
        (["russa", "russo", "russian", "eslav", "slavic", "sovietic", "ucranian"], "russa_eslava"),
        (["polones", "polish", "polonia", "tchec", "czech", "bohemia"], "polonesa_tcheca"),
        (["hebraic", "hebrew", "judaic", "jewish", "israel", "iidiche", "yiddish"], "hebraica_judaica"),
        (["arabe", "arabic", "persa", "persian", "islamic", "oriente medio"], "arabe"),
        (["chines", "chinese", "china"], "chinesa"),
        (["japones", "japanese", "japao", "japan"], "japonesa"),
        (["african", "nigeria", "senegal", "queniano", "sul african"], "africana"),
    ]
    for palavras_origem, chave_origem in mapa_origens:
        if any(p in texto_limpo for p in palavras_origem):
            resultado["origem_autor"] = chave_origem
            break

    # 4. Detecção de Formas Literárias Explícitas (Tabela 3 CDD)
    marcadores_ficcao_explicita = [
        "ficcao", "fiction", "romance", "romances", "novel", "novels",
        "fantasia", "fantasy", "science fiction", "ficcao cientifica",
        "distopia", "dystopian", "thriller", "suspense", "policial",
        "detective", "mystery", "terror", "horror", "aventura", "adventure",
        "conto", "contos", "short stories", "novela", "novelas",
        "poesia", "poemas", "poetica", "poetry", "poems", "lirica", "sonetos",
        "teatro", "drama", "peca teatral", "tragedia", "comedia teatral", "plays",
        "cronica", "cronicas", "antologia", "anthology", "coletanea",
        "critica literaria", "historia e critica", "history and criticism", "teoria literaria",
        "miscelanea", "miscellany", "fragmentos", "aforismos", "prosa poetica", "desassossego",
    ]
    eh_literatura_explicita = any(k in texto_limpo for k in marcadores_ficcao_explicita)

    # Remove termos compostos de ficção (ex: "science fiction", "historical fiction", "psychological fiction")
    # ao avaliar temas de Não-Ficção para evitar falsos positivos
    texto_nao_ficcao = texto_limpo
    for composto_ficcao in [
        "science fiction", "ficcao cientifica", "historical fiction", "ficcao historica",
        "psychological fiction", "ficcao psicologica", "political fiction", "ficcao politica",
        "religious fiction", "ficcao religiosa", "christian fiction", "ficcao crista",
        "biographical fiction", "ficcao biografica", "legal fiction", "legal stories",
        "medical fiction", "domestic fiction", "war stories", "love stories",
    ]:
        texto_nao_ficcao = texto_nao_ficcao.replace(composto_ficcao, " romance_ficcao ")

    # 5. Mapeamento completo de todas as Classes Temáticas de Não-Ficção (MAPA_TEMAS_CDD)
    if "categoria_principal" not in resultado:
        mapa_temas = [
            (["rio grande do sul", "gauch", "farroupilha", "serra gaucha", "porto alegre"], "historia_rs"),
            (["historia do brasil", "brazil history", "brasil colonia", "brasil imperio", "ditadura militar", "escravidao no brasil"], "historia_brasil"),
            (["historia antiga", "ancient history", "egito antigo", "mesopotamia", "antiguidade", "imperio romano", "grecia antiga"], "historia_antiga"),
            (["historia da europa", "european history", "guerra mundial", "world war", "idade media", "medieval", "revolucao francesa", "holocausto"], "historia_europa"),
            (["geografia do brasil", "territorio brasileiro", "regioes do brasil", "biomas brasileiros"], "geografia_brasil"),
            (["autoajuda", "selfhelp", "self help", "desenvolvimento pessoal", "personal growth", "motivacional", "sucesso pessoal"], "autoajuda"),
            (["espiritismo", "kardec", "espirita", "mediunidade", "chico xavier", "spiritualism"], "espiritismo"),
            (["teologia", "biblia", "bible", "cristianismo", "christianity", "igreja", "evangelho", "catolicismo", "protestantismo", "jesus cristo"], "teologia_crista"),
            (["folclore", "folklore", "lendas", "mitos populares", "cultura popular", "customs and traditions"], "folclore"),
            (["programacao", "programming", "python", "javascript", "java", "software", "algoritmos", "algorithms", "coding", "desenvolvimento web", "engenharia de software", "banco de dados", "sql"], "programacao"),
            (["computacao", "informatica", "computers", "computer science", "hardware", "redes de computadores", "inteligencia artificial", "sistemas operacionais", "tecnologia da informacao", "cybersecurity"], "computacao"),
            (["administracao publica", "public administration", "gestao publica", "servico publico", "politicas publicas"], "administracao_publica"),
            (["administracao", "negocios", "business", "gestao", "management", "marketing", "empreendedorismo", "entrepreneurship", "lideranca", "leadership", "recursos humanos", "vendas", "contabilidade"], "administracao_empresas"),
            (["direito", "law", "legislacao", "juridic", "constituicao", "constitucional", "codigo civil", "codigo penal", "justica", "advocacia", "direitos humanos"], "direito"),
            (["economia", "economics", "financas", "finance", "investimentos", "mercado financeiro", "macroeconomia", "microeconomia", "capitalismo"], "economia"),
            (["politica", "ciencia politica", "politics", "political science", "democracia", "geopolitica", "relacoes internacionais", "estado", "governo"], "politica"),
            (["sociologia", "sociology", "ciencias sociais", "social sciences", "antropologia", "anthropology", "sociedade", "movimentos sociais", "questao racial", "feminismo", "estudos de genero"], "sociologia"),
            (["educacao", "pedagogia", "education", "ensino", "teaching", "didatica", "alfabetizacao", "escola", "aprendizagem", "curriculo"], "educacao"),
            (["psicologia", "psychology", "psicanalise", "psychoanalysis", "saude mental", "terapia", "comportamento", "cognicao", "freud", "jung"], "psicologia"),
            (["etica", "ethics", "moral", "bioetica", "filosofia moral"], "etica"),
            (["filosofia", "philosophy", "metafisica", "epistemologia", "logica", "existencialismo", "estoicismo", "filosofos"], "filosofia"),
            (["religiao", "religion", "mitologia", "mythology", "espiritualidade", "budismo", "islamismo", "judaismo", "umbanda", "candomble", "ocultismo"], "religiao"),
            (["lingua portuguesa", "gramatica portuguesa", "ortografia", "redacao", "portuguese language", "dicionario portugues"], "lingua_portuguesa"),
            (["lingua inglesa", "english language", "ingles para", "gramatica inglesa", "vocabulary"], "lingua_inglesa"),
            (["linguistica", "linguistics", "semiotica", "fonetica", "morfologia", "sintaxe", "filologia", "language and languages"], "linguistica"),
            (["matematica", "mathematics", "calculo", "calculus", "algebra", "geometria", "estatistica", "statistics", "probabilidade", "aritmetica"], "matematica"),
            (["astronomia", "astronomy", "astrofisica", "astrophysics", "cosmologia", "universo", "sistema solar", "planetas"], "astronomia"),
            (["fisica", "physics", "mecanica", "eletromagnetismo", "termodinamica", "fisica quantica", "relatividade", "optica"], "fisica"),
            (["quimica", "chemistry", "bioquimica", "tabela periodica", "quimica organica", "quimica inorganica"], "quimica"),
            (["botanica", "botany", "plantas", "plants", "flora", "fisiologia vegetal"], "botanica"),
            (["zoologia", "zoology", "animais", "animals", "fauna", "vertebrados", "invertebrados", "etologia"], "zoologia"),
            (["biologia", "biology", "genetica", "genetics", "ecologia", "ecology", "evolucao", "evolution", "microbiologia", "meio ambiente", "natureza", "sustentabilidade"], "biologia"),
            (["ciencias", "science", "ciencias naturais", "divulgacao cientifica", "historia da ciencia", "metodo cientifico"], "ciencias"),
            (["medicina", "saude", "health", "medical", "anatomia", "anatomy", "enfermagem", "nursing", "nutricao", "nutrition", "farmacologia", "psiquiatria", "pediatria", "fisioterapia", "odontologia"], "medicina_saude"),
            (["engenharia", "engineering", "eletronica", "electronics", "mecanica industrial", "construcao civil", "automacao", "robotica", "telecomunicacoes"], "engenharia"),
            (["agricultura", "agriculture", "agronomia", "pecuaria", "veterinaria", "horticultura", "jardinagem", "gardening", "silvicultura"], "agricultura"),
            (["culinaria", "gastronomia", "cooking", "cookery", "receitas", "recipes", "confeitaria", "panificacao", "alimentacao", "vinhos"], "culinaria"),
            (["arquitetura", "architecture", "urbanismo", "design de interiores", "paisagismo"], "arquitetura"),
            (["musica", "music", "instrumentos musicais", "teoria musical", "composers", "compositores", "cancoes"], "musica"),
            (["cinema", "filme", "movies", "motion pictures", "fotografia", "photography", "audiovisual", "direcao teatral", "artes cenicas", "performing arts"], "cinema_teatro"),
            (["esporte", "esportes", "sports", "futebol", "soccer", "volei", "basquete", "educacao fisica", "atletismo", "artes marciais", "xadrez", "jogos", "recreacao"], "esportes"),
            (["arte", "artes", "arts", "fine arts", "pintura", "painting", "escultura", "sculpture", "desenho", "drawing", "design", "historia da arte"], "artes"),
            (["geografia", "geography", "viagens", "travel", "turismo", "cartografia", "atlas", "geopolitica"], "geografia_viagens"),
            (["enciclopedia", "encyclopedia", "almanaque", "obras de referencia", "reference", "curiosidades gerais"], "enciclopedia"),
            (["jornalismo", "journalism", "imprensa", "reportagem", "comunicacao social", "midia", "media studies"], "jornalismo"),
        ]

        # Biografia e História Geral têm tratamento especial para não colidir com romances ficcionais
        if any(p in texto_nao_ficcao for p in ["biografia", "biography", "autobiografia", "autobiography", "memorias", "memoirs"]) and "critica" not in texto_nao_ficcao:
            resultado["categoria_principal"] = "biografia"
        elif not eh_literatura_explicita:
            for palavras, cat in mapa_temas:
                if any(p in texto_nao_ficcao for p in palavras):
                    resultado["categoria_principal"] = cat
                    break
            if "categoria_principal" not in resultado and any(p in texto_nao_ficcao for p in ["historia", "history", "civilizacao", "arqueologia"]):
                resultado["categoria_principal"] = "historia_geral"
        else:
            # Mesmo com marcador genérico de literatura, temas muito específicos prevalecem
            temas_fortes = {"historia_rs", "historia_brasil", "autoajuda", "espiritismo", "folclore", "programacao", "computacao", "culinaria"}
            for palavras, cat in mapa_temas:
                if cat in temas_fortes and any(p in texto_nao_ficcao for p in palavras):
                    resultado["categoria_principal"] = cat
                    break

    # 6. Classificação detalhada de Literatura (Gênero / Forma Literária e Subdivisão de Período)
    if "categoria_principal" not in resultado or resultado.get("categoria_principal") == "literatura":
        if any(k in texto_limpo for k in ["miscelanea", "miscellany", "fragmentos", "aforismos", "diarios", "diaries", "prosa poetica", "obras completas", "textos diversos", "desassossego"]):
            resultado["categoria_principal"] = "literatura"
            resultado["genero_literario"] = "miscelanea"
        elif any(k in texto_limpo for k in ["critica literaria", "historia e critica", "history and criticism", "criticism and interpretation", "teoria literaria"]):
            resultado["categoria_principal"] = "literatura"
            resultado["genero_literario"] = "historia_critica"
        elif any(k in texto_limpo for k in ["antologia", "anthology", "coletanea", "colecao literaria"]):
            resultado["categoria_principal"] = "literatura"
            resultado["genero_literario"] = "antologia_colecao"
        elif any(k in texto_limpo for k in ["poesia", "poemas", "poetica", "poetry", "poems", "lirica", "sonetos", "haikai", "epopeia", "versos"]):
            resultado["categoria_principal"] = "literatura"
            resultado["genero_literario"] = "poesia"
        elif any(k in texto_limpo for k in ["cronica", "cronicas", "ensaio", "ensaios", "essays"]):
            resultado["categoria_principal"] = "literatura"
            resultado["genero_literario"] = "cronica_ensaio"
        elif any(k in texto_limpo for k in ["teatro", "drama", "peca teatral", "tragedia", "comedia teatral", "dramaturgia", "plays", "shakespeare"]):
            resultado["categoria_principal"] = "literatura"
            resultado["genero_literario"] = "teatro_drama"
        elif any(k in texto_limpo for k in ["conto", "contos", "short stories", "novela", "novelas", "fabula", "fabulas"]):
            resultado["categoria_principal"] = "literatura"
            resultado["genero_literario"] = "conto_novela"
        elif any(k in texto_limpo for k in ["humor", "satira", "piadas", "humorous", "satire", "comedia", "parodia"]):
            resultado["categoria_principal"] = "literatura"
            resultado["genero_literario"] = "humor_satira"
        elif any(k in texto_limpo for k in ["cartas", "correspondencia", "epistolar", "letters"]):
            resultado["categoria_principal"] = "literatura"
            resultado["genero_literario"] = "cartas"
        elif any(k in texto_limpo for k in ["discurso", "discursos", "oratoria", "speeches", "retorica"]):
            resultado["categoria_principal"] = "literatura"
            resultado["genero_literario"] = "discursos"
        elif eh_literatura_explicita or any(k in texto_limpo for k in ["literatura", "literature"]):
            resultado["categoria_principal"] = "literatura"
            resultado["genero_literario"] = "romance_ficcao"

    # 7. Inferência opcional de Período Literário (Subdivisão 1 a 9)
    if resultado.get("categoria_principal") == "literatura":
        mapa_periodos = [
            (["seculo xxi", "21st century", "literatura contemporanea"], "9"),
            (["contemporane", "pos modern", "postmodern", "2000"], "8"),
            (["seculo xx", "20th century", "modernismo", "modernism"], "7"),
            (["realismo", "naturalismo", "simbolismo", "parnasianismo"], "6"),
            (["seculo xix", "19th century", "romantismo", "romanticism"], "5"),
            (["seculo xviii", "18th century", "neoclassicismo", "arcadismo", "iluminismo"], "4"),
            (["seculo xvii", "17th century", "barroco", "seiscentismo"], "3"),
            (["seculo xvi", "16th century", "renascimento", "quinhentismo", "classicismo"], "2"),
            (["idade media", "medieval", "trovadorismo", "origens"], "1"),
        ]
        for palavras_per, digito_per in mapa_periodos:
            if any(p in texto_limpo for p in palavras_per):
                resultado["subdivisao_literaria"] = digito_per
                break

    # 8. Complementa com o CDD Oficial da API (caso exista)
    if cdd_oficial:
        _inferir_por_cdd_oficial(cdd_oficial, resultado)

    return resultado
