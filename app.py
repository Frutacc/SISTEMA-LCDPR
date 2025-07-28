import streamlit as st
import requests, json
from datetime import date, datetime, timedelta
import pandas as pd
import plotly.graph_objects as go

# --- Supabase via REST (credentials via secrets) ---
SUPABASE_URL      = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
HEADERS = {
    "apikey":        SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type":  "application/json"
}

# --- Helpers Supabase CRUD ---
def supa_get(table, select="*", filters=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}"
    if filters:
        url += "&" + "&".join(filters)
    r = requests.get(url, headers=HEADERS); r.raise_for_status()
    return r.json()

def supa_insert(table, payload):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.post(url, headers=HEADERS, data=json.dumps(payload)); r.raise_for_status()
    return r.json()

def supa_update(table, key, key_val, payload):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{key}=eq.{key_val}"
    r = requests.patch(url, headers=HEADERS, data=json.dumps(payload)); r.raise_for_status()
    return r.json()

def supa_delete(table, key, key_val):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{key}=eq.{key_val}"
    r = requests.delete(url, headers=HEADERS); r.raise_for_status()
    return r.status_code

def format_cpf_cnpj(v):
    d = "".join(filter(str.isdigit, v))
    if len(d)==11: return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d)==14: return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return v

# --- Streamlit Setup ---
st.set_page_config(page_title="AgroContábil - LCDPR", layout="wide")
st.sidebar.title("🔍 Menu")
page = st.sidebar.radio("", ["Painel","Lançamentos","Cadastros","Relatórios"], key="menu_sel")

# --- 1) Painel ---
if page == "Painel":
    st.header("📊 Painel Financeiro")
    # Filtros de data com keys
    c1, c2 = st.columns([1,3])
    with c1:
        d1 = st.date_input("De", date.today().replace(day=1), key="dash_d1")
        d2 = st.date_input("Até", date.today(), key="dash_d2")
    # Busca dados
    dados = supa_get("lancamento","valor_entrada,valor_saida",
                     [f"data=gte.{d1}",f"data=lte.{d2}"])
    rec  = sum(x["valor_entrada"] for x in dados)
    desp = sum(x["valor_saida"]   for x in dados)
    saldo = rec - desp
    # Métricas
    m1, m2, m3 = st.columns(3)
    m1.metric("💰 Saldo Total", f"R$ {saldo:,.2f}", key="met_saldo")
    m2.metric("📈 Receitas"    , f"R$ {rec:,.2f}",   key="met_rec")
    m3.metric("📉 Despesas"    , f"R$ {desp:,.2f}",   key="met_desp")
    # Pizza animada
    fig = go.Figure(go.Pie(
        labels=["Receitas","Despesas"],
        values=[rec, desp],
        hole=0.4, textinfo="label+percent"
    ))
    fig.update_layout(
        transition={"duration":500, "easing":"cubic-in-out"}
    )
    st.plotly_chart(fig, use_container_width=True, key="dash_pie")
    # Alertas de estoque
    st.subheader("⚠️ Alertas de Estoque")
    hoje = date.today().isoformat()
    vencido = supa_get("estoque","produto,data_validade",[f"data_validade=lt.{hoje}"])
    prox30   = supa_get("estoque","produto,data_validade",
                        [f"data_validade=gte.{hoje}",
                         f"data_validade=lte.{(date.today()+timedelta(30)).isoformat()}"])
    for x in vencido: st.warning(f"Vencido: {x['produto']} em {x['data_validade']}", icon="⚠️")
    for x in prox30: st.info   (f"Vence em até 30d: {x['produto']} em {x['data_validade']}")
    # Últimas atividades
    st.subheader("🕒 Últimas Atividades")
    acts = supa_get("lancamento","data,historico,valor_entrada,valor_saida",
                    ["order=data.desc","limit=5"])
    tabela = [{
        "Data": a["data"],
        "Descrição": a["historico"],
        "Valor": f"R$ {a['valor_entrada']-a['valor_saida']:,.2f}"
    } for a in acts]
    st.table(tabela)

