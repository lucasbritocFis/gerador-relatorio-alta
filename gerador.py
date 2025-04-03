import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io
import os
from PyPDF2 import PdfReader, PdfWriter
import numpy as np
import tempfile
import requests
import shutil
from pdf2image import convert_from_path

# URL do modelo PDF
MODELO_URL = "https://raw.githubusercontent.com/lucasbritocFis/gerador-relatorio-alta/main/Modelo_RESUMO_ALTA.pdf"

# Função para baixar o modelo
def get_modelo_pdf():
    try:
        response = requests.get(MODELO_URL, timeout=10)
        response.raise_for_status()
        modelo_path = "Modelo_RESUMO_ALTA.pdf"
        with open(modelo_path, "wb") as f:
            f.write(response.content)
        
        # Verifica se o PDF é válido
        with open(modelo_path, "rb") as f:
            PdfReader(f)
        return modelo_path
    except Exception as e:
        st.error(f"Erro ao baixar modelo: {str(e)}")
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

# Processar PDFs de entrada
def processar_pdfs(pdf_files):
    all_images = []
    text = ""
    for pdf_file in pdf_files:
        try:
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
        except Exception as e:
            st.warning(f"Erro ao processar PDF: {str(e)}")
    return all_images, text

# Criar páginas intermediárias
def criar_paginas_intermediarias(all_images, text, dvh_path):
    try:
        linhas = text.splitlines()
        info_patient = linhas[13:38] if len(linhas) > 38 else linhas
        
        # Extrair informações do paciente
        nome_paciente = "Nome não identificado"
        id_part = "ID não identificado"
        
        if len(info_patient) > 3:
            partes = info_patient[3].split(", ")
            if len(partes) > 1:
                sobrenome = partes[0]
                nomes_id = partes[1].split(" (")
                if len(nomes_id) > 1:
                    nomes = nomes_id[0]
                    id_part = nomes_id[1].rstrip(")") if ")" in partes[1] else "ID não identificado"
                    nome_paciente = f"{nomes} {sobrenome}"
                else:
                    nome_paciente = partes[1]
            else:
                nome_paciente = info_patient[3]

        output_jpgs = []
        for idx in range(5):
            output_pdf_path = f"output_{idx}.pdf"
            c = canvas.Canvas(output_pdf_path, pagesize=letter)
            
            # Configurações de página
            c.setFont("Helvetica", 6.5)
            c.setLineWidth(1.5)
            c.setStrokeColorRGB(0.82, 0.70, 0.53)
            c.line(50, 720, 580, 720)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(50, 710, "Informações do Plano de Tratamento")
            c.setFont("Helvetica", 6)
            c.line(50, 705, 580, 705)
            c.setStrokeColorRGB(0.0, 0.0, 0.0)

            # Informações do paciente
            c.drawString(50, 770, info_patient[0] if len(info_patient) > 0 else "")
            c.drawString(50, 760, "Prontuário: ")
            c.drawString(50, 750, info_patient[1] if len(info_patient) > 1 else "")
            c.drawString(110, 770, nome_paciente)
            c.drawString(110, 760, id_part)
            c.drawString(110, 750, info_patient[4] if len(info_patient) > 4 else "")

            if idx < 4 and len(all_images) > idx:
                try:
                    c.drawImage(all_images[idx], 70, 50, width=500, height=500)
                except Exception as e:
                    st.warning(f"Erro ao desenhar imagem {idx}: {str(e)}")
                
                # Rodapé da imagem
                c.setFont("Helvetica", 6)
                c.setStrokeColorRGB(0.82, 0.70, 0.53)
                c.line(50, 570, 580, 570)
                c.setFont("Helvetica-Bold", 9)
                c.setFillColorRGB(0, 0, 0)
                c.drawString(50, 560, "Representação Gráfica do Planejamento do Tratamento")
                c.setFont("Helvetica", 6)
                c.line(50, 555, 580, 555)
            
            if idx == 4:
                try:
                    c.drawImage(dvh_path, 45, 170, width=540, height=380)
                except Exception as e:
                    st.warning(f"Erro ao desenhar DVH: {str(e)}")
                
                # Rodapé do DVH
                c.setFont("Helvetica", 6)
                c.setStrokeColorRGB(0.82, 0.70, 0.53)
                c.line(50, 570, 580, 570)
                c.setFont("Helvetica-Bold", 9)
                c.setFillColorRGB(0, 0, 0)
                c.drawString(50, 560, "Histograma Dose Volume")
                c.setFont("Helvetica", 6)
                c.line(50, 555, 580, 555)

            c.save()
            
            # Converter para JPG
            try:
                images = convert_from_path(output_pdf_path, dpi=300)
                if images:
                    jpg_path = f"output_{idx}.jpg"
                    images[0].save(jpg_path, "JPEG")
                    output_jpgs.append(jpg_path)
                    os.remove(output_pdf_path)  # Remove o PDF temporário
            except Exception as e:
                st.warning(f"Erro ao converter página {idx}: {str(e)}")

        return output_jpgs, nome_paciente, id_part

    except Exception as e:
        st.error(f"Erro ao criar páginas: {str(e)}")
        raise

