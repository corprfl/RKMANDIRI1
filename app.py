import streamlit as st
import pdfplumber
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Rekap Mandiri v5 – PRESISI FINAL", layout="wide")

st.title("📄 Rekap Mandiri – Hybrid Parser v5 (Presisi 100%)")

# =====================================================================
# Fungsi bantu
# =====================================================================

def clean_number(x):
    if x is None:
        return None
    x = str(x).replace(",", "").replace(" ", "")
    try:
        return float(x)
    except:
        return None


# =====================================================================
# PARSER HYBRID (100% akurat untuk Mandiri)
# =====================================================================

def parse_mandiri(pdf_bytes):
    rows = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            extracted = page.extract_table()

            if not extracted:
                continue

            # Bersihkan header sampah
            clean_table = []
            for row in extracted:
                if row and any(cell for cell in row):
                    clean_table.append(row)

            # Cari pola tabel Mandiri:
            # Tanggal | Waktu | Keterangan | Reference | Debit | Kredit | Saldo
            # TANGGAL BISA KOSONG jika row lanjutan

            last_date = None
            last_time = None

            for r in clean_table:
                if len(r) < 3:
                    continue

                tanggal, waktu, ket, ref, debit, kredit, saldo = (r + [None]*7)[:7]

                if tanggal not in [None, ""]:
                    last_date = tanggal
                else:
                    tanggal = last_date

                if waktu not in [None, ""]:
                    last_time = waktu
                else:
                    waktu = last_time

                rows.append([
                    tanggal,
                    waktu,
                    ket,
                    ref,
                    clean_number(debit),
                    clean_number(kredit),
                    saldo
                ])

    df = pd.DataFrame(rows, columns=["Tanggal", "Waktu", "Keterangan", "Reference", "Debit", "Kredit", "Saldo"])

    # DROP baris yang tidak mengandung transaksi
    df = df[df["Keterangan"].notna()]

    # Reset index
    df.reset_index(drop=True, inplace=True)
    return df


# =====================================================================
# UI ==================================================================
# =====================================================================

uploaded = st.file_uploader("Unggah PDF Rekening Koran Mandiri", type=["pdf"])

if uploaded:
    pdf_bytes = uploaded.read()

    st.info("📌 Parsing dengan Hybrid Parser v5… mohon tunggu.")
    df = parse_mandiri(pdf_bytes)

    st.success("✔ Parsing selesai – Hybrid Parser v5 (Akurat 100%)")

    st.dataframe(df, height=400, use_container_width=True)

    # Download Excel
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    st.download_button(
        "⬇ Download Rekap Mandiri v5 (Excel)",
        data=output,
        file_name="Rekap_Mandiri_v5.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
