import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Mandiri", layout="wide")
st.title("📄 Extractor Rekening Koran Mandiri – FIX Version")

uploaded = st.file_uploader("Upload PDF", type=["pdf"])

# =====================================================
# Convert angka
# =====================================================
def to_float(x):
    if not x: 
        return None
    x = x.replace(".", "").replace(",", ".")
    try:
        return float(x)
    except:
        return None

# =====================================================
# Ambil 3 angka terakhir (debit, kredit, saldo)
# =====================================================
def extract_amounts(line):
    nums = re.findall(r"-?\d[\d.,]*", line)
    if len(nums) < 3:
        return None, None, None
    return to_float(nums[-3]), to_float(nums[-2]), to_float(nums[-1])

# =====================================================
# PARSER FIX TOTAL
# =====================================================
def parse_pdf(pdf_bytes):

    rows = []
    tgl = None
    jam = None
    remark = []
    ref = ""
    last_amount_line = ""

    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:
            lines = page.extract_text().splitlines()

            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # ------------------------
                # 1) DETEKSI TANGGAL
                # ------------------------
                m = re.match(r"(\d{2} \w{3} \d{4}),?", line)
                if m:
                    # Jika transaksi lama ada → flush
                    if tgl:
                        debit, credit, saldo = extract_amounts(last_amount_line)
                        rows.append([tgl, jam, " ".join(remark), ref, debit, credit, saldo])

                    # Ambil tanggal
                    tgl = m.group(1)
                    remark = []
                    ref = ""
                    last_amount_line = ""

                    # Ambil jam di BARIS SELANJUTNYA
                    if i + 1 < len(lines):
                        jam_line = lines[i+1].strip()
                        if re.match(r"\d{2}:\d{2}:\d{2}", jam_line):
                            jam = jam_line
                            i += 2
                            continue

                # ------------------------
                # 2) DETEKSI REFERENCE
                # ------------------------
                if re.fullmatch(r"\d{10,}", line):
                    ref = line

                # ------------------------
                # 3) DETEKSI AKHIR TRANSAKSI
                # ------------------------
                debit, credit, saldo = extract_amounts(line)
                if debit is not None and credit is not None and saldo is not None:
                    last_amount_line = line
                else:
                    if line:
                        remark.append(line)

                i += 1

    # Flush transaksi terakhir
    if tgl:
        debit, credit, saldo = extract_amounts(last_amount_line)
        rows.append([tgl, jam, " ".join(remark), ref, debit, credit, saldo])

    df = pd.DataFrame(rows, columns=[
        "Tanggal","Waktu","Keterangan","Reference","Debit","Kredit","Saldo"
    ])

    return df


# =====================================================
# EXEC — JIKA FILE DIUPLOAD
# =====================================================
if uploaded:
    st.info("Membaca PDF...")

    file_data = uploaded.read()  # BACA SEKALI
    pdf_bytes = BytesIO(file_data)

    try:
        df = parse_pdf(pdf_bytes)
        st.success("Berhasil membaca data Mandiri!")
        st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
