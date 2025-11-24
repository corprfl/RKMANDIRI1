import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO
import datetime

# ===============================
#   UI / PAGE SETTINGS
# ===============================
st.set_page_config(page_title="Extractor Mandiri - Level 6", layout="wide")

st.markdown("""
<style>
body { background-color:#0d1117 !important; color:white !important; }
.stButton>button {
    background:#0070C0 !important;
    color:white !important;
    border-radius:8px;
    padding:8px 16px;
}
</style>

<h2>📘 Extractor Rekening Koran Mandiri – LEVEL 6</h2>
<p>By Reza Fahlevi Lubis BKP @zavibis</p>
""", unsafe_allow_html=True)


# ===============================
#   FORMATTER FUNCTIONS
# ===============================
def to_float(num):
    """Convert Mandiri style number → float."""
    if not num or num.strip() == "" or num == "-":
        return 0.0
    num = num.replace(".", "").replace(",", ".")
    try:
        return float(num)
    except:
        return 0.0


def indo(num):
    """Decimal comma + no thousand separator."""
    return f"{num:,.2f}".replace(",", "_").replace(".", ",").replace("_", "")


# ===============================
#   LEVEL-6 PARSER ENGINE
# ===============================
def parse_mandiri(pdf):
    rows = []
    nomor_rekening = ""
    saldo_awal = None
    currency = "IDR"

    for page in pdf.pages:

        page_text = page.extract_text() or ""
        lines = page_text.splitlines()

        # -----------------------------------
        # Detect Account Number (Header)
        # -----------------------------------
        m = re.search(r"\b(\d{10,16})\b", page_text)
        if m:
            nomor_rekening = m.group(1)

        ket_buffer = []
        current_date = ""

        for ln in lines:
            ln_clean = ln.strip()

            # -----------------------------------
            # Detect date pattern
            # -----------------------------------
            m_tgl = re.search(r"(\d{2} \w{3} \d{4})", ln_clean)
            if m_tgl:
                try:
                    current_date = datetime.datetime.strptime(
                        m_tgl.group(1), "%d %b %Y"
                    ).strftime("%d/%m/%Y")
                except:
                    current_date = ""
                continue

            # -----------------------------------
            # Detect transaction line via 3 numbers
            # -----------------------------------
            nums = re.findall(r"\d[\d.,]*", ln_clean)

            if len(nums) >= 3:

                # Ignore noise numbers: 02, 99102, 12424
                if ln_clean in ["02", "99102", "12424"]:
                    continue

                debit_raw = nums[-3]
                kredit_raw = nums[-2]
                saldo_raw = nums[-1]

                debit = to_float(debit_raw)
                kredit = to_float(kredit_raw)
                saldo = to_float(saldo_raw)

                if saldo_awal is None:
                    saldo_awal = saldo

                # -----------------------------------
                # Construct remark (joined 1 line)
                # -----------------------------------
                remark = " ".join(ket_buffer).strip()
                remark = re.sub(r"\s+", " ", remark)

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

                ket_buffer = []
            else:
                # append remark line
                if ln_clean not in ["", "Page 1 of 2", "Page 2 of 2"]:
                    ket_buffer.append(ln_clean)

    df = pd.DataFrame(rows, columns=[
        "Nomor Rekening", "Tanggal", "Keterangan",
        "Debit", "Kredit", "Saldo", "Currency", "Saldo Awal"
    ])
    return df


# ===============================
#   FILE UPLOAD
# ===============================
file = st.file_uploader("Upload PDF Rekening Koran Mandiri", type=["pdf"])
if not file:
    st.stop()

with pdfplumber.open(file) as pdf:
    df = parse_mandiri(pdf)

st.dataframe(df, use_container_width=True)

# ===============================
#   DOWNLOAD
# ===============================
buffer = BytesIO()
df.to_excel(buffer, index=False, engine="openpyxl")
buffer.seek(0)

st.download_button(
    "Download Excel",
    buffer,
    "mandiri_extracted_l6.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
