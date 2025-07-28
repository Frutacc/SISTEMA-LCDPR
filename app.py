import streamlit as st
import requests, json
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

# --- Helpers Supabase CRUD ---
@st.cache_data(ttl=300)
def supa_get(table, select="*", filters=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}"
    if filters:
        url += "&" + "&".join(filters)
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()

def supa_insert(table, payload):
    resp = requests.post(f"{SUPABASE_URL}/rest/v1/{table}",
                         headers=HEADERS,
                         data=json.dumps(payload))
    resp.raise_for_status()
    try: return resp.json()
    except: return None

def supa_update(table, key, key_val, payload):
    resp = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}?{key}=eq.{key_val}",
                          headers=HEADERS,
                          data=json.dumps(payload))
    resp.raise_for_status()
    try: return resp.json()
    except: return None

def supa_delete(table, key, key_val):
    resp = requests.delete(f"{SUPABASE_URL}/rest/v1/{table}?{key}=eq.{key_val}",
                           headers=HEADERS)
    resp.raise_for_status()
    return resp.status_code

def format_cpf_cnpj(v: str) -> str:
    d = "".join(filter(str.isdigit, v))
    if len(d)==11: return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d)==14: return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return v

def rerun_app():
    try: st.experimental_rerun()
    except: st.stop()

# --- 1) Painel ---
def show_dashboard():
    st.header("📊 Painel Financeiro")
    c1, c2 = st.columns([1,3])
    with c1:
        d1 = st.date_input("De",  date.today().replace(day=1), key="dash_d1")
        d2 = st.date_input("Até", date.today(),               key="dash_d2")
    dados = supa_get("lancamento","valor_entrada,valor_saida",
                     [f"data=gte.{d1}", f"data=lte.{d2}"])
    rec   = sum(x["valor_entrada"] for x in dados)
    desp  = sum(x["valor_saida"]   for x in dados)
    saldo = rec - desp

    m1, m2, m3 = st.columns(3)
    m1.metric("💰 Saldo Total", f"R$ {saldo:,.2f}")
    m2.metric("📈 Receitas"    , f"R$ {rec:,.2f}")
    m3.metric("📉 Despesas"    , f"R$ {desp:,.2f}")

    fig = go.Figure(go.Pie(
        labels=["Receitas","Despesas"],
        values=[rec,desp],
        hole=0.4, textinfo="label+percent"
    ))
    fig.update_layout(transition={"duration":500,"easing":"cubic-in-out"})
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("⚠️ Alertas de Estoque")
    hoje   = date.today().isoformat()
    venc   = supa_get("estoque","produto,data_validade",[f"data_validade=lt.{hoje}"])
    prox30 = supa_get("estoque","produto,data_validade",[
        f"data_validade=gte.{hoje}",
        f"data_validade=lte.{(date.today()+timedelta(30)).isoformat()}"
    ])
    for x in venc:
        st.warning(f"Vencido: {x['produto']} em {x['data_validade']}", icon="⚠️")
    for x in prox30:
        st.info(f"Vence em até 30d: {x['produto']} em {x['data_validade']}")

    st.subheader("🕒 Últimas Atividades")
    acts = supa_get("lancamento","data,historico,valor_entrada,valor_saida",
                    ["order=data.desc","limit=5"])
    tabela = [{
        "Data":      a["data"],
        "Descrição": a["historico"],
        "Valor":     f"R$ {a['valor_entrada']-a['valor_saida']:,.2f}"
    } for a in acts]
    st.table(tabela)


