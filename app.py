import streamlit as st
import requests
import json
from datetime import date, datetime, timedelta
import pandas as pd
import plotly.graph_objects as go

# --- Configurações da página ---
st.set_page_config(
    page_title="AgroContábil - LCDPR",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Supabase via REST (credenciais via secrets) ---
SUPABASE_URL      = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
HEADERS = {
    "apikey":        SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type":  "application/json"
}

def rerun_app():
    """Tenta forçar o reload; cai em st.stop() se não disponível."""
    try:
        st.experimental_rerun()
    except AttributeError:
        st.stop()

# --- Helpers Supabase CRUD ---
@st.cache_data(ttl=300)
def supa_get(table: str, select: str = "*", filters: list[str] | None = None) -> list[dict]:
    """GET genérico ao Supabase."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}"
    if filters:
        url += "&" + "&".join(filters)
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()

def supa_insert(table: str, payload: dict) -> None:
    """POST genérico ao Supabase (ignora corpo vazio)."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    resp = requests.post(url, headers=HEADERS, json=payload)
    resp.raise_for_status()

def supa_update(table: str, key: str, key_val, payload: dict) -> None:
    """PATCH genérico ao Supabase (ignora corpo vazio)."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?{key}=eq.{key_val}"
    resp = requests.patch(url, headers=HEADERS, json=payload)
    resp.raise_for_status()

def supa_delete(table: str, key: str, key_val) -> None:
    """DELETE genérico ao Supabase."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?{key}=eq.{key_val}"
    resp = requests.delete(url, headers=HEADERS)
    resp.raise_for_status()

def format_cpf_cnpj(v: str) -> str:
    """Formata CPF ou CNPJ."""
    digits = "".join(filter(str.isdigit, v))
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return v

# --- Funções de renderização de cada seção ---
def show_dashboard():
    st.header("📊 Painel Financeiro")
    col_filters, _ = st.columns([1, 3])
    with col_filters:
        d1 = st.date_input("De", date.today().replace(day=1), key="dash_d1")
        d2 = st.date_input("Até", date.today(),               key="dash_d2")

    # Busca e cálculos
    dados = supa_get(
        "lancamento",
        "valor_entrada,valor_saida",
        [f"data=gte.{d1}", f"data=lte.{d2}"]
    )
    rec   = sum(item["valor_entrada"] for item in dados)
    desp  = sum(item["valor_saida"]   for item in dados)
    saldo = rec - desp

    # Métricas
    m1, m2, m3 = st.columns(3)
    m1.metric("💰 Saldo Total", f"R$ {saldo:,.2f}")
    m2.metric("📈 Receitas",    f"R$ {rec:,.2f}")
    m3.metric("📉 Despesas",     f"R$ {desp:,.2f}")

    # Gráfico de pizza
    pie = go.Figure(go.Pie(
        labels=["Receitas","Despesas"],
        values=[rec, desp],
        hole=0.4,
        textinfo="label+percent"
    ))
    pie.update_layout(transition={"duration": 500, "easing": "cubic-in-out"})
    st.plotly_chart(pie, use_container_width=True)

    # Alertas de estoque
    st.subheader("⚠️ Alertas de Estoque")
    hoje = date.today().isoformat()
    vencidos = supa_get("estoque","produto,data_validade",[f"data_validade=lt.{hoje}"])
    proximos = supa_get(
        "estoque","produto,data_validade",
        [f"data_validade=gte.{hoje}", f"data_validade=lte.{(date.today()+timedelta(30)).isoformat()}"]
    )
    for item in vencidos:
        st.warning(f"Vencido: {item['produto']} em {item['data_validade']}")
    for item in proximos:
        st.info(f"Vence em até 30 dias: {item['produto']} em {item['data_validade']}")

    # Últimas atividades
    st.subheader("🕒 Últimas Atividades")
    acts = supa_get(
        "lancamento",
        "data,historico,valor_entrada,valor_saida",
        ["order=data.desc","limit=5"]
    )
    df_acts = pd.DataFrame([
        {
            "Data": a["data"],
            "Descrição": a["historico"],
            "Valor": f"R$ {a['valor_entrada']-a['valor_saida']:,.2f}"
        }
        for a in acts
    ])
    st.table(df_acts)

def show_lancamentos():
    st.header("📝 Lançamentos")
    c1, c2 = st.columns([1, 3])
    with c1:
        d1 = st.date_input("Data inicial", date.today().replace(day=1), key="lanc_fi")
        d2 = st.date_input("Data final",   date.today(),               key="lanc_ff")

    # Mapas para nomes
    imovs = supa_get("imovel_rural","id,nome_imovel")
    mapa_i = {i["id"]: i["nome_imovel"] for i in imovs}
    cts   = supa_get("conta_bancaria","id,nome_banco")
    mapa_c = {c["id"]: c["nome_banco"]    for c in cts}

    # Fetch lançamentos e DataFrame
    lans = supa_get(
        "lancamento",
        "id,data,cod_imovel,cod_conta,historico,tipo_lanc,valor_entrada,valor_saida,saldo_final,natureza_saldo,categoria",
        [f"data=gte.{d1}", f"data=lte.{d2}", "order=data.desc"]
    )
    df = pd.DataFrame(lans)
    if df.empty:
        st.info("Nenhum lançamento encontrado.")
    else:
        df["Imóvel"] = df["cod_imovel"].map(mapa_i)
        df["Conta"]  = df["cod_conta"].map(mapa_c)
        df["Tipo"]   = df["tipo_lanc"].map({1:"Receita",2:"Despesa",3:"Adiantamento"})
        df["Saldo"]  = df.apply(
            lambda r: (1 if r["natureza_saldo"]=="P" else -1)*r["saldo_final"], axis=1
        )
        df = df.rename(columns={
            "data":"Data", "historico":"Histórico",
            "valor_entrada":"Entrada", "valor_saida":"Saída",
            "categoria":"Categoria"
        })
        st.dataframe(df[["id","Data","Imóvel","Histórico","Tipo","Entrada","Saída","Saldo","Categoria"]],
                     use_container_width=True)

    # Expander: Novo lançamento
    with st.expander("➕ Novo Lançamento"):
        with st.form("form_lanc_new", clear_on_submit=True):
            dn  = st.date_input("Data", date.today(), key="new_d")
            imv = st.selectbox(
                "Imóvel", options=list(mapa_i.keys()),
                format_func=lambda x: mapa_i[x], key="new_imv"
            )
            cta = st.selectbox(
                "Conta", options=list(mapa_c.keys()),
                format_func=lambda x: mapa_c[x], key="new_cta"
            )
            hist = st.text_input("Histórico", key="new_hist")
            tp   = st.selectbox("Tipo", ["Receita","Despesa","Adiantamento"], key="new_tp")
            ent  = st.number_input("Entrada", min_value=0.0, format="%.2f", key="new_ent")
            sai  = st.number_input("Saída",   min_value=0.0, format="%.2f", key="new_sai")
            cat  = st.text_input("Categoria", key="new_cat")
            submit_new = st.form_submit_button("Salvar")
        if submit_new:
            supa_insert("lancamento", {
                "data": dn.isoformat(),
                "cod_imovel": imv,
                "cod_conta": cta,
                "historico": hist,
                "tipo_lanc": ["Receita","Despesa","Adiantamento"].index(tp)+1,
                "valor_entrada": ent,
                "valor_saida": sai,
                "saldo_final": abs(ent-sai),
                "natureza_saldo": "P" if ent>=sai else "N",
                "categoria": cat
            })
            st.success("Lançamento criado!")
            rerun_app()

    # Editar / Excluir
    if not df.empty:
        sel = st.selectbox("ID p/ Editar/Excluir", df["id"].tolist(), key="sel_lanc")
        col_edit, col_del = st.columns(2)

        with col_edit:
            if st.button("✏️ Editar", key="btn_edit_lanc"):
                rec = df.loc[df["id"]==sel].iloc[0]
                with st.form("form_lanc_edit", clear_on_submit=True):
                    de = st.date_input("Data", datetime.fromisoformat(rec["Data"]).date(), key="edit_d")
                    imv_e = st.selectbox(
                        "Imóvel", options=list(mapa_i.keys()),
                        format_func=lambda x: mapa_i[x],
                        index=list(mapa_i).index(rec["cod_imovel"]),
                        key="edit_imv"
                    )
                    cta_e = st.selectbox(
                        "Conta", options=list(mapa_c.keys()),
                        format_func=lambda x: mapa_c[x],
                        index=list(mapa_c).index(rec["cod_conta"]),
                        key="edit_cta"
                    )
                    hist_e = st.text_input("Histórico", rec["Histórico"], key="edit_hist")
                    tp_e   = st.selectbox(
                        "Tipo", ["Receita","Despesa","Adiantamento"],
                        index=["Receita","Despesa","Adiantamento"].index(rec["Tipo"]),
                        key="edit_tp"
                    )
                    ent_e  = st.number_input("Entrada", value=rec["Entrada"], format="%.2f", key="edit_ent")
                    sai_e  = st.number_input("Saída",   value=rec["Saída"],   format="%.2f", key="edit_sai")
                    cat_e  = st.text_input("Categoria", rec["Categoria"], key="edit_cat")
                    submit_edit = st.form_submit_button("Atualizar")
                if submit_edit:
                    supa_update("lancamento", "id", sel, {
                        "data": de.isoformat(),
                        "cod_imovel": imv_e,
                        "cod_conta": cta_e,
                        "historico": hist_e,
                        "tipo_lanc": ["Receita","Despesa","Adiantamento"].index(tp_e)+1,
                        "valor_entrada": ent_e,
                        "valor_saida": sai_e,
                        "saldo_final": abs(ent_e-sai_e),
                        "natureza_saldo": "P" if ent_e>=sai_e else "N",
                        "categoria": cat_e
                    })
                    st.success("Lançamento atualizado!")
                    rerun_app()

        with col_del:
            if st.button("🗑️ Excluir", key="btn_del_lanc"):
                supa_delete("lancamento", "id", sel)
                st.success("Lançamento excluído!")
                rerun_app()

def show_cadastros():
    st.header("📇 Cadastros")
    tabs = st.tabs([
        "🏠 Imóveis", "🏦 Contas", "👥 Participantes",
        "🌱 Culturas", "📐 Áreas", "📦 Estoque"
    ])

    # ---- Imóveis ----
    with tabs[0]:
        st.subheader("Imóveis Rurais")
        df = pd.DataFrame(supa_get(
            "imovel_rural",
            "id,cod_imovel,nome_imovel,endereco,bairro,uf,cod_mun,cep," +
            "tipo_exploracao,participacao,area_total,area_utilizada"
        ))
        st.dataframe(df, use_container_width=True, key="tbl_im")

        with st.expander("➕ Novo Imóvel"):
            with st.form("form_im_new", clear_on_submit=True):
                cod     = st.text_input("Código")
                nome    = st.text_input("Nome")
                end     = st.text_input("Endereço")
                bairro  = st.text_input("Bairro")
                uf      = st.text_input("UF")
                cm      = st.text_input("Cód. Município")
                cep     = st.text_input("CEP")
                te      = st.selectbox("Tipo Exploração", [1,2,3,4,5,6])
                part    = st.number_input("Participação (%)", value=100.0, format="%.2f")
                at      = st.number_input("Área Total (ha)", format="%.2f")
                au      = st.number_input("Área Utilizada (ha)", format="%.2f")
                submit  = st.form_submit_button("Salvar")
            if submit:
                supa_insert("imovel_rural", {
                    "cod_imovel":      cod,
                    "nome_imovel":     nome,
                    "endereco":        end,
                    "bairro":          bairro,
                    "uf":              uf,
                    "cod_mun":         cm,
                    "cep":             cep,
                    "tipo_exploracao": te,
                    "participacao":    part,
                    "area_total":      at,
                    "area_utilizada":  au
                })
                st.success("Imóvel criado!")
                rerun_app()

        if not df.empty:
            sel = st.selectbox("ID p/ Editar/Excluir", df["id"].tolist())
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar"):
                    rec = df.loc[df["id"]==sel].iloc[0]
                    with st.form("form_im_edit", clear_on_submit=True):
                        cod_e    = st.text_input("Código", rec["cod_imovel"])
                        nome_e   = st.text_input("Nome",   rec["nome_imovel"])
                        end_e    = st.text_input("Endereço", rec["endereco"])
                        bairro_e = st.text_input("Bairro",   rec["bairro"])
                        uf_e     = st.text_input("UF",       rec["uf"])
                        cm_e     = st.text_input("Cód. Município", rec["cod_mun"])
                        cep_e    = st.text_input("CEP",      rec["cep"])
                        te_e     = st.selectbox("Tipo Exploração", [1,2,3,4,5,6], index=int(rec["tipo_exploracao"])-1)
                        part_e   = st.number_input("Participação (%)", value=rec["participacao"], format="%.2f")
                        at_e     = st.number_input("Área Total (ha)", value=rec["area_total"] or 0, format="%.2f")
                        au_e     = st.number_input("Área Utilizada (ha)", value=rec["area_utilizada"] or 0, format="%.2f")
                        submit_e = st.form_submit_button("Atualizar")
                    if submit_e:
                        supa_update("imovel_rural", "id", sel, {
                            "cod_imovel":      cod_e,
                            "nome_imovel":     nome_e,
                            "endereco":        end_e,
                            "bairro":          bairro_e,
                            "uf":              uf_e,
                            "cod_mun":         cm_e,
                            "cep":             cep_e,
                            "tipo_exploracao": te_e,
                            "participacao":    part_e,
                            "area_total":      at_e,
                            "area_utilizada":  au_e
                        })
                        st.success("Imóvel atualizado!")
                        rerun_app()
            with c2:
                if st.button("🗑️ Excluir"):
                    supa_delete("imovel_rural", "id", sel)
                    st.success("Imóvel excluído!")
                    rerun_app()

    # ---- Contas ----
    with tabs[1]:
        st.subheader("Contas Bancárias")
        df = pd.DataFrame(supa_get(
            "conta_bancaria",
            "id,cod_conta,nome_banco,agencia,num_conta,saldo_inicial"
        ))
        st.dataframe(df, use_container_width=True, key="tbl_ct")

        with st.expander("➕ Nova Conta"):
            with st.form("form_ct_new", clear_on_submit=True):
                cod_ct = st.text_input("Código")
                nb_ct  = st.text_input("Banco")
                ag_ct  = st.text_input("Agência")
                nc_ct  = st.text_input("Número da Conta")
                si_ct  = st.number_input("Saldo Inicial", format="%.2f")
                submit = st.form_submit_button("Salvar")
            if submit:
                supa_insert("conta_bancaria", {
                    "cod_conta":   cod_ct,
                    "nome_banco":  nb_ct,
                    "agencia":     ag_ct,
                    "num_conta":   nc_ct,
                    "saldo_inicial": si_ct
                })
                st.success("Conta criada!")
                rerun_app()

        if not df.empty:
            sel = st.selectbox("ID p/ Editar/Excluir", df["id"].tolist())
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar"):
                    rec = df.loc[df["id"]==sel].iloc[0]
                    with st.form("form_ct_edit", clear_on_submit=True):
                        cod_e = st.text_input("Código", rec["cod_conta"])
                        nb_e  = st.text_input("Banco", rec["nome_banco"])
                        ag_e  = st.text_input("Agência", rec["agencia"])
                        nc_e  = st.text_input("Número da Conta", rec["num_conta"])
                        si_e  = st.number_input("Saldo Inicial", value=rec["saldo_inicial"], format="%.2f")
                        submit_e = st.form_submit_button("Atualizar")
                    if submit_e:
                        supa_update("conta_bancaria","id", sel, {
                            "cod_conta":    cod_e,
                            "nome_banco":   nb_e,
                            "agencia":      ag_e,
                            "num_conta":    nc_e,
                            "saldo_inicial": si_e
                        })
                        st.success("Conta atualizada!")
                        rerun_app()
            with c2:
                if st.button("🗑️ Excluir"):
                    supa_delete("conta_bancaria","id", sel)
                    st.success("Conta excluída!")
                    rerun_app()

    # ---- Participantes ----
    with tabs[2]:
        st.subheader("Participantes")
        raw = supa_get("participante","id,cpf_cnpj,nome,tipo_contraparte,data_cadastro")
        df = pd.DataFrame(raw)
        df["CPF/CNPJ"] = df["cpf_cnpj"].map(format_cpf_cnpj)
        df["Tipo"]     = df["tipo_contraparte"].map({1:"PF",2:"PJ",3:"Órgão Público",4:"Outros"})
        st.dataframe(df[["id","CPF/CNPJ","nome","Tipo","data_cadastro"]], use_container_width=True)

        with st.expander("➕ Novo Participante"):
            with st.form("form_pa_new", clear_on_submit=True):
                cpf = st.text_input("CPF/CNPJ")
                nome = st.text_input("Nome")
                tipo = st.selectbox("Tipo", ["PF","PJ","Órgão Público","Outros"])
                submit = st.form_submit_button("Salvar")
            if submit:
                supa_insert("participante", {
                    "cpf_cnpj": cpf,
                    "nome": nome,
                    "tipo_contraparte": ["PF","PJ","Órgão Público","Outros"].index(tipo)+1
                })
                st.success("Participante criado!")
                rerun_app()

        if not df.empty:
            sel = st.selectbox("ID p/ Editar/Excluir", df["id"].tolist())
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar"):
                    rec = df.loc[df["id"]==sel].iloc[0]
                    with st.form("form_pa_edit", clear_on_submit=True):
                        cpf_e = st.text_input("CPF/CNPJ", rec["cpf_cnpj"])
                        nome_e= st.text_input("Nome", rec["nome"])
                        tipo_e= st.selectbox(
                            "Tipo", ["PF","PJ","Órgão Público","Outros"],
                            index=["PF","PJ","Órgão Público","Outros"].index(rec["Tipo"])
                        )
                        submit_e = st.form_submit_button("Atualizar")
                    if submit_e:
                        supa_update("participante","id", sel, {
                            "cpf_cnpj": cpf_e,
                            "nome": nome_e,
                            "tipo_contraparte": ["PF","PJ","Órgão Público","Outros"].index(tipo_e)+1
                        })
                        st.success("Participante atualizado!")
                        rerun_app()
            with c2:
                if st.button("🗑️ Excluir"):
                    supa_delete("participante","id", sel)
                    st.success("Participante excluído!")
                    rerun_app()

    # ---- Culturas ----
    with tabs[3]:
        st.subheader("Culturas")
        df = pd.DataFrame(supa_get("cultura","id,nome,tipo,ciclo,unidade_medida"))
        st.dataframe(df, use_container_width=True)

        with st.expander("➕ Nova Cultura"):
            with st.form("form_cu_new", clear_on_submit=True):
                nm = st.text_input("Nome")
                tp = st.text_input("Tipo")
                ci = st.text_input("Ciclo")
                um = st.text_input("Unidade Medida")
                submit = st.form_submit_button("Salvar")
            if submit:
                supa_insert("cultura", {
                    "nome": nm, "tipo": tp, "ciclo": ci, "unidade_medida": um
                })
                st.success("Cultura criada!")
                rerun_app()

        if not df.empty:
            sel = st.selectbox("ID p/ Editar/Excluir", df["id"].tolist())
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar"):
                    rec = df.loc[df["id"]==sel].iloc[0]
                    with st.form("form_cu_edit", clear_on_submit=True):
                        nm_e = st.text_input("Nome", rec["nome"])
                        tp_e = st.text_input("Tipo", rec["tipo"])
                        ci_e = st.text_input("Ciclo", rec["ciclo"])
                        um_e = st.text_input("Unidade Medida", rec["unidade_medida"])
                        submit_e = st.form_submit_button("Atualizar")
                    if submit_e:
                        supa_update("cultura","id", sel, {
                            "nome": nm_e, "tipo": tp_e, "ciclo": ci_e, "unidade_medida": um_e
                        })
                        st.success("Cultura atualizada!")
                        rerun_app()
            with c2:
                if st.button("🗑️ Excluir"):
                    supa_delete("cultura","id", sel)
                    st.success("Cultura excluída!")
                    rerun_app()

    # ---- Áreas ----
    with tabs[4]:
        st.subheader("Áreas de Produção")
        imovs = supa_get("imovel_rural","id,nome_imovel")
        mapa_i = {i["id"]: i["nome_imovel"] for i in imovs}
        cults = supa_get("cultura","id,nome")
        mapa_c = {c["id"]: c["nome"] for c in cults}

        df = pd.DataFrame(supa_get(
            "area_producao","id,imovel_id,cultura_id,area,data_plantio,data_colheita_estimada,produtividade_estimada"
        ))
        if not df.empty:
            df["Imóvel"]  = df["imovel_id"].map(mapa_i)
            df["Cultura"] = df["cultura_id"].map(mapa_c)
            st.dataframe(df[[
                "id","Imóvel","Cultura","area","data_plantio","data_colheita_estimada","produtividade_estimada"
            ]], use_container_width=True)

        with st.expander("➕ Nova Área"):
            with st.form("form_ar_new", clear_on_submit=True):
                imv = st.selectbox("Imóvel", options=list(mapa_i.keys()), format_func=lambda x: mapa_i[x])
                cul = st.selectbox("Cultura", options=list(mapa_c.keys()), format_func=lambda x: mapa_c[x])
                ar  = st.number_input("Área (ha)", format="%.2f")
                dp  = st.date_input("Plantio", date.today())
                dc  = st.date_input("Colheita Estimada", date.today())
                pe  = st.number_input("Produtividade Estimada", format="%.2f")
                submit = st.form_submit_button("Salvar")
            if submit:
                supa_insert("area_producao", {
                    "imovel_id": imv,
                    "cultura_id": cul,
                    "area": ar,
                    "data_plantio": dp.isoformat(),
                    "data_colheita_estimada": dc.isoformat(),
                    "produtividade_estimada": pe
                })
                st.success("Área criada!")
                rerun_app()

        if not df.empty:
            sel = st.selectbox("ID p/ Editar/Excluir", df["id"].tolist())
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar"):
                    rec = df.loc[df["id"]==sel].iloc[0]
                    with st.form("form_ar_edit", clear_on_submit=True):
                        imv_e = st.selectbox(
                            "Imóvel", options=list(mapa_i.keys()),
                            index=list(mapa_i).index(rec["imovel_id"]), format_func=lambda x: mapa_i[x]
                        )
                        cul_e = st.selectbox(
                            "Cultura", options=list(mapa_c.keys()),
                            index=list(mapa_c).index(rec["cultura_id"]), format_func=lambda x: mapa_c[x]
                        )
                        ar_e  = st.number_input("Área (ha)", value=rec["area"], format="%.2f")
                        dp_e  = st.date_input("Plantio", datetime.fromisoformat(rec["data_plantio"]).date())
                        dc_e  = st.date_input("Colheita Estimada", datetime.fromisoformat(rec["data_colheita_estimada"]).date())
                        pe_e  = st.number_input("Produtividade Estimada", value=rec["produtividade_estimada"], format="%.2f")
                        submit_e = st.form_submit_button("Atualizar")
                    if submit_e:
                        supa_update("area_producao","id", sel, {
                            "imovel_id": imv_e,
                            "cultura_id": cul_e,
                            "area": ar_e,
                            "data_plantio": dp_e.isoformat(),
                            "data_colheita_estimada": dc_e.isoformat(),
                            "produtividade_estimada": pe_e
                        })
                        st.success("Área atualizada!")
                        rerun_app()
            with c2:
                if st.button("🗑️ Excluir"):
                    supa_delete("area_producao","id", sel)
                    st.success("Área excluída!")
                    rerun_app()

    # ---- Estoque ----
    with tabs[5]:
        st.subheader("Estoque")
        imovs = supa_get("imovel_rural","id,nome_imovel")
        mapa_i = {i["id"]: i["nome_imovel"] for i in imovs}

        df = pd.DataFrame(supa_get(
            "estoque","id,produto,quantidade,unidade_medida,valor_unitario,local_armazenamento,data_entrada,data_validade,imovel_id"
        ))
        if not df.empty:
            df["Imóvel"] = df["imovel_id"].map(mapa_i)
            st.dataframe(df[[
                "id","produto","quantidade","unidade_medida",
                "valor_unitario","local_armazenamento","data_validade","Imóvel"
            ]], use_container_width=True)

        with st.expander("➕ Novo Estoque"):
            with st.form("form_es_new", clear_on_submit=True):
                prod = st.text_input("Produto")
                qt   = st.number_input("Quantidade", format="%.2f")
                um   = st.text_input("Unidade Medida")
                vu   = st.number_input("Valor Unitário", format="%.2f")
                la   = st.text_input("Local de Armazenamento")
                de   = st.date_input("Data de Entrada", date.today())
                dv   = st.date_input("Data de Validade", date.today())
                imv  = st.selectbox("Imóvel", options=list(mapa_i.keys()), format_func=lambda x: mapa_i[x])
                submit = st.form_submit_button("Salvar")
            if submit:
                supa_insert("estoque", {
                    "produto": prod,
                    "quantidade": qt,
                    "unidade_medida": um,
                    "valor_unitario": vu,
                    "local_armazenamento": la,
                    "data_entrada": de.isoformat(),
                    "data_validade": dv.isoformat(),
                    "imovel_id": imv
                })
                st.success("Estoque criado!")
                rerun_app()

        if not df.empty:
            sel = st.selectbox("ID p/ Editar/Excluir", df["id"].tolist())
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar"):
                    rec = df.loc[df["id"]==sel].iloc[0]
                    with st.form("form_es_edit", clear_on_submit=True):
                        prod_e = st.text_input("Produto", rec["produto"])
                        qt_e   = st.number_input("Quantidade", value=rec["quantidade"], format="%.2f")
                        um_e   = st.text_input("Unidade Medida", rec["unidade_medida"])
                        vu_e   = st.number_input("Valor Unitário", value=rec["valor_unitario"], format="%.2f")
                        la_e   = st.text_input("Local de Armazenamento", rec["local_armazenamento"])
                        de_e   = st.date_input("Data de Entrada", datetime.fromisoformat(rec["data_entrada"]).date())
                        dv_e   = st.date_input("Data de Validade", datetime.fromisoformat(rec["data_validade"]).date())
                        imv_e  = st.selectbox(
                            "Imóvel", options=list(mapa_i.keys()),
                            index=list(mapa_i).index(rec["imovel_id"]), format_func=lambda x: mapa_i[x]
                        )
                        submit_e = st.form_submit_button("Atualizar")
                    if submit_e:
                        supa_update("estoque","id", sel, {
                            "produto": prod_e,
                            "quantidade": qt_e,
                            "unidade_medida": um_e,
                            "valor_unitario": vu_e,
                            "local_armazenamento": la_e,
                            "data_entrada": de_e.isoformat(),
                            "data_validade": dv_e.isoformat(),
                            "imovel_id": imv_e
                        })
                        st.success("Estoque atualizado!")
                        rerun_app()
            with c2:
                if st.button("🗑️ Excluir"):
                    supa_delete("estoque","id", sel)
                    st.success("Estoque excluído!")
                    rerun_app()

def show_relatorios():
    st.header("📑 Relatórios")
    rpt = st.radio("Escolha relatório", ["Balancete","Razão"])
    d1  = st.date_input("Data inicial", date.today().replace(day=1), key="rel_d1")
    d2  = st.date_input("Data final",   date.today(),             key="rel_d2")
    if st.button("Gerar"):
        st.info(f"Gerando **{rpt}** de {d1} a {d2}… 🚧 Em desenvolvimento")

# --- Menu lateral ---
st.sidebar.title("🔍 Menu")
choice = st.sidebar.radio(
    "Seção",
    ["Painel","Lançamentos","Cadastros","Relatórios"],
    key="menu_sel"
)

# --- Roteamento ---
if choice == "Painel":
    show_dashboard()
elif choice == "Lançamentos":
    show_lancamentos()
elif choice == "Cadastros":
    show_cadastros()
else:
    show_relatorios()
