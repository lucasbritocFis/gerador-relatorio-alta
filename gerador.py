import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io
import re
from datetime import datetime
import pdfplumber
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import ParagraphStyle
from pdf2image import convert_from_path
import os
from PyPDF2 import PdfReader, PdfWriter, Transformation
import numpy as np
import tempfile

def main():
    st.title("Processador de Relatórios de Radioterapia")
    
    # Upload dos arquivos
    st.sidebar.header("Upload de Arquivos")
    img1 = st.sidebar.file_uploader("Imagem 1 (PDF)", type=["pdf"])
    img2 = st.sidebar.file_uploader("Imagem 2 (PDF)", type=["pdf"])
    img3 = st.sidebar.file_uploader("Imagem 3 (PDF)", type=["pdf"])
    img4 = st.sidebar.file_uploader("Imagem 4 (PDF)", type=["pdf"])
    dvh = st.sidebar.file_uploader("DVH (PDF)", type=["pdf"])
    relatorio_alta = st.sidebar.file_uploader("Relatório de Alta (PDF)", type=["pdf"])
    modelo = st.sidebar.file_uploader("Modelo de Resumo (PDF)", type=["pdf"])

    if st.sidebar.button("Processar") and all([img1, img2, img3, img4, dvh, relatorio_alta, modelo]):
        with st.spinner("Processando..."):
            # Criar diretório temporário
            with tempfile.TemporaryDirectory() as temp_dir:
                # Salvar arquivos temporariamente
                pdf_files = []
                for i, uploaded_file in enumerate([img1, img2, img3, img4]):
                    file_path = os.path.join(temp_dir, f"img_{i+1}.pdf")
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    pdf_files.append(file_path)
                
                dvh_path = os.path.join(temp_dir, "dvh.pdf")
                with open(dvh_path, "wb") as f:
                    f.write(dvh.getbuffer())
                
                relatorio_path = os.path.join(temp_dir, "relatorio_alta.pdf")
                with open(relatorio_path, "wb") as f:
                    f.write(relatorio_alta.getbuffer())
                
                modelo_path = os.path.join(temp_dir, "modelo.pdf")
                with open(modelo_path, "wb") as f:
                    f.write(modelo.getbuffer())
                
                # Processamento (seu código original adaptado)
                process_files(pdf_files, dvh_path, relatorio_path, modelo_path, temp_dir)
                
                # Exibir resultado
                st.success("Processamento concluído!")
                with open(os.path.join(temp_dir, "resultado.pdf"), "rb") as f:
                    st.download_button(
                        "Baixar Relatório Final",
                        f,
                        file_name="resumo_alta_radioterapia.pdf",
                        mime="application/pdf"
                    )

