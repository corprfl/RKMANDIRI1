import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Rekap Mandiri v7.1 FINAL", layout="wide")
st.title("📄 Rekap Rekening Koran Mandiri – v7.1 FINAL (Presisi 100%)")


# ======================================================
# REGEX / PATTERN
# ======================================================

tanggal_re = re.compile(r"(\d{2} \w{3} \d{4}),")
jam_re = re.compile(r"(\d{2}:\d{2}:\d{2})")
num_re = re.compile(r"[\d.,]+\.\d{2}")

BAD_LINES = [
    "Account Statement", "Account Name", "Opening Balance",
    "Closing Balance", "Currency", "Branch",
    "For further questions", "Page ", "Summary",
    "Posting Date Remark Reference No. Debit Credit Balance"
]


# ======================================================
# FUNCTIONS
# ======================================================

def clean_amount_float(x):
    """
    Mandiri format:
    '1,234,567.89' → float 1234567.89
    """
    if not x:
        return None
    x = x.replace(",", "")
    try:
        return float(x)
    except:
        return None


def extract_transactions(text):
    lines = text.split("\n")
    tx = []
    cur = None

    def push():
        nonlocal cur, tx
        if cur and cur["Tanggal"]:
            cur["Keterangan"] = cur["Keterangan"].strip()
            tx.append(cur.copy())

    for raw in lines:
        line = raw.strip()

        # Abaikan header/footer
        if any(bad in line for bad in BAD_LINES):
            continue

        # ==============================================
        # DETEKSI TRANSAKSI BARU (POSTING DATE)
        # ==============================================
        m = tanggal_re.search(line)
        if m:
            push()
            cur = {
                "Tanggal": m.group(1),
                "Waktu": "",
                "Keterangan": "",
                "Reference": "",
                "Debit": None,
                "Kredit": None,
                "Saldo": None
            }

            jm = jam_re.search(line)
            if jm:
                cur["Waktu"] = jm.group(1)

            continue

        # ==============================================
        # WAKTU BARIS BERIKUT
        # ==============================================
        if cur and cur["Waktu"] == "":
            jm = jam_re.search(line)
            if jm:
                cur["Waktu"] = jm.group(1)
                continue

        # ==============================================
        # REFERENCE NUMBER
        # ==============================================
        if cur and re.fullmatch(r"\d{15,}", line):
            cur["Reference"] = line
            continue

        # ==============================================
        # DEBIT – KREDIT – SALDO
        # ==============================================
        if cur and ("." in line or "," in line):
            nums = num_re.findall(line)
            if len(nums) == 3:
                d, k, s = nums
                cur["Debit"] = clean_amount_float(d)
                cur["Kredit"] = clean_amount_float(k)
                cur["Saldo"] = clean_amount_float(s)
                continue

        # ==============================================
        # KETERANGAN MULTILINE
        # ==============================================
        if cur and line not in ["", "-", "–"]:
            cur["Keterangan"] += line + "\n"

    push()
    return tx


def format_comma(df):
    """Convert float → string desimal koma untuk Excel export."""
    out = df.copy()
    for col in ["Debit", "Kredit", "Saldo"]:
        out[col] = out[col].apply(
            lambda v: "" if v is None else str(v).replace(".", ",")
        )
    return out


# ======================================================
# UI
# ======================================================

uploaded = st.file_uploader("Unggah PDF Rekening Mandiri", type=["pdf"])

if uploaded:
    pdf_bytes = uploaded.read()

    text = ""
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for p in pdf.pages:
            t = p.extract_text()
            if t:
                text += t + "\n"

    st.info("🔍 Memproses PDF dengan mode PRESISI v7.1…")

    tx = extract_transactions(text)
    df = pd.DataFrame(tx)

    st.success(f"✔ Berhasil membaca {len(df)} transaksi. (v7.1 FINAL)")

    st.dataframe(df, use_container_width=True)

    # ===========================
    # EXPORT EXCEL (format koma)
    # ===========================
    excel_df = format_comma(df)

    output = BytesIO()
    excel_df.to_excel(output, index=False)
    output.seek(0)

    st.download_button(
        "⬇ Download Rekap Mandiri v7.1 (Excel, desimal koma)",
        data=output.getvalue(),
        file_name="Rekap_Mandiri_v7.1.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
