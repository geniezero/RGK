"""Thème visuel commun : styles, en-tête de page, cartes."""
from html import escape
from pathlib import Path

import streamlit as st

STATIC = Path(__file__).with_name("static")
LOGO = STATIC / "logo.svg"
ICONE = STATIC / "icone.svg"

# palette
TEAL = "#0F6B5C"
TEAL_FONCE = "#0E2F29"
MENTHE = "#7FD1B9"
ENCRE = "#16201C"
GRIS = "#55625C"
BORD = "#DCE6E2"
FOND = "#F2F5F3"
ORANGE = "#C2702E"
ROUGE = "#9C1C14"

CSS = """
<style>
/* ---------- page */
.block-container {padding-top: 3rem; padding-bottom: 3rem; max-width: 1480px;}
h1 {font-size: 1.85rem !important; font-weight: 700 !important; letter-spacing: -.01em;}
h2, h3 {letter-spacing: -.005em;}
h4 {font-size: 1.12rem !important;}
[data-testid="stCaptionContainer"] {color: #5E6B65;}

/* ---------- en-tête de page */
.ia-head {display: flex; align-items: center; gap: 14px; margin: 0 0 .35rem 0;}
.ia-head .ico {width: 46px; height: 46px; border-radius: 12px; background: linear-gradient(135deg, #DDEFE8, #C6E6DA);
               display: flex; align-items: center; justify-content: center; font-size: 1.45rem; flex: none;
               box-shadow: inset 0 0 0 1px rgba(15,107,92,.12);}
.ia-head .sec {font-size: .72rem; font-weight: 700; letter-spacing: .09em; text-transform: uppercase; color: #0F6B5C; margin-bottom: 1px;}
.ia-head h1 {margin: 0 !important; padding: 0 !important; line-height: 1.15;}
.ia-sub {color: #5E6B65; font-size: .95rem; margin: .1rem 0 1.1rem 0;}

/* ---------- indicateurs */
[data-testid="stMetric"] {background: #FFFFFF; border: 1px solid #DCE6E2; border-top: 3px solid #0F6B5C;
                          padding: 12px 16px 10px; border-radius: 10px; box-shadow: 0 1px 2px rgba(14,47,41,.05);}
[data-testid="stMetricLabel"] {color: #55625C;}
[data-testid="stMetricValue"] {font-size: 1.55rem; font-weight: 700;}

/* ---------- onglets */
[data-baseweb="tab-list"] {gap: 6px; border-bottom: 1px solid #DCE6E2;}
button[data-baseweb="tab"] {padding: 8px 14px !important;}
button[data-baseweb="tab"] p {font-size: .98rem; font-weight: 600;}
button[data-baseweb="tab"][aria-selected="true"] p {color: #0F6B5C;}

/* ---------- conteneurs, tableaux, expanders */
[data-testid="stVerticalBlockBorderWrapper"] {border-radius: 12px;}
[data-testid="stExpander"] details {border-radius: 10px;}
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {border-radius: 10px;}
hr {margin: 1.1rem 0 !important;}

/* ---------- boutons */
.stButton button, .stDownloadButton button, .stLinkButton a {font-weight: 600;}
.stButton button[kind="primary"], .stDownloadButton button[kind="primary"] {box-shadow: 0 1px 2px rgba(15,107,92,.25);}

/* ---------- barre latérale */
[data-testid="stSidebar"] [data-testid="stSidebarNavSeparator"] {border-color: #2A5C51;}
[data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"] {color: #7FD1B9 !important; font-size: .72rem; font-weight: 700;
                                                                letter-spacing: .09em; text-transform: uppercase; margin-top: .6rem;}
[data-testid="stSidebarNavLink"] {border-radius: 8px; margin: 1px 0;}
[data-testid="stSidebarNavLink"][aria-current="page"] {background: rgba(127,209,185,.16);}
[data-testid="stSidebarNavLink"][aria-current="page"] span {color: #FFFFFF; font-weight: 700;}
.ia-side {border-top: 1px solid #2A5C51; margin-top: .4rem; padding-top: .8rem; font-size: .82rem; color: #A9C4BC;}
.ia-side b {color: #E4EFEB;}
.ia-side .tag {display: inline-block; background: #174A40; color: #7FD1B9; border-radius: 10px; padding: 1px 9px; font-weight: 700;
               font-size: .75rem; margin-top: 4px;}

/* ---------- cartes de l'accueil */
.ia-card {border: 1px solid #DCE6E2; border-radius: 12px; padding: 14px 16px 8px; background: #FFFFFF; min-height: 172px;
          box-shadow: 0 1px 2px rgba(14,47,41,.04);}
.ia-card .t {display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.02rem;}
.ia-card .t span {width: 34px; height: 34px; border-radius: 9px; background: #EAF4F0; display: flex; align-items: center; justify-content: center;}
.ia-card .d {color: #5E6B65; font-size: .87rem; margin: 8px 0 2px;}
.ia-card .n {font-size: .82rem; color: #0F6B5C; font-weight: 600;}
.ia-todo {display: flex; gap: 10px; align-items: flex-start; padding: 4px 0; font-size: .92rem;}
.ia-todo b.i {width: 26px; height: 26px; border-radius: 7px; display: flex; align-items: center; justify-content: center; flex: none;
              color: #fff; font-size: .8rem;}
.ia-hero {background: linear-gradient(120deg, #0E2F29 0%, #0F6B5C 100%); color: #E4EFEB; border-radius: 16px; padding: 22px 26px;
          margin-bottom: 1.1rem;}
.ia-hero h1 {color: #FFFFFF !important; margin: 0 0 4px 0 !important; padding: 0 !important;}
.ia-hero p {margin: 0; color: #CFE5DE; font-size: .98rem;}
.ia-hero .chips {margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap;}
.ia-hero .chips span {background: rgba(255,255,255,.12); border-radius: 12px; padding: 3px 11px; font-size: .82rem;}
</style>
"""


def appliquer():
    """À appeler une fois par exécution, avant d'afficher la page."""
    st.markdown(CSS, unsafe_allow_html=True)
    if LOGO.exists():
        st.logo(str(LOGO), size="large", icon_image=str(ICONE))


def entete(titre, sous_titre=None, icone=None, section=None, conteneur=None):
    """En-tête de page harmonisé : pictogramme, section de navigation, titre, sous-titre."""
    c = conteneur or st
    ico = f"<div class='ico'>{icone}</div>" if icone else ""
    sec = f"<div class='sec'>{escape(section)}</div>" if section else ""
    c.markdown(f"<div class='ia-head'>{ico}<div>{sec}<h1>{escape(titre)}</h1></div></div>", unsafe_allow_html=True)
    if sous_titre:
        c.markdown(f"<div class='ia-sub'>{sous_titre}</div>", unsafe_allow_html=True)


def carte(icone, titre, description, note=""):
    """Carte d'accès rapide (accueil) ; le lien est ajouté en dessous avec st.page_link."""
    st.markdown(f"<div class='ia-card'><div class='t'><span>{icone}</span>{escape(titre)}</div>"
                f"<div class='d'>{description}</div><div class='n'>{note}</div></div>", unsafe_allow_html=True)


def a_faire(icone, couleur, texte):
    return f"<div class='ia-todo'><b class='i' style='background:{couleur}'>{icone}</b><div>{texte}</div></div>"