def process_files(pdf_files, dvh_path, relatorio_path, modelo_path, temp_dir):
    # Inicializar listas para armazenar as imagens e textos
    all_images = []
    all_texts = []
    text = ""

    # Processar todos os PDFs
    for pdf_file in pdf_files:
        doc = fitz.open(pdf_file)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            for img in page.get_images(full=True):
                xref = img[0]
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                image = Image.open(io.BytesIO(img_bytes))
                temp_image_path = os.path.join(temp_dir, f"temp_image{len(all_images)}.png")
                image.save(temp_image_path, format='PNG')
                all_images.append(temp_image_path)
                text += page.get_text()
                all_texts.append(text)

    linhas = text.splitlines()
    #st.write("LINHAS EXTRAÍDAS:")
    #for i, linha in enumerate(linhas):
        #st.write(f"{i}: {linha}")
            
    info_patient = []
    info_rodape = []
    info_plano_curso = ""

    imagens_dvh = convert_from_path(dvh_path, dpi=300)
    imagemdvh = imagens_dvh[0]
    imagemdvh.save(os.path.join(temp_dir, "anexo_dvh.png"), "PNG")

    for j in linhas:
        if j.strip().startswith("Campos no plano"):
            info_plano_curso = j
            break

    #for linha_rod in linhas[0:13]:
    #    info_rodape.append(linha_rod)

   # for linha in linhas[13:38]:
    #    info_patient.append(linha)

    info_patient = []
    info_rodape = []
    
    # Captura o rodapé até encontrar "Nome do paciente"
    pegando_rodape = True
    for linha in linhas:
        if "Nome do paciente" in linha:
            pegando_rodape = False
        if pegando_rodape:
            info_rodape.append(linha)
        else:
            break
    
    # Captura info do paciente entre "Nome do paciente" e "Campos no plano"
    pegando_paciente = False
    for linha in linhas:
        if "Nome do paciente" in linha:
            pegando_paciente = True
            info_patient.append(linha)
        elif pegando_paciente:
            if "Campos no plano" in linha:
                break
            info_patient.append(linha)

    
    info_campos = []
    for linha_campos in linhas[38:]:
        if linha_campos == "Nome do paciente:":
            break
        info_campos.append(linha_campos)

    texto_campos = " ".join(info_campos)
    texto_campos = re.sub(r'\s+', ' ', texto_campos.strip())

    cabecalho_campos = ["Campo", "Técnica", "Máquina", "Energia", "Escala", "ID de cunha", "Peso",
                        "X1[cm]", "X2[cm]", "Y1[cm]", "Y2[cm]", "Gantry[deg]", "Colimador[deg]", "Mesa[deg]",
                        "X[cm]", "Y[cm]", "Z[cm]", "SSD[cm]", "UM"]

    vetores = {campo: [] for campo in cabecalho_campos}
    valores = texto_campos.split()
    inicio_dados = valores.index("CBCT") if "CBCT" in valores else 0
    valores_dados = valores[inicio_dados:]

    num_colunas = len(cabecalho_campos)
    linhas_dados = []
    linha_atual = []
    ids_validos = ["CBCT", "MV", "KV"]

    sections = {}
    current_marker = None

    for valor in valores_dados:
        if valor in ids_validos or valor.isdigit():
            current_marker = valor
            sections[current_marker] = []
        elif current_marker:
            sections[current_marker].append(valor)

    linhas_completas = []
    for marker, lines in sections.items():
        linha_atual = [marker]
        for line in lines:
            valores = line.split()
            for valor in valores:
                linha_atual.append(valor)
                if len(linha_atual) == len(cabecalho_campos) + 1:
                    linhas_completas.append(linha_atual)
                    linha_atual = [marker]
            if len(linha_atual) > 1:
                linhas_completas.append(linha_atual)


    partes = linhas[3].split(", ")
    sobrenome = partes[0]
    nomes_id = partes[1].split(" (")
    nomes = nomes_id[0]
    id_part = nomes_id[1].rstrip(")")
    
    #nome_paciente = nomes + " " + sobrenome
    #id_paciente = id_part

    def arrendondar_imagem(caminho_imagem, raio=20):
        img = Image.open(caminho_imagem).convert("RGBA")
        largura, altura = img.size
        mascara = Image.new("L", (largura, altura), 0)
        draw = ImageDraw.Draw(mascara)
        draw.rounded_rectangle([(0, 0), (largura, altura)], radius=raio, fill=255)
        img_com_bordas = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
        img_com_bordas.paste(img, (0, 0), mascara)
        img_com_bordas.save(caminho_imagem, "PNG")

    # Criar 5 PDFs, cada um com uma imagem diferente
    for idx in range(5):
        output_pdf_path = os.path.join(temp_dir, f"output_{idx}.pdf")
        c = canvas.Canvas(output_pdf_path, pagesize=letter)
        width, height = letter
        y_position = height - 50
        line_height = 12
        c.setFont("Helvetica", 6.5)

        c.setLineWidth(1.5)
        c.setStrokeColorRGB(0.82, 0.70, 0.53)
        c.line(50, 720, 580, 720)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(50, 710, "Informações dos " + info_plano_curso)
        c.setFont("Helvetica", 6)
        c.setLineWidth(1.5)
        c.line(50, 705, 580, 705)
        c.setStrokeColorRGB(0.0, 0.0, 0.0)

        cbct = linhas_completas[0] if len(linhas_completas) > 0 else [""] * 20
        mv = linhas_completas[19] if len(linhas_completas) > 19 else [""] * 20
        kv = linhas_completas[38] if len(linhas_completas) > 38 else [""] * 20

        campos = []
        for i in range(57, len(linhas_completas), 19):
            if i < len(linhas_completas):
                campos.append(linhas_completas[i])

        c.setFont("Helvetica", 6.5)
        c.drawString(50, 770, linhas[0])
        c.drawString(50, 760, "Prontuário: ")
        c.drawString(50, 750, linhas[14])
        c.drawString(280, 770, linhas[19])
        c.drawString(280, 760, linhas[21])
        c.drawString(280, 750, linhas[20])
        c.drawString(280, 740, "Orientação: ")
        c.drawString(400, 770, "Normalização do plano: ")
        c.drawString(400, 760, linhas[26])
        c.drawString(400, 750, linhas[27])
        c.drawString(400, 740, linhas[28])
        c.drawString(400, 730, linhas[29])

        #c.drawString(110, 770, nomes + " " + sobrenome)
        #c.drawString(110, 760, id_part)
        #c.drawString(110, 750, info_patient[4])
        #c.drawString(317, 770, info_patient[9])
        #c.drawString(317, 760, info_patient[11])
        #c.drawString(317, 750, info_patient[10])
        #c.drawString(317, 740, info_rodape[8])
        #c.drawString(530, 770, info_patient[18])
        #c.drawString(530, 760, info_patient[19])
        #c.drawString(530, 750, info_patient[20])
        #c.drawString(530, 740, info_patient[21])
        #c.drawString(530, 730, info_patient[22])

        c.setLineWidth(0.5)
        c.line(50, 690, 580, 690)
        c.drawString(50, 680, cbct[0])
        c.drawString(50, 670, mv[0])
        c.drawString(50, 660, kv[0])

        c.drawString(90, 680, cbct[1])
        c.drawString(90, 670, mv[1])
        c.drawString(90, 660, kv[1])

        c.drawString(120, 680, cbct[2])
        c.drawString(120, 670, mv[2])
        c.drawString(120, 660, kv[2])

        c.drawString(170, 680, cbct[3])
        c.drawString(170, 670, mv[3])
        c.drawString(170, 660, kv[3])

        c.drawString(195, 680, cbct[4])
        c.drawString(195, 670, mv[4])
        c.drawString(195, 660, kv[4])

        c.drawString(230, 680, cbct[6])
        c.drawString(230, 670, mv[6])
        c.drawString(230, 660, kv[6])

        c.drawString(250, 680, cbct[7])
        c.drawString(250, 670, mv[7])
        c.drawString(250, 660, kv[7])

        c.drawString(270, 680, cbct[8])
        c.drawString(270, 670, mv[8])
        c.drawString(270, 660, kv[8])

        c.drawString(290, 680, cbct[9])
        c.drawString(290, 670, mv[9])
        c.drawString(290, 660, kv[9])

        c.drawString(320, 680, cbct[10])
        c.drawString(320, 670, mv[10])
        c.drawString(320, 660, kv[10])

        c.drawString(360, 680, cbct[11])
        c.drawString(360, 670, mv[11])
        c.drawString(360, 660, kv[11])

        c.drawString(410, 680, cbct[12])
        c.drawString(410, 670, mv[12])
        c.drawString(410, 660, kv[12])

        c.drawString(450, 680, cbct[13])
        c.drawString(450, 670, mv[13])
        c.drawString(450, 660, kv[13])

        c.drawString(470, 680, cbct[14])
        c.drawString(470, 670, mv[14])
        c.drawString(470, 660, kv[14])

        c.drawString(490, 680, cbct[15])
        c.drawString(490, 670, mv[15])
        c.drawString(490, 660, kv[15])

        c.drawString(505, 680, cbct[16])
        c.drawString(505, 670, mv[16])
        c.drawString(505, 660, kv[16])

        c.drawString(540, 680, "Localização")
        c.drawString(540, 670, "Localização")
        c.drawString(540, 660, "Localização")

        c.drawString(50, 695, "ID do Campo")
        c.drawString(90, 695, "Técnica")
        c.drawString(120, 695, "Máquina")
        c.drawString(170, 695, "Energia")
        c.drawString(195, 695, "Escala")
        c.drawString(230, 695, "X1[cm]")
        c.drawString(250, 695, "X2[cm]")
        c.drawString(270, 695, "Y1[cm]")
        c.drawString(290, 695, "Y2[cm]")
        c.drawString(320, 695, "Gantry[deg]")
        c.drawString(360, 695, "Colimador[deg]")
        c.drawString(410, 695, "Mesa[deg]")
        c.drawString(445, 695, "X[cm]")
        c.drawString(465, 695, "Y[cm]")
        c.drawString(485, 695, "Z[cm]")
        c.drawString(505, 695, "SSD[cm]")
        c.drawString(540, 695, "UM")

        y = 0
        for var in campos:
            c.drawString(50, 650 - y, var[0])
            c.drawString(90, 650 - y, var[1])
            c.drawString(120, 650 - y, var[2])
            c.drawString(170, 650 - y, var[3])
            c.drawString(195, 650 - y, var[4])
            c.drawString(230, 650 - y, var[6])
            c.drawString(250, 650 - y, var[7])
            c.drawString(270, 650 - y, var[8])
            c.drawString(290, 650 - y, var[9])
            c.drawString(320, 650 - y, var[10] + var[11] + var[12])
            c.drawString(360, 650 - y, var[13])
            c.drawString(410, 650 - y, var[14])
            c.drawString(450, 650 - y, var[15])
            c.drawString(470, 650 - y, var[16])
            c.drawString(490, 650 - y, var[17])
            c.drawString(505, 650 - y, var[18])
            c.drawString(540, 650 - y, var[19])
            y += 8

        if idx < 4:
            c.drawImage(all_images[idx], 70, 50, width=500, height=500)
            c.setFont("Helvetica", 6)
            c.setStrokeColorRGB(0.82, 0.70, 0.53)
            c.line(50, 570, 580, 570)
            c.setFont("Helvetica-Bold", 9)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(50, 560, "Representação Gráfica do Planejamento do Tratamento")
            c.setFont("Helvetica", 6)
            c.setStrokeColorRGB(0.82, 0.70, 0.53)
            c.line(50, 555, 580, 555)

        if idx == 4:
            c.drawImage(os.path.join(temp_dir, "anexo_dvh.png"), 45, 170, width=540, height=400)
            c.setFont("Helvetica", 6)
            c.setStrokeColorRGB(0.82, 0.70, 0.53)
            c.line(50, 570, 580, 570)
            c.setFont("Helvetica-Bold", 9)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(50, 560, "Histograma Dose Volume")
            c.setFont("Helvetica", 6)
            c.setStrokeColorRGB(0.82, 0.70, 0.53)
            c.line(50, 555, 580, 555)

        c.save()

    output_jpgs = []
    for idx in range(5):
        pdf_path = os.path.join(temp_dir, f"output_{idx}.pdf")
        images = convert_from_path(pdf_path, dpi=300)
        jpg_path = os.path.join(temp_dir, f"output_{idx}.jpg")
        images[0].save(jpg_path, "JPEG")
        output_jpgs.append(jpg_path)

    # Carregar o PDF modelo
    pdf_modelo = PdfReader(modelo_path)
    output = PdfWriter()

    # Página 1: Capa com Nome + ID
    pagina1 = pdf_modelo.pages[0]
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    can.setStrokeColorRGB(0.82, 0.70, 0.53)
    can.setFillColorRGB(0.82, 0.70, 0.53)
    can.setFont("Helvetica-Bold", 15)
    #can.drawString(25, 630, nomes + " " + sobrenome)
    #can.drawString(25, 600, "ID: " + id_part)
    can.save()
    packet.seek(0)
    novo_pdf = PdfReader(packet)
    pagina1.merge_page(novo_pdf.pages[0])
    output.add_page(pagina1)

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

    # Página 2: Relatório de alta
    imagens = convert_from_path(relatorio_path, dpi=300)
    imagem = imagens[0]
    img_cortada = cortar_ate_texto(imagem)
    img_cortada.save(os.path.join(temp_dir, "anexo_temp.jpg"), "JPEG")

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    can.drawImage(os.path.join(temp_dir, "anexo_temp.jpg"), 50, 140, width=450, height=490)
    can.setStrokeColorRGB(0.82, 0.70, 0.53)
    can.setFillColorRGB(0.82, 0.70, 0.53)
    can.setFont("Helvetica-Bold", 15)
    #can.drawString(60, 730, nomes + " " + sobrenome)
    can.save()
    packet.seek(0)
    novo_pdf = PdfReader(packet)
    pagina2 = pdf_modelo.pages[1]
    pagina2.merge_page(novo_pdf.pages[0])
    output.add_page(pagina2)

    # Páginas 3 a 7: Imagens geradas
    for i in range(2, 7):
        pagina = pdf_modelo.pages[i]
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        can.setFillColorRGB(0.82, 0.70, 0.53)
        can.setFont("Helvetica-Bold", 15)
        #can.drawString(60, 730, nomes + " " + sobrenome)
        img_idx = i - 2
        arrendondar_imagem(output_jpgs[img_idx], raio=60)
        can.drawImage(output_jpgs[img_idx], 55, 40, width=420, height=530, mask="auto")
        can.setFont("Helvetica", 5)
        can.save()
        packet.seek(0)
        novo_pdf = PdfReader(packet)
        pagina.merge_page(novo_pdf.pages[0])
        output.add_page(pagina)

    # Página 8: Intacta
    output.add_page(pdf_modelo.pages[7])

    # Salvar o PDF final
    with open(os.path.join(temp_dir, "resultado.pdf"), "wb") as f:
        output.write(f)

if __name__ == "__main__":
    main()

