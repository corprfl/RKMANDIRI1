import streamlit as st
import pdfplumber
import pandas as pd
import re
import datetime
from io import BytesIO

st.set_page_config(page_title="Extractor Mandiri Level-7", layout="wide")

st.markdown("""
<style>
body { background:#0d1117 !important; color:white !important; }
.stButton>button { background:#0070C0 !important; color:white !important;
    border-radius:8px; padding:8px 16px; }
</style>
<h2>📘 Extractor Mandiri – LEVEL 7 (Premium Parser)</h2>
<p>By Reza Fahlevi Lubis BKP @zavibis</p>
""", unsafe_allow_html=True)


# ===========================
# HELPERS
# ===========================
def to_float(n):
    if not n or n == "-" or n.strip() == "":
        return 0.0
    return float(n.replace(".", "").replace(",", "."))

def indo(num):
    return f"{num:,.2f}".replace(",", "_").replace(".", ",").replace("_", "")


# ===========================
# LEVEL-7 PARSER ENGINE
# ===========================
def parse(pdf):
    rows = []
    nomor_rekening = ""
    saldo_awal = None
    currency = "IDR"

    for page in pdf.pages:
        txt = page.extract_text() or ""
        lines = [l.strip() for l in txt.splitlines() if l.strip()]

        # Detect account number
        m = re.search(r"\b(\d{10,16})\b", txt)
        if m:
            nomor_rekening = m.group(1)

        # BLOCK ACCUMULATOR
        block = []
        current_date = ""

        def flush_block():
            nonlocal block, current_date, saldo_awal
            if not block:
                return

            # find last numeric line inside block
            num_line = None
            for ln in reversed(block):
                parts = re.findall(r"\d[\d.,]*", ln)
                if len(parts) >= 3:
                    num_line = ln
                    break
            if not num_line:
                block = []
                return

            nums = re.findall(r"\d[\d.,]*", num_line)
            debit_raw, kredit_raw, saldo_raw = nums[-3], nums[-2], nums[-1]
            debit = to_float(debit_raw)
            kredit = to_float(kredit_raw)
            saldo = to_float(saldo_raw)

            if saldo_awal is None:
                saldo_awal = saldo

            # remark = all lines except numeric lines + skip noise
            remark_lines = []
            for ln in block:
                if ln in ["99102", "02", "12424"]:
                    continue
                if ln == num_line:
                    continue
                remark_lines.append(ln)

            remark = " ".join(remark_lines)
            remark = re.sub(r"\s+", " ", remark).strip()

            rows.append([
                nomor_rekening,
                current_date,
                remark,
                indo(debit),
                indo(kredit),
                indo(saldo),
                currency,
                indo(saldo_awal)
            ])

            block = []

        for ln in lines:

            # detect date
            m_t = re.search(r"(\d{2} \w{3} \d{4})", ln)
            if m_t:
                current_date = datetime.datetime.strptime(
                    m_t.group(1), "%d %b %Y"
                ).strftime("%d/%m/%Y")
                continue

            # identify numeric line → marks END OF BLOCK
            nums = re.findall(r"\d[\d.,]*", ln)
            if len(nums) >= 3:
                block.append(ln)
                flush_block()
                continue

            # normal line → remark part
            block.append(ln)

        # flush last block on page
        flush_block()

    df = pd.DataFrame(rows, columns=[
        "Nomor Rekening", "Tanggal", "Keterangan",
        "Debit", "Kredit", "Saldo", "Currency", "Saldo Awal"
    ])
    return df


# ===========================
# UI
# ===========================
pdf_file = st.file_uploader("Upload PDF Mandiri", type=["pdf"])
if not pdf_file:
    st.stop()

with pdfplumber.open(pdf_file) as pdf:
    df = parse(pdf)

st.dataframe(df, use_container_width=True)

buff = BytesIO()
df.to_excel(buff, index=False, engine="openpyxl")
buff.seek(0)

st.download_button(
    "Download Excel",
    buff,
    "mandiri_extracted_l7.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
