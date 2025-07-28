import streamlit as st
import requests
import json
from datetime import date, datetime, timedelta
import pandas as pd
import plotly.graph_objects as go

# --- Supabase configuration via Streamlit secrets ---
SUPABASE_URL      = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
HEADERS = {
    "apikey":        SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type":  "application/json"
}

# --- Helper functions for Supabase REST CRUD ---
def supa_get(table, select="*", filters=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}"
    if filters:
        url += "&" + "&".join(filters)
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def supa_insert(table, payload):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.post(url, headers=HEADERS, data=json.dumps(payload))
    r.raise_for_status()
    return r.json()

def supa_update(table, key, key_val, payload):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{key}=eq.{key_val}"
    r = requests.patch(url, headers=HEADERS, data=json.dumps(payload))
    r.raise_for_status()
    return r.json()

def supa_delete(table, key, key_val):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{key}=eq.{key_val}"
    r = requests.delete(url, headers=HEADERS)
    r.raise_for_status()
    return r.status_code

def format_cpf_cnpj(value):
    digits = ''.join(filter(str.isdigit, value))
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return value

# --- Streamlit setup ---
st.set_page_config(page_title="Sistema AgroContábil - LCDPR", layout="wide")
st.sidebar.title("🔍 Menu")
page = st.sidebar.radio("", ["Painel","Lançamentos","Cadastros","Relatórios"])

# --- Página Painel ---
if page == "Painel":
    st.header("📊 Painel Financeiro")
    # Filtro de datas
    c1, c2 = st.columns([1,3])
    with c1:
        d1 = st.date_input("📅 De", date.today().replace(day=1))
        d2 = st.date_input("📅 Até", date.today())
    # Métricas
    dados = supa_get("lancamento","valor_entrada,valor_saida",
                     [f"data=gte.{d1.isoformat()}",f"data=lte.{d2.isoformat()}"])
    rec  = sum(item["valor_entrada"] for item in dados)
    desp = sum(item["valor_saida"]   for item in dados)
    saldo = rec - desp
    m1, m2, m3 = st.columns(3)
    m1.metric("💰 Saldo Total", f"R$ {saldo:,.2f}")
    m2.metric("📈 Receitas"    , f"R$ {rec:,.2f}")
    m3.metric("📉 Despesas"    , f"R$ {desp:,.2f}")
    # Gráfico de pizza
    fig = go.Figure(go.Pie(
        labels=["Receitas","Despesas"],
        values=[rec,desp],
        hole=0.4,
        textinfo="label+percent"
    ))
    st.plotly_chart(fig, use_container_width=True)
    # Alertas de estoque
    st.subheader("⚠️ Alertas de Estoque")
    hoje = date.today().isoformat()
    vencidos = supa_get("estoque","produto,data_validade",[f"data_validade=lt.{hoje}"])
    proximos = supa_get("estoque","produto,data_validade",
                        [f"data_validade=gte.{hoje}",f"data_validade=lte.{(date.today()+timedelta(days=30)).isoformat()}"])
    for it in vencidos:
        st.warning(f"Vencido: {it['produto']} em {it['data_validade']}")
    for it in proximos:
        st.info   (f"Vence em até 30d: {it['produto']} em {it['data_validade']}")
    # Últimas atividades
    st.subheader("🕒 Últimas Atividades")
    acts = supa_get("lancamento","data,historico,valor_entrada,valor_saida",
                    ["order=data.desc","limit=5"])
    table = [{"Data":a["data"],"Descrição":a["historico"],
              "Valor":f"R$ {a['valor_entrada']-a['valor_saida']:,.2f}"} for a in acts]
    st.table(table)

