import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(layout="wide", page_title="Extractor Mandiri - CorpRFL")

# =====================
# Styling
# =====================
st.markdown("""
<style>
body { background-color:#0d1117 !important; color:white !important; }
.stButton>button { background:#0070C0 !important; color:white !important; border-radius:8px; padding:8px 16px; }
</style>
<h2>📘 Extractor Rekening Koran Mandiri</h2>
<p>By Reza Fahlevi Lubis BKP @zavibis</p>
""", unsafe_allow_html=True)

# =====================
# Helper: Format angka ke INDONESIA
# =====================
def normalize_number(raw):
    """
    Convert Mandiri number format:
    '266,000,296.00' → 266000296.00 (float)
    """
    if raw is None:
        return 0.0
    raw = raw.strip()
    if raw == "" or raw == "-":
        return 0.0
    # Hapus pemisah ribuan
    raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except:
        return 0.0

def format_indonesia(num):
    """
    Output final:
    - No thousand separator
    - Decimal comma
    Example:
    266000296.0 → '266000296,00'
    """
    return f"{num:,.2f}".replace(",", "_").replace(".", ",").replace("_", "")

# =====================
# Upload section
# =====================
uploaded = st.file_uploader("Upload PDF Mandiri", type=["pdf"])
if not uploaded:
    st.stop()

# =====================
# AUTOPARSE LEVEL-4
# =====================
rows = []
nomor_rekening = ""
currency = "IDR"
saldo_awal = None

with pdfplumber.open(uploaded) as pdf:
    for page in pdf.pages:
        text = page.extract_text() or ""

        # Detect account number di header
        m = re.search(r"\b(\d{10,16})\b", text)
        if m:
            nomor_rekening = m.group(1)

        # Split lines
        lines = text.splitlines()
        buffer_ket = []

        for ln in lines:
            # Cari 3 angka terakhir (Debit - Kredit - Saldo)
            angka = re.findall(r"\d[\d.,]*", ln)

            if len(angka) >= 3:
                # Ambil 3 angka terakhir
                debit_raw = angka[-3]
                kredit_raw = angka[-2]
                saldo_raw = angka[-1]

                debit = normalize_number(debit_raw)
                kredit = normalize_number(kredit_raw)
                saldo = normalize_number(saldo_raw)

                if saldo_awal is None:
                    saldo_awal = saldo

                # Extract tanggal
                tgl = re.findall(r"(\d{2} \w{3} \d{4})", ln)
                tanggal = ""
                if tgl:
                    # Convert 03 Oct 2025 → 03/10/2025
                    import datetime
                    try:
                        tanggal = datetime.datetime.strptime(tgl[0], "%d %b %Y").strftime("%d/%m/%Y")
                    except:
                        tanggal = ""

                # Gabungkan remark yang stacked sebelumnya
                remark = " ".join(buffer_ket).strip()
                remark = re.sub(r"\s+", " ", remark)  # pastikan 1 baris

                rows.append([
                    nomor_rekening,
                    tanggal,
                    remark,
                    format_indonesia(debit),
                    format_indonesia(kredit),
                    format_indonesia(saldo),
                    currency,
                    format_indonesia(saldo_awal)
                ])

                buffer_ket = []  # reset remark block
            else:
                # Kumpulkan remark
                buffer_ket.append(ln)

# =====================
# DataFrame
# =====================
df = pd.DataFrame(rows, columns=[
    "Nomor Rekening", "Tanggal", "Keterangan",
    "Debit", "Kredit", "Saldo", "Currency", "Saldo Awal"
])

st.dataframe(df, use_container_width=True)

# =====================
# DOWNLOAD FIX (BytesIO)
# =====================
buffer = BytesIO()
df.to_excel(buffer, index=False, engine='openpyxl')
buffer.seek(0)

st.download_button(
    "Download Excel",
    data=buffer,
    file_name="mandiri_extracted.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
