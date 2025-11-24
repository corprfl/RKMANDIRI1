import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Rekap Mandiri – Presisi Final", layout="wide")
st.title("📄 Rekap Rekening Mandiri – PRESISI FINAL")

uploaded = st.file_uploader("Upload Rekening Koran Mandiri (PDF)", type=["pdf"])

# ============================================
# REGEX DEFINISI
# ============================================
re_date = re.compile(r"(\d{2} \w{3} \d{4})")
re_time = re.compile(r"(\d{2}:\d{2}:\d{2})")
re_ref = re.compile(r"^\d{12,}$")      # reference panjang
re_number = re.compile(r"(-?\d[\d.,]*)")  # untuk debit/kredit/saldo


def to_float(v):
    if not v:
        return None
    v = v.replace(".", "").replace(",", ".")
    try:
        return float(v)
    except:
        return None


# ============================================
# PARSER FINAL FULL PRESISI
# ============================================
def parse(pdf_bytes):
    rows = []
    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:

            words = page.extract_words()  # XY text
            # Group berdasarkan Y-coordinate (baris)
            lines = {}
            for w in words:
                y = int(w["top"])
                text = w["text"].strip()

                # skip header panjang Mandiri
                if any(h in text.lower() for h in [
                    "account statement",
                    "opening balance",
                    "closing balance",
                    "summary",
                    "posting date remark",
                    "for further questions"
                ]):
                    continue

                lines.setdefault(y, []).append(text)

            # sort baris dari atas ke bawah
            sorted_lines = dict(sorted(lines.items()))

            # CLUSTER TRANSAKSI: setiap baris yang mengandung tanggal memulai transaksi baru
            clusters = []
            current = []

            for y, parts in sorted_lines.items():
                joined = " ".join(parts)

                if re_date.search(joined):  # tanggal muncul
                    if current:
                        clusters.append(current)
                    current = [joined]
                else:
                    if current:
                        current.append(joined)

            if current:
                clusters.append(current)

            # ============================================
            # PROSES SETIAP CLUSTER
            # ============================================
            for block in clusters:
                tanggal = waktu = ""
                remark = ""
                reference = ""
                debit = kredit = saldo = None

                # AMBIL TANGGAL & JAM
                for line in block:
                    md = re_date.search(line)
                    if md:
                        tanggal = md.group(1)
                    mt = re_time.search(line)
                    if mt:
                        waktu = mt.group(1)

                # CARI REFERENCE
                for line in block:
                    sp = line.split()
                    for token in sp:
                        if re_ref.match(token):
                            reference = token

                # CARI ANGGKA (DEBIT/KREDIT/SALDO)
                for line in block:
                    nums = re_number.findall(line)
                    # pola Mandiri = 3 angka berturut-turut
                    if len(nums) >= 3:
                        # Ambil angka terakhir 3 nilai
                        d, c, s = nums[-3:]
                        debit = to_float(d)
                        kredit = to_float(c)
                        saldo = to_float(s)
                        break

                # KETERANGAN = semua baris selain ref / angka / tanggal
                kets = []
                for line in block:
                    if tanggal in line:
                        continue
                    if waktu in line:
                        continue
                    if reference and reference in line:
                        continue
                    if re_number.findall(line):
                        continue
                    if "99102" in line:
                        continue
                    if line.strip():
                        kets.append(line.strip())

                remark = " ".join(kets).strip()

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


# ============================================
# STREAMLIT UI
# ============================================
if uploaded:
    st.info("Membaca PDF…")
    pdf_bytes = BytesIO(uploaded.read())
    df = parse(pdf_bytes)
    st.success("Berhasil membaca data Mandiri (Mode Presisi Final).")
    st.dataframe(df, use_container_width=True)

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buf.seek(0)

    st.download_button(
        "⬇️ Download Excel",
        buf,
        "Rekap-Mandiri-Presisi-Final.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
