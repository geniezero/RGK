"""Registre des pages : rempli par app.py, utilisé pour les liens entre écrans (st.switch_page, st.page_link)."""
PAGES = {}  # url_path -> st.Page


def page(url_path):
    return PAGES.get(url_path)
