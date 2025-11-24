import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Rekening Koran Mandiri", layout="wide")
st.title("📄 Extractor Rekening Koran Mandiri – Stable Version")

uploaded = st.file_uploader("Upload PDF Rekening Mandiri", type=["pdf"])

# ============================================================
# Helper: clean number
# ============================================================
def to_float(text):
    if not text:
        return None
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except:
        return None

# ============================================================
# Helper: extract 3 numbers at end of transaction
# ============================================================
def extract_amounts(line):
    nums = re.findall(r"\d[\d.,]*", line)
    if len(nums) < 3:
        return None, None, None
    debit = to_float(nums[-3])
    credit = to_float(nums[-2])
    saldo = to_float(nums[-1])
    return debit, credit, saldo

# ============================================================
# Parser utama
# ============================================================
def parse_mandiri(pdf_bytes):

    rows = []
    current_tanggal = None
    current_jam = None
    current_remark = []
    current_ref = ""
    last_amount_line = ""

    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.splitlines():

                # Deteksi tanggal & jam
                m = re.match(r"(\d{2} \w{3} \d{4}),\s*(\d{2}:\d{2}:\d{2})", line)
                if m:
                    # Flush transaksi lama
                    if current_tanggal:
                        debit, credit, saldo = extract_amounts(last_amount_line)
                        rows.append([
                            current_tanggal,
                            current_jam,
                            " ".join(current_remark).strip(),
                            current_ref,
                            debit, credit, saldo
                        ])

                    # Reset block baru
                    current_tanggal = m.group(1)
                    current_jam = m.group(2)
                    current_remark = []
                    current_ref = ""
                    last_amount_line = ""
                    continue

                # Deteksi reference
                if re.search(r"\d{10,}", line):
                    current_ref = line.strip()

                # Jika line mengandung 3 angka → ini amount line
                debit, credit, saldo = extract_amounts(line)
                if (debit is not None and credit is not None and saldo is not None):
                    last_amount_line = line
                else:
                    # Remark multiline
                    if line.strip():
                        current_remark.append(line.strip())

    # Flush transaksi terakhir
    if current_tanggal:
        debit, credit, saldo = extract_amounts(last_amount_line)
        rows.append([
            current_tanggal,
            current_jam,
            " ".join(current_remark).strip(),
            current_ref,
            debit, credit, saldo
        ])

    df = pd.DataFrame(rows, columns=[
        "Tanggal", "Waktu", "Keterangan", "Reference", "Debit", "Kredit", "Saldo"
    ])
    return df

# ============================================================
# Eksekusi jika file diupload
# ============================================================
if uploaded:
    st.info("Membaca PDF...")
    file_data = uploaded.read()        # BACA SEKALI SAJA
    pdf_bytes = BytesIO(file_data)

    try:
        df = parse_mandiri(pdf_bytes)
        st.success("Berhasil membaca data rekening Mandiri!")
        st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Error saat membaca PDF: {e}")
