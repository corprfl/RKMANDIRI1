import streamlit as st
import pdfplumber, pandas as pd, re
from io import BytesIO

st.set_page_config(layout="wide", page_title="Extractor Mandiri - CorpRFL")
st.markdown("""<style>
body { background-color:#0d1117; color:white; }
.stButton>button { background:#0070C0; color:white; border-radius:8px; }
</style><h2>📘 Extractor Rekening Koran Mandiri</h2>
<p>By Reza Fahlevi Lubis BKP @zavibis</p>""", unsafe_allow_html=True)

file = st.file_uploader("Upload PDF", type=["pdf"])
if not file:
    st.stop()

rows=[]
with pdfplumber.open(file) as pdf:
    for page in pdf.pages:
        text = page.extract_text() or ""
        lines = text.splitlines()
        # simple fallback autoparse
        for ln in lines:
            nums = re.findall(r"[0-9][0-9.,]*", ln)
            if len(nums)>=3:
                debit=nums[-3]; kredit=nums[-2]; saldo=nums[-1]
                remark=" ".join(lines[max(0,lines.index(ln)-3):lines.index(ln)]).replace("\n"," ")
                rows.append(["", "", remark, debit, kredit, saldo, "IDR", ""])

df = pd.DataFrame(rows, columns=["Nomor Rekening","Tanggal","Keterangan","Debit","Kredit","Saldo","Currency","Saldo Awal"])

buffer = BytesIO()
df.to_excel(buffer, index=False, engine="openpyxl")
buffer.seek(0)

st.dataframe(df)
st.download_button("Download Excel", data=buffer, file_name="mandiri.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
