import streamlit as st
import pandas as pd
import numpy as np
import folium
from folium.plugins import Fullscreen, DualMap
import plotly.express as px
import pathlib
import math
from pathlib impor Path

from streamlit_folium import st_folium


# Configuração da página
st.set_page_config(
    page_title="Mapeamento Eleitoral SJDR - UFSJ",
    page_icon="📊",
    layout="wide"
)

# Título e Introdução
st.title("📊 Mapeamento Eleitoral e Visualização Geoespacial (SJDR)")
st.markdown("""
Dashboard desenvolvido para a disciplina de **Tecnologias para Data Science** (DCOMP/UFSJ) — Prof.ª Carolina Ribeiro Xavier.    
**Autores:** Nathan Mateus de Lima e Vítor Oliveira Amorim  
""")

# Barra Lateral (Sidebar) - Controles e Filtros
st.sidebar.header("⚙️ Configurações e Filtros")
nome_usuario = st.sidebar.text_input("Seu Nome:", "Estudante DCOMP")
st.sidebar.write(f"Bem-vindo(a), **{nome_usuario}**!")


CORES_PARTIDOS = {
    13: "#ff0000",  # Lula
    14: "#f0d01a",  # Renan Santos
    16: "#780f07",  # Hertz Dias
    21: "#fc4521",  # Edmilson Costa
    22: "#0c7a0a",  # Flavio Bolsonaro
    27: "#80d7ff",  # Clariana Barão
    28: "#0a1e57",  # Leonardo Avalanche
    29: "#9c2308",  # Rui Costa Pimenta
    30: "#e66909",  # Zema
    35: "#187031",  # Veterinário Wilson Grassi
    55: "#0306a6",  # Ronaldo Caiado
    70: "#077375",  # Escritor Augusto Cury
    80: "#000000",  # Samara Martins
    95: "#cfcfcf",  # Branco
    96: "#a3a3a3",  # Nulo
}

def get_candidate_color(party: int) -> str:
    return CORES_PARTIDOS.get(party, "#ff00dd")


@st.cache_data
def carregar_dados():
    base_dir = pathlib.Path(__file__).parent
    data_path = base_dir / 'data' / 'votacao_sjdr.csv'
    df = pd.read_csv(data_path, sep=',')
    
    # Tratamento de coordenadas
    for col in ['NR_LATITUDE', 'NR_LONGITUDE']:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.strip().str.replace(',', '.')
        ).round(4)
        
    return df