# --- 2) Lançamentos ---
elif page == "Lançamentos":
    st.header("📝 Lançamentos")
    # Filtros
    d1 = st.date_input("Data inicial", date.today().replace(day=1), key="lanc_fi")
    d2 = st.date_input("Data final"  , date.today(),             key="lanc_ff")
    # Mapas de ID → Nome
    imovs = supa_get("imovel_rural","id,nome_imovel"); mapa_i={i["id"]:i["nome_imovel"] for i in imovs}
    cts   = supa_get("conta_bancaria","id,nome_banco");    mapa_c={c["id"]:c["nome_banco"] for c in cts}
    # Fetch
    lans = supa_get("lancamento",
        "id,data,cod_imovel,cod_conta,historico,tipo_lanc,valor_entrada,valor_saida,saldo_final,natureza_saldo,categoria",
        [f"data=gte.{d1}",f"data=lte.{d2}","order=data.desc"]
    )
    df = pd.DataFrame(lans)
    if not df.empty:
        df["Imóvel"] = df["cod_imovel"].map(mapa_i)
        df["Conta"]  = df["cod_conta"].map(mapa_c)
        df["Tipo"]   = df["tipo_lanc"].map({1:"Receita",2:"Despesa",3:"Adiantamento"})
        df["Saldo"]  = df["natureza_saldo"].apply(lambda s:1 if s=="P" else -1)*df["saldo_final"]
        df = df.rename(columns={
            "data":"Data","historico":"Histórico",
            "valor_entrada":"Entrada","valor_saida":"Saída",
            "categoria":"Categoria"
        })
        df = df[["id","Data","Imóvel","Histórico","Tipo","Entrada","Saída","Saldo","Categoria"]]
        st.dataframe(df, use_container_width=True, key="df_lans")
    else:
        st.info("Nenhum lançamento encontrado.", icon="ℹ️")
    # Novo lançamento
    with st.expander("➕ Novo Lançamento", expanded=False):
        with st.form("form_lanc_new", clear_on_submit=True):
            dn  = st.date_input("Data", date.today(), key="new_d")
            imv = st.selectbox(
                "Imóvel", list(mapa_i.items()), 
                format_func=lambda x:x[1], key="new_imv"
            )[0]
            cta = st.selectbox(
                "Conta" , list(mapa_c.items()), 
                format_func=lambda x:x[1], key="new_cta"
            )[0]
            hist= st.text_input("Histórico", key="new_hist")
            tp  = st.selectbox("Tipo", ["Receita","Despesa","Adiantamento"], key="new_tp")
            ent = st.number_input("Entrada", min_value=0.0, format="%.2f", key="new_ent")
            sai = st.number_input("Saída"   , min_value=0.0, format="%.2f", key="new_sai")
            cat = st.text_input("Categoria", key="new_cat")
            ok  = st.form_submit_button("Salvar", use_container_width=True)
        if ok:
            supa_insert("lancamento",{
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
            st.success("Lançamento criado!", icon="✅")
            st.experimental_rerun()
    # Editar/Excluir
    if not df.empty:
        sel = st.selectbox("ID p/ Editar/Excluir", df["id"].tolist(), key="sel_lanc")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✏️ Editar Lançamento", key="btn_edit_lanc"):
                rec = df[df["id"]==sel].iloc[0]
                with st.form("form_lanc_edit", clear_on_submit=True):
                    de  = st.date_input("Data", datetime.fromisoformat(rec["Data"]).date(), key="edit_d")
                    imv = st.selectbox(
                        "Imóvel", list(mapa_i.items()),
                        index=list(mapa_i).index(rec["cod_imovel"]), format_func=lambda x:x[1], key="edit_imv"
                    )[0]
                    cta = st.selectbox(
                        "Conta", list(mapa_c.items()),
                        index=list(mapa_c).index(rec["cod_conta"]), format_func=lambda x:x[1], key="edit_cta"
                    )[0]
                    hist= st.text_input("Histórico", rec["Histórico"], key="edit_hist")
                    tp  = st.selectbox(
                        "Tipo", ["Receita","Despesa","Adiantamento"],
                        index=["Receita","Despesa","Adiantamento"].index(rec["Tipo"]), key="edit_tp"
                    )
                    ent = st.number_input("Entrada", value=float(rec["Entrada"]), format="%.2f", key="edit_ent")
                    sai = st.number_input("Saída"   , value=float(rec["Saída"])   , format="%.2f", key="edit_sai")
                    cat = st.text_input("Categoria", rec["Categoria"], key="edit_cat")
                    ok2 = st.form_submit_button("Atualizar", use_container_width=True)
                if ok2:
                    supa_update("lancamento","id",sel,{
                        "data": de.isoformat(),
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
                    st.success("Atualizado!", icon="✅")
                    st.experimental_rerun()
        with c2:
            if st.button("🗑️ Excluir Lançamento", key="btn_del_lanc"):
                supa_delete("lancamento","id",sel)
                st.success("Excluído!", icon="✅")
                st.experimental_rerun()

# --- 3) Cadastros ---
elif page == "Cadastros":
    st.header("📇 Cadastros")
    tabs = st.tabs(["Imóveis","Contas","Participantes","Culturas","Áreas","Estoque"])
    # Imóveis
    with tabs[0]:
        st.subheader("🏠 Imóveis Rurais")
        df_im = pd.DataFrame(supa_get("imovel_rural",
            "id,cod_imovel,nome_imovel,uf,area_total,area_utilizada,participacao"
        ))
        st.dataframe(df_im, use_container_width=True, key="tbl_im")
        with st.expander("➕ Novo Imóvel", expanded=False):
            with st.form("form_im_new", clear_on_submit=True):
                cod = st.text_input("Código", key="im_new_cod")
                nome= st.text_input("Nome"  , key="im_new_nome")
                end = st.text_input("Endereço", key="im_new_end")
                uf  = st.text_input("UF"    , key="im_new_uf")
                cm  = st.text_input("Cód. Mun", key="im_new_cm")
                cep = st.text_input("CEP"   , key="im_new_cep")
                te  = st.selectbox("Tipo Exploração", [1,2,3,4,5,6], key="im_new_te")
                part= st.number_input("Participação (%)", value=100.0, format="%.2f", key="im_new_part")
                at  = st.number_input("Área Total (ha)", format="%.2f", key="im_new_at")
                au  = st.number_input("Área Utilizada (ha)", format="%.2f", key="im_new_au")
                ok  = st.form_submit_button("Salvar", use_container_width=True)
            if ok:
                supa_insert("imovel_rural",{
                    "cod_imovel":cod,"nome_imovel":nome,
                    "endereco":end,"uf":uf,"cod_mun":cm,"cep":cep,
                    "tipo_exploracao":te,"participacao":part,
                    "area_total":at,"area_utilizada":au
                })
                st.success("Imóvel criado!", icon="✅")
                st.experimental_rerun()
        sel = st.selectbox("ID p/ Editar/Excluir", df_im["id"].tolist(), key="sel_im")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✏️ Editar Imóvel", key="btn_edit_im"):
                rec = df_im[df_im["id"]==sel].iloc[0]
                with st.form("form_im_edit", clear_on_submit=True):
                    cod = st.text_input("Código", rec["cod_imovel"], key="im_edit_cod")
                    nome= st.text_input("Nome", rec["nome_imovel"], key="im_edit_nome")
                    end = st.text_input("Endereço", rec["uf"], key="im_edit_end")
                    uf  = st.text_input("UF", rec["uf"], key="im_edit_uf")
                    cm  = st.text_input("Cód. Mun", rec["cod_mun"], key="im_edit_cm")
                    cep = st.text_input("CEP", rec["cep"], key="im_edit_cep")
                    te  = st.selectbox("Tipo Exploração", [1,2,3,4,5,6],
                                       index=int(rec["tipo_exploracao"])-1, key="im_edit_te")
                    part= st.number_input("Participação (%)",
                                         value=float(rec["participacao"]), format="%.2f", key="im_edit_part")
                    at  = st.number_input("Área Total (ha)",
                                         value=float(rec["area_total"] or 0), format="%.2f", key="im_edit_at")
                    au  = st.number_input("Área Utilizada (ha)",
                                         value=float(rec["area_utilizada"] or 0), format="%.2f", key="im_edit_au")
                    ok2 = st.form_submit_button("Atualizar", use_container_width=True)
                if ok2:
                    supa_update("imovel_rural","id",sel,{
                        "cod_imovel":cod,"nome_imovel":nome,
                        "endereco":end,"uf":uf,"cod_mun":cm,"cep":cep,
                        "tipo_exploracao":te,"participacao":part,
                        "area_total":at,"area_utilizada":au
                    })
                    st.success("Atualizado!", icon="✅")
                    st.experimental_rerun()
        with c2:
            if st.button("🗑️ Excluir Imóvel", key="btn_del_im"):
                supa_delete("imovel_rural","id",sel)
                st.success("Excluído!", icon="✅")
                st.experimental_rerun()

    # Contas
    with tabs[1]:
        st.subheader("🏦 Contas Bancárias")
        df_ct = pd.DataFrame(supa_get("conta_bancaria",
            "id,cod_conta,nome_banco,agencia,num_conta,saldo_inicial"
        ))
        st.dataframe(df_ct, use_container_width=True, key="tbl_ct")
        with st.expander("➕ Nova Conta", expanded=False):
            with st.form("form_ct_new", clear_on_submit=True):
                cod = st.text_input("Código", key="ct_new_cod")
                nb  = st.text_input("Banco", key="ct_new_nb")
                ag  = st.text_input("Agência", key="ct_new_ag")
                nc  = st.text_input("Número Conta", key="ct_new_nc")
                si  = st.number_input("Saldo Inicial", format="%.2f", key="ct_new_si")
                ok  = st.form_submit_button("Salvar", use_container_width=True)
            if ok:
                supa_insert("conta_bancaria",{
                    "cod_conta":cod,"nome_banco":nb,
                    "agencia":ag,"num_conta":nc,"saldo_inicial":si
                })
                st.success("Conta criada!", icon="✅")
                st.experimental_rerun()
        sel = st.selectbox("ID p/ Editar/Excluir", df_ct["id"].tolist(), key="sel_ct")
        c1,c2 = st.columns(2)
        with c1:
            if st.button("✏️ Editar Conta", key="btn_edit_ct"):
                rec = df_ct[df_ct["id"]==sel].iloc[0]
                with st.form("form_ct_edit", clear_on_submit=True):
                    cod = st.text_input("Código", rec["cod_conta"], key="ct_edit_cod")
                    nb  = st.text_input("Banco", rec["nome_banco"], key="ct_edit_nb")
                    ag  = st.text_input("Agência", rec["agencia"], key="ct_edit_ag")
                    nc  = st.text_input("Número Conta", rec["num_conta"], key="ct_edit_nc")
                    si  = st.number_input("Saldo Inicial", value=float(rec["saldo_inicial"]), format="%.2f", key="ct_edit_si")
                    ok2 = st.form_submit_button("Atualizar", use_container_width=True)
                if ok2:
                    supa_update("conta_bancaria","id",sel,{
                        "cod_conta":cod,"nome_banco":nb,
                        "agencia":ag,"num_conta":nc,"saldo_inicial":si
                    })
                    st.success("Atualizado!", icon="✅")
                    st.experimental_rerun()
        with c2:
            if st.button("🗑️ Excluir Conta", key="btn_del_ct"):
                supa_delete("conta_bancaria","id",sel)
                st.success("Excluído!", icon="✅")
                st.experimental_rerun()

    # Participantes
    with tabs[2]:
        st.subheader("👥 Participantes")
        df_pa = pd.DataFrame(supa_get("participante","id,cpf_cnpj,nome,tipo_contraparte,data_cadastro"))
        df_pa["CPF/CNPJ"] = df_pa["cpf_cnpj"].apply(format_cpf_cnpj)
        df_pa["Tipo"]     = df_pa["tipo_contraparte"].map({1:"PF",2:"PJ",3:"Órgão Público",4:"Outros"})
        st.dataframe(df_pa[["id","CPF/CNPJ","nome","Tipo","data_cadastro"]], use_container_width=True, key="tbl_pa")
        with st.expander("➕ Novo Participante", expanded=False):
            with st.form("form_pa_new", clear_on_submit=True):
                cpf = st.text_input("CPF/CNPJ", key="pa_new_cpf")
                no  = st.text_input("Nome"   , key="pa_new_nome")
                tp  = st.selectbox("Tipo", ["PF","PJ","Órgão Público","Outros"], key="pa_new_tp")
                ok  = st.form_submit_button("Salvar", use_container_width=True)
            if ok:
                supa_insert("participante",{
                    "cpf_cnpj": cpf, "nome": no,
                    "tipo_contraparte": ["PF","PJ","Órgão Público","Outros"].index(tp)+1
                })
                st.success("Participante criado!", icon="✅")
                st.experimental_rerun()
        sel = st.selectbox("ID p/ Editar/Excluir", df_pa["id"].tolist(), key="sel_pa")
        c1,c2 = st.columns(2)
        with c1:
            if st.button("✏️ Editar Participante", key="btn_edit_pa"):
                rec = df_pa[df_pa["id"]==sel].iloc[0]
                with st.form("form_pa_edit", clear_on_submit=True):
                    cpf = st.text_input("CPF/CNPJ", rec["cpf_cnpj"], key="pa_edit_cpf")
                    no  = st.text_input("Nome", rec["nome"], key="pa_edit_nome")
                    tp  = st.selectbox("Tipo", ["PF","PJ","Órgão Público","Outros"],
                                       index=["PF","PJ","Órgão Público","Outros"].index(rec["Tipo"]), key="pa_edit_tp")
                    ok2 = st.form_submit_button("Atualizar", use_container_width=True)
                if ok2:
                    supa_update("participante","id",sel,{
                        "cpf_cnpj": cpf, "nome": no,
                        "tipo_contraparte": ["PF","PJ","Órgão Público","Outros"].index(tp)+1
                    })
                    st.success("Atualizado!", icon="✅")
                    st.experimental_rerun()
        with c2:
            if st.button("🗑️ Excluir Participante", key="btn_del_pa"):
                supa_delete("participante","id",sel)
                st.success("Excluído!", icon="✅")
                st.experimental_rerun()

    # Culturas
    with tabs[3]:
        st.subheader("🌱 Culturas")
        df_cu = pd.DataFrame(supa_get("cultura","id,nome,tipo,ciclo,unidade_medida"))
        st.dataframe(df_cu, use_container_width=True, key="tbl_cu")
        with st.expander("➕ Nova Cultura", expanded=False):
            with st.form("form_cu_new", clear_on_submit=True):
                nm  = st.text_input("Nome", key="cu_new_nm")
                tp  = st.text_input("Tipo", key="cu_new_tp")
                ci  = st.text_input("Ciclo", key="cu_new_ci")
                um  = st.text_input("Unidade Medida", key="cu_new_um")
                ok  = st.form_submit_button("Salvar", use_container_width=True)
            if ok:
                supa_insert("cultura",{"nome":nm,"tipo":tp,"ciclo":ci,"unidade_medida":um})
                st.success("Cultura criada!", icon="✅")
                st.experimental_rerun()
        sel = st.selectbox("ID p/ Editar/Excluir", df_cu["id"].tolist(), key="sel_cu")
        c1,c2 = st.columns(2)
        with c1:
            if st.button("✏️ Editar Cultura", key="btn_edit_cu"):
                rec = df_cu[df_cu["id"]==sel].iloc[0]
                with st.form("form_cu_edit", clear_on_submit=True):
                    nm  = st.text_input("Nome", rec["nome"], key="cu_edit_nm")
                    tp  = st.text_input("Tipo", rec["tipo"], key="cu_edit_tp")
                    ci  = st.text_input("Ciclo", rec["ciclo"], key="cu_edit_ci")
                    um  = st.text_input("Unidade Medida", rec["unidade_medida"], key="cu_edit_um")
                    ok2 = st.form_submit_button("Atualizar", use_container_width=True)
                if ok2:
                    supa_update("cultura","id",sel,{"nome":nm,"tipo":tp,"ciclo":ci,"unidade_medida":um})
                    st.success("Atualizado!", icon="✅")
                    st.experimental_rerun()
        with c2:
            if st.button("🗑️ Excluir Cultura", key="btn_del_cu"):
                supa_delete("cultura","id",sel)
                st.success("Excluído!", icon="✅")
                st.experimental_rerun()

    # Áreas de Produção
    with tabs[4]:
        st.subheader("📐 Áreas de Produção")
        imovs = supa_get("imovel_rural","id,nome_imovel"); mapa_i={i["id"]:i["nome_imovel"] for i in imovs}
        cults = supa_get("cultura","id,nome");        mapa_c={c["id"]:c["nome"]       for c in cults}
        df_ar = pd.DataFrame(supa_get("area_producao",
            "id,imovel_id,cultura_id,area,data_plantio,data_colheita_estimada,produtividade_estimada"
        ))
        if not df_ar.empty:
            df_ar["Imóvel"]  = df_ar["imovel_id"].map(mapa_i)
            df_ar["Cultura"] = df_ar["cultura_id"].map(mapa_c)
            st.dataframe(df_ar[["id","Imóvel","Cultura","area","data_plantio","data_colheita_estimada","produtividade_estimada"]],
                         use_container_width=True, key="tbl_ar")
        with st.expander("➕ Nova Área", expanded=False):
            with st.form("form_ar_new", clear_on_submit=True):
                imv = st.selectbox("Imóvel", list(mapa_i.items()), format_func=lambda x:x[1], key="ar_new_imv")[0]
                cul = st.selectbox("Cultura", list(mapa_c.items()), format_func=lambda x:x[1], key="ar_new_cul")[0]
                ar  = st.number_input("Área (ha)", format="%.2f", key="ar_new_ar")
                dp  = st.date_input("Plantio", key="ar_new_dp")
                dc  = st.date_input("Colheita Est.", key="ar_new_dc")
                pe  = st.number_input("Prod. Est.", format="%.2f", key="ar_new_pe")
                ok  = st.form_submit_button("Salvar", use_container_width=True)
            if ok:
                supa_insert("area_producao",{
                    "imovel_id":imv,"cultura_id":cul,
                    "area":ar,"data_plantio":dp.isoformat(),
                    "data_colheita_estimada":dc.isoformat(),
                    "produtividade_estimada":pe
                })
                st.success("Área criada!", icon="✅")
                st.experimental_rerun()
        sel = st.selectbox("ID p/ Editar/Excluir", df_ar["id"].tolist(), key="sel_ar")
        c1,c2 = st.columns(2)
        with c1:
            if st.button("✏️ Editar Área", key="btn_edit_ar"):
                rec = df_ar[df_ar["id"]==sel].iloc[0]
                with st.form("form_ar_edit", clear_on_submit=True):
                    imv = st.selectbox("Imóvel", list(mapa_i.items()), index=list(mapa_i).index(rec["imovel_id"]),
                                       format_func=lambda x:x[1], key="ar_edit_imv")[0]
                    cul = st.selectbox("Cultura", list(mapa_c.items()), index=list(mapa_c).index(rec["cultura_id"]),
                                       format_func=lambda x:x[1], key="ar_edit_cul")[0]
                    ar  = st.number_input("Área (ha)", value=float(rec["area"]), format="%.2f", key="ar_edit_ar")
                    dp  = st.date_input("Plantio", datetime.fromisoformat(rec["data_plantio"]).date(), key="ar_edit_dp")
                    dc  = st.date_input("Colheita Est.", datetime.fromisoformat(rec["data_colheita_estimada"]).date(), key="ar_edit_dc")
                    pe  = st.number_input("Prod. Est.", value=float(rec["produtividade_estimada"] or 0), format="%.2f", key="ar_edit_pe")
                    ok2 = st.form_submit_button("Atualizar", use_container_width=True)
                if ok2:
                    supa_update("area_producao","id",sel,{
                        "imovel_id":imv,"cultura_id":cul,
                        "area":ar,"data_plantio":dp.isoformat(),
                        "data_colheita_estimada":dc.isoformat(),
                        "produtividade_estimada":pe
                    })
                    st.success("Atualizado!", icon="✅")
                    st.experimental_rerun()
        with c2:
            if st.button("🗑️ Excluir Área", key="btn_del_ar"):
                supa_delete("area_producao","id",sel)
                st.success("Excluído!", icon="✅")
                st.experimental_rerun()

    # Estoque
    with tabs[5]:
        st.subheader("📦 Estoque")
        imovs = supa_get("imovel_rural","id,nome_imovel"); mapa_i={i["id"]:i["nome_imovel"] for i in imovs}
        df_es = pd.DataFrame(supa_get("estoque",
            "id,produto,quantidade,unidade_medida,valor_unitario,local_armazenamento,data_entrada,data_validade,imovel_id"
        ))
        if not df_es.empty:
            df_es["Imóvel"] = df_es["imovel_id"].map(mapa_i)
            st.dataframe(df_es[["id","produto","quantidade","unidade_medida","valor_unitario","local_armazenamento","data_validade","Imóvel"]],
                         use_container_width=True, key="tbl_es")
        with st.expander("➕ Novo Estoque", expanded=False):
            with st.form("form_es_new", clear_on_submit=True):
                prod = st.text_input("Produto", key="es_new_prod")
                qt   = st.number_input("Quantidade", format="%.2f", key="es_new_qt")
                um   = st.text_input("Unidade Medida", key="es_new_um")
                vu   = st.number_input("Valor Unitário", format="%.2f", key="es_new_vu")
                la   = st.text_input("Local Armazenamento", key="es_new_la")
                de   = st.date_input("Data Entrada", date.today(), key="es_new_de")
                dv   = st.date_input("Data Validade", date.today(), key="es_new_dv")
                imv  = st.selectbox("Imóvel", list(mapa_i.items()), format_func=lambda x:x[1], key="es_new_imv")[0]
                ok   = st.form_submit_button("Salvar", use_container_width=True)
            if ok:
                supa_insert("estoque",{
                    "produto":prod,"quantidade":qt,"unidade_medida":um,
                    "valor_unitario":vu,"local_armazenamento":la,
                    "data_entrada":de.isoformat(),"data_validade":dv.isoformat(),
                    "imovel_id":imv
                })
                st.success("Estoque criado!", icon="✅")
                st.experimental_rerun()
        sel = st.selectbox("ID p/ Editar/Excluir", df_es["id"].tolist(), key="sel_es")
        c1,c2 = st.columns(2)
        with c1:
            if st.button("✏️ Editar Estoque", key="btn_edit_es"):
                rec = df_es[df_es["id"]==sel].iloc[0]
                with st.form("form_es_edit", clear_on_submit=True):
                    prod = st.text_input("Produto", rec["produto"], key="es_edit_prod")
                    qt   = st.number_input("Quantidade", value=float(rec["quantidade"]), format="%.2f", key="es_edit_qt")
                    um   = st.text_input("Unidade Medida", rec["unidade_medida"], key="es_edit_um")
                    vu   = st.number_input("Valor Unitário", value=float(rec["valor_unitario"]), format="%.2f", key="es_edit_vu")
                    la   = st.text_input("Local Armazenamento", rec["local_armazenamento"], key="es_edit_la")
                    de   = st.date_input("Data Entrada", datetime.fromisoformat(rec["data_entrada"]).date(), key="es_edit_de")
                    dv   = st.date_input("Data Validade", datetime.fromisoformat(rec["data_validade"]).date(), key="es_edit_dv")
                    imv  = st.selectbox("Imóvel", list(mapa_i.items()), 
                                       index=list(mapa_i).index(rec["imovel_id"]), format_func=lambda x:x[1], key="es_edit_imv")[0]
                    ok2  = st.form_submit_button("Atualizar", use_container_width=True)
                if ok2:
                    supa_update("estoque","id",sel,{
                        "produto":prod,"quantidade":qt,"unidade_medida":um,
                        "valor_unitario":vu,"local_armazenamento":la,
                        "data_entrada":de.isoformat(),"data_validade":dv.isoformat(),
                        "imovel_id":imv
                    })
                    st.success("Atualizado!", icon="✅")
                    st.experimental_rerun()
        with c2:
            if st.button("🗑️ Excluir Estoque", key="btn_del_es"):
                supa_delete("estoque","id",sel)
                st.success("Excluído!", icon="✅")
                st.experimental_rerun()

# --- 4) Relatórios ---
elif page == "Relatórios":
    st.header("📑 Relatórios")
    rpt = st.radio("Escolha relatório", ["Balancete","Razão"], key="rel_tp")
    d1  = st.date_input("Data inicial", date.today().replace(day=1), key="rel_d1")
    d2  = st.date_input("Data final",   date.today(),             key="rel_d2")
    if st.button("Gerar", key="btn_gerar_rel"):
        st.info(f"Gerando **{rpt}** de {d1} a {d2}... 🚧 Em desenvolvimento")
