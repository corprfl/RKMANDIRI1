import streamlit as st
import pdfplumber
import pandas as pd
import re
import datetime
from io import BytesIO

# ==============================
# UI SETTINGS
# ==============================
st.set_page_config(page_title="Extractor Mandiri L7 Final", layout="wide")

st.markdown("""
<style>
body { background:#0d1117 !important; color:white !important; }
.stButton>button {
    background:#0070C0 !important;
    color:white !important; border-radius:8px;
    padding:8px 16px; font-weight:bold;
}
</style>
<h2>📘 Extractor Rekening Koran Mandiri — LEVEL 7 FINAL</h2>
<p>By Reza Fahlevi Lubis BKP @zavibis</p>
""", unsafe_allow_html=True)


# ==============================
# NUMBER FORMATTER
# ==============================
def to_float(n):
    if not n or n == "-" or n.strip() == "":
        return 0.0
    return float(n.replace(".", "").replace(",", "."))


def indo(num):
    return f"{num:,.2f}".replace(",", "_").replace(".", ",").replace("_", "")


# ==============================
# LEVEL-7 PARSER (FINAL)
# ==============================
def parse(pdf):
    rows = []
    nomor_rekening = ""
    saldo_awal = None
    currency = "IDR"

    for page in pdf.pages:
        text = page.extract_text() or ""
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        # detect account number only from header
        m = re.search(r"\b(\d{10,16})\b", text)
        if m:
            nomor_rekening = m.group(1)

        block = []
        current_date = ""

        # ------------------------
        # helper: flush a block
        # ------------------------
        def flush_block():
            nonlocal block, current_date, saldo_awal

            if not block:
                return

            # find numeric line
            num_line = None
            for ln in reversed(block):
                nums = re.findall(r"\d[\d.,]*", ln)
                if len(nums) >= 3:
                    num_line = ln
                    break

            if not num_line:
                block = []
                return

            # filter numeric patterns
            nums = re.findall(r"\d[\d.,]*", num_line)
            debit_raw, kredit_raw, saldo_raw = nums[-3], nums[-2], nums[-1]

            debit = to_float(debit_raw)
            kredit = to_float(kredit_raw)
            saldo = to_float(saldo_raw)

            if saldo_awal is None:
                saldo_awal = saldo

            # build remark
            remark_lines = []
            for ln in block:
                # skip known noise
                if ln in ["02", "99102", "12424"]:
                    continue

                # skip pure long-number reference
                if re.fullmatch(r"\d{8,}", ln):
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

        # ===========================
        # MAIN LOOP LINES
        # ===========================
        for ln in lines:

            # detect date
            tg = re.search(r"(\d{2} \w{3} \d{4})", ln)
            if tg:
                try:
                    current_date = datetime.datetime.strptime(
                        tg.group(1), "%d %b %Y"
                    ).strftime("%d/%m/%Y")
                except:
                    current_date = ""
                continue

            # detect numeric line with strong filter
            nums = re.findall(r"\d[\d.,]*", ln)

            is_real_numeric = (
                len(nums) >= 3
                and ln.count(",") >= 2
                and "99102" not in ln
                and ln.strip() not in ["02", "12424"]
                and not re.fullmatch(r"\d{8,}", ln.strip())
            )

            if is_real_numeric:
                block.append(ln)
                flush_block()
                continue

            # normal line → collect remark
            block.append(ln)

        # last block on page
        flush_block()

    df = pd.DataFrame(rows, columns=[
        "Nomor Rekening", "Tanggal", "Keterangan",
        "Debit", "Kredit", "Saldo", "Currency", "Saldo Awal"
    ])
    return df


# ==============================
# UPLOADER
# ==============================
file = st.file_uploader("Upload PDF Mandiri", type=["pdf"])
if not file:
    st.stop()

with pdfplumber.open(file) as pdf:
    df = parse(pdf)

st.dataframe(df, use_container_width=True)

# ==============================
# DOWNLOAD
# ==============================
buff = BytesIO()
df.to_excel(buff, index=False, engine="openpyxl")
buff.seek(0)

st.download_button(
    "Download Excel",
    buff,
    "mandiri_extracted_L7_final.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