def processar_turno(df_turno: pd.DataFrame):
    # Nome do local por coordenada
    nm_local_principal = (
        df_turno.groupby(['NR_LATITUDE', 'NR_LONGITUDE', 'NM_LOCAL_VOTACAO'], as_index=False)['QT_VOTOS']
        .sum()
        .sort_values(by='QT_VOTOS', ascending=False)
        .drop_duplicates(subset=['NR_LATITUDE', 'NR_LONGITUDE'])
        [['NR_LATITUDE', 'NR_LONGITUDE', 'NM_LOCAL_VOTACAO']]
    )

    # Agrupamento por local e candidato
    df_locais = (
        df_turno.groupby(['NR_LATITUDE', 'NR_LONGITUDE', 'NM_VOTAVEL', 'NR_VOTAVEL'], as_index=False)['QT_VOTOS']
        .sum()
        .merge(nm_local_principal, on=['NR_LATITUDE', 'NR_LONGITUDE'], how='left')
        .sort_values(by=['NM_LOCAL_VOTACAO', 'QT_VOTOS'], ascending=[True, False])
    )

    total_votos_local = df_locais.groupby(['NR_LATITUDE', 'NR_LONGITUDE'])['QT_VOTOS'].transform('sum')
    df_locais['PCT_VOTOS_LOCAL'] = ((df_locais['QT_VOTOS'] / total_votos_local) * 100.0).round(2)

    votos_invalidos = ['Branco', 'Nulo']
    votos_validos = df_locais['QT_VOTOS'].where(~df_locais['NM_VOTAVEL'].isin(votos_invalidos), 0)
    total_votos_validos = votos_validos.groupby([df_locais['NR_LATITUDE'], df_locais['NR_LONGITUDE']]).transform('sum')
    df_locais['PCT_VOTOS_VALIDOS_LOCAL'] = ((votos_validos / total_votos_validos) * 100.0).round(2)

    mais_votado = df_locais.groupby(['NR_LATITUDE', 'NR_LONGITUDE'])['QT_VOTOS'].transform('max')
    df_locais['MAIS_VOTADO_LOCAL'] = (df_locais['QT_VOTOS'] == mais_votado)

    # Dominância local
    p10 = df_locais.groupby('NR_VOTAVEL')['PCT_VOTOS_LOCAL'].transform(lambda x: x.quantile(0.10))
    p90 = df_locais.groupby('NR_VOTAVEL')['PCT_VOTOS_LOCAL'].transform(lambda x: x.quantile(0.90))
    denom = (p90 - p10).replace(0, np.nan)
    df_locais['DOMINANCIA_LOCAL'] = (((df_locais['PCT_VOTOS_LOCAL'] - p10) / denom).fillna(0.5).clip(0, 1)).round(2)

    # Seções por coordenada
    secoes_por_coord = (
        df_turno.groupby(['NR_LATITUDE', 'NR_LONGITUDE'])['NR_SECAO']
        .apply(lambda s: ", ".join(map(str, sorted(s.unique()))))
        .to_dict()
    )

    # Agrupamento por Bairro
    df_bairros = (
        df_turno.groupby(['NM_BAIRRO', 'NM_VOTAVEL', 'NR_VOTAVEL'], as_index=False)['QT_VOTOS']
        .sum()
        .sort_values(by=['NM_BAIRRO', 'QT_VOTOS'], ascending=[True, False])
    )
    total_bairro = df_bairros.groupby('NM_BAIRRO')['QT_VOTOS'].transform('sum')
    df_bairros['PCT_VOTOS_BAIRRO'] = ((df_bairros['QT_VOTOS'] / total_bairro) * 100.0).round(2)

    return df_locais, df_bairros, secoes_por_coord

df_raw = carregar_dados()

st.sidebar.header("⚙️ Filtros da Análise")

turno_selecionado = st.sidebar.radio(
    "Selecione o Turno:",
    options=[1, 2],
    format_func=lambda x: f"{x}º Turno"
)

df_turno = df_raw[df_raw["NR_TURNO"] == turno_selecionado]
df_locais, df_bairros, secoes_dict = processar_turno(df_turno)

# Filtro de Bairros
bairros_disponiveis = sorted(df_turno['NM_BAIRRO'].dropna().unique())
bairros_selecionados = st.sidebar.multiselect(
    "Filtrar por Bairro(s):",
    options=bairros_disponiveis,
    default=bairros_disponiveis
)

# Filtro de Candidatos p/ o Mapa
candidatos_disponiveis = sorted(df_locais['NM_VOTAVEL'].unique())
default_cands = [c for c in ["LULA", "FLAVIO BOLSONARO"] if c in candidatos_disponiveis]
candidatos_selecionados = st.sidebar.multiselect(
    "Candidatos / Opções no Mapa:",
    options=candidatos_disponiveis,
    default=default_cands if default_cands else candidatos_disponiveis[:2]
)

df_turno_filtrado = df_turno[df_turno['NM_BAIRRO'].isin(bairros_selecionados)]
df_bairros_filtrado = df_bairros[df_bairros['NM_BAIRRO'].isin(bairros_selecionados)]

coords_validas = set(zip(df_turno_filtrado['NR_LATITUDE'], df_turno_filtrado['NR_LONGITUDE']))
df_locais_filtrado = df_locais[
    df_locais.apply(lambda r: (r['NR_LATITUDE'], r['NR_LONGITUDE']) in coords_validas, axis=1)
]



