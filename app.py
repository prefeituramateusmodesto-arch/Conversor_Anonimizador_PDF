import streamlit as st
import tempfile
import subprocess
import fitz  # PyMuPDF
import re
import csv
import os

# Função para rodar OCR no PDF
def rodar_ocr(input_path, output_path):
    try:
        result = subprocess.run(
            ["ocrmypdf", "--skip-text", "-l", "por", input_path, output_path],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            st.error(f"Erro ao rodar OCR em {input_path}: {result.stderr}")
            return False
        return True
    except Exception as e:
        st.error(f"Erro inesperado ao rodar OCR: {e}")
        return False

# Função para anonimizar PDF (com tarja preta)
def anonimizar_pdf(input_path, output_path, termos, csv_path):
    doc = fitz.open(input_path)
    achados = []

    for page_num, page in enumerate(doc, start=1):
        text_instances = []
        for termo in termos:
            termo_regex = re.compile(re.escape(termo), re.IGNORECASE)
            for match in page.search_for(termo):
                text_instances.append((termo, match))

        for termo, inst in text_instances:
            # Aplica tarja preta
            page.add_redact_annot(inst, fill=(0, 0, 0))
            achados.append({"pagina": page_num, "termo": termo})

        page.apply_redactions()

    doc.save(output_path)

    # Salvar CSV com os termos achados
    if achados:
        with open(csv_path, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=["pagina", "termo"])
            writer.writeheader()
            writer.writerows(achados)

# ------------------------------
# Interface Streamlit
# ------------------------------
st.title("📑 OCR + Anonimização de PDFs")

uploaded_files = st.file_uploader("Selecione arquivos PDF", type=["pdf"], accept_multiple_files=True)

termos_input = st.text_area("Digite os termos a anonimizar (separados por vírgula)", "CPF, RG, CNPJ, Processo")
termos = [t.strip() for t in termos_input.split(",") if t.strip()]

if uploaded_files and termos:
    for uploaded_file in uploaded_files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_in:
            tmp_in.write(uploaded_file.read())
            input_path = tmp_in.name

        ocr_path = tempfile.NamedTemporaryFile(delete=False, suffix="_ocr.pdf").name
        anon_path = tempfile.NamedTemporaryFile(delete=False, suffix="_anon.pdf").name
        csv_path = tempfile.NamedTemporaryFile(delete=False, suffix=".csv").name

        # Passo 1: OCR
        if rodar_ocr(input_path, ocr_path):
            # Passo 2: Anonimização
            anonimizar_pdf(ocr_path, anon_path, termos, csv_path)

            st.success(f"Processado: {uploaded_file.name}")

            with open(anon_path, "rb") as f:
                st.download_button(
                    label=f"⬇️ Baixar PDF anonimizado ({uploaded_file.name})",
                    data=f,
                    file_name=f"{os.path.splitext(uploaded_file.name)[0]}_anon.pdf",
                    mime="application/pdf"
                )

            with open(csv_path, "rb") as f:
                st.download_button(
                    label=f"⬇️ Baixar CSV ({uploaded_file.name})",
                    data=f,
                    file_name=f"{os.path.splitext(uploaded_file.name)[0]}_achados.csv",
                    mime="text/csv"
                )
