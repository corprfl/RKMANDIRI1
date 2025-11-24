import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO
import datetime


st.set_page_config(page_title="Extractor Mandiri - CorpRFL", layout="wide")

# ============================ UI THEME ===============================
st.markdown("""
<style>
body { background-color:#0d1117 !important; color:white !important; }
.stButton>button { background:#0070C0 !important; color:white !important; border-radius:8px; padding:8px 16px; }
</style>
<h2>📘 Extractor Rekening Koran Mandiri – CorpRFL</h2>
<p>By Reza Fahlevi Lubis BKP @zavibis</p>
""", unsafe_allow_html=True)


# ============================ FORMATTER ===============================
def to_float(num):
    """Convert Mandiri number to float."""
    if not num or num == "-" or num.strip() == "":
        return 0.0
    num = num.replace(".", "").replace(",", ".")
    try:
        return float(num)
    except:
        return 0.0


def indo(num):
    """Format float -> decimal comma, no thousand separators."""
    return f"{num:,.2f}".replace(",", "_").replace(".", ",").replace("_", "")


# ============================ PARSER ===============================
def parse_mandiri(pdf):
    rows = []
    nomor_rekening = ""
    saldo_awal = None
    currency = "IDR"

    for page in pdf.pages:
        words = page.extract_words(use_text_flow=True, keep_blank_chars=False)

        # Detect account number from header
        header_text = page.extract_text()
        m = re.search(r"\b(\d{10,16})\b", header_text or "")
        if m:
            nomor_rekening = m.group(1)

        # Group words by line (y0 clone)
        lines = {}
        for w in words:
            y = round(w["top"])
            if y not in lines:
                lines[y] = []
            lines[y].append(w)

        # Sort line by Y ascending
        sorted_lines = sorted(lines.items(), key=lambda x: x[0])

        buffer_ket = []

        for y, items in sorted_lines:
            # Sort text inside line by x0
            items = sorted(items, key=lambda x: x["x0"])
            line_text = " ".join([i["text"] for i in items])

            # Extract all numbers on this line
            nums = re.findall(r"\d[\d.,]*", line_text)

            if len(nums) >= 3:
                # DEFINISI 3 ANGKA TERAKHIR = debit | kredit | saldo
                debit_raw = nums[-3]
                kredit_raw = nums[-2]
                saldo_raw = nums[-1]

                debit = to_float(debit_raw)
                kredit = to_float(kredit_raw)
                saldo = to_float(saldo_raw)

                if saldo_awal is None:
                    saldo_awal = saldo

                # Extract tanggal
                tgl = re.findall(r"(\d{2} \w{3} \d{4})", line_text)
                tanggal = ""
                if tgl:
                    try:
                        tanggal = datetime.datetime.strptime(
                            tgl[0], "%d %b %Y"
                        ).strftime("%d/%m/%Y")
                    except:
                        tanggal = ""

                # Gabung remark
                remark = " ".join(buffer_ket).strip()
                remark = re.sub(r"\s+", " ", remark)

                rows.append([
                    nomor_rekening,
                    tanggal,
                    remark,
                    indo(debit),
                    indo(kredit),
                    indo(saldo),
                    currency,
                    indo(saldo_awal)
                ])

                buffer_ket = []  # reset remark
            else:
                # Kumpulkan remark
                buffer_ket.append(line_text)

    # Convert ke DataFrame
    df = pd.DataFrame(rows, columns=[
        "Nomor Rekening", "Tanggal", "Keterangan",
        "Debit", "Kredit", "Saldo", "Currency", "Saldo Awal"
    ])
    return df


# ============================ UPLOADER ===============================
file = st.file_uploader("Upload PDF Rekening Koran Mandiri", type=["pdf"])
if not file:
    st.stop()

with pdfplumber.open(file) as pdf:
    df = parse_mandiri(pdf)

st.dataframe(df, use_container_width=True)

# ============================ DOWNLOAD ===============================
buffer = BytesIO()
df.to_excel(buffer, index=False, engine="openpyxl")
buffer.seek(0)

st.download_button(
    "Download Excel",
    data=buffer,
    file_name="mandiri_extracted.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
