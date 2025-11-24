import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO
import datetime


st.set_page_config(page_title="Extractor Mandiri - CorpRFL", layout="wide")

# ============================ UI DARK MODE ===============================
st.markdown("""
<style>
body { background-color:#0d1117 !important; color:white !important; }
.stButton>button { background:#0070C0 !important; color:white !important;
                   border-radius:8px; padding:8px 16px; }
</style>
<h2>📘 Extractor Rekening Koran Mandiri – CorpRFL</h2>
<p>By Reza Fahlevi Lubis BKP @zavibis</p>
""", unsafe_allow_html=True)


# =============== FORMATTER =================
def to_float(num):
    """
    Convert Mandiri number string → float.
    Example:
      '266,000,296.00' → 266000296.00 (float)
    """
    if num is None or num.strip() == "" or num == "-":
        return 0.0
    num = num.replace(".", "").replace(",", ".")
    try:
        return float(num)
    except:
        return 0.0


def indo(num):
    """
    Format float → Indonesian format:
    - no thousand separator
    - decimal comma
    Example:
      266000296.0 → '266000296,00'
    """
    return f"{num:,.2f}".replace(",", "_").replace(".", ",").replace("_", "")


# =======================================================================
#                MANDIRI AUTOPARSE ENGINE – LEVEL 5
# =======================================================================
def parse_mandiri(pdf):
    rows = []
    nomor_rekening = ""
    saldo_awal = None
    currency = "IDR"

    for page in pdf.pages:

        # -------- Extract words with coordinates (X/Y) ----------
        words = page.extract_words(use_text_flow=True, keep_blank_chars=False)

        # -------- Detect account number (from header) ----------
        header_text = page.extract_text() or ""
        m = re.search(r"\b(\d{10,16})\b", header_text)
        if m:
            nomor_rekening = m.group(1)

        # -------- Group words per-line by Y coordinate ----------
        lines = {}
        for w in words:
            y = round(w["top"])  # integer y
            if y not in lines:
                lines[y] = []
            lines[y].append(w)

        # Sort ascending
        sorted_lines = sorted(lines.items(), key=lambda x: x[0])
        buffer_ket = []

        for y, items in sorted_lines:
            # Sort words in a line by X position
            items = sorted(items, key=lambda x: x["x0"])
            line_text = " ".join([i["text"] for i in items])

            # Extract all numeric patterns
            nums = re.findall(r"\d[\d.,]*", line_text)

            # =========== DETECT TRANSACTION LINE ==============
            # If >= 3 numbers exist in one line → debit, kredit, saldo
            if len(nums) >= 3:

                debit_raw = nums[-3]
                kredit_raw = nums[-2]
                saldo_raw = nums[-1]

                debit = to_float(debit_raw)
                kredit = to_float(kredit_raw)
                saldo = to_float(saldo_raw)

                if saldo_awal is None:
                    saldo_awal = saldo

                # ---------- extract date ----------
                tgl = re.findall(r"(\d{2} \w{3} \d{4})", line_text)
                tanggal = ""
                if tgl:
                    try:
                        tanggal = datetime.datetime.strptime(
                            tgl[0], "%d %b %Y"
                        ).strftime("%d/%m/%Y")
                    except:
                        tanggal = ""

                # ---------- join remark ----------
                remark = " ".join(buffer_ket).strip()
                remark = re.sub(r"\s+", " ", remark)

                # ---------- append row ----------
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

                buffer_ket = []  # reset

            else:
                # collect remark
                buffer_ket.append(line_text)

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
