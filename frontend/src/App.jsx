import { useState, useEffect } from "react";
import "./App.css";

const API_URL = "http://localhost:8000/api";

const INITIAL_FORM = {
  tipo_acervo: "livro",
  isbn_issn: "",
  titulo: "",
  subtitulo: "",
  autor_sobrenome: "",
  autor_nome: "",
  categoria_principal: "literatura",
  genero_literario: "romance_ficcao",
  origem_autor: "brasileira",
  publico_alvo: "adulto",
  editora: "",
  ano_publicacao: "",
  edicao: "1ª Ed.",
  paginas: "",
  idioma: "Português",
  capa_url: "",
  colecao: "Acervo Geral",
  quantidade_exemplares: 1,
  cdd_manual: "",
  cutter_manual: "",
  subdivisao_literaria: ""
};

export default function App() {
  const [form, setForm] = useState(INITIAL_FORM);

  const [preview, setPreview] = useState({
    cdd_gerado: "869.93",
    cutter_gerado: "---",
    etiqueta_lombada: "869.93 ---",
  });

  // Status enxuto: { state: "IDLE" | "WORKING" | "OK" | "ERR", code: string, meta: string }
  const [sysStatus, setSysStatus] = useState({ state: "IDLE", code: "READY", meta: "" });
  const [ultimoRegistro, setUltimoRegistro] = useState(null);

  useEffect(() => {
    if (!form.titulo.trim() || !form.autor_sobrenome.trim()) return;

    const timer = setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          titulo: form.titulo,
          autor_sobrenome: form.autor_sobrenome,
          autor_nome: form.autor_nome,
          tipo_acervo: form.tipo_acervo,
          categoria_principal: form.categoria_principal,
          genero_literario: form.genero_literario,
          origem_autor: form.origem_autor,
          publico_alvo: form.publico_alvo,
          subdivisao_literaria: form.subdivisao_literaria
        });
        const res = await fetch(`${API_URL}/classificar-preview?${params}`);
        if (res.ok) {
          const data = await res.json();
          setPreview(data);
        }
      } catch {
        // Silencioso durante digitação
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [
    form.titulo,
    form.autor_sobrenome,
    form.autor_nome,
    form.tipo_acervo,
    form.categoria_principal,
    form.genero_literario,
    form.origem_autor,
    form.publico_alvo,
    form.subdivisao_literaria
  ]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleAutorBlur = () => {
    const texto = form.autor_sobrenome.trim();
    if (!texto || texto.includes(",")) return;

    const partes = texto.split(/\s+/);
    if (partes.length > 1) {
      const sufixos = ["FILHO", "NETO", "SOBRINHO", "JUNIOR", "JR"];
      const ultima = partes[partes.length - 1].toUpperCase().replace(".", "");

      let sobrenome = "";
      let prenome = "";

      if (sufixos.includes(ultima) && partes.length >= 2) {
        sobrenome = `${partes[partes.length - 2].toUpperCase()} ${ultima}`;
        prenome = partes.slice(0, -2).join(" ");
      } else {
        sobrenome = partes[partes.length - 1].toUpperCase();
        prenome = partes.slice(0, -1).join(" ");
      }

      setForm((prev) => ({
        ...prev,
        autor_sobrenome: sobrenome,
        autor_nome: prev.autor_nome ? `${prev.autor_nome} ${prenome}`.trim() : prenome,
      }));
    } else {
      setForm((prev) => ({ ...prev, autor_sobrenome: texto.toUpperCase() }));
    }
  };

  const buscarPorIsbn = async () => {
    const isbnLimpo = form.isbn_issn.replace(/[^0-9X]/gi, "");
    if (isbnLimpo.length < 10) {
      setSysStatus({ state: "ERR", code: "ERR_ISBN_LEN", meta: "" });
      return;
    }

    setSysStatus({ state: "WORKING", code: "FETCHING_ISBN", meta: isbnLimpo });

    try {
      const res = await fetch(`${API_URL}/isbn/${isbnLimpo}`);
      const data = await res.json();

      if (!res.ok) {
        setSysStatus({ state: "ERR", code: `HTTP_${res.status}`, meta: "NOT_FOUND" });
        return;
      }

      setForm((prev) => ({
        ...prev,
        isbn_issn: isbnLimpo,
        titulo: data.titulo || prev.titulo,
        subtitulo: data.subtitulo ?? prev.subtitulo,
        autor_sobrenome: data.autor_sobrenome || prev.autor_sobrenome,
        autor_nome: data.autor_nome ?? prev.autor_nome,
        editora: data.editora || prev.editora,
        ano_publicacao: data.ano_publicacao ? String(data.ano_publicacao) : prev.ano_publicacao,
        paginas: data.paginas ? String(data.paginas) : prev.paginas,
        capa_url: data.capa_url || prev.capa_url,
        categoria_principal: data.categoria_principal || prev.categoria_principal,
        genero_literario: data.genero_literario || prev.genero_literario,
        origem_autor: data.origem_autor || prev.origem_autor,
        publico_alvo: data.publico_alvo || prev.publico_alvo,
        cdd_manual: data.cdd_oficial || "",
      }));

      if (data.ja_cadastrado) {
        setSysStatus({ state: "ERR", code: "HTTP_409_EXISTS", meta: `ID #${data.obra_id}` });
      } else {
        setSysStatus({ state: "OK", code: "200_OK", meta: data.fonte || "API" });
      }
    } catch {
      setSysStatus({ state: "ERR", code: "ERR_NET_REFUSED", meta: "" });
    }
  };

  const handleUploadCapa = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setSysStatus({ state: "WORKING", code: "CONVERTING_WEBP", meta: "" });
    const formData = new FormData();
    formData.append("arquivo", file);

    try {
      const res = await fetch(`${API_URL}/upload-capa`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        setForm((prev) => ({ ...prev, capa_url: data.capa_url }));
        setSysStatus({ state: "OK", code: "WEBP_READY", meta: "" });
      } else {
        setSysStatus({ state: "ERR", code: `HTTP_${res.status}`, meta: "IMG_ERR" });
      }
    } catch {
      setSysStatus({ state: "ERR", code: "ERR_UPLOAD", meta: "" });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSysStatus({ state: "WORKING", code: "COMMITTING_DB", meta: "" });

    const payload = {
      ...form,
      isbn_issn: form.isbn_issn.trim() || null,
      subtitulo: form.subtitulo.trim() || null,
      editora: form.editora.trim() || null,
      ano_publicacao: form.ano_publicacao ? parseInt(form.ano_publicacao, 10) : null,
      paginas: form.paginas ? parseInt(form.paginas, 10) : null,
      quantidade_exemplares: parseInt(form.quantidade_exemplares, 10) || 1,
      cdd_manual: form.cdd_manual.trim() || null,
      cutter_manual: form.cutter_manual.trim() || null,
    };

    try {
      const res = await fetch(`${API_URL}/obras`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        setSysStatus({ state: "ERR", code: `HTTP_${res.status}`, meta: "DB_REJECTED" });
        return;
      }

      const data = await res.json();
      setUltimoRegistro(data);
      setSysStatus({
        state: "OK",
        code: "201_CREATED",
        meta: `ID #${data.obra_id} (${data.tombos_gerados[0]})`,
      });
    } catch {
      setSysStatus({ state: "ERR", code: "ERR_NET_REFUSED", meta: "" });
    }
  };

  const limparFormulario = () => {
    setForm(INITIAL_FORM);
    setPreview({ cdd_gerado: "869.93", cutter_gerado: "---", etiqueta_lombada: "869.93 ---" });
    setSysStatus({ state: "IDLE", code: "READY", meta: "" });
  };

  return (
    <div className="workstation">
      {/* BARRA SUPERIOR COMPACTA COM TELEMETRIA DE STATUS */}
      <header className="topbar">
        <div className="brand">
          <span className="brand-dot" />
          <strong>SISTEMABIBLIO</strong>
          <span className="brand-tag">CATALOGAÇÃO</span>
        </div>

        <div className="telemetry">
          {ultimoRegistro && (
            <div className="last-commit">
              ÚLTIMO REGISTRO: <strong>#{ultimoRegistro.obra_id}</strong> [{ultimoRegistro.etiqueta_chamada}] —{" "}
              {ultimoRegistro.tombos_gerados.join(", ")}
            </div>
          )}
          <div className={`status-pill status-${sysStatus.state.toLowerCase()}`}>
            <span className="status-code">{sysStatus.code}</span>
            {sysStatus.meta && <span className="status-meta">{sysStatus.meta}</span>}
          </div>
        </div>
      </header>

      {/* GRID FULL-SCREEN EM 3 COLUNAS */}
      <form className="workspace-grid" onSubmit={handleSubmit}>
        {/* COLUNA 1: IDENTIFICAÇÃO, AUTORIA E DADOS FÍSICOS */}
        <section className="panel">
          <div className="panel-header">
            <h3>Identificação & Metadados</h3>
            <button type="button" className="btn-ghost" onClick={limparFormulario}>
              Limpar
            </button>
          </div>

          <div className="grid-row cols-3">
            <div className="field">
              <label>Tipo</label>
              <select name="tipo_acervo" value={form.tipo_acervo} onChange={handleChange}>
                <option value="livro">Livro</option>
                <option value="periodico">Periódico</option>
                <option value="quadrinho">Quadrinho / HQ</option>
              </select>
            </div>

            <div className="field span-2">
              <label>ISBN / ISSN</label>
              <div className="input-group">
                <input
                  type="text"
                  name="isbn_issn"
                  placeholder="978..."
                  value={form.isbn_issn}
                  onChange={handleChange}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      buscarPorIsbn();
                    }
                  }}
                />
                <button
                  type="button"
                  className="btn-action"
                  onClick={buscarPorIsbn}
                  disabled={sysStatus.state === "WORKING"}
                >
                  Fetch
                </button>
              </div>
            </div>
          </div>

          <div className="grid-row cols-3">
            <div className="field span-2">
              <label>Título Principal *</label>
              <input
                type="text"
                name="titulo"
                required
                value={form.titulo}
                onChange={handleChange}
              />
            </div>

            <div className="field">
              <label>Subtítulo</label>
              <input
                type="text"
                name="subtitulo"
                value={form.subtitulo}
                onChange={handleChange}
              />
            </div>
          </div>

          <div className="grid-row cols-2">
            <div className="field">
              <label>Sobrenome (ou Nome Completo) *</label>
              <input
                type="text"
                name="autor_sobrenome"
                required
                value={form.autor_sobrenome}
                onChange={handleChange}
                onBlur={handleAutorBlur}
              />
            </div>

            <div className="field">
              <label>Prenome / Nome</label>
              <input
                type="text"
                name="autor_nome"
                value={form.autor_nome}
                onChange={handleChange}
              />
            </div>
          </div>

          <div className="divider" />

          <div className="grid-row cols-3">
            <div className="field span-2">
              <label>Editora</label>
              <input type="text" name="editora" value={form.editora} onChange={handleChange} />
            </div>

            <div className="field">
              <label>Edição</label>
              <input type="text" name="edicao" value={form.edicao} onChange={handleChange} />
            </div>
          </div>

          <div className="grid-row cols-4">
            <div className="field">
              <label>Ano</label>
              <input
                type="number"
                name="ano_publicacao"
                min="1450"
                max="2026"
                value={form.ano_publicacao}
                onChange={handleChange}
              />
            </div>

            <div className="field">
              <label>Páginas</label>
              <input
                type="number"
                name="paginas"
                min="1"
                value={form.paginas}
                onChange={handleChange}
              />
            </div>

            <div className="field">
              <label>Idioma</label>
              <input type="text" name="idioma" value={form.idioma} onChange={handleChange} />
            </div>

            <div className="field">
              <label>Exemplares</label>
              <input
                type="number"
                name="quantidade_exemplares"
                min="1"
                max="50"
                value={form.quantidade_exemplares}
                onChange={handleChange}
              />
            </div>
          </div>
        </section>

        {/* COLUNA 2: PARÂMETROS DE CLASSIFICAÇÃO E OVERRIDE */}
        <section className="panel">
          <div className="panel-header">
            <h3>Classificação Bibliográfica</h3>
          </div>

          <div className="grid-row cols-2">
            <div className="field">
              <label>Público-Alvo</label>
              <select name="publico_alvo" value={form.publico_alvo} onChange={handleChange}>
                <option value="adulto">Adulto / Geral</option>
                <option value="infantil">Infantojuvenil (028.5)</option>
              </select>
            </div>

            <div className="field">
              <label>Coleção / Locação</label>
              <input type="text" name="colecao" value={form.colecao} onChange={handleChange} />
            </div>
          </div>

          <div className="grid-row cols-1">
            <div className="field">
              <label>Classe Temática (CDD)</label>
              <select name="categoria_principal" value={form.categoria_principal} onChange={handleChange}>
                <optgroup label="Literatura">
                  <option value="literatura">Literatura (800)</option>
                </optgroup>
                <optgroup label="Ciências Humanas e Sociais">
                  <option value="filosofia">Filosofia (100)</option>
                  <option value="psicologia">Psicologia (150)</option>
                  <option value="autoajuda">Autoajuda (158.1)</option>
                  <option value="etica">Ética (170)</option>
                  <option value="religiao">Religião (200)</option>
                  <option value="teologia_crista">Teologia Cristã (230)</option>
                  <option value="espiritismo">Espiritismo (133.9)</option>
                  <option value="sociologia">Sociologia (301)</option>
                  <option value="politica">Ciência Política (320)</option>
                  <option value="economia">Economia (330)</option>
                  <option value="direito">Direito (340)</option>
                  <option value="administracao_publica">Administração Pública (350)</option>
                  <option value="educacao">Educação / Pedagogia (370)</option>
                  <option value="folclore">Folclore (398)</option>
                </optgroup>
                <optgroup label="História, Geografia e Biografia">
                  <option value="historia_geral">História Geral (909)</option>
                  <option value="historia_antiga">História Antiga (930)</option>
                  <option value="historia_europa">História da Europa (940)</option>
                  <option value="historia_brasil">História do Brasil (981)</option>
                  <option value="historia_rs">História Regional / RS (981.65)</option>
                  <option value="geografia_viagens">Geografia e Viagens (910)</option>
                  <option value="geografia_brasil">Geografia do Brasil (918.1)</option>
                  <option value="biografia">Biografia (920)</option>
                </optgroup>
                <optgroup label="Exatas, Saúde e Tecnologia">
                  <option value="computacao">Computação (004)</option>
                  <option value="programacao">Programação (005)</option>
                  <option value="ciencias">Ciências Naturais (500)</option>
                  <option value="matematica">Matemática (510)</option>
                  <option value="astronomia">Astronomia (520)</option>
                  <option value="fisica">Física (530)</option>
                  <option value="quimica">Química (540)</option>
                  <option value="biologia">Biologia (570)</option>
                  <option value="botanica">Botânica (580)</option>
                  <option value="zoologia">Zoologia (590)</option>
                  <option value="medicina_saude">Medicina e Saúde (610)</option>
                  <option value="engenharia">Engenharia (620)</option>
                  <option value="agricultura">Agricultura (630)</option>
                  <option value="culinaria">Culinária (641.5)</option>
                  <option value="administracao_empresas">Administração e Negócios (658)</option>
                </optgroup>
                <optgroup label="Linguística, Artes e Esportes">
                  <option value="linguistica">Linguística (410)</option>
                  <option value="lingua_portuguesa">Língua Portuguesa (469)</option>
                  <option value="lingua_inglesa">Língua Inglesa (420)</option>
                  <option value="artes">Artes (700)</option>
                  <option value="arquitetura">Arquitetura (720)</option>
                  <option value="quadrinhos_mangas">Quadrinhos / Mangás (741.5)</option>
                  <option value="musica">Música (780)</option>
                  <option value="cinema_teatro">Cinema e Teatro (791)</option>
                  <option value="esportes">Esportes (796)</option>
                  <option value="enciclopedia">Enciclopédias (030)</option>
                  <option value="jornalismo">Jornalismo (070)</option>
                </optgroup>
              </select>
            </div>
          </div>

          {form.categoria_principal === "literatura" && form.publico_alvo !== "infantil" && (
            <div className="sub-panel">
              <div className="grid-row cols-2">
                <div className="field">
                  <label>Origem Literária</label>
                  <select name="origem_autor" value={form.origem_autor} onChange={handleChange}>
                    <optgroup label="Língua Portuguesa">
                      <option value="brasileira">Brasileira (869.9)</option>
                      <option value="portuguesa">Portuguesa (869)</option>
                      <option value="angolana_mocambicana">Lusófona Africana (869.89)</option>
                    </optgroup>
                    <optgroup label="Américas e Europa Ocidental">
                      <option value="americana">Norte-Americana (81)</option>
                      <option value="canadense">Canadense (819)</option>
                      <option value="inglesa">Inglesa / Britânica (82)</option>
                      <option value="alema">Alemã (83)</option>
                      <option value="nordica_escandinava">Nórdica / Escandinava (839.5)</option>
                      <option value="francesa">Francesa (84)</option>
                      <option value="italiana">Italiana (85)</option>
                      <option value="espanhola">Espanhola (86)</option>
                      <option value="latino_americana">Hispano / Latino-Americana (868.99)</option>
                    </optgroup>
                    <optgroup label="Clássica, Leste Europeu e Oriente">
                      <option value="classica_latina">Clássica Latina (87)</option>
                      <option value="classica_grega">Clássica Grega (88)</option>
                      <option value="russa_eslava">Russa / Eslava (891.7)</option>
                      <option value="polonesa_tcheca">Polonesa / Tcheca (891.8)</option>
                      <option value="hebraica_judaica">Hebraica / Judaica (892.4)</option>
                      <option value="arabe">Árabe / Persa (892.7)</option>
                      <option value="chinesa">Chinesa (895.1)</option>
                      <option value="japonesa">Japonesa (895.6)</option>
                      <option value="africana">Africana Geral (896)</option>
                      <option value="outras">Outras Origens (89)</option>
                    </optgroup>
                  </select>
                </div>

                <div className="field">
                  <label>Forma Literária (Tabela 3)</label>
                  <select name="genero_literario" value={form.genero_literario} onChange={handleChange}>
                    <option value="poesia">Poesia (.1)</option>
                    <option value="teatro_drama">Teatro / Drama (.2)</option>
                    <option value="romance_ficcao">Romance / Ficção (.3)</option>
                    <option value="conto_novela">Conto / Novela (.3)</option>
                    <option value="cronica_ensaio">Crônica / Ensaio (.4)</option>
                    <option value="discursos">Discursos / Oratória (.5)</option>
                    <option value="cartas">Cartas / Epistolar (.6)</option>
                    <option value="humor_satira">Humor / Sátira (.7)</option>
                    <option value="miscelanea">Miscelânea / Prosa Poética / Diários (.8)</option>
                    <option value="antologia_colecao">Antologia / Coletânea (.08)</option>
                    <option value="historia_critica">História e Crítica Literária (.09)</option>
                  </select>
                </div>
              </div>

              <div className="grid-row cols-1" style={{ marginTop: "0.6rem" }}>
                <div className="field">
                  <label>Período / Subdivisão Específica (Opcional)</label>
                  <select name="subdivisao_literaria" value={form.subdivisao_literaria} onChange={handleChange}>
                    <option value="">Padrão (Sem subdivisão de período)</option>
                    <option value="1">Período 1 — Origens / Idade Média (.x1)</option>
                    <option value="2">Período 2 — Renascimento / Quinhentismo (.x2)</option>
                    <option value="3">Período 3 — Seiscentismo / Barroco (.x3)</option>
                    <option value="4">Período 4 — Setecentismo / Neoclassicismo (.x4)</option>
                    <option value="5">Período 5 — Século XIX / Romantismo (.x5)</option>
                    <option value="6">Período 6 — Realismo / Simbolismo (.x6)</option>
                    <option value="7">Período 7 / Subtipo .x7 — Modernismo / Séc. XX (.x7)</option>
                    <option value="8">Período 8 / Subtipo .x8 — Contemporâneo (.x8)</option>
                    <option value="9">Período 9 / Subtipo .x9 — Século XXI (.x9)</option>
                  </select>
                </div>
              </div>
            </div>
          )}
          <div className="divider" />

          <div className="panel-header">
            <h3>Override Manual</h3>
          </div>

          <div className="grid-row cols-2">
            <div className="field">
              <label>CDD Manual</label>
              <input
                type="text"
                name="cdd_manual"
                placeholder={preview.cdd_gerado}
                value={form.cdd_manual}
                onChange={handleChange}
              />
            </div>

            <div className="field">
              <label>Cutter Manual</label>
              <input
                type="text"
                name="cutter_manual"
                placeholder={preview.cutter_gerado}
                value={form.cutter_manual}
                onChange={handleChange}
              />
            </div>
          </div>

          <div className="abnt-box">
            <span className="abnt-label">ENTRADA ABNT</span>
            <span className="abnt-value">
              {form.autor_sobrenome
                ? `${form.autor_sobrenome}${form.autor_nome ? `, ${form.autor_nome}` : ""}`
                : "—"}
            </span>
          </div>
        </section>

        {/* COLUNA 3: CAPA WEBP, LOMBADA E AÇÃO DE COMMIT */}
        <section className="panel preview-column">
          <div className="panel-header">
            <h3>Inspeção Visual</h3>
          </div>

          <div className="inspection-split">
            {/* CAPA */}
            <div className="cover-slot">
              {form.capa_url ? (
                <img
                  src={form.capa_url.startsWith("/static") ? `http://localhost:8000${form.capa_url}` : form.capa_url}
                  alt="Capa"
                  className="cover-img"
                />
              ) : (
                <div className="cover-empty">NO_COVER</div>
              )}
              <label className="btn-upload">
                Upload WebP
                <input type="file" accept="image/*" onChange={handleUploadCapa} hidden />
              </label>
            </div>

            {/* ETIQUETA DE LOMBADA */}
            <div className="spine-wrapper">
              <div className="spine-tag">
                <div className="spine-top">{form.colecao.toUpperCase()}</div>
                <div className="spine-cdd">{form.cdd_manual || preview.cdd_gerado}</div>
                <div className="spine-cutter">{form.cutter_manual || preview.cutter_gerado}</div>
                <div className="spine-ex">ex. 1</div>
              </div>
            </div>
          </div>

          <div className="commit-zone">
            <button
              type="submit"
              className="btn-primary"
              disabled={sysStatus.state === "WORKING"}
            >
              {sysStatus.state === "WORKING" ? "PROCESSANDO..." : "GRAVAR NO ACERVO"}
            </button>
          </div>
        </section>
      </form>
    </div>
  );
}