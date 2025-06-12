from flask import Flask, request, render_template, send_file, redirect, url_for, send_file
import yt_dlp
import os
import subprocess
import shutil
import tempfile
import time
from werkzeug.utils import secure_filename
import re
from werkzeug.utils import secure_filename
import os, tempfile, subprocess, shutil


app = Flask(__name__)

# Rutas absolutas para evitar problemas
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
RESULT_FOLDER = os.path.join(BASE_DIR, 'results')
DOWNLOADS_FOLDER = os.path.join(BASE_DIR, 'downloads')
INDIVIDUAL_FOLDER = os.path.join(DOWNLOADS_FOLDER, 'individuales')

# Crear carpetas necesarias
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)
os.makedirs(INDIVIDUAL_FOLDER, exist_ok=True)

# Carpetas
DOWNLOAD_FOLDER = 'static/downloads'
INDIVIDUAL_FOLDER = os.path.join(DOWNLOAD_FOLDER, 'individuales')
ACAPELLAS_FOLDER = os.path.join(DOWNLOAD_FOLDER, 'acapellas')
COOKIES_FILE = 'cookies.txt'

# Crear carpetas necesarias
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(INDIVIDUAL_FOLDER, exist_ok=True)
os.makedirs(ACAPELLAS_FOLDER, exist_ok=True)

# Verifica que FFmpeg esté disponible
def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False

if not check_ffmpeg():
    print("FFmpeg no está instalado. Por favor, agrégalo al PATH.")
    exit(1)

# Esperar que el archivo esté libre
def wait_for_file_release(file_path, timeout=10):
    start_time = time.time()
    while True:
        try:
            with open(file_path, 'rb'):
                return
        except PermissionError:
            if time.time() - start_time > timeout:
                raise TimeoutError("No se pudo acceder al archivo.")
            time.sleep(0.1)

# Limpiar nombre para usar en archivos
def safe_name(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

@app.route('/')
def index():
    return render_template('index.html')

def clean_filename(title):
    return re.sub(r'[\\/*?:"<>|]', '_', title)

@app.route('/single_download', methods=['POST'])
def single_download():
    url = request.form['youtube_url']
    if not url:
        return "URL inválida", 400

    try:
        # Primero, extraemos la info del video para obtener el título
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', f'video_{int(time.time())}')
            safe_title = secure_filename(title)

        # Creamos la ruta temporal para guardar el archivo mp3
        output_template = os.path.join(tempfile.gettempdir(), f'{safe_title}.%(ext)s')
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Construimos la ruta completa del archivo mp3
        mp3_path = os.path.join(tempfile.gettempdir(), f"{safe_title}.mp3")

        wait_for_file_release(mp3_path)

        # Te preguntamos dónde guardar usando send_file (el navegador lo pregunta)
        return send_file(mp3_path, as_attachment=True)

    except Exception as e:
        return f"Error al descargar: {str(e)}", 500


@app.route('/playlist_download', methods=['POST'])
def playlist_download():
    url = request.form['playlist_url']
    if not url:
        return "URL inválida", 400

    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            playlist_title = info.get('title', f'playlist_{int(time.time())}')
            safe_title = secure_filename(playlist_title)

        playlist_dir = os.path.join(tempfile.gettempdir(), safe_title)
        os.makedirs(playlist_dir, exist_ok=True)

        output_template = os.path.join(playlist_dir, '%(title)s.%(ext)s')
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        for filename in os.listdir(playlist_dir):
            wait_for_file_release(os.path.join(playlist_dir, filename))

        zip_path = os.path.join(tempfile.gettempdir(), f"{safe_title}.zip")
        shutil.make_archive(zip_path.replace('.zip', ''), 'zip', playlist_dir)

        return send_file(zip_path, as_attachment=True)

    except Exception as e:
        return f"Error al descargar la playlist: {str(e)}", 500

@app.route('/subir_y_separar', methods=['POST'])
def subir_y_separar():
    if 'archivo' not in request.files:
        return "No se envió archivo", 400

    archivo = request.files['archivo']
    if archivo.filename == '':
        return "Nombre de archivo vacío", 400

    if archivo and archivo.filename.endswith('.mp3'):
        # Crear nombre seguro y único
        nombre_base = secure_filename(os.path.splitext(archivo.filename)[0])
        unique_id = str(int(time.time()))
        carpeta_nombre = f"{nombre_base}_{unique_id}"

        # Crear carpeta temporal
        carpeta_temporal = os.path.join(tempfile.gettempdir(), carpeta_nombre)
        os.makedirs(carpeta_temporal, exist_ok=True)

        filepath = os.path.join(carpeta_temporal, f'{carpeta_nombre}.mp3')
        archivo.save(filepath)

        try:
            # Ejecutar Demucs
            filepath_abs = os.path.abspath(filepath)
            subprocess.run(['python', '-m', 'demucs', filepath_abs], check=True)

            # Carpeta de salida de Demucs
            resultados_dir = os.path.join('separated', 'htdemucs', carpeta_nombre)

            # Copiar stems a la carpeta temporal
            for stem in os.listdir(resultados_dir):
                origen = os.path.join(resultados_dir, stem)
                destino = os.path.join(carpeta_temporal, stem)
                shutil.copy(origen, destino)

            # Crear archivo ZIP
            zip_path = os.path.join(tempfile.gettempdir(), f"{carpeta_nombre}.zip")
            shutil.make_archive(zip_path.replace('.zip', ''), 'zip', carpeta_temporal)

            # Limpieza
            shutil.rmtree(resultados_dir, ignore_errors=True)
            shutil.rmtree(carpeta_temporal, ignore_errors=True)

            # Enviar archivo ZIP al usuario
            return send_file(zip_path, as_attachment=True)

        except Exception as e:
            return f"Error procesando el archivo: {e}", 500

    return "Archivo inválido. Solo se permiten archivos .mp3", 400


if __name__ == '__main__':
    app.run(debug=True)