import streamlit as st
import tempfile
import os
import pandas as pd
import fitz  # PyMuPDF
import pytesseract
import ocrmypdf
import re
from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime

# =========================
# Funções de Anonimização
# =========================
def redact_pdf(input_pdf_path, output_pdf_path, words_to_redact):
    """Apaga/mancha palavras e padrões do PDF"""
    doc = fitz.open(input_pdf_path)
    log = []
    for page_num, page in enumerate(doc):
        text_instances = []
        for word in words_to_redact:
            text_instances.extend(page.search_for(word))
        # Padrões comuns
        patterns = {
            r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b": "CPF",
            r"\b\d{2}\.\d{3}\.\d{3}-\d\b": "RG",
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}": "Email",
            r"\(?\d{2}\)?\s?\d{4,5}-\d{4}": "Telefone",
        }
        for pattern, label in patterns.items():
            for match in re.finditer(pattern, page.get_text()):
                text_instances.append(page.search_for(match.group()))
                log.append({"Page": page_num+1, "Type": label, "Value": match.group()})

        for inst in text_instances:
            page.add_redact_annot(inst, fill=(0, 0, 0))
        page.apply_redactions()

    doc.save(output_pdf_path)
    doc.close()
    return log

# =========================
# Streamlit Interface
# =========================
st.title("Anonimizador de PDFs com OCR")
st.write("Faça upload de PDFs, o app vai aplicar OCR e anonimizar CPF, RG, emails, telefones e palavras que você definir.")

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

            ocr_path = os.path.join(tmpdir, "ocr_" + uploaded_file.name)

            # Rodar OCR
            try:
                ocrmypdf.ocr(
                    input_path,
                    ocr_path,
                    language="por",
                    force_ocr=True,
                    redo_ocr=True
                )
            except Exception as e:
                st.warning(f"Erro ao rodar OCR em {uploaded_file.name}: {e}")
                continue

            # Anonimizar
            words_to_redact = [w.strip() for w in extra_words if w.strip()]
            log = redact_pdf(ocr_path, os.path.join(tmpdir, "anon_" + uploaded_file.name), words_to_redact)
            for item in log:
                item["File"] = uploaded_file.name
            all_logs.extend(log)

            # Botão para download do PDF anonimizador
            with open(os.path.join(tmpdir, "anon_" + uploaded_file.name), "rb") as f:
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
# Configuração para Render
# =========================
if __name__ == "__main__":
    import sys
    import streamlit.web.cli as stcli

    # Pega a porta do Render ou usa 8501 localmente
    port = int(os.environ.get("PORT", 8501))

    # Configura os argumentos do Streamlit
    sys.argv = [
        "streamlit",
        "run",
        "app.py",
        "--server.port", str(port),
        "--server.address", "0.0.0.0"
    ]

    stcli.main()