total_votos = int(df_turno_filtrado['QT_VOTOS'].sum())
qtd_locais = len(coords_validas)
qtd_secoes = df_turno_filtrado['NR_SECAO'].nunique()

# Candidato líder no recorte
lider_df = (
    df_turno_filtrado[~df_turno_filtrado['NM_VOTAVEL'].isin(['Branco', 'Nulo'])]
    .groupby('NM_VOTAVEL')['QT_VOTOS'].sum()
    .sort_values(ascending=False)
)
lider_nome = lider_df.index[0].title() if not lider_df.empty else "N/A"
lider_votos = int(lider_df.iloc[0]) if not lider_df.empty else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total de Votos (Recorte)", f"{total_votos:,}".replace(",", "."))
col2.metric("Locais de Votação", qtd_locais)
col3.metric("Seções Eleitorais", qtd_secoes)
col4.metric("Líder no Recorte", lider_nome, f"{lider_votos:,} votos".replace(",", "."))

st.divider()



def construir_mapa_folium(df_loc: pd.DataFrame, candidatos_filtro: list, secoes_map: dict):
    sjdr_lat_lon = [-21.1365, -44.2619]
    mapa = folium.Map(
        location=sjdr_lat_lon,
        zoom_start=14,
        tiles='https://tile.openstreetmap.de/{z}/{x}/{y}.png',
        attr='© OpenStreetMap contributors',
        control_scale=True,
        max_bounds=True,
        min_lat=sjdr_lat_lon[0] - 1.0,
        max_lat=sjdr_lat_lon[0] + 1.0,
        min_lon=sjdr_lat_lon[1] - 1.0,
        max_lon=sjdr_lat_lon[1] + 1.0,
    )

    Fullscreen(
        position="topright",
        force_separate_button=True,
        title="Entrar no Modo Tela Cheia",
        title_cancel="Sair do Modo Tela Cheia",
    ).add_to(mapa)

    estilo_tooltip = """
        background-color: #ffffff;
        color: #000000;
        font-family: 'Helvetica Neue', Arial, sans-serif;
        font-size: 13px;
        border-radius: 6px;
        border: 1px solid #444444;
        padding: 8px 12px;
        box-shadow: 3px 3px 10px rgba(0, 0, 0, 0.4);
    """

    camadas = {
        cand: folium.FeatureGroup(name=cand.title(), show=(i == 0))
        for i, cand in enumerate(candidatos_filtro)
    }

    df_plot = df_loc[df_loc['NM_VOTAVEL'].isin(candidatos_filtro)]

    for row in df_plot.itertuples(index=False):
        lat, lon = row.NR_LATITUDE, row.NR_LONGITUDE
        cand_raw = row.NM_VOTAVEL
        candidato = str(cand_raw).title()
        camada = camadas[cand_raw]

        color = get_candidate_color(row.NR_VOTAVEL)
        vencedor = row.MAIS_VOTADO_LOCAL
        secoes_str = secoes_map.get((lat, lon), "N/A")

        titulo_popup = (
            f'<h4 style="color: {color}; margin:0;"><b>{candidato} <span style="color: #fca503;">(Vencedor)</span></b></h4>'
            if vencedor else
            f'<h4 style="color: {color}; margin:0;"><b>{candidato}</b></h4>'
        )

        html_popup = (
            f"{titulo_popup}<hr style='margin: 5px 0;'>"
            f"<b>Local:</b> {row.NM_LOCAL_VOTACAO}<br>"
            f"<b>Votos:</b> {row.QT_VOTOS} ({row.PCT_VOTOS_LOCAL}%)<br>"
            f"<b>Votos Válidos:</b> {row.PCT_VOTOS_VALIDOS_LOCAL}%<br>"
            f"<b>Seções:</b> {secoes_str}"
        )

        geojson_point = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"local": row.NM_LOCAL_VOTACAO}
            }]
        }

        marker = folium.Circle(
            radius=math.sqrt(row.QT_VOTOS) * 5,
            color=color if not vencedor else '#fca503',
            fill=True,
            fill_color=color,
            fill_opacity=min(max(0.15, row.DOMINANCIA_LOCAL), 0.80)
        )

        folium.GeoJson(
            geojson_point,
            marker=marker,
            popup=folium.Popup(html_popup, max_width=350),
            tooltip=folium.GeoJsonTooltip(
                fields=['local'],
                aliases=['Local:'],
                style=estilo_tooltip,
                sticky=True
            )
        ).add_to(camada)

    for camada in camadas.values():
        camada.add_to(mapa)

    folium.LayerControl(collapsed=False).add_to(mapa)
    return mapa



