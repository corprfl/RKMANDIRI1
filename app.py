import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Rekening Mandiri", layout="wide")
st.title("📄 Extractor Rekening Mandiri – FINAL (Cluster Parser)")


uploaded = st.file_uploader("Upload PDF Rekening Mandiri", type=["pdf"])


# ============================================================
# REGEX
# ============================================================
pat_tgl = re.compile(r"^\d{2} \w{3} \d{4}")
pat_tgl_full = re.compile(r"(?P<tgl>\d{2} \w{3} \d{4})")
pat_jam = re.compile(r"(?P<jam>\d{2}:\d{2}:\d{2})$")
pat_ref = re.compile(r"^\d{10,}$")
pat_amount = re.compile(r"(-?\s?\d[\d.,]*)\s+(-?\s?\d[\d.,]*)\s+(-?\s?\d[\d.,]*)$")

HEADER_BAD_WORDS = [
    "Account Statement",
    "Posting Date",
    "Summary",
    "Created",
]


def is_header_line(text):
    for w in HEADER_BAD_WORDS:
        if w.lower() in text.lower():
            return True
    return False


def to_float(v):
    if not v:
        return None
    v = v.replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(v)
    except:
        return None


# ============================================================
# PARSER – CLUSTER PER TRANSAKSI
# ============================================================
def parse(pdf_bytes):
    rows = []

    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:
            raw_lines = page.extract_text().splitlines()

            # CLEAN LINE: hapus header Mandiri yg panjang
            lines = []
            for ln in raw_lines:
                if not is_header_line(ln.strip()):
                    lines.append(ln.strip())

            # CLUSTER TRANSAKSI: setiap baris tanggal memulai cluster baru
            clusters = []
            current = []

            for ln in lines:
                if pat_tgl.match(ln):
                    if current:
                        clusters.append(current)
                    current = [ln]
                else:
                    if ln.strip():
                        current.append(ln)

            if current:
                clusters.append(current)

            # ============================================================
            # PROCESS EACH CLUSTER
            # ============================================================
            for blk in clusters:

                tgl = None
                jam = None
                remarks = []
                ref = ""
                debit = credit = saldo = None

                # 1 — Ambil tanggal (selalu baris pertama cluster)
                m = pat_tgl_full.search(blk[0])
                if m:
                    tgl = m.group("tgl")

                # 2 — cari jam (bisa di baris 1 atau baris lain)
                for ln in blk:
                    m = pat_jam.search(ln)
                    if m:
                        jam = m.group("jam")
                        break

                # 3 — cari reference
                for ln in blk:
                    if pat_ref.match(ln):
                        ref = ln.strip()
                        break

                # 4 — cari amount
                for ln in blk:
                    m = pat_amount.search(ln)
                    if m:
                        debit  = to_float(m.group(1))
                        credit = to_float(m.group(2))
                        saldo  = to_float(m.group(3))
                        break

                # 5 — remarks = semua baris selain tanggal/jam/reference/amount
                for ln in blk:
                    if pat_tgl.match(ln):
                        continue
                    if pat_jam.search(ln):
                        continue
                    if pat_ref.match(ln):
                        continue
                    if pat_amount.search(ln):
                        continue
                    if ln.strip() == "99102":
                        continue
                    if ln.strip():
                        remarks.append(ln.strip())

                # Gabung remark jadi 1 baris
                remarks = " ".join(remarks).strip()

                rows.append([
                    tgl,
                    jam,
                    remarks,
                    ref,
                    debit,
                    credit,
                    saldo
                ])

    df = pd.DataFrame(rows, columns=[
        "Tanggal", "Waktu", "Keterangan", "Reference",
        "Debit", "Kredit", "Saldo"
    ])
    return df


# ============================================================
# STREAMLIT UI
# ============================================================
if uploaded:
    st.info("📥 Memproses PDF Mandiri...")
    pdf_bytes = BytesIO(uploaded.read())

    try:
        df = parse(pdf_bytes)
        st.success("Berhasil membaca data Mandiri (Mode Presisi).")
        st.dataframe(df, use_container_width=True)

        # export Excel
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        buf.seek(0)

        st.download_button(
            "⬇️ Download Excel",
            data=buf,
            file_name="RekapMandiri_Final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ Error: {e}")
