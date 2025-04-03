import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io
import re
from pdf2image import convert_from_path
import os
from PyPDF2 import PdfReader, PdfWriter
import numpy as np
import tempfile
import requests
import shutil

# URL do modelo hospedado no GitHub (substitua pelo seu URL raw)
MODELO_URL = "https://raw.githubusercontent.com/lucasbritocFis/gerador-relatorio-alta/main/Modelo_RESUMO_ALTA.pdf"

# Função para baixar o modelo do GitHub com verificação
def get_modelo_pdf():
    try:
        response = requests.get(MODELO_URL, timeout=10)
        response.raise_for_status()  # Verifica se o download foi bem-sucedido
        modelo_path = "Modelo_RESUMO_ALTA.pdf"
        with open(modelo_path, "wb") as f:
            f.write(response.content)
        
        # Verifica se o PDF é válido
        try:
            with open(modelo_path, "rb") as f:
                PdfReader(f)
            return modelo_path
        except Exception as e:
            st.error(f"Erro ao verificar o PDF baixado: {e}")
            raise
    except Exception as e:
        st.error(f"Falha ao baixar o modelo: {e}")
        raise

# Função para arredondar bordas de imagens
def arrendondar_imagem(caminho_imagem, raio=20):
    img = Image.open(caminho_imagem).convert("RGBA")
    largura, altura = img.size
    mascara = Image.new("L", (largura, altura), 0)
    draw = ImageDraw.Draw(mascara)
    draw.rounded_rectangle([(0, 0), (largura, altura)], radius=raio, fill=255)
    img_com_bordas = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    img_com_bordas.paste(img, (0, 0), mascara)
    img_com_bordas.save(caminho_imagem, "PNG")

# Função para processar PDFs de entrada e extrair imagens e texto
def processar_pdfs(pdf_files):
    all_images = []
    text = ""
    for pdf_file in pdf_files:
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            for img in page.get_images(full=True):
                xref = img[0]
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                image = Image.open(io.BytesIO(img_bytes))
                temp_image_path = f"temp_image{len(all_images)}.png"
                image.save(temp_image_path, format='PNG')
                all_images.append(temp_image_path)
            text += page.get_text()
    return all_images, text

# Função para criar as páginas intermediárias (output_0 a output_4)
def criar_paginas_intermediarias(all_images, text, dvh_path):
    linhas = text.splitlines()
    info_patient = linhas[13:38]
    info_plano_curso = next((j for j in linhas if j.strip().startswith("Campos no plano")), "")
    info_rodape = linhas[0:13]

    partes = info_patient[3].split(", ")
    sobrenome = partes[0]
    nomes_id = partes[1].split(" (")
    nomes = nomes_id[0]
    id_part = nomes_id[1].rstrip(")")
    nome_paciente = nomes + " " + sobrenome

    output_jpgs = []
    for idx in range(5):
        output_pdf_path = f"output_{idx}.pdf"
        c = canvas.Canvas(output_pdf_path, pagesize=letter)
        width, height = letter
        c.setFont("Helvetica", 6.5)

        c.setLineWidth(1.5)
        c.setStrokeColorRGB(0.82, 0.70, 0.53)
        c.line(50, 720, 580, 720)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(50, 710, "Informações dos " + info_plano_curso)
        c.setFont("Helvetica", 6)
        c.line(50, 705, 580, 705)
        c.setStrokeColorRGB(0.0, 0.0, 0.0)

        c.drawString(50, 770, info_patient[0])
        c.drawString(50, 760, "Prontuário: ")
        c.drawString(50, 750, info_patient[1])
        c.drawString(110, 770, nome_paciente)
        c.drawString(110, 760, id_part)
        c.drawString(110, 750, info_patient[4])

        if idx < 4:
            c.drawImage(all_images[idx], 70, 50, width=500, height=500)
            c.setFont("Helvetica", 6)
            c.setStrokeColorRGB(0.82, 0.70, 0.53)
            c.line(50, 570, 580, 570)
            c.setFont("Helvetica-Bold", 9)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(50, 560, "Representação Gráfica do Planejamento do Tratamento")
            c.setFont("Helvetica", 6)
            c.line(50, 555, 580, 555)
        if idx == 4:
            c.drawImage(dvh_path, 45, 170, width=540, height=380)
            c.setFont("Helvetica", 6)
            c.setStrokeColorRGB(0.82, 0.70, 0.53)
            c.line(50, 570, 580, 570)
            c.setFont("Helvetica-Bold", 9)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(50, 560, "Histograma Dose Volume")
            c.setFont("Helvetica", 6)
            c.line(50, 555, 580, 555)

        c.save()
        images = convert_from_path(output_pdf_path, dpi=300)
        jpg_path = f"output_{idx}.jpg"
        images[0].save(jpg_path, "JPEG")
        output_jpgs.append(jpg_path)
    return output_jpgs, nome_paciente, id_part

