import streamlit as st
import requests
import json
from datetime import date, datetime, timedelta
import pandas as pd
import plotly.graph_objects as go

# =====================================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================================
st.set_page_config(
    page_title="AgroContábil • LCDPR",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================================
# CLIENTE SUPABASE (REST)
# =====================================================================
class SupaClient:
    def __init__(self, url, anon_key):
        self.base = f"{url}/rest/v1"
        self.headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Content-Type": "application/json"
        }

    @st.cache_data(ttl=300)
    def get(self, table, select="*", filters=None):
        q = f"{self.base}/{table}?select={select}"
        if filters:
            q += "&" + "&".join(filters)
        r = requests.get(q, headers=self.headers)
        r.raise_for_status()
        return r.json()

    def insert(self, table, payload):
        r = requests.post(f"{self.base}/{table}", headers=self.headers, json=payload)
        r.raise_for_status()

    def update(self, table, key, key_val, payload):
        q = f"{self.base}/{table}?{key}=eq.{key_val}"
        r = requests.patch(q, headers=self.headers, json=payload)
        r.raise_for_status()

    def delete(self, table, key, key_val):
        q = f"{self.base}/{table}?{key}=eq.{key_val}"
        r = requests.delete(q, headers=self.headers)
        r.raise_for_status()

# inicializa o cliente Supabase
supa = SupaClient(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

# =====================================================================
# UTILITÁRIOS
# =====================================================================
def format_cpf_cnpj(raw: str) -> str:
    d = "".join(filter(str.isdigit, raw))
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return raw

def reload():
    try:
        st.experimental_rerun()
    except:
        st.stop()

# =====================================================================
# COMPONENTE: PAINEL FINANCEIRO
# =====================================================================
def painel_financeiro():
    st.markdown("## 📊 Painel Financeiro")
    with st.expander("🔎 Filtros"):
        col1, col2 = st.columns(2)
        with col1:
            de = st.date_input("Data de", date.today().replace(day=1), key="f_de")
        with col2:
            ate = st.date_input("Data até", date.today(), key="f_ate")

    lançs = supa.get(
        "lancamento",
        "valor_entrada,valor_saida",
        [f"data=gte.{de}", f"data=lte.{ate}"]
    )
    total_in = sum(x["valor_entrada"] for x in lançs)
    total_out= sum(x["valor_saida"]   for x in lançs)
    saldo     = total_in - total_out

    m1, m2, m3 = st.columns(3)
    m1.metric("💰 Saldo",    f"R$ {saldo:,.2f}")
    m2.metric("📈 Entradas", f"R$ {total_in:,.2f}")
    m3.metric("📉 Saídas",   f"R$ {total_out:,.2f}")

    fig = go.Figure(
        go.Pie(
            labels=["Entradas", "Saídas"],
            values=[total_in, total_out],
            hole=0.4,
            textinfo="label+percent"
        )
    )
    fig.update_layout(margin=dict(t=0,b=0))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### ⚠️ Vencimento de Estoque")
    hoje = date.today().isoformat()
    venc  = supa.get("estoque", "produto,data_validade", [f"data_validade=lt.{hoje}"])
    prox  = supa.get(
        "estoque", "produto,data_validade",
        [f"data_validade=gte.{hoje}", f"data_validade=lte.{(date.today()+timedelta(30)).isoformat()}"]
    )
    for x in venc:
        st.warning(f"{x['produto']} — vencido em {x['data_validade']}")
    for x in prox:
        st.info(f"{x['produto']} — vence até {x['data_validade']}")

    st.markdown("### 🕒 Últimas Operações")
    recent = supa.get("lancamento", "data,historico,valor_entrada,valor_saida", ["order=data.desc","limit=5"])
    df_r = pd.DataFrame([
        {"Data":r["data"], "Descrição":r["historico"], "Valor":f"R$ {r['valor_entrada']-r['valor_saida']:,.2f}"}
        for r in recent
    ])
    st.table(df_r)

# =====================================================================
# COMPONENTE: LANÇAMENTOS
# =====================================================================
def pagina_lancamentos():
    st.markdown("## 📝 Lançamentos")
    de, ate = st.columns(2)
    with de:
        d1 = st.date_input("De", date.today().replace(day=1), key="l1")
    with ate:
        d2 = st.date_input("Até", date.today(),               key="l2")

    imovs = supa.get("imovel_rural","id,nome_imovel"); mapa_im = {i["id"]:i["nome_imovel"] for i in imovs}
    ctas  = supa.get("conta_bancaria","id,nome_banco");  mapa_ct = {c["id"]:c["nome_banco"] for c in ctas}

    data = supa.get(
        "lancamento",
        "id,data,cod_imovel,cod_conta,historico,tipo_lanc,valor_entrada,valor_saida,saldo_final,natureza_saldo,categoria",
        [f"data=gte.{d1}", f"data=lte.{d2}", "order=data.desc"]
    )
    df = pd.DataFrame(data)
    if df.empty:
        st.info("Nenhum lançamento encontrado.")
    else:
        df["Imóvel"] = df["cod_imovel"].map(mapa_im)
        df["Conta"]  = df["cod_conta"].map(mapa_ct)
        df["Tipo"]   = df["tipo_lanc"].map({1:"Receita",2:"Despesa",3:"Adiantamento"})
        df["Saldo"]  = df.apply(lambda r:(1 if r["natureza_saldo"]=="P" else -1)*r["saldo_final"], axis=1)
        df = df.rename(columns={
            "data":"Data","historico":"Histórico",
            "valor_entrada":"Entrada","valor_saida":"Saída","categoria":"Categoria"
        })
        st.dataframe(df[["id","Data","Imóvel","Histórico","Tipo","Entrada","Saída","Saldo","Categoria"]],
                     use_container_width=True)

    st.markdown("### ➕ Novo Lançamento")
    with st.form("form_new_lanc", clear_on_submit=True):
        dn   = st.date_input("Data", date.today())
        imv  = st.selectbox("Imóvel", list(mapa_im.keys()), format_func=lambda x: mapa_im[x])
        cta  = st.selectbox("Conta",  list(mapa_ct.keys()), format_func=lambda x: mapa_ct[x])
        hist = st.text_input("Histórico")
        tp   = st.selectbox("Tipo", ["Receita","Despesa","Adiantamento"])
        ent  = st.number_input("Entrada", min_value=0.0, format="%.2f")
        sai  = st.number_input("Saída",   min_value=0.0, format="%.2f")
        cat  = st.text_input("Categoria")
        btn  = st.form_submit_button("Salvar")
    if btn:
        supa.insert("lancamento", {
            "data":dn.isoformat(),
            "cod_imovel":imv,
            "cod_conta":cta,
            "historico":hist,
            "tipo_lanc":["Receita","Despesa","Adiantamento"].index(tp)+1,
            "valor_entrada":ent,
            "valor_saida":sai,
            "saldo_final":abs(ent-sai),
            "natureza_saldo":"P" if ent>=sai else "N",
            "categoria":cat
        })
        st.success("Lançamento salvo!")
        reload()

    if not df.empty:
        sel_id = st.selectbox("Selecione ID para editar/excluir", df["id"].tolist())
        e, d = st.columns(2)
        with e:
            if st.button("✏️ Editar"):
                rec = df[df["id"]==sel_id].iloc[0]
                with st.form("form_edit_lanc", clear_on_submit=True):
                    de = st.date_input("Data", datetime.fromisoformat(rec["Data"]).date())
                    imve = st.selectbox("Imóvel", list(mapa_im.keys()), index=list(mapa_im).index(rec["cod_imovel"]), format_func=lambda x: mapa_im[x])
                    cte  = st.selectbox("Conta",  list(mapa_ct.keys()), index=list(mapa_ct).index(rec["cod_conta"]), format_func=lambda x: mapa_ct[x])
                    his  = st.text_input("Histórico", rec["Histórico"])
                    tpe  = st.selectbox("Tipo", ["Receita","Despesa","Adiantamento"], index=["Receita","Despesa","Adiantamento"].index(rec["Tipo"]))
                    ente = st.number_input("Entrada", value=rec["Entrada"], format="%.2f")
                    saie = st.number_input("Saída",   value=rec["Saída"],   format="%.2f")
                    cate = st.text_input("Categoria", rec["Categoria"])
                    ok2  = st.form_submit_button("Atualizar")
                if ok2:
                    supa.update("lancamento","id",sel_id,{
                        "data":de.isoformat(),
                        "cod_imovel":imve,
                        "cod_conta":cte,
                        "historico":his,
                        "tipo_lanc":["Receita","Despesa","Adiantamento"].index(tpe)+1,
                        "valor_entrada":ente,
                        "valor_saida":saie,
                        "saldo_final":abs(ente-saie),
                        "natureza_saldo":"P" if ente>=saie else "N",
                        "categoria":cate
                    })
                    st.success("Atualizado!")
                    reload()
        with d:
            if st.button("🗑️ Excluir"):
                supa.delete("lancamento","id",sel_id)
                st.success("Excluído!")
                reload()

# =====================================================================
# GANCHO DE ROTEAMENTO
# =====================================================================
st.sidebar.title("Menu")
secoes = ["Painel","Lançamentos"]
escolha = st.sidebar.radio("", secoes)

if escolha == "Painel":
    painel_financeiro()
else:
    pagina_lancamentos()