# --- 2) Lançamentos ---
def show_lancamentos():
    st.header("📝 Lançamentos")
    d1 = st.date_input("Data inicial", date.today().replace(day=1), key="lanc_d1")
    d2 = st.date_input("Data final",   date.today(),               key="lanc_d2")

    imovs = supa_get("imovel_rural","id,nome_imovel")
    mapa_i = {i["id"]:i["nome_imovel"] for i in imovs}
    cts   = supa_get("conta_bancaria","id,nome_banco")
    mapa_c = {c["id"]:c["nome_banco"]    for c in cts}
    parts = supa_get("participante","id,nome")
    mapa_p = {p["id"]:p["nome"]           for p in parts}

    lans = supa_get(
        "lancamento",
        "id,data,cod_imovel,cod_conta,num_doc,tipo_doc,historico,id_participante,"
        "tipo_lanc,valor_entrada,valor_saida,saldo_final,natureza_saldo,categoria",
        [f"data=gte.{d1}", f"data=lte.{d2}", "order=data.desc"]
    )
    df = pd.DataFrame(lans)
    if df.empty:
        st.info("Nenhum lançamento encontrado.", icon="ℹ️")
    else:
        df["Imóvel"]        = df["cod_imovel"].map(mapa_i)
        df["Conta"]         = df["cod_conta"].map(mapa_c)
        df["Nº Documento"]  = df["num_doc"].fillna("")
        df["Tipo Doc"]      = df["tipo_doc"].map({1:"NF",2:"Recibo",3:"Boleto",4:"Outros"})
        df["Participante"]  = df["id_participante"].map(mapa_p)
        df["Tipo"]          = df["tipo_lanc"].map({1:"Receita",2:"Despesa",3:"Adiantamento"})
        df["Saldo"]         = df.apply(
            lambda r: (1 if r["natureza_saldo"]=="P" else -1)*r["saldo_final"], axis=1
        )
        df = df.rename(columns={
            "data":"Data","historico":"Histórico",
            "valor_entrada":"Entrada","valor_saida":"Saída",
            "categoria":"Categoria"
        })
        st.dataframe(df[[
            "id","Data","Imóvel","Conta","Nº Documento","Tipo Doc",
            "Participante","Histórico","Tipo","Entrada","Saída","Saldo","Categoria"
        ]], use_container_width=True)

    with st.expander("➕ Novo Lançamento"):
        with st.form("form_new_lanc", clear_on_submit=True):
            dn     = st.date_input("Data", date.today(), key="new_l_d")
            imv    = st.selectbox("Imóvel", list(mapa_i.keys()), format_func=lambda x: mapa_i[x], key="new_l_imv")
            cta    = st.selectbox("Conta",  list(mapa_c.keys()), format_func=lambda x: mapa_c[x], key="new_l_cta")
            numdoc = st.text_input("Nº Documento", key="new_l_num")
            tipod  = st.selectbox("Tipo Doc", ["NF","Recibo","Boleto","Outros"], key="new_l_tipo")
            part   = st.selectbox("Participante", list(mapa_p.keys()), format_func=lambda x: mapa_p[x], key="new_l_part")
            hist   = st.text_input("Histórico", key="new_l_hist")
            tp     = st.selectbox("Tipo Lançamento", ["Receita","Despesa","Adiantamento"], key="new_l_tp")
            ent    = st.number_input("Entrada", min_value=0.0, format="%.2f", key="new_l_ent")
            sai    = st.number_input("Saída",   min_value=0.0, format="%.2f", key="new_l_sai")
            cat    = st.text_input("Categoria", key="new_l_cat")
            btn_n  = st.form_submit_button("Salvar", use_container_width=True)
        if btn_n:
            payload = {
                "data": dn.isoformat(),
                "cod_imovel": imv,
                "cod_conta": cta,
                "num_doc": numdoc or None,
                "tipo_doc": ["NF","Recibo","Boleto","Outros"].index(tipod)+1,
                "id_participante": part,
                "historico": hist,
                "tipo_lanc": ["Receita","Despesa","Adiantamento"].index(tp)+1,
                "valor_entrada": ent,
                "valor_saida": sai,
                "saldo_final": abs(ent-sai),
                "natureza_saldo": "P" if ent>=sai else "N",
                "categoria": cat
            }
            try:
                supa_insert("lancamento", payload)
                st.success("Lançamento criado!", icon="✅")
                rerun_app()
            except requests.HTTPError as e:
                # Se for conflito de FK no Supabase (código 23503), aviso específico
                if e.response.status_code == 409 and "violates foreign key constraint" in e.response.text:
                    st.error(
                        "Não foi possível criar o lançamento: o Imóvel, Conta ou Participante selecionado não existe mais.\n"
                        "Verifique se ele ainda está cadastrado em Cadastros antes de tentar novamente.",
                        icon="🚫"
                    )
                else:
                    # Qualquer outro erro
                    st.error(f"Erro {e.response.status_code}: {e.response.text}", icon="❌")


    if not df.empty:
        sel = st.selectbox("ID p/ Editar/Excluir", df["id"].tolist(), key="sel_lanc")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✏️ Editar Lançamento", use_container_width=True):
                rec = df.loc[df["id"]==sel].iloc[0]
                with st.form("form_edit_lanc", clear_on_submit=True):
                    de     = st.date_input("Data", datetime.fromisoformat(rec["Data"]).date(), key="edit_l_d")
                    imv_e  = st.selectbox("Imóvel", list(mapa_i.keys()), format_func=lambda x: mapa_i[x],
                                          index=list(mapa_i).index(rec["cod_imovel"]), key="edit_l_imv")
                    cta_e  = st.selectbox("Conta", list(mapa_c.keys()), format_func=lambda x: mapa_c[x],
                                          index=list(mapa_c).index(rec["cod_conta"]), key="edit_l_cta")
                    num_e  = st.text_input("Nº Documento", rec["Nº Documento"], key="edit_l_num")
                    tipo_e = st.selectbox("Tipo Doc", ["NF","Recibo","Boleto","Outros"],
                                          index=["NF","Recibo","Boleto","Outros"].index(rec["Tipo Doc"]), key="edit_l_tipo")
                    part_e = st.selectbox("Participante", list(mapa_p.keys()), format_func=lambda x: mapa_p[x],
                                          index=list(mapa_p).index(rec["id_participante"]), key="edit_l_part")
                    hist_e = st.text_input("Histórico", rec["Histórico"], key="edit_l_hist")
                    tp_e   = st.selectbox("Tipo Lançamento", ["Receita","Despesa","Adiantamento"],
                                          index=["Receita","Despesa","Adiantamento"].index(rec["Tipo"]), key="edit_l_tp")
                    ent_e  = st.number_input("Entrada", value=rec["Entrada"], format="%.2f", key="edit_l_ent")
                    sai_e  = st.number_input("Saída",   value=rec["Saída"],   format="%.2f", key="edit_l_sai")
                    cat_e  = st.text_input("Categoria", rec["Categoria"], key="edit_l_cat")
                    btn_e  = st.form_submit_button("Atualizar", use_container_width=True)
                if btn_e:
                    payload = {
                        "data": de.isoformat(),
                        "cod_imovel": imv_e,
                        "cod_conta": cta_e,
                        "num_doc": num_e or None,
                        "tipo_doc": ["NF","Recibo","Boleto","Outros"].index(tipo_e)+1,
                        "id_participante": part_e,
                        "historico": hist_e,
                        "tipo_lanc": ["Receita","Despesa","Adiantamento"].index(tp_e)+1,
                        "valor_entrada": ent_e,
                        "valor_saida": sai_e,
                        "saldo_final": abs(ent_e-sai_e),
                        "natureza_saldo": "P" if ent_e>=sai_e else "N",
                        "categoria": cat_e
                    }
                    try:
                        supa_update("lancamento","id",sel,payload)
                        st.success("Atualizado!", icon="✅")
                        rerun_app()
                    except requests.HTTPError as e:
                        st.error(f"Erro {e.response.status_code}: {e.response.text}")
        with c2:
            if st.button("🗑️ Excluir Lançamento", use_container_width=True):
                supa_delete("lancamento","id", sel)
                st.success("Excluído!", icon="✅")
                rerun_app()


