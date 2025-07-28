import runpy

# Executa seu Streamlit app que está em streamlit_app.py
runpy.run_path("streamlit_app.py", run_name="__main__")

import os
import json
import streamlit as st
from datetime import date
import requests
import plotly.graph_objects as go

# — credenciais via Streamlit Secrets —
SUPABASE_URL      = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

# — cabeçalhos para REST —
headers = {
    "apikey":        SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type":  "application/json"
}

def fetch_lancamentos(start: date, end: date):
    """Retorna lista de dicts com valor_entrada e valor_saida."""
    url = (
        f"{SUPABASE_URL}/rest/v1/lancamento"
        f"?select=valor_entrada,valor_saida"
        f"&data=gte.{start.isoformat()}"
        f"&data=lte.{end.isoformat()}"
    )
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

def insert_lancamento(payload: dict):
    """Insere um lançamento novo."""
    url = f"{SUPABASE_URL}/rest/v1/lancamento"
    r = requests.post(url, headers=headers, data=json.dumps(payload))
    r.raise_for_status()
    return r.json()

# — Streamlit App —
st.set_page_config(page_title="AgroContábil", layout="wide")
st.sidebar.title("Menu")
page = st.sidebar.radio("", ["Painel", "Lançamentos", "Cadastros"])

if page == "Painel":
    st.header("📊 Painel Financeiro")
    col1, col2, col3, col4 = st.columns([1,1,1,2])
    start = st.date_input("De", date.today().replace(day=1))
    end   = st.date_input("Até", date.today())

    data = fetch_lancamentos(start, end)
    rec  = sum(item["valor_entrada"] for item in data)
    desp = sum(item["valor_saida"]   for item in data)
    saldo = rec - desp

    col1.metric("Saldo Total", f"R$ {saldo:,.2f}")
    col2.metric("Receitas"    , f"R$ {rec:,.2f}")
    col3.metric("Despesas"    , f"R$ {desp:,.2f}")

    fig = go.Figure(go.Pie(
        labels=["Receitas","Despesas"],
        values=[rec, desp],
        hole=.3,
        textinfo="label+percent"
    ))
    col4.plotly_chart(fig, use_container_width=True)

elif page == "Lançamentos":
    st.header("📝 Lançamentos")
    # busca tudo (poderia por paginação/filtro também)
    url_all = f"{SUPABASE_URL}/rest/v1/lancamento?select=*"
    df = requests.get(url_all, headers=headers).json()
    st.dataframe(df, use_container_width=True)

    with st.expander("➕ Novo Lançamento"):
        form = st.form("novo")
        data_l = form.date_input("Data", date.today())
        imovel = form.text_input("Imóvel (ID)")
        conta  = form.text_input("Conta (ID)")
        hist   = form.text_input("Histórico")
        tipo   = form.selectbox("Tipo", ["Receita","Despesa"])
        ent    = form.number_input("Entrada", min_value=0.0, format="%.2f")
        sai    = form.number_input("Saída"   , min_value=0.0, format="%.2f")
        cat    = form.text_input("Categoria")
        ok     = form.form_submit_button("Salvar")
        if ok:
            payload = {
                "data": data_l.isoformat(),
                "cod_imovel": int(imovel),
                "cod_conta":  int(conta),
                "historico":  hist,
                "tipo_lanc":  1 if tipo=="Receita" else 2,
                "valor_entrada": ent,
                "valor_saida":   sai,
                "saldo_final":   ent - sai,
                "natureza_saldo": "P" if ent - sai >= 0 else "N",
                "categoria":      cat
            }
            insert_lancamento(payload)
            st.success("Lançamento criado!")
            st.experimental_rerun()

elif page == "Cadastros":
    st.header("📇 Cadastros")
    tab = st.sidebar.selectbox("Tabela", ["Imóveis","Contas","Participantes"])
    endpoint = {
      "Imóveis":       "imovel_rural",
      "Contas":        "conta_bancaria",
      "Participantes": "participante"
    }[tab]
    data = requests.get(f"{SUPABASE_URL}/rest/v1/{endpoint}?select=*",
                        headers=headers).json()
    st.dataframe(data, use_container_width=True)
