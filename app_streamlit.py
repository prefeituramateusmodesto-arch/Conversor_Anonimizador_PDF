import streamlit as st
import tempfile
import os
import pandas as pd
import fitz  # PyMuPDF
import re
from datetime import datetime
from pdf2image import convert_from_path
import easyocr
import io

# =========================
# Função de OCR com EasyOCR
# =========================
def ocr_pdf_with_easyocr(input_pdf_path):
    """Converte PDF em imagens e aplica OCR com EasyOCR (português)."""
    reader = easyocr.Reader(['pt'])
    text_pages = []
    images = convert_from_path(input_pdf_path)

    for img in images:
        # Converte a imagem para OCR
        result = reader.readtext(np.array(img))
        page_text = " ".join([res[1] for res in result])
        text_pages.append(page_text)

    return text_pages

# =========================
# Função de Anonimização
# =========================
def redact_pdf(input_pdf_path, output_pdf_path, words_to_redact, text_pages):
    """Apaga/mancha palavras e padrões do PDF"""
    doc = fitz.open(input_pdf_path)
    log = []

    for page_num, page in enumerate(doc):
        text_instances = []

        # Palavras extras definidas pelo usuário
        for word in words_to_redact:
            text_instances.extend(page.search_for(word))

        # Padrões comuns
        patterns = {
            r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b": "CPF",
            r"\b\d{2}\.\d{3}\.\d{3}-\d\b": "RG",
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}": "Email",
            r"\(?\d{2}\)?\s?\d{4,5}-\d{4}": "Telefone",
        }

        # Buscar padrões com base no OCR
        for pattern, label in patterns.items():
            matches = re.finditer(pattern, text_pages[page_num])
            for match in matches:
                areas = page.search_for(match.group())
                for area in areas:
                    page.add_redact_annot(area, fill=(0, 0, 0))
                log.append({"Page": page_num+1, "Type": label, "Value": match.group()})

        # Aplicar redactions
        page.apply_redactions()

    doc.save(output_pdf_path)
    doc.close()
    return log

# =========================
# Streamlit Interface
# =========================
st.title("Anonimizador de PDFs com EasyOCR (Português)")
st.write("Faça upload de PDFs. O app vai aplicar OCR (EasyOCR) e anonimizar CPF, RG, emails, telefones e palavras que você definir.")

uploaded_files = st.file_uploader("Selecione PDFs", type=["pdf"], accept_multiple_files=True)

extra_words = st.text_area("Palavras adicionais para anonimizar (separe por vírgula)").split(",")

if st.button("Processar PDFs") and uploaded_files:
    all_logs = []
    for uploaded_file in uploaded_files:
        st.info(f"Processando {uploaded_file.name}...")

        # Criar arquivos temporários
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, uploaded_file.name)
            uploaded_file.seek(0)
            with open(input_path, "wb") as f:
                f.write(uploaded_file.read())

            # Rodar OCR com EasyOCR
            try:
                text_pages = ocr_pdf_with_easyocr(input_path)
            except Exception as e:
                st.warning(f"Erro ao rodar OCR em {uploaded_file.name}: {e}")
                continue

            # Anonimizar
            words_to_redact = [w.strip() for w in extra_words if w.strip()]
            anon_path = os.path.join(tmpdir, "anon_" + uploaded_file.name)
            log = redact_pdf(input_path, anon_path, words_to_redact, text_pages)
            for item in log:
                item["File"] = uploaded_file.name
            all_logs.extend(log)

            # Botão para download do PDF anonimizado
            with open(anon_path, "rb") as f:
                st.download_button(
                    label=f"Download PDF Anonimizado: {uploaded_file.name}",
                    data=f,
                    file_name="anon_" + uploaded_file.name,
                    mime="application/pdf"
                )

    # Gerar CSV de log
    if all_logs:
        df_log = pd.DataFrame(all_logs)
        csv_name = f"log_anonimizacao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        st.download_button(
            label="Download CSV de Log",
            data=df_log.to_csv(index=False).encode("utf-8"),
            file_name=csv_name,
            mime="text/csv"
        )

# =========================
# Ajuste para Render
# =========================
if __name__ == "__main__":
    import sys
    import streamlit.web.cli as stcli

    port = int(os.environ.get("PORT", 8501))
    sys.argv = [
        "streamlit",
        "run",
        "app.py",
        "--server.port", str(port),
        "--server.address", "0.0.0.0"
    ]
    stcli.main()