# --- Página Lançamentos ---
elif page == "Lançamentos":
    st.header("📝 Lançamentos")
    # Filtro
    d1 = st.date_input("Data inicial", date.today().replace(day=1))
    d2 = st.date_input("Data final",   date.today())
    # Mappings
    imovs  = supa_get("imovel_rural","id,nome_imovel")
    mapa_i = {i["id"]:i["nome_imovel"] for i in imovs}
    cts    = supa_get("conta_bancaria","id,nome_banco")
    mapa_c = {c["id"]:c["nome_banco"] for c in cts}
    # Fetch lançamentos
    lans = supa_get("lancamento",
        "id,data,cod_imovel,cod_conta,historico,tipo_lanc,valor_entrada,valor_saida,saldo_final,natureza_saldo,categoria",
        [f"data=gte.{d1.isoformat()}",f"data=lte.{d2.isoformat()}","order=data.desc"]
    )
    df = pd.DataFrame(lans)
    if not df.empty:
        df["Imóvel"] = df["cod_imovel"].map(mapa_i)
        df["Conta"]  = df["cod_conta"].map(mapa_c)
        df["Tipo"]   = df["tipo_lanc"].map({1:"Receita",2:"Despesa",3:"Adiantamento"})
        df["Saldo"]  = df["natureza_saldo"].apply(lambda x:1 if x=="P" else -1) * df["saldo_final"]
        df = df.rename(columns={
            "data":"Data","historico":"Histórico",
            "valor_entrada":"Entrada","valor_saida":"Saída"
        })
        df = df[["id","Data","Imóvel","Histórico","Tipo","Entrada","Saída","Saldo","categoria"]]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Nenhum lançamento encontrado.")

    # Novo lançamento
    with st.expander("➕ Novo Lançamento"):
        with st.form("novo_lanc"):
            d   = st.date_input("Data", date.today())
            imv = st.selectbox("Imóvel", list(mapa_i.items()), format_func=lambda x:x[1])[0]
            cta = st.selectbox("Conta" , list(mapa_c.items()), format_func=lambda x:x[1])[0]
            hist= st.text_input("Histórico")
            tp  = st.selectbox("Tipo", ["Receita","Despesa","Adiantamento"])
            ent = st.number_input("Entrada", min_value=0.0, format="%.2f")
            sai = st.number_input("Saída"   , min_value=0.0, format="%.2f")
            cat = st.text_input("Categoria")
            ok  = st.form_submit_button("Salvar")
        if ok:
            supa_insert("lancamento", {
                "data": d.isoformat(),
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
            st.experimental_rerun()

    # Editar / Excluir
    if not df.empty:
        sel = st.selectbox("Selecione ID", df["id"].tolist())
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✏️ Editar Lançamento"):
                rec = df[df["id"]==sel].iloc[0]
                with st.form("edit_lanc"):
                    d   = st.date_input("Data", datetime.fromisoformat(rec["Data"]).date())
                    imv = st.selectbox("Imóvel", list(mapa_i.items()), index=list(mapa_i).index(rec["cod_imovel"]))[0]
                    cta = st.selectbox("Conta" , list(mapa_c.items()), index=list(mapa_c).index(rec["cod_conta"]))[0]
                    hist= st.text_input("Histórico", rec["Histórico"])
                    tp  = st.selectbox("Tipo", ["Receita","Despesa","Adiantamento"], index=["Receita","Despesa","Adiantamento"].index(rec["Tipo"]))
                    ent = st.number_input("Entrada", value=float(rec["Entrada"]), format="%.2f")
                    sai = st.number_input("Saída"   , value=float(rec["Saída"])   , format="%.2f")
                    cat = st.text_input("Categoria", rec["categoria"])
                    ok2 = st.form_submit_button("Atualizar")
                if ok2:
                    supa_update("lancamento","id", sel, {
                        "data": d.isoformat(),
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
                    st.success("Atualizado!")
                    st.experimental_rerun()
        with col2:
            if st.button("🗑️ Excluir Lançamento"):
                supa_delete("lancamento","id",sel)
                st.success("Excluído!")
                st.experimental_rerun()

# --- Página Cadastros ---
elif page == "Cadastros":
    st.header("📇 Cadastros")
    tabs = st.tabs(["Imóveis","Contas","Participantes","Culturas","Áreas","Estoque"])
    # --- Imóveis ---
    with tabs[0]:
        st.subheader("🏠 Imóveis Rurais")
        df_im = pd.DataFrame(supa_get("imovel_rural","id,cod_imovel,nome_imovel,uf,area_total,area_utilizada,participacao"))
        st.dataframe(df_im, use_container_width=True)
        with st.expander("➕ Novo Imóvel"):
            with st.form("form_im"):
                cod = st.text_input("Código")
                nome= st.text_input("Nome")
                end = st.text_input("Endereço")
                uf  = st.text_input("UF")
                cm  = st.text_input("Município")
                cep = st.text_input("CEP")
                te  = st.selectbox("Tipo Exploração", [1,2,3,4,5,6])
                part= st.number_input("Participação (%)", value=100.0, format="%.2f")
                at = st.number_input("Área Total (ha)", format="%.2f")
                au = st.number_input("Área Utilizada (ha)", format="%.2f")
                ok = st.form_submit_button("Salvar")
            if ok:
                supa_insert("imovel_rural",{
                    "cod_imovel":cod,"nome_imovel":nome,
                    "endereco":end,"uf":uf,"cod_mun":cm,"cep":cep,
                    "tipo_exploracao":te,"participacao":part,
                    "area_total":at,"area_utilizada":au
                })
                st.success("Imóvel criado!")
                st.experimental_rerun()
        sel = st.selectbox("ID p/ Editar/Excluir", df_im["id"].tolist() if not df_im.empty else [])
        if sel:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar Imóvel"):
                    rec = df_im[df_im["id"]==sel].iloc[0]
                    with st.form("edit_im"):
                        cod = st.text_input("Código", rec["cod_imovel"])
                        nome= st.text_input("Nome", rec["nome_imovel"])
                        end = st.text_input("Endereço", rec["uf"])
                        uf  = st.text_input("UF", rec["uf"])
                        cm  = st.text_input("Município", rec["cod_mun"])
                        cep = st.text_input("CEP", rec["cep"])
                        te  = st.selectbox("Tipo Exploração", [1,2,3,4,5,6], index=int(rec["tipo_exploracao"])-1)
                        part= st.number_input("Participação (%)", value=float(rec["participacao"]), format="%.2f")
                        at = st.number_input("Área Total (ha)", value=float(rec["area_total"] or 0), format="%.2f")
                        au = st.number_input("Área Utilizada (ha)", value=float(rec["area_utilizada"] or 0), format="%.2f")
                        ok2= st.form_submit_button("Atualizar")
                    if ok2:
                        supa_update("imovel_rural","id",sel,{
                            "cod_imovel":cod,"nome_imovel":nome,
                            "endereco":end,"uf":uf,"cod_mun":cm,"cep":cep,
                            "tipo_exploracao":te,"participacao":part,
                            "area_total":at,"area_utilizada":au
                        })
                        st.success("Atualizado!")
                        st.experimental_rerun()
            with c2:
                if st.button("🗑️ Excluir Imóvel"):
                    supa_delete("imovel_rural","id",sel)
                    st.success("Excluído!")
                    st.experimental_rerun()
    # --- Contas ---
    with tabs[1]:
        st.subheader("🏦 Contas Bancárias")
        df_ct = pd.DataFrame(supa_get("conta_bancaria","id,cod_conta,nome_banco,agencia,num_conta,saldo_inicial"))
        st.dataframe(df_ct, use_container_width=True)
        with st.expander("➕ Nova Conta"):
            with st.form("form_ct"):
                cod = st.text_input("Código")
                nb  = st.text_input("Banco")
                ag  = st.text_input("Agência")
                nc  = st.text_input("Número da Conta")
                si  = st.number_input("Saldo Inicial", format="%.2f")
                ok = st.form_submit_button("Salvar")
            if ok:
                supa_insert("conta_bancaria",{
                    "cod_conta":cod,"nome_banco":nb,
                    "agencia":ag,"num_conta":nc,"saldo_inicial":si
                })
                st.success("Conta criada!")
                st.experimental_rerun()
        sel = st.selectbox("ID p/ Editar/Excluir", df_ct["id"].tolist() if not df_ct.empty else [])
        if sel:
            c1,c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar Conta"):
                    rec = df_ct[df_ct["id"]==sel].iloc[0]
                    with st.form("edit_ct"):
                        cod = st.text_input("Código", rec["cod_conta"])
                        nb  = st.text_input("Banco", rec["nome_banco"])
                        ag  = st.text_input("Agência", rec["agencia"])
                        nc  = st.text_input("Número da Conta", rec["num_conta"])
                        si  = st.number_input("Saldo Inicial", value=float(rec["saldo_inicial"]), format="%.2f")
                        ok2 = st.form_submit_button("Atualizar")
                    if ok2:
                        supa_update("conta_bancaria","id",sel,{
                            "cod_conta":cod,"nome_banco":nb,
                            "agencia":ag,"num_conta":nc,"saldo_inicial":si
                        })
                        st.success("Atualizado!")
                        st.experimental_rerun()
            with c2:
                if st.button("🗑️ Excluir Conta"):
                    supa_delete("conta_bancaria","id",sel)
                    st.success("Excluído!")
                    st.experimental_rerun()
    # --- Participantes ---
    with tabs[2]:
        st.subheader("👥 Participantes")
        df_pa = pd.DataFrame(supa_get("participante","id,cpf_cnpj,nome,tipo_contraparte,data_cadastro"))
        df_pa["CPF/CNPJ"] = df_pa["cpf_cnpj"].apply(format_cpf_cnpj)
        df_pa["Tipo"] = df_pa["tipo_contraparte"].map({1:"PF",2:"PJ",3:"Órgão Público",4:"Outros"})
        st.dataframe(df_pa[["id","CPF/CNPJ","nome","Tipo","data_cadastro"]], use_container_width=True)
        with st.expander("➕ Novo Participante"):
            with st.form("form_pa"):
                cpf = st.text_input("CPF/CNPJ")
                nome= st.text_input("Nome")
                tp  = st.selectbox("Tipo", ["PF","PJ","Órgão Público","Outros"])
                ok  = st.form_submit_button("Salvar")
            if ok:
                supa_insert("participante",{
                    "cpf_cnpj": cpf, "nome": nome,
                    "tipo_contraparte": ["PF","PJ","Órgão Público","Outros"].index(tp)+1
                })
                st.success("Participante criado!")
                st.experimental_rerun()
        sel = st.selectbox("ID p/ Editar/Excluir", df_pa["id"].tolist() if not df_pa.empty else [])
        if sel:
            c1,c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar Participante"):
                    rec = df_pa[df_pa["id"]==sel].iloc[0]
                    with st.form("edit_pa"):
                        cpf = st.text_input("CPF/CNPJ", rec["cpf_cnpj"])
                        nome= st.text_input("Nome", rec["nome"])
                        tp  = st.selectbox("Tipo", ["PF","PJ","Órgão Público","Outros"], index=[1,2,3,4].index(rec["tipo_contraparte"]))
                        ok2 = st.form_submit_button("Atualizar")
                    if ok2:
                        supa_update("participante","id",sel,{
                            "cpf_cnpj": cpf, "nome": nome,
                            "tipo_contraparte": ["PF","PJ","Órgão Público","Outros"].index(tp)+1
                        })
                        st.success("Atualizado!")
                        st.experimental_rerun()
            with c2:
                if st.button("🗑️ Excluir Participante"):
                    supa_delete("participante","id",sel)
                    st.success("Excluído!")
                    st.experimental_rerun()
    # --- Culturas ---
    with tabs[3]:
        st.subheader("🌱 Culturas")
        df_cu = pd.DataFrame(supa_get("cultura","id,nome,tipo,ciclo,unidade_medida"))
        st.dataframe(df_cu, use_container_width=True)
        with st.expander("➕ Nova Cultura"):
            with st.form("form_cu"):
                nome= st.text_input("Nome")
                tp  = st.text_input("Tipo")
                ci  = st.text_input("Ciclo")
                um  = st.text_input("Unidade de Medida")
                ok  = st.form_submit_button("Salvar")
            if ok:
                supa_insert("cultura",{"nome":nome,"tipo":tp,"ciclo":ci,"unidade_medida":um})
                st.success("Cultura criada!")
                st.experimental_rerun()
        sel = st.selectbox("ID p/ Editar/Excluir", df_cu["id"].tolist() if not df_cu.empty else [])
        if sel:
            c1,c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar Cultura"):
                    rec = df_cu[df_cu["id"]==sel].iloc[0]
                    with st.form("edit_cu"):
                        nome= st.text_input("Nome", rec["nome"])
                        tp  = st.text_input("Tipo", rec["tipo"])
                        ci  = st.text_input("Ciclo", rec["ciclo"])
                        um  = st.text_input("Unidade de Medida", rec["unidade_medida"])
                        ok2 = st.form_submit_button("Atualizar")
                    if ok2:
                        supa_update("cultura","id",sel,{"nome":nome,"tipo":tp,"ciclo":ci,"unidade_medida":um})
                        st.success("Atualizado!")
                        st.experimental_rerun()
            with c2:
                if st.button("🗑️ Excluir Cultura"):
                    supa_delete("cultura","id",sel)
                    st.success("Excluído!")
                    st.experimental_rerun()
    # --- Áreas de Produção ---
    with tabs[4]:
        st.subheader("📐 Áreas de Produção")
        imovs = supa_get("imovel_rural","id,nome_imovel")
        cults = supa_get("cultura","id,nome")
        mapa_i = {i["id"]:i["nome_imovel"] for i in imovs}
        mapa_c = {c["id"]:c["nome"]        for c in cults}
        df_ar = pd.DataFrame(supa_get("area_producao","id,imovel_id,cultura_id,area,data_plantio,data_colheita_estimada,produtividade_estimada"))
        if not df_ar.empty:
            df_ar["Imóvel"]  = df_ar["imovel_id"].map(mapa_i)
            df_ar["Cultura"] = df_ar["cultura_id"].map(mapa_c)
            st.dataframe(df_ar[["id","Imóvel","Cultura","area","data_plantio","data_colheita_estimada","produtividade_estimada"]], use_container_width=True)
        with st.expander("➕ Nova Área"):
            with st.form("form_ar"):
                imv = st.selectbox("Imóvel", list(mapa_i.items()), format_func=lambda x:x[1])[0]
                cul = st.selectbox("Cultura", list(mapa_c.items()), format_func=lambda x:x[1])[0]
                ar  = st.number_input("Área (ha)", format="%.2f")
                dp  = st.date_input("Plantio")
                dc  = st.date_input("Colheita Estimada")
                pe  = st.number_input("Produtividade Est.", format="%.2f")
                ok  = st.form_submit_button("Salvar")
            if ok:
                supa_insert("area_producao",{
                    "imovel_id":imv,"cultura_id":cul,
                    "area":ar,"data_plantio":dp.isoformat(),
                    "data_colheita_estimada":dc.isoformat(),
                    "produtividade_estimada":pe
                })
                st.success("Área criada!")
                st.experimental_rerun()
        sel = st.selectbox("ID p/ Editar/Excluir", df_ar["id"].tolist() if not df_ar.empty else [])
        if sel:
            c1,c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar Área"):
                    rec = df_ar[df_ar["id"]==sel].iloc[0]
                    with st.form("edit_ar"):
                        imv = st.selectbox("Imóvel", list(mapa_i.items()), index=list(mapa_i).index(rec["imovel_id"]))[0]
                        cul = st.selectbox("Cultura", list(mapa_c.items()), index=list(mapa_c).index(rec["cultura_id"]))[0]
                        ar  = st.number_input("Área (ha)", value=float(rec["area"]), format="%.2f")
                        dp  = st.date_input("Plantio", datetime.fromisoformat(rec["data_plantio"]).date())
                        dc  = st.date_input("Colheita Estimada", datetime.fromisoformat(rec["data_colheita_estimada"]).date())
                        pe  = st.number_input("Produtividade Est.", value=float(rec["produtividade_estimada"] or 0), format="%.2f")
                        ok2 = st.form_submit_button("Atualizar")
                    if ok2:
                        supa_update("area_producao","id",sel,{
                            "imovel_id":imv,"cultura_id":cul,
                            "area":ar,"data_plantio":dp.isoformat(),
                            "data_colheita_estimada":dc.isoformat(),
                            "produtividade_estimada":pe
                        })
                        st.success("Atualizado!")
                        st.experimental_rerun()
            with c2:
                if st.button("🗑️ Excluir Área"):
                    supa_delete("area_producao","id",sel)
                    st.success("Excluído!")
                    st.experimental_rerun()
    # --- Estoque ---
    with tabs[5]:
        st.subheader("📦 Estoque")
        imovs = supa_get("imovel_rural","id,nome_imovel")
        mapa_i = {i["id"]:i["nome_imovel"] for i in imovs}
        df_es = pd.DataFrame(supa_get("estoque","id,produto,quantidade,unidade_medida,valor_unitario,local_armazenamento,data_entrada,data_validade,imovel_id"))
        if not df_es.empty:
            df_es["Imóvel"] = df_es["imovel_id"].map(mapa_i)
            st.dataframe(df_es[["id","produto","quantidade","unidade_medida","valor_unitario","local_armazenamento","data_validade","Imóvel"]], use_container_width=True)
        with st.expander("➕ Novo Estoque"):
            with st.form("form_es"):
                prod = st.text_input("Produto")
                qt   = st.number_input("Quantidade", format="%.2f")
                um   = st.text_input("Unidade de Medida")
                vu   = st.number_input("Valor Unitário", format="%.2f")
                la   = st.text_input("Local Armazenamento")
                de   = st.date_input("Data Entrada", date.today())
                dv   = st.date_input("Data Validade")
                imv  = st.selectbox("Imóvel", list(mapa_i.items()), format_func=lambda x:x[1])[0]
                ok   = st.form_submit_button("Salvar")
            if ok:
                supa_insert("estoque",{
                    "produto":prod,"quantidade":qt,"unidade_medida":um,
                    "valor_unitario":vu,"local_armazenamento":la,
                    "data_entrada":de.isoformat(),"data_validade":dv.isoformat(),
                    "imovel_id":imv
                })
                st.success("Estoque criado!")
                st.experimental_rerun()
        sel = st.selectbox("ID p/ Editar/Excluir", df_es["id"].tolist() if not df_es.empty else [])
        if sel:
            c1,c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar Estoque"):
                    rec = df_es[df_es["id"]==sel].iloc[0]
                    with st.form("edit_es"):
                        prod = st.text_input("Produto", rec["produto"])
                        qt   = st.number_input("Quantidade", value=float(rec["quantidade"]), format="%.2f")
                        um   = st.text_input("Unidade de Medida", rec["unidade_medida"])
                        vu   = st.number_input("Valor Unitário", value=float(rec["valor_unitario"]), format="%.2f")
                        la   = st.text_input("Local Armazenamento", rec["local_armazenamento"])
                        de   = st.date_input("Data Entrada", datetime.fromisoformat(rec["data_entrada"]).date())
                        dv   = st.date_input("Data Validade", datetime.fromisoformat(rec["data_validade"]).date())
                        imv  = st.selectbox("Imóvel", list(mapa_i.items()), index=list(mapa_i).index(rec["imovel_id"]))[0]
                        ok2  = st.form_submit_button("Atualizar")
                    if ok2:
                        supa_update("estoque","id",sel,{
                            "produto":prod,"quantidade":qt,"unidade_medida":um,
                            "valor_unitario":vu,"local_armazenamento":la,
                            "data_entrada":de.isoformat(),"data_validade":dv.isoformat(),
                            "imovel_id":imv
                        })
                        st.success("Atualizado!")
                        st.experimental_rerun()
            with c2:
                if st.button("🗑️ Excluir Estoque"):
                    supa_delete("estoque","id",sel)
                    st.success("Excluído!")
                    st.experimental_rerun()

# --- Página Relatórios ---
elif page == "Relatórios":
    st.header("📑 Relatórios")
    rpt = st.radio("Escolha relatório", ["Balancete","Razão"])
    d1 = st.date_input("Data inicial", date.today().replace(day=1))
    d2 = st.date_input("Data final",   date.today())
    if st.button("Gerar"):
        st.info(f"Gerando **{rpt}** de {d1.isoformat()} a {d2.isoformat()}...")
        # Aqui você pode chamar uma RPC ou lógica SQL customizada no Supabase
        # Exemplo placeholder:
        st.write("🚧 Em desenvolvimento")
