import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Rekening Mandiri", layout="wide")
st.title("📄 Extractor Rekening Koran Mandiri – FINAL VERSION (CorpRFL x Zavibis)")

uploaded = st.file_uploader("Upload PDF Rekening Mandiri", type=["pdf"])

# =====================================================
# Helper: convert angka
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
# Regex definisi
# =====================================================
r_tanggal = re.compile(r"^(?P<tanggal>\d{2} \w{3} \d{4}),?$")
r_jam     = re.compile(r"^(?P<jam>\d{2}:\d{2}:\d{2})$")
r_ref     = re.compile(r"^(?P<ref>\d{10,})$")
r_amount  = re.compile(r".*?(-?\d[\d.,]*)\s+(-?\d[\d.,]*)\s+(-?\d[\d.,]*)$")

# =====================================================
# Extract 3 angka terakhir
# =====================================================
def extract_amounts(line):
    m = r_amount.match(line)
    if not m:
        return None, None, None
    debit  = to_float(m.group(1))
    credit = to_float(m.group(2))
    saldo  = to_float(m.group(3))
    return debit, credit, saldo

# =====================================================
# PARSER UTAMA – sesuai format PDF Mandiri
# =====================================================
def parse_mandiri(pdf_bytes):
    rows = []

    tgl = None
    jam = None
    remark = []
    ref = ""
    amount_line = ""

    with pdfplumber.open(pdf_bytes) as pdf:

        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.splitlines()
            i = 0

            while i < len(lines):
                line = lines[i].strip()

                # -----------------------------------
                # 1) DETEKSI TANGGAL
                # -----------------------------------
                m = r_tanggal.match(line)
                if m:
                    # flush transaksi sebelumnya
                    if tgl:
                        debit, credit, saldo = extract_amounts(amount_line)
                        rows.append([
                            tgl,
                            jam,
                            " ".join(remark),
                            ref,
                            debit, credit, saldo
                        ])

                    tgl = m.group("tanggal")
                    remark = []
                    ref = ""
                    amount_line = ""

                    # Ambil jam dari baris berikutnya
                    if i + 1 < len(lines):
                        line_jam = lines[i+1].strip()
                        m2 = r_jam.match(line_jam)
                        if m2:
                            jam = m2.group("jam")
                            i += 2
                            continue

                # -----------------------------------
                # 2) DETEKSI REFERENCE NUMBER
                # -----------------------------------
                m = r_ref.match(line)
                if m:
                    ref = m.group("ref")

                # -----------------------------------
                # 3) DETEKSI AMOUNT
                # -----------------------------------
                debit, credit, saldo = extract_amounts(line)
                if debit is not None and credit is not None and saldo is not None:
                    amount_line = line
                else:
                    if line.strip():
                        remark.append(line.strip())

                i += 1

    # -----------------------------------
    # Flush transaksi terakhir
    # -----------------------------------
    if tgl:
        debit, credit, saldo = extract_amounts(amount_line)
        rows.append([
            tgl,
            jam,
            " ".join(remark),
            ref,
            debit, credit, saldo
        ])

    df = pd.DataFrame(rows, columns=[
        "Tanggal", "Waktu", "Keterangan", "Reference",
        "Debit", "Kredit", "Saldo"
    ])

    return df

# =====================================================
# Excel generator
# =====================================================
def to_excel(df):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Rekap", index=False)
    buffer.seek(0)
    return buffer

# =====================================================
# ACTION — Jika file diupload
# =====================================================
if uploaded:
    st.info("📥 Membaca PDF...")
    file_data = uploaded.read()  # baca sekali
    pdf_bytes = BytesIO(file_data)

    try:
        df = parse_mandiri(pdf_bytes)

        st.success("✅ Berhasil membaca data rekening Mandiri!")
        st.dataframe(df, use_container_width=True)

        # tombol download
        excel_file = to_excel(df)
        st.download_button(
            label="⬇️ Download Excel",
            data=excel_file,
            file_name="Rekap-Rekening-Mandiri.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ Error parsing: {e}")