tab_mapa, tab_graficos, tab_dados = st.tabs([
    "🗺️ Mapa Geoespacial (Folium)",
    "📊 Análise por Bairro e Candidato",
    "📋 Dados Detalhados e Exportação"
])

with tab_mapa:
    st.subheader(f"Distribuição Espacial de Votos — {turno_selecionado}º Turno")
    st.caption("O tamanho do círculo reflete o volume de votos, a opacidade indica a dominância relativa do candidato na cidade e a borda dourada destaca o vencedor no local.")
    
    if not candidatos_selecionados:
        st.warning("Selecione ao menos um candidato na barra lateral para visualizar no mapa.")
    else:
        mapa_folium = construir_mapa_folium(df_locais_filtrado, candidatos_selecionados, secoes_dict)
        st_folium(mapa_folium, width=None, height=620, returned_objects=[])

with tab_graficos:
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.subheader("Total de Votos por Candidato")
        df_cand_total = (
            df_turno_filtrado.groupby(['NM_VOTAVEL', 'NR_VOTAVEL'], as_index=False)['QT_VOTOS']
            .sum()
            .sort_values(by='QT_VOTOS', ascending=True)
        )
        fig_bar = px.bar(
            df_cand_total,
            x="QT_VOTOS",
            y="NM_VOTAVEL",
            orientation="h",
            text="QT_VOTOS",
            color="NM_VOTAVEL",
            color_discrete_map={
                row.NM_VOTAVEL: get_candidate_color(row.NR_VOTAVEL)
                for row in df_cand_total.itertuples()
            },
            labels={"QT_VOTOS": "Quantidade de Votos", "NM_VOTAVEL": "Candidato / Opção"}
        )
        fig_bar.update_layout(showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_g2:
        st.subheader("Proporção de Votos por Bairro")
        df_bairros_plot = df_bairros_filtrado[df_bairros_filtrado['NM_VOTAVEL'].isin(candidatos_selecionados)]
        fig_bairro = px.bar(
            df_bairros_plot,
            x="NM_BAIRRO",
            y="PCT_VOTOS_BAIRRO",
            color="NM_VOTAVEL",
            barmode="group",
            color_discrete_map={
                row.NM_VOTAVEL: get_candidate_color(row.NR_VOTAVEL)
                for row in df_bairros_plot.itertuples()
            },
            labels={"NM_BAIRRO": "Bairro", "PCT_VOTOS_BAIRRO": "% de Votos no Bairro", "NM_VOTAVEL": "Candidato"}
        )
        st.plotly_chart(fig_bairro, use_container_width=True)

with tab_dados:
    st.subheader("Resultados Consolidados por Local de Votação")
    st.dataframe(df_locais_filtrado, use_container_width=True)
    
    csv = df_locais_filtrado.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Baixar Tabela Filtrada (CSV)",
        data=csv,
        file_name=f"votacao_sjdr_{turno_selecionado}T_filtrada.csv",
        mime="text/csv"
    )
