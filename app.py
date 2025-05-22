from flask import Flask, request, render_template, send_from_directory, redirect, url_for
import yt_dlp
import os
import subprocess
import shutil

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/downloads/individuales'

# Carpetas
DOWNLOAD_FOLDER = 'static/downloads'
INDIVIDUAL_FOLDER = os.path.join(DOWNLOAD_FOLDER, 'individuales')
ACAPELLAS_FOLDER = os.path.join(DOWNLOAD_FOLDER, 'acapellas')
COOKIES_FILE = 'cookies.txt'

# Crear carpetas necesarias
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(INDIVIDUAL_FOLDER, exist_ok=True)
os.makedirs(ACAPELLAS_FOLDER, exist_ok=True)

# Verificar que FFmpeg esté disponible
def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False

if not check_ffmpeg():
    print("FFmpeg no está instalado. Por favor, instalalo y asegurate de que esté en tu PATH.")
    exit(1)

@app.route('/')
def index():
    archivos = [f for f in os.listdir(INDIVIDUAL_FOLDER) if f.endswith('.mp3')]
    return render_template('index.html', archivos=archivos)

@app.route('/single_download', methods=['POST'])
def single_download():
    url = request.form['youtube_url']
    if not url:
        return "URL inválida", 400

    try:
        with yt_dlp.YoutubeDL({
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(INDIVIDUAL_FOLDER, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }) as ydl:
            ydl.extract_info(url, download=True)
            return redirect(url_for('index'))
    except Exception as e:
        return f"Error al descargar: {str(e)}", 500

@app.route('/playlist_download', methods=['POST'])
def playlist_download():
    url = request.form['playlist_url']
    if not url:
        return "URL de playlist inválida", 400

    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            playlist_title = info.get('title', 'playlist_sin_nombre').replace('/', '_')
            playlist_folder = os.path.join(DOWNLOAD_FOLDER, 'playlists', playlist_title)
            os.makedirs(playlist_folder, exist_ok=True)

        with yt_dlp.YoutubeDL({
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(playlist_folder, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }) as ydl:
            ydl.download([url])

        return redirect(url_for('index'))

    except Exception as e:
        return f"Error al descargar playlist: {str(e)}", 500

@app.route('/subir_y_separar', methods=['POST'])
def subir_y_separar():
    if 'archivo' not in request.files:
        return "No se envió archivo", 400

    archivo = request.files['archivo']
    if archivo.filename == '':
        return "Nombre de archivo vacío", 400

    if archivo and archivo.filename.endswith('.mp3'):
        # Limpiar nombre
        nombre_limpio = archivo.filename.replace("｜", "").replace("|", "").replace("?", "").replace(":", "").strip()
        filepath = os.path.join(INDIVIDUAL_FOLDER, nombre_limpio)
        archivo.save(filepath)

        try:
            # Ejecutar Demucs
            filepath_abs = os.path.abspath(filepath)
            subprocess.run(['python', '-m', 'demucs', filepath_abs], check=True)

            # Carpeta de salida de Demucs
            nombre_base = os.path.splitext(nombre_limpio)[0]
            resultados_dir = os.path.join('extractor', nombre_base)

            # Archivos separados esperados
            vocals = os.path.join(resultados_dir, 'vocals.wav')
            no_vocals = os.path.join(resultados_dir, 'no_vocals.wav')

            if os.path.exists(vocals):
                shutil.move(vocals, os.path.join(ACAPELLAS_FOLDER, f'{nombre_base}.wav'))


            # Limpiar carpeta de salida
            shutil.rmtree(resultados_dir, ignore_errors=True)

        except Exception as e:
            return f"Error procesando el archivo: {e}", 500

        return redirect(url_for('index'))

    return "Archivo inválido. Solo se permiten archivos .mp3", 400

@app.route('/downloads/<path:filename>')
def download_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)