# Função principal para gerar o PDF final
def gerar_pdf_final(pdf_img1, pdf_img2, pdf_img3, pdf_img4, pdf_relatorio, pdf_dvh):
    # Inicializa variáveis
    output_jpgs = []
    tmp_dvh_path = None
    tmp_file_path = None
    tmp_relatorio_path = None
    modelo_path = None

    try:
        # 1. Baixar modelo
        modelo_path = get_modelo_pdf()
        
        # 2. Processar PDFs de entrada
        pdf_files = [pdf_img1, pdf_img2, pdf_img3, pdf_img4]
        all_images, text = processar_pdfs(pdf_files)
        if not all_images:
            raise ValueError("Nenhuma imagem extraída dos PDFs")

        # 3. Processar DVH
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_dvh:
            tmp_dvh.write(pdf_dvh.read())
            tmp_dvh_path = tmp_dvh.name

        dvh_images = convert_from_path(tmp_dvh_path, dpi=300)
        if not dvh_images:
            raise ValueError("Falha ao converter DVH")
        
        dvh_images[0].save("anexo_dvh.png", "PNG")

        # 4. Criar páginas intermediárias
        output_jpgs, nome_paciente, id_paciente = criar_paginas_intermediarias(all_images, text, "anexo_dvh.png")
        if not output_jpgs:
            raise ValueError("Páginas intermediárias não geradas")

        # 5. Carregar modelo PDF
        try:
            pdf_modelo = PdfReader(modelo_path)
        except Exception:
            import pikepdf
            pdf_modelo = pikepdf.Pdf.open(modelo_path)

        output = PdfWriter()

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

        # Página 2: Relatório
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_relatorio:
            tmp_relatorio.write(pdf_relatorio.read())
            tmp_relatorio_path = tmp_relatorio.name

        relatorio_images = convert_from_path(tmp_relatorio_path, dpi=300)
        if relatorio_images:
            img_cortada = cortar_ate_texto(relatorio_images[0])
            img_cortada.save("anexo_temp.jpg", "JPEG")

        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        can.drawImage("anexo_temp.jpg", 40, 120, width=450, height=450)
        can.save()
        packet.seek(0)
        novo_pdf = PdfReader(packet)
        pagina2 = pdf_modelo.pages[1]
        pagina2.merge_page(novo_pdf.pages[0])
        output.add_page(pagina2)

        # Páginas 3-7: Imagens
        for i in range(2, 7):
            if (i-2) < len(output_jpgs):
                pagina = pdf_modelo.pages[i]
                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=letter)
                can.setFillColorRGB(0.82, 0.70, 0.53)
                can.setFont("Helvetica-Bold", 15)
                can.drawString(60, 730, nome_paciente)
                
                arrendondar_imagem(output_jpgs[i-2], raio=60)
                can.drawImage(output_jpgs[i-2], 55, 40, width=420, height=530, mask="auto")
                can.setFont("Helvetica", 5)
                can.save()
                packet.seek(0)
                novo_pdf = PdfReader(packet)
                pagina.merge_page(novo_pdf.pages[0])
                output.add_page(pagina)

        # Página 8: Final
        output.add_page(pdf_modelo.pages[7])

        # Salvar PDF final
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            output.write(tmp_file)
            tmp_file_path = tmp_file.name

        # Verificar se o PDF foi criado
        if not os.path.exists(tmp_file_path) or os.path.getsize(tmp_file_path) == 0:
            raise ValueError("PDF final não foi gerado corretamente")

        return tmp_file_path

    except Exception as e:
        st.error(f"Erro ao gerar PDF: {str(e)}")
        return None

    finally:
        # Limpeza de arquivos temporários
        temp_files = [
            tmp_dvh_path,
            "anexo_dvh.png",
            "anexo_temp.jpg",
            tmp_relatorio_path,
            *output_jpgs
        ]
        
        for file in temp_files:
            try:
                if file and os.path.exists(file):
                    os.remove(file)
            except Exception as e:
                st.warning(f"Não foi possível remover {file}")

        if modelo_path and os.path.exists(modelo_path):
            try:
                os.remove(modelo_path)
            except Exception:
                pass

