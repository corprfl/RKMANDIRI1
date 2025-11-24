import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Rekap Mandiri Presisi", layout="wide")
st.title("📄 Rekap Rekening Koran Mandiri – PRESISI FINAL v3")


uploaded = st.file_uploader("Upload PDF Mandiri", type=["pdf"])


# ============================================================
# REGEX
# ============================================================
re_date = re.compile(r"(\d{2} \w{3} \d{4})")
re_time = re.compile(r"(\d{2}:\d{2}:\d{2})")
re_ref = re.compile(r"^\d{12,}$")   # reference 12 digit+
re_money = re.compile(r"-?\d[\d.,]*")  # angka uang mentah


def to_float(v):
    if not v:
        return None
    v = v.replace(".", "").replace(",", ".")
    try:
        return float(v)
    except:
        return None


# ============================================================
# PARSER FINAL MANDIRI PRESISI
# ============================================================
def parse(pdf_bytes):

    rows = []

    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:

            words = page.extract_words()

            # --- Group by Y (baris) ---
            lines = {}
            for w in words:
                y = int(w["top"])
                lines.setdefault(y, []).append(w["text"].strip())

            # --- Sort berdasarkan Y ---
            sorted_lines = sorted(lines.items(), key=lambda x: x[0])

            # --- Filter header Mandiri (VERSI FINAL) ---
            filtered = []
            for y, parts in sorted_lines:
                line = " ".join(parts)
                lower = line.lower()

                if any(key in lower for key in [
                    "account statement",
                    "opening balance",
                    "closing balance",
                    "posting date",
                    "summary",
                    "period",
                    "alias",
                    "for further questions",
                ]):
                    continue

                filtered.append(line)

            # --- CLUSTER PER TRANSAKSI ---
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

                # -------------------------
                # Ambil tanggal + waktu
                # -------------------------
                for line in block:
                    md = re_date.search(line)
                    if md:
                        tanggal = md.group(1)
                    mt = re_time.search(line)
                    if mt:
                        waktu = mt.group(1)

                # -------------------------
                # Ambil reference
                # -------------------------
                for line in block:
                    tokens = line.split()
                    for t in tokens:
                        if re_ref.match(t):
                            reference = t

                # -------------------------
                # AMBIL AMOUNT (FIX FINAL)
                # Ambil SEMUA angka besar, buang angka kecil <5 digit
                # Ambil 3 yang terakhir = Debit, Kredit, Saldo
                # -------------------------
                all_nums = []

                for line in block:
                    nums = re_money.findall(line)
                    cleaned = []

                    for n in nums:
                        pure = n.replace(".", "").replace(",", "")
                        # angka amount Mandiri biasanya 5 digit ke atas atau ada desimal
                        if len(pure) >= 5 or ("," in n or "." in n):
                            cleaned.append(n)

                    all_nums.extend(cleaned)

                if len(all_nums) >= 3:
                    d, c, s = all_nums[-3:]
                    debit = to_float(d)
                    kredit = to_float(c)
                    saldo = to_float(s)

                # -------------------------
                # Ambil remark (selain ref, tanggal, time, amount)
                # -------------------------
                rlist = []
                for line in block:

                    if tanggal in line:
                        continue
                    if waktu in line:
                        continue
                    if reference and reference in line:
                        continue
                    if "99102" in line:
                        continue
                    if re_money.findall(line):  # amount → skip
                        continue

                    if line.strip():
                        rlist.append(line.strip())

                remark = " ".join(rlist).strip()

                rows.append([
                    tanggal,
                    waktu,
                    remark,
                    reference,
                    debit,
                    kredit,
                    saldo
                ])

    df = pd.DataFrame(rows, columns=[
        "Tanggal", "Waktu", "Keterangan", "Reference",
        "Debit", "Kredit", "Saldo"
    ])
    return df


# ============================================================
# STREAMLIT
# ============================================================
if uploaded:
    st.info("⏳ Membaca PDF Mandiri...")
    pdf_bytes = BytesIO(uploaded.read())
    df = parse(pdf_bytes)
    st.success("✅ Berhasil membaca data Mandiri – PRESISI FINAL v3")
    st.dataframe(df, use_container_width=True)

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buf.seek(0)

    st.download_button(
        "⬇ Download Excel – Mandiri Presisi v3",
        buf,
        "Rekap-Mandiri-Presisi-Final.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
