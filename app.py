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
    url = request.form.get('youtube_url')
    if not url or 'youtube.com' not in url and 'youtu.be' not in url:
        return "URL de YouTube inválida", 400

    try:
        # Configuración para extraer información del video
        ydl_info = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False
        }
        
        with yt_dlp.YoutubeDL(ydl_info) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', f'video_{int(time.time())}')
            # Limpieza más exhaustiva del nombre de archivo
            safe_title = re.sub(r'[^\w\-_\. ]', '', title)[:100].strip()
            safe_title = secure_filename(safe_title)
            
            # Directorio de descargas
            os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)
            
            # Ruta temporal única para evitar colisiones
            temp_filename = f"temp_{int(time.time())}_{safe_title}.mp3"
            output_path = os.path.join(DOWNLOADS_FOLDER, temp_filename)
            final_path = os.path.join(DOWNLOADS_FOLDER, f"{safe_title}.mp3")
            
            # Opciones de descarga
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_path.replace('.mp3', '.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
            }
            
            # Descargar el archivo
            with yt_dlp.YoutubeDL(ydl_opts) as ydl_download:
                ydl_download.download([url])
            
            # Renombrar el archivo temporal al nombre final
            if os.path.exists(output_path):
                os.rename(output_path, final_path)
            else:
                # Buscar el archivo con posible extensión diferente
                for f in os.listdir(DOWNLOADS_FOLDER):
                    if f.startswith(f"temp_{int(time.time())}_"):
                        os.rename(os.path.join(DOWNLOADS_FOLDER, f), final_path)
                        break
            
            wait_for_file_release(final_path)
            
            if not os.path.exists(final_path):
                return "Error: No se pudo crear el archivo MP3", 500
                
            # Enviar el archivo al usuario
            response = send_file(
                final_path,
                as_attachment=True,
                download_name=f"{safe_title}.mp3",
                mimetype='audio/mpeg'
            )
            
            # Programar la eliminación del archivo después de enviarlo
            try:
                os.unlink(final_path)
            except:
                pass
                
            return response

    except yt_dlp.utils.DownloadError as e:
        return f"Error al descargar el video: {str(e)}", 500
    except Exception as e:
        return f"Error inesperado: {str(e)} - Tipo: {type(e)}", 500


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