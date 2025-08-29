import streamlit as st
import tempfile
import os
import pandas as pd
import fitz  # PyMuPDF
import easyocr
import re
from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime
from pdf2image import convert_from_path

# =========================
# Função para rodar OCR com EasyOCR
# =========================
def run_ocr_with_easyocr(pdf_path, output_text_path):
    """Extrai texto do PDF usando EasyOCR e salva em um txt auxiliar"""
    reader = easyocr.Reader(["pt", "en"])  # português + inglês
    images = convert_from_path(pdf_path)

    all_text = []
    for i, img in enumerate(images):
        result = reader.readtext(img)
        text_page = " ".join([res[1] for res in result])
        all_text.append(text_page)

    with open(output_text_path, "w", encoding="utf-8") as f:
        f.write("\n".join(all_text))
    return "\n".join(all_text)

# =========================
# Funções de Anonimização
# =========================
def redact_pdf(input_pdf_path, output_pdf_path, words_to_redact):
    """Apaga/mancha palavras e padrões do PDF"""
    doc = fitz.open(input_pdf_path)
    log = []

    for page_num, page in enumerate(doc):
        text_instances = []

        # Buscar palavras customizadas
        for word in words_to_redact:
            text_instances.extend(page.search_for(word))

        # Padrões comuns
        patterns = {
            r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b": "CPF",
            r"\b\d{2}\.\d{3}\.\d{3}-\d\b": "RG",
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}": "Email",
            r"\(?\d{2}\)?\s?\d{4,5}-\d{4}": "Telefone",
        }

        page_text = page.get_text()

        for pattern, label in patterns.items():
            for match in re.finditer(pattern, page_text):
                rects = page.search_for(match.group())
                for rect in rects:
                    text_instances.append(rect)
                log.append({"Page": page_num + 1, "Type": label, "Value": match.group()})

        # Aplicar tarja preta
        for inst in text_instances:
            page.add_redact_annot(inst, fill=(0, 0, 0))
        page.apply_redactions()

    doc.save(output_pdf_path)
    doc.close()
    return log

# =========================
# Interface Streamlit
# =========================
st.title("📄 Anonimizador de PDFs com OCR (Streamlit Cloud)")
st.write("Faça upload de PDFs. O app usa OCR (EasyOCR) e anonimiza CPF, RG, emails, telefones e palavras extras.")

uploaded_files = st.file_uploader("Selecione PDFs", type=["pdf"], accept_multiple_files=True)

extra_words = st.text_area("Palavras adicionais para anonimizar (separe por vírgula)").split(",")

if st.button("Processar PDFs") and uploaded_files:
    all_logs = []
    for uploaded_file in uploaded_files:
        st.info(f"📌 Processando {uploaded_file.name}...")

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, uploaded_file.name)
            uploaded_file.seek(0)
            with open(input_path, "wb") as f:
                f.write(uploaded_file.read())

            # OCR auxiliar
            ocr_txt_path = os.path.join(tmpdir, "ocr_" + uploaded_file.name + ".txt")
            try:
                extracted_text = run_ocr_with_easyocr(input_path, ocr_txt_path)
            except Exception as e:
                st.warning(f"⚠️ Erro no OCR para {uploaded_file.name}: {e}")
                continue

            # Anonimizar
            words_to_redact = [w.strip() for w in extra_words if w.strip()]
            anon_pdf_path = os.path.join(tmpdir, "anon_" + uploaded_file.name)
            log = redact_pdf(input_path, anon_pdf_path, words_to_redact)

            for item in log:
                item["File"] = uploaded_file.name
            all_logs.extend(log)

            # Download do PDF
            with open(anon_pdf_path, "rb") as f:
                st.download_button(
                    label=f"⬇️ Baixar PDF Anonimizado: {uploaded_file.name}",
                    data=f,
                    file_name="anon_" + uploaded_file.name,
                    mime="application/pdf"
                )

    # CSV de log
    if all_logs:
        df_log = pd.DataFrame(all_logs)
        csv_name = f"log_anonimizacao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        st.download_button(
            label="⬇️ Baixar CSV de Log",
            data=df_log.to_csv(index=False).encode("utf-8"),
            file_name=csv_name,
            mime="text/csv"
        )