# Função para cortar imagem
def cortar_ate_texto(imagem):
    try:
        dpi = 300
        cm_para_cortar = 3
        pixels_para_cortar = int((cm_para_cortar / 2.54) * dpi)
        largura, altura = imagem.size
        img_cortada = imagem.crop((0, pixels_para_cortar, largura, altura))
        return img_cortada
    except Exception as e:
        st.warning(f"Erro ao cortar imagem: {str(e)}")
        return imagem
import streamlit as st
import time
from io import BytesIO

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Upload de PDFs Moderno",
    page_icon="📤",
    layout="centered"
)

# --- CSS PERSONALIZADO ---
st.markdown("""
<style>
    /* Caixa de upload principal */
    .stFileUploader > div > div {
        border: 2px dashed #4e8cff !important;
        border-radius: 12px !important;
        background: #f8faff !important;
        padding: 30px !important;
        transition: all 0.3s;
    }
    /* Texto da caixa */
    .stFileUploader > div > div > small {
        font-size: 16px !important;
        color: #2c3e50 !important;
        font-weight: 500;
    }
    /* Hover */
    .stFileUploader > div > div:hover {
        border-color: #2e7bff !important;
        background: #e6f0ff !important;
    }
    /* Cards de pré-visualização */
    .file-card {
        background: white;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 3px solid #4e8cff;
        transition: transform 0.2s;
    }
    .file-card:hover {
        transform: translateY(-3px);
    }
    /* Botão de limpar */
    .stButton>button {
        border: 1px solid #ff4b4b !important;
        color: #ff4b4b !important;
        background: white !important;
    }
    .stButton>button:hover {
        background: #fff0f0 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- TÍTULO E DESCRIÇÃO ---
st.title("📤 Upload de PDFs")
st.markdown("""
    <p style='text-align: center; color: #6c757d;'>
    Arraste os arquivos para a área abaixo ou clique para selecionar.<br>
    <span style='font-size: 0.9em;'>Formatos suportados: PDF (máx. 200MB cada)</span>
    </p>
""", unsafe_allow_html=True)

# --- UPLOADER ---
uploaded_files = st.file_uploader(
    label=" ",
    type="pdf",
    accept_multiple_files=True,
    label_visibility="collapsed",
    help="Selecione os PDFs para gerar o relatório"
)

# --- PRÉ-VISUALIZAÇÃO DOS ARQUIVOS ---
if uploaded_files:
    # Feedback de sucesso
    st.success(f"✅ **{len(uploaded_files)} arquivo(s) carregado(s)!**")
    
    # Barra de progresso (simulada)
    with st.status("Processando arquivos...", expanded=True) as status:
        progress_bar = st.progress(0)
        for percent in range(0, 101, 10):
            time.sleep(0.1)
            progress_bar.progress(percent)
        status.update(label="Pronto!", state="complete", expanded=False)
    
    # Cards com detalhes dos arquivos
    st.subheader("📂 Arquivos Carregados:")
    cols = st.columns(2)
    for i, file in enumerate(uploaded_files):
        with cols[i % 2]:
            file_size = len(file.getvalue()) / 1024  # Tamanho em KB
            st.markdown(f"""
            <div class="file-card">
                <strong>📄 {file.name}</strong>
                <p style="color: #6c757d; font-size: 0.8em; margin: 5px 0;">
                    Tamanho: {file_size:.2f} KB<br>
                    Tipo: PDF
                </p>
            </div>
            """, unsafe_allow_html=True)
    
    # Botão de ação (exemplo: gerar relatório)
    if st.button("🪄 **Gerar Relatório Consolidado**", type="primary", use_container_width=True):
        with st.spinner("Unindo PDFs..."):
            time.sleep(2)  # Simulação de processamento
            st.toast("Relatório gerado com sucesso!", icon="🎉")
            
            # Simulação de um PDF gerado (substitua pelo seu código real)
            fake_pdf = BytesIO(b"%PDF-1.4 fake-pdf-for-demo")
            st.download_button(
                label="⬇️ Baixar Relatório",
                data=fake_pdf,
                file_name="relatorio_consolidado.pdf",
                mime="application/pdf"
            )
    
    # Botão para limpar arquivos (opcional)
    if st.button("🗑️ Limpar Arquivos", use_container_width=True):
        st.session_state.uploaded_files = []
        st.rerun()

# --- MENSAGEM SE NÃO HOUVER ARQUIVOS ---
elif not uploaded_files:
    st.markdown("""
    <div style='text-align: center; margin-top: 20px; color: #6c757d;'>
        <p>Nenhum arquivo carregado ainda.</p>
    </div>
    """, unsafe_allow_html=True)

# --- RODAPÉ ---
st.markdown("---")
st.caption("Desenvolvido com Streamlit • ✉️ suporte@empresa.com")
