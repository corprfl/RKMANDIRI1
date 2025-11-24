import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Rekap Mandiri v7 FINAL", layout="wide")
st.title("📄 Rekap Rekening Koran Mandiri – v7 FINAL (Presisi 100%)")

# ============================================
#   FUNGSI BANTU
# ============================================

tanggal_re = re.compile(r"(\d{2} \w{3} \d{4}),")
jam_re = re.compile(r"(\d{2}:\d{2}:\d{2})")
num_re = re.compile(r"[\d.,]+\.\d{2}")

BAD_LINES = [
    "Account Statement", "Account Name", "Opening Balance",
    "Closing Balance", "Currency", "Branch",
    "For further questions", "Page ", "Summary",
    "Posting Date Remark Reference No. Debit Credit Balance"
]

def clean_amount(x):
    """
    Mandiri format: 1,234,567.89
    Output v7:      1234567,89
    """
    if not x:
        return ""
    x = x.replace(",", "")
    x = x.replace(" ", "")
    try:
        val = float(x)
        return f"{val:.2f}".replace(".", ",")
    except:
        return ""

def extract_transactions(text):
    lines = text.split("\n")
    tx = []
    cur = None

    def push():
        nonlocal cur, tx
        if cur and cur["Tanggal"]:
            # Final cleanup
            cur["Keterangan"] = cur["Keterangan"].strip()
            tx.append(cur.copy())

    for raw in lines:
        line = raw.strip()

        # Abaikan header/footer
        if any(bad in line for bad in BAD_LINES):
            continue

        # ==============================================
        # DETEKSI AWAL TRANSAKSI (Tanggal)
        # ==============================================
        m = tanggal_re.search(line)
        if m:
            push()
            cur = {
                "Tanggal": m.group(1),
                "Waktu": "",
                "Keterangan": "",
                "Reference": "",
                "Debit": "",
                "Kredit": "",
                "Saldo": ""
            }

            jm = jam_re.search(line)
            if jm:
                cur["Waktu"] = jm.group(1)

            continue

        # ==============================================
        # JAM di baris berikut
        # ==============================================
        if cur and cur["Waktu"] == "":
            jm = jam_re.search(line)
            if jm:
                cur["Waktu"] = jm.group(1)
                continue

        # ==============================================
        # REFERENCE NUMBER (nomor panjang)
        # ==============================================
        if cur and re.fullmatch(r"\d{15,}", line):
            cur["Reference"] = line
            continue

        # ==============================================
        # ANGKA (Debit – Kredit – Balance)
        # Format Mandiri = "- 1,000,000.00 0.00 250,000,000.00"
        # ==============================================
        if cur and ("." in line or "," in line):
            nums = num_re.findall(line)
            if len(nums) == 3:
                d, k, s = nums
                cur["Debit"] = clean_amount(d)
                cur["Kredit"] = clean_amount(k)
                cur["Saldo"] = clean_amount(s)
                continue

        # ==============================================
        # SISANYA = KETERANGAN
        # ==============================================
        if cur and line not in ["", "-", "–"]:
            cur["Keterangan"] += line + "\n"

    push()
    return tx


# ============================================
#   UI
# ============================================

uploaded = st.file_uploader("Unggah PDF Rekening Mandiri", type=["pdf"])

if uploaded:
    pdf_bytes = uploaded.read()

    text = ""
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for p in pdf.pages:
            t = p.extract_text()
            if t:
                text += t + "\n"

    st.info("🔍 Memproses PDF dengan Mode Presisi v7…")

    tx = extract_transactions(text)
    df = pd.DataFrame(tx)

    st.success(f"✔ Berhasil membaca {len(df)} transaksi. (v7 FINAL)")

    st.dataframe(df, use_container_width=True)

    # Export Excel
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    st.download_button(
        "⬇ Download Rekap Mandiri v7 (Excel)",
        data=output.getvalue(),
        file_name="Rekap_Mandiri_v7.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
