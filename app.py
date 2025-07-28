import os
import streamlit as st
from datetime import date
from supabase import create_client, Client
import plotly.graph_objects as go

# — inicializa Supabase —
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_ANON_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# — configuração do Streamlit —
st.set_page_config(page_title="AgroContábil", layout="wide")
st.sidebar.title("Menu")
page = st.sidebar.radio("", ["Painel", "Lançamentos", "Cadastros"])

# — Painel principal —
if page == "Painel":
    st.header("📊 Painel Financeiro")
    col1, col2, col3, col4 = st.columns([1,1,1,2])
    start = st.date_input("De", date.today().replace(day=1))
    end   = st.date_input("Até", date.today())

    # busca lançamentos no período
    data = supabase.table("lancamento") \
        .select("valor_entrada,valor_saida") \
        .gte("data", start.isoformat()) \
        .lte("data", end.isoformat()) \
        .execute().data

    rec  = sum(item["valor_entrada"] for item in data)
    desp = sum(item["valor_saida"]   for item in data)
    saldo = rec - desp

    col1.metric("Saldo Total", f"R$ {saldo:,.2f}")
    col2.metric("Receitas"    , f"R$ {rec: , .2f}")
    col3.metric("Despesas"    , f"R$ {desp: , .2f}")

    # pizza com porcentagem
    fig = go.Figure(go.Pie(
        labels=["Receitas","Despesas"],
        values=[rec, desp],
        hole=.3,
        textinfo="label+percent"
    ))
    col4.plotly_chart(fig, use_container_width=True)

# — CRUD de lançamentos —
elif page == "Lançamentos":
    st.header("📝 Lançamentos")
    df = supabase.table("lancamento") \
        .select("*") \
        .order("data", desc=True) \
        .execute().data
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
            supabase.table("lancamento").insert({
                "data": data_l.isoformat(),
                "cod_imovel": int(imovel),
                "cod_conta": int(conta),
                "historico": hist,
                "tipo_lanc": 1 if tipo=="Receita" else 2,
                "valor_entrada": ent,
                "valor_saida": sai,
                "saldo_final": ent - sai,
                "natureza_saldo": "P" if ent - sai >= 0 else "N",
                "categoria": cat
            }).execute()
            st.success("Lançamento criado!")
            st.experimental_rerun()

# — CRUD de cadastros —
elif page == "Cadastros":
    st.header("📇 Cadastros")
    tab = st.sidebar.selectbox("Escolha tabela", ["Imóveis","Contas","Participantes"])
    if tab == "Imóveis":
        rows = supabase.table("imovel_rural").select("*").execute().data
    elif tab == "Contas":
        rows = supabase.table("conta_bancaria").select("*").execute().data
    else:
        rows = supabase.table("participante").select("*").execute().data
    st.dataframe(rows, use_container_width=True)