# Função para cortar imagem até o texto
def cortar_ate_texto(imagem):
    dpi = 300
    cm_para_cortar = 3
    polegadas_para_cortar = cm_para_cortar / 2.54
    pixels_para_cortar = int(polegadas_para_cortar * dpi)
    largura, altura = imagem.size
    img_cortada_inicial = imagem.crop((0, pixels_para_cortar, largura, altura))
    img_array = np.array(img_cortada_inicial.convert("L"))
    nova_altura, nova_largura = img_array.shape
    limiar_branco = 245
    ultima_linha = 0
    for y in range(nova_altura):
        if np.mean(img_array[y, :]) < limiar_branco:
            ultima_linha = y
    margem = 20
    bottom = min(ultima_linha + margem, nova_altura)
    img_cortada_final = img_cortada_inicial.crop((0, 0, nova_largura, bottom))
    return img_cortada_final

# Função principal para gerar o PDF final
def gerar_pdf_final(pdf_img1, pdf_img2, pdf_img3, pdf_img4, pdf_relatorio, pdf_dvh):
    # Initialize all file paths
    output_jpgs = []
    tmp_dvh_path = None
    tmp_file_path = None
    anexo_dvh_path = "anexo_dvh.png"
    anexo_temp_path = "anexo_temp.jpg"

    try:
        modelo_path = get_modelo_pdf()
        pdf_files = [pdf_img1, pdf_img2, pdf_img3, pdf_img4]
        all_images, text = processar_pdfs(pdf_files)

        # Process DVH
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_dvh:
            tmp_dvh.write(pdf_dvh.read())
            tmp_dvh_path = tmp_dvh.name

        try:
            dvh_images = convert_from_path(tmp_dvh_path, dpi=300)
            dvh_images[0].save(anexo_dvh_path, "PNG")
            
            output_jpgs, nome_paciente, id_paciente = criar_paginas_intermediarias(all_images, text, anexo_dvh_path)

            # Fallback to pikepdf if PyPDF2 fails
            try:
                pdf_modelo = PdfReader(modelo_path)
            except Exception:
                st.warning("PyPDF2 falhou, tentando pikepdf...")
                import pikepdf
                pdf_modelo = pikepdf.Pdf.open(modelo_path)

            output = PdfWriter()

            # [Rest of your PDF generation code remains the same...]
            # Página 1: Capa
            pagina1 = pdf_modelo.pages[0]
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            can.setStrokeColorRGB(0.82, 0.70, 0.53)
            can.setFillColorRGB(0.82, 0.70, 0.53)
            can.setFont("Helvetica-Bold", 15)
            can.drawString(25, 630, nome_paciente)
            can.drawString(25, 600, "ID: " + id_paciente)
            can.save()
            packet.seek(0)
            novo_pdf = PdfReader(packet)
            pagina1.merge_page(novo_pdf.pages[0])
            output.add_page(pagina1)

            # [Continue with all your page generation code...]

            # Save final PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                output.write(tmp_file)
                tmp_file_path = tmp_file.name

            # Verify file was created
            if not os.path.exists(tmp_file_path):
                raise FileNotFoundError(f"Arquivo PDF final não foi criado: {tmp_file_path}")
            
            return tmp_file_path

        except Exception as e:
            st.error(f"Erro durante o processamento: {str(e)}")
            raise

    finally:
        # Cleanup all temporary files
        cleanup_files = [
            tmp_dvh_path,
            anexo_dvh_path,
            anexo_temp_path,
            *output_jpgs,
            tmp_file_path  # This will be handled by the download part
        ]
        
        for file_path in cleanup_files:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                st.warning(f"Não foi possível remover arquivo temporário {file_path}: {e}")

# Interface do Streamlit
st.title("Gerador de Relatório de Alta")
st.write("Faça upload dos arquivos necessários para gerar o relatório final. O modelo já está embutido.")

# Upload dos arquivos separadamente (sem modelo)
pdf_img1 = st.file_uploader("Upload do PDF da Imagem 1", type="pdf")
pdf_img2 = st.file_uploader("Upload do PDF da Imagem 2", type="pdf")
pdf_img3 = st.file_uploader("Upload do PDF da Imagem 3", type="pdf")
pdf_img4 = st.file_uploader("Upload do PDF da Imagem 4", type="pdf")
pdf_relatorio = st.file_uploader("Upload do PDF do Relatório de Alta", type="pdf")
pdf_dvh = st.file_uploader("Upload do PDF DVH", type="pdf")

# In your Streamlit interface code:
if st.button("Gerar PDF"):
    if all([pdf_img1, pdf_img2, pdf_img3, pdf_img4, pdf_relatorio, pdf_dvh]):
        with st.spinner("Gerando o PDF..."):
            try:
                pdf_final_path = gerar_pdf_final(pdf_img1, pdf_img2, pdf_img3, pdf_img4, pdf_relatorio, pdf_dvh)
                
                # Verify file exists before trying to download
                if os.path.exists(pdf_final_path):
                    with open(pdf_final_path, "rb") as f:
                        st.download_button(
                            label="Baixar PDF Gerado",
                            data=f,
                            file_name="resultado.pdf",
                            mime="application/pdf"
                        )
                    # Clean up the final file after download
                    try:
                        os.remove(pdf_final_path)
                    except Exception as e:
                        st.warning(f"Não foi possível remover arquivo final: {e}")
                else:
                    st.error("O arquivo PDF final não foi gerado corretamente.")
                    
            except Exception as e:
                st.error(f"Falha ao gerar PDF: {str(e)}")
    else:
        st.error("Por favor, envie todos os arquivos necessários.")