# --- 3) Cadastros ---
def show_cadastros():
    st.header("📇 Cadastros")
    tabs = st.tabs([
        "🏠 Imóveis","🏦 Contas","👥 Participantes",
        "🌱 Culturas","📐 Áreas","📦 Estoque"
    ])

    # ---- Imóveis ----
    with tabs[0]:
        st.subheader("Imóveis Rurais")
        df_im = pd.DataFrame(supa_get(
            "imovel_rural",
            "id,cod_imovel,nome_imovel,endereco,bairro,uf,cod_mun,cep,"
            "tipo_exploracao,participacao,area_total,area_utilizada"
        ))
        st.dataframe(df_im, use_container_width=True)

        with st.expander("➕ Novo Imóvel"):
            with st.form("form_new_imov", clear_on_submit=True):
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
                btn_i   = st.form_submit_button("Salvar")
            if btn_i:
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

        if not df_im.empty:
            sel = st.selectbox("ID p/ Editar/Excluir", df_im["id"].tolist())
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar Imóvel"):
                    rec = df_im.loc[df_im["id"]==sel].iloc[0]
                    with st.form("form_edit_imov", clear_on_submit=True):
                        cod_e    = st.text_input("Código", rec["cod_imovel"])
                        nome_e   = st.text_input("Nome", rec["nome_imovel"])
                        end_e    = st.text_input("Endereço", rec["endereco"])
                        bairro_e = st.text_input("Bairro", rec["bairro"])
                        uf_e     = st.text_input("UF", rec["uf"])
                        cm_e     = st.text_input("Cód. Município", rec["cod_mun"])
                        cep_e    = st.text_input("CEP", rec["cep"])
                        te_e     = st.selectbox("Tipo Exploração", [1,2,3,4,5,6],
                                                index=int(rec["tipo_exploracao"])-1)
                        part_e   = st.number_input("Participação (%)", value=rec["participacao"], format="%.2f")
                        at_e     = st.number_input("Área Total (ha)", value=rec["area_total"] or 0, format="%.2f")
                        au_e     = st.number_input("Área Utilizada (ha)", value=rec["area_utilizada"] or 0, format="%.2f")
                        btn_ie   = st.form_submit_button("Atualizar")
                    if btn_ie:
                        supa_update("imovel_rural","id",sel,{
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
                if st.button("🗑️ Excluir Imóvel"):
                    supa_delete("imovel_rural","id",sel)
                    st.success("Imóvel excluído!")
                    rerun_app()

    # ---- Contas ----
    with tabs[1]:
        st.subheader("Contas Bancárias")
        df_ct = pd.DataFrame(supa_get(
            "conta_bancaria",
            "id,cod_conta,nome_banco,agencia,num_conta,saldo_inicial"
        ))
        st.dataframe(df_ct, use_container_width=True)

        with st.expander("➕ Nova Conta"):
            with st.form("form_new_ct", clear_on_submit=True):
                cod_ct = st.text_input("Código")
                nb_ct  = st.text_input("Banco")
                ag_ct  = st.text_input("Agência")
                nc_ct  = st.text_input("Número da Conta")
                si_ct  = st.number_input("Saldo Inicial", format="%.2f")
                btn_ct = st.form_submit_button("Salvar")
            if btn_ct:
                supa_insert("conta_bancaria", {
                    "cod_conta":    cod_ct,
                    "nome_banco":   nb_ct,
                    "agencia":      ag_ct,
                    "num_conta":    nc_ct,
                    "saldo_inicial":si_ct
                })
                st.success("Conta criada!")
                rerun_app()

        if not df_ct.empty:
            sel_ct = st.selectbox("ID p/ Editar/Excluir", df_ct["id"].tolist())
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar Conta"):
                    rec = df_ct.loc[df_ct["id"]==sel_ct].iloc[0]
                    with st.form("form_edit_ct", clear_on_submit=True):
                        cod_e = st.text_input("Código", rec["cod_conta"])
                        nb_e  = st.text_input("Banco", rec["nome_banco"])
                        ag_e  = st.text_input("Agência", rec["agencia"])
                        nc_e  = st.text_input("Número da Conta", rec["num_conta"])
                        si_e  = st.number_input("Saldo Inicial", value=rec["saldo_inicial"], format="%.2f")
                        btn_e = st.form_submit_button("Atualizar")
                    if btn_e:
                        supa_update("conta_bancaria","id",sel_ct,{
                            "cod_conta":    cod_e,
                            "nome_banco":   nb_e,
                            "agencia":      ag_e,
                            "num_conta":    nc_e,
                            "saldo_inicial":si_e
                        })
                        st.success("Conta atualizada!")
                        rerun_app()
            with c2:
                if st.button("🗑️ Excluir Conta"):
                    supa_delete("conta_bancaria","id",sel_ct)
                    st.success("Conta excluída!")
                    rerun_app()

    # ---- Participantes ----
    with tabs[2]:
        st.subheader("👥 Participantes")
        raw_pa = supa_get(
            "participante",
            "id,cpf_cnpj,nome,tipo_contraparte,data_cadastro"
        )

        # Se não houver participantes, mostramos apenas o info
        if not raw_pa:
            st.info("Nenhum participante cadastrado ainda.", icon="ℹ️")
        else:
            # Só agora criamos o DataFrame
            df_pa = pd.DataFrame(raw_pa)
            df_pa["CPF/CNPJ"] = df_pa["cpf_cnpj"].map(format_cpf_cnpj)
            df_pa["Tipo"]     = df_pa["tipo_contraparte"].map({
                1: "PF", 2: "PJ", 3: "Órgão Público", 4: "Outros"
            })
            st.dataframe(
                df_pa[["id","CPF/CNPJ","nome","Tipo","data_cadastro"]],
                use_container_width=True,
                key="tbl_pa"
            )

            # formulário de criação
            with st.expander("➕ Novo Participante"):
                with st.form("form_new_pa", clear_on_submit=True):
                    cpf = st.text_input("CPF/CNPJ")
                    no  = st.text_input("Nome")
                    tp  = st.selectbox("Tipo", ["PF","PJ","Órgão Público","Outros"])
                    btn = st.form_submit_button("Salvar")
                if btn:
                    supa_insert("participante", {
                        "cpf_cnpj": cpf,
                        "nome": no,
                        "tipo_contraparte": ["PF","PJ","Órgão Público","Outros"].index(tp) + 1
                    })
                    st.success("Participante criado!", icon="✅")
                    rerun_app()

            # edit / delete
            sel_pa = st.selectbox("ID p/ Editar/Excluir", df_pa["id"].tolist(), key="sel_pa")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar Participante"):
                    rec = df_pa.loc[df_pa["id"] == sel_pa].iloc[0]
                    with st.form("form_edit_pa", clear_on_submit=True):
                        cpf_e = st.text_input("CPF/CNPJ", rec["cpf_cnpj"])
                        no_e  = st.text_input("Nome", rec["nome"])
                        tp_e  = st.selectbox(
                            "Tipo",
                            ["PF","PJ","Órgão Público","Outros"],
                            index=["PF","PJ","Órgão Público","Outros"].index(rec["Tipo"])
                        )
                        btn_e = st.form_submit_button("Atualizar")
                    if btn_e:
                        supa_update("participante", "id", sel_pa, {
                            "cpf_cnpj": cpf_e,
                            "nome": no_e,
                            "tipo_contraparte": ["PF","PJ","Órgão Público","Outros"].index(tp_e) + 1
                        })
                        st.success("Participante atualizado!", icon="✅")
                        rerun_app()
            with c2:
                if st.button("🗑️ Excluir Participante"):
                    supa_delete("participante", "id", sel_pa)
                    st.success("Participante excluído!", icon="✅")
                    rerun_app()


    # ---- Culturas ----
    with tabs[3]:
        st.subheader("Culturas")
        df_cu = pd.DataFrame(supa_get("cultura","id,nome,tipo,ciclo,unidade_medida"))
        st.dataframe(df_cu, use_container_width=True)

        with st.expander("➕ Nova Cultura"):
            with st.form("form_new_cu", clear_on_submit=True):
                nm = st.text_input("Nome")
                tp = st.text_input("Tipo")
                ci = st.text_input("Ciclo")
                um = st.text_input("Unidade Medida")
                btn = st.form_submit_button("Salvar")
            if btn:
                supa_insert("cultura", {
                    "nome": nm, "tipo": tp, "ciclo": ci, "unidade_medida": um
                })
                st.success("Cultura criada!")
                rerun_app()

        if not df_cu.empty:
            sel_cu = st.selectbox("ID p/ Editar/Excluir", df_cu["id"].tolist())
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar Cultura"):
                    rec = df_cu.loc[df_cu["id"]==sel_cu].iloc[0]
                    with st.form("form_edit_cu", clear_on_submit=True):
                        nm_e = st.text_input("Nome", rec["nome"])
                        tp_e = st.text_input("Tipo", rec["tipo"])
                        ci_e = st.text_input("Ciclo", rec["ciclo"])
                        um_e = st.text_input("Unidade Medida", rec["unidade_medida"])
                        btn_e= st.form_submit_button("Atualizar")
                    if btn_e:
                        supa_update("cultura","id",sel_cu,{
                            "nome": nm_e, "tipo": tp_e,
                            "ciclo": ci_e, "unidade_medida": um_e
                        })
                        st.success("Cultura atualizada!")
                        rerun_app()
            with c2:
                if st.button("🗑️ Excluir Cultura"):
                    supa_delete("cultura","id",sel_cu)
                    st.success("Cultura excluída!")
                    rerun_app()

    # ---- Áreas ----
    with tabs[4]:
        st.subheader("Áreas de Produção")
        imovs = supa_get("imovel_rural","id,nome_imovel")
        mapa_i = {i["id"]:i["nome_imovel"] for i in imovs}
        cults = supa_get("cultura","id,nome")
        mapa_c = {c["id"]:c["nome"]          for c in cults}

        df_ar = pd.DataFrame(supa_get(
            "area_producao",
            "id,imovel_id,cultura_id,area,data_plantio,data_colheita_estimada,produtividade_estimada"
        ))
        if not df_ar.empty:
            df_ar["Imóvel"]  = df_ar["imovel_id"].map(mapa_i)
            df_ar["Cultura"] = df_ar["cultura_id"].map(mapa_c)
            st.dataframe(df_ar[[
                "id","Imóvel","Cultura","area",
                "data_plantio","data_colheita_estimada","produtividade_estimada"
            ]], use_container_width=True)

        with st.expander("➕ Nova Área"):
            with st.form("form_new_ar", clear_on_submit=True):
                imv = st.selectbox("Imóvel", options=list(mapa_i.keys()), format_func=lambda x: mapa_i[x])
                cul = st.selectbox("Cultura",options=list(mapa_c.keys()), format_func=lambda x: mapa_c[x])
                ar  = st.number_input("Área (ha)", format="%.2f")
                dp  = st.date_input("Plantio")
                dc  = st.date_input("Colheita Estimada")
                pe  = st.number_input("Produtividade Estimada", format="%.2f")
                btn = st.form_submit_button("Salvar")
            if btn:
                supa_insert("area_producao", {
                    "imovel_id": imv, "cultura_id": cul,
                    "area": ar,
                    "data_plantio": dp.isoformat(),
                    "data_colheita_estimada": dc.isoformat(),
                    "produtividade_estimada": pe
                })
                st.success("Área criada!")
                rerun_app()

        if not df_ar.empty:
            sel_ar = st.selectbox("ID p/ Editar/Excluir", df_ar["id"].tolist())
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar Área"):
                    rec = df_ar.loc[df_ar["id"]==sel_ar].iloc[0]
                    with st.form("form_edit_ar", clear_on_submit=True):
                        imv_e = st.selectbox("Imóvel", options=list(mapa_i.keys()),
                                             index=list(mapa_i).index(rec["imovel_id"]),
                                             format_func=lambda x: mapa_i[x])
                        cul_e = st.selectbox("Cultura", options=list(mapa_c.keys()),
                                             index=list(mapa_c).index(rec["cultura_id"]),
                                             format_func=lambda x: mapa_c[x])
                        ar_e  = st.number_input("Área (ha)", value=rec["area"], format="%.2f")
                        dp_e  = st.date_input("Plantio", datetime.fromisoformat(rec["data_plantio"]).date())
                        dc_e  = st.date_input("Colheita Estimada", datetime.fromisoformat(rec["data_colheita_estimada"]).date())
                        pe_e  = st.number_input("Produtividade Estimada", value=rec["produtividade_estimada"], format="%.2f")
                        btn_e = st.form_submit_button("Atualizar")
                    if btn_e:
                        supa_update("area_producao","id",sel_ar,{
                            "imovel_id": imv_e, "cultura_id": cul_e,
                            "area": ar_e,
                            "data_plantio": dp_e.isoformat(),
                            "data_colheita_estimada": dc_e.isoformat(),
                            "produtividade_estimada": pe_e
                        })
                        st.success("Área atualizada!")
                        rerun_app()
            with c2:
                if st.button("🗑️ Excluir Área"):
                    supa_delete("area_producao","id",sel_ar)
                    st.success("Área excluída!")
                    rerun_app()

    # ---- Estoque ----
    with tabs[5]:
        st.subheader("Estoque")
        imovs = supa_get("imovel_rural","id,nome_imovel")
        mapa_i = {i["id"]:i["nome_imovel"] for i in imovs}

        df_es = pd.DataFrame(supa_get(
            "estoque",
            "id,produto,quantidade,unidade_medida,valor_unitario,"
            "local_armazenamento,data_entrada,data_validade,imovel_id"
        ))
        if not df_es.empty:
            df_es["Imóvel"] = df_es["imovel_id"].map(mapa_i)
            st.dataframe(df_es[[
                "id","produto","quantidade","unidade_medida",
                "valor_unitario","local_armazenamento","data_validade","Imóvel"
            ]], use_container_width=True)

        with st.expander("➕ Novo Estoque"):
            with st.form("form_new_es", clear_on_submit=True):
                prod  = st.text_input("Produto")
                qt    = st.number_input("Quantidade", format="%.2f")
                um    = st.text_input("Unidade Medida")
                vu    = st.number_input("Valor Unitário", format="%.2f")
                la    = st.text_input("Local de Armazenamento")
                de    = st.date_input("Data de Entrada", date.today())
                dv    = st.date_input("Data de Validade", date.today())
                imv_e = st.selectbox("Imóvel", options=list(mapa_i.keys()), format_func=lambda x: mapa_i[x])
                btn   = st.form_submit_button("Salvar")
            if btn:
                supa_insert("estoque", {
                    "produto": prod,
                    "quantidade": qt,
                    "unidade_medida": um,
                    "valor_unitario": vu,
                    "local_armazenamento": la,
                    "data_entrada": de.isoformat(),
                    "data_validade": dv.isoformat(),
                    "imovel_id": imv_e
                })
                st.success("Estoque criado!")
                rerun_app()

        if not df_es.empty:
            sel_es = st.selectbox("ID p/ Editar/Excluir", df_es["id"].tolist())
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar Estoque"):
                    rec = df_es.loc[df_es["id"]==sel_es].iloc[0]
                    with st.form("form_edit_es", clear_on_submit=True):
                        prod_e = st.text_input("Produto", rec["produto"])
                        qt_e   = st.number_input("Quantidade", value=rec["quantidade"], format="%.2f")
                        um_e   = st.text_input("Unidade Medida", rec["unidade_medida"])
                        vu_e   = st.number_input("Valor Unitário", value=rec["valor_unitario"], format="%.2f")
                        la_e   = st.text_input("Local de Armazenamento", rec["local_armazenamento"])
                        de_e   = st.date_input("Data de Entrada", datetime.fromisoformat(rec["data_entrada"]).date())
                        dv_e   = st.date_input("Data de Validade", datetime.fromisoformat(rec["data_validade"]).date())
                        imv_ed = st.selectbox("Imóvel", options=list(mapa_i.keys()),
                                              index=list(mapa_i).index(rec["imovel_id"]),
                                              format_func=lambda x: mapa_i[x])
                        btn_e  = st.form_submit_button("Atualizar")
                    if btn_e:
                        supa_update("estoque","id",sel_es,{
                            "produto": prod_e,
                            "quantidade": qt_e,
                            "unidade_medida": um_e,
                            "valor_unitario": vu_e,
                            "local_armazenamento": la_e,
                            "data_entrada": de_e.isoformat(),
                            "data_validade": dv_e.isoformat(),
                            "imovel_id": imv_ed
                        })
                        st.success("Estoque atualizado!")
                        rerun_app()
            with c2:
                if st.button("🗑️ Excluir Estoque"):
                    supa_delete("estoque","id",sel_es)
                    st.success("Estoque excluído!")
                    rerun_app()

# --- 4) Relatórios ---
def show_relatorios():
    st.header("📑 Relatórios")
    rpt = st.radio("Escolha relatório", ["Balancete","Razão"])
    d1  = st.date_input("Data inicial", date.today().replace(day=1), key="rel_d1")
    d2  = st.date_input("Data final",   date.today(),             key="rel_d2")
    if st.button("Gerar"):
        st.info(f"Gerando **{rpt}** de {d1} a {d2}… 🚧 Em desenvolvimento")

# --- Menu lateral e roteamento ---
st.sidebar.title("🔍 Menu")
choice = st.sidebar.radio(
    "",
    ["Painel","Lançamentos","Cadastros","Relatórios"],
    key="menu_sel"
)

if choice == "Painel":
    show_dashboard()
elif choice == "Lançamentos":
    show_lancamentos()
elif choice == "Cadastros":
    show_cadastros()
else:
    show_relatorios()
