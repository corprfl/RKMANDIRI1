import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Rekap Mandiri Presisi", layout="wide")
st.title("📄 Rekap Rekening Mandiri – PRESISI FINAL v4")


uploaded = st.file_uploader("Upload PDF Mandiri", type=["pdf"])


# ============================================================
# REGEX DEFINITIONS
# ============================================================
re_date = re.compile(r"(\d{2} \w{3} \d{4})")
re_time = re.compile(r"(\d{2}:\d{2}:\d{2})")
re_ref  = re.compile(r"^\d{12,}$")      # reference angka >= 12 digit
re_money = re.compile(r"-?\d[\d.,]*")   # angka uang


def to_float(v):
    if not v:
        return None
    v = v.replace(".", "").replace(",", ".")
    try:
        return float(v)
    except:
        return None


# ============================================================
# PARSER FINAL MANDIRI v4
# ============================================================
def parse(pdf_bytes):

    rows = []

    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:

            words = page.extract_words()

            # -------- GROUP PER Y BARIS --------
            lines = {}
            for w in words:
                y = int(w["top"])
                lines.setdefault(y, []).append(w["text"].strip())

            sorted_lines = sorted(lines.items(), key=lambda x: x[0])

            # -------- BUANG HEADER & META MANDIRI --------
            filtered = []
            for y, parts in sorted_lines:
                line = " ".join(parts).strip()
                lower = line.lower()

                if any(key in lower for key in [
                    "account statement",
                    "opening balance",
                    "closing balance",
                    "summary",
                    "posting date",
                    "period",
                    "alias",
                    "for further questions",
                    "debit credit balance",
                ]):
                    continue

                filtered.append(line)

            # -------- CLUSTER PER TRANSAKSI --------
            clusters = []
            current = []

            for line in filtered:
                if re_date.search(line):
                    if current:
                        clusters.append(current)
                    current = [line]
                else:
                    if current:
                        current.append(line)

            if current:
                clusters.append(current)

            # =====================================================
            # PROSES SETIAP CLUSTER
            # =====================================================
            for block in clusters:

                tanggal = waktu = ""
                remark = ""
                reference = ""
                debit = kredit = saldo = None

                # ------------------------
                # TANGGAL & JAM
                # ------------------------
                for line in block:
                    md = re_date.search(line)
                    if md:
                        tanggal = md.group(1)

                    mt = re_time.search(line)
                    if mt:
                        waktu = mt.group(1)

                # ------------------------
                # REFERENCE
                # ------------------------
                for line in block:
                    tokens = line.split()
                    for t in tokens:
                        if re_ref.match(t):
                            reference = t

                # ------------------------
                # AMOUNT — FIX v4 (paling presisi)
                # Ambil baris dengan 3 angka uang valid
                # ------------------------
                amount_line = None
                for line in block:

                    nums = re_money.findall(line)

                    if len(nums) >= 3:
                        # validasi: minimal 2 angka harus punya koma/titik
                        money_like = sum(1 for x in nums if ("," in x or "." in x))
                        if money_like >= 2:
                            amount_line = nums
                            break

                if amount_line and len(amount_line) >= 3:
                    # Ambil 3 terakhir karena mandiri = debit kredit saldo
                    d, c, s = amount_line[-3:]
                    debit  = to_float(d)
                    kredit = to_float(c)
                    saldo  = to_float(s)

                # ------------------------
                # KETERANGAN
                # ------------------------
                remarks = []
                for line in block:

                    if tanggal in line:
                        continue
                    if waktu in line:
                        continue
                    if reference and reference in line:
                        continue
                    if "99102" in line:
                        continue
                    if amount_line and any(x in line for x in amount_line):
                        continue

                    if line.strip():
                        remarks.append(line.strip())

                remark = " ".join(remarks).strip()

                rows.append([
                    tanggal,
                    waktu,
                    remark,
                    reference,
                    debit,
                    kredit,
                    saldo
                ])

    return pd.DataFrame(rows, columns=[
        "Tanggal", "Waktu", "Keterangan",
        "Reference", "Debit", "Kredit", "Saldo"
    ])


# ============================================================
# STREAMLIT UI
# ============================================================
if uploaded:
    st.info("⏳ Membaca dan memproses PDF…")
    pdf_bytes = BytesIO(uploaded.read())
    df = parse(pdf_bytes)

    st.success("✅ Berhasil membaca data Mandiri – PRESISI FINAL v4")
    st.dataframe(df, use_container_width=True)

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buf.seek(0)

    st.download_button(
        "⬇ Download Excel – Mandiri Presisi v4",
        buf,
        file_name="Rekap-Mandiri-Presisi-v4.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
