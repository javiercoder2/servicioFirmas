import os
import requests
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import urllib3

# Deshabilita las advertencias SSL (¡SOLO PARA DESARROLLO/PRUEBAS!).
# En un entorno de producción, DEBES configurar la verificación SSL correctamente.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# Configuración de la clave secreta para las sesiones de Flask.
# ¡IMPORTANTE!: En producción, genera una clave compleja y almacénala de forma segura
# (ej. como variable de entorno).
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "una_clave_secreta_muy_segura_y_larga_para_entel_firmas_2024")

# --- Credenciales de Usuario (Hardcodeadas como se solicitó) ---
VALID_USERNAME = "entel"
VALID_PASSWORD = "1234"

# --- Configuración de la API: ¡Ahora usa variables de entorno! ---
# Estas variables deben configurarse en Render.
SFA_API_BASE_URL = os.environ.get("SFA_API_BASE_URL")
SFA_USERNAME = os.environ.get("SFA_USERNAME")
SFA_PASSWORD = os.environ.get("SFA_PASSWORD")

CPQ_API_BASE_URL = os.environ.get("CPQ_API_BASE_URL")
CPQ_USERNAME = os.environ.get("CPQ_USERNAME")
CPQ_PASSWORD = os.environ.get("CPQ_PASSWORD")

# Asegúrate de que las variables obligatorias estén definidas
if not all([SFA_API_BASE_URL, SFA_USERNAME, SFA_PASSWORD, CPQ_API_BASE_URL, CPQ_USERNAME, CPQ_PASSWORD]):
    # Para depuración: si no están definidas, usa valores por defecto SOLO en desarrollo local
    # En Render, esto indicaría que no configuraste las variables de entorno.
    print("WARNING: API credentials/URLs are not set as environment variables. Using default local values (DO NOT USE IN PRODUCTION).")
    SFA_API_BASE_URL = SFA_API_BASE_URL or "https://fa-erry-saasfaprod1.fa.ocs.oraclecloud.com/crmRestApi/resources/11.13.18.05/serviceRequests/"
    SFA_USERNAME = SFA_USERNAME or "Usuario.Pruebas.integracion"
    SFA_PASSWORD = SFA_PASSWORD or "Entel.123"
    CPQ_API_BASE_URL = CPQ_API_BASE_URL or "https://fa-erry-saasfaprod1.fa.ocs.oraclecloud.com/crmRestApi/resources/11.13.18.05/serviceRequests/"
    CPQ_USERNAME = CPQ_USERNAME or SFA_USERNAME
    CPQ_PASSWORD = CPQ_PASSWORD or SFA_PASSWORD


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Usuario o contraseña incorrectos.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/', methods=['GET'])
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/sign_sfa_sr', methods=['POST'])
def sign_sfa_sr():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "No autorizado. Por favor, inicie sesión."}), 401

    sr_id = request.json.get('sr_id')
    if not sr_id:
        return jsonify({"status": "error", "message": "El ID de la SR es requerido."}), 400

    api_url = f"{SFA_API_BASE_URL}{sr_id}"
    auth_sfa = (SFA_USERNAME, SFA_PASSWORD)
    payload = {"cus_FlagSignDocNoCPQ_c": True}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.patch(
            api_url,
            auth=auth_sfa,
            headers=headers,
            json=payload,
            verify=False,
            timeout=30
        )
        response.raise_for_status()
        response_data = response.json()
        flag_value = response_data.get("cus_FlagSignDocNoCPQ_c", "No disponible en respuesta")
        return jsonify({
            "status": "success",
            "message": f"SR firmada correctamente en SFA. Valor de cus_FlagSignDocNoCPQ_c: {flag_value}",
            "cus_FlagSignDocNoCPQ_c": flag_value
        }), 200

    except requests.exceptions.HTTPError as http_err:
        error_message = f"Error HTTP al firmar SR {sr_id} en SFA: {http_err.response.status_code} - {http_err.response.text}"
        app.logger.error(error_message)
        try: # Intenta parsear error si es JSON
            error_details = http_err.response.json()
            error_message = f"Error SFA ({http_err.response.status_code}): {error_details.get('message') or error_details.get('detail') or http_err.response.text}"
        except json.JSONDecodeError:
            pass
        return jsonify({"status": "error", "message": error_message}), http_err.response.status_code if http_err.response is not None else 500
    except requests.exceptions.ConnectionError as conn_err:
        error_message = f"Error de conexión al firmar SR {sr_id} en SFA: {conn_err}"
        app.logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500
    except requests.exceptions.Timeout as timeout_err:
        error_message = f"Tiempo de espera excedido al firmar SR {sr_id} en SFA: {timeout_err}"
        app.logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500
    except requests.exceptions.RequestException as req_err:
        error_message = f"Error inesperado de solicitud al firmar SR {sr_id} en SFA: {req_err}"
        app.logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500
    except json.JSONDecodeError as json_err:
        error_message = f"Error al decodificar la respuesta JSON de SFA: {json_err}. Respuesta: {response.text[:200]}..."
        app.logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500
    except Exception as e:
        error_message = f"Ocurrió un error interno del servidor al firmar SR en SFA: {e}"
        app.logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500

@app.route('/sign_cpq_doc', methods=['POST'])
def sign_cpq_doc():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "No autorizado. Por favor, inicie sesión."}), 401

    cpq_doc_id = request.json.get('cpq_doc_id')
    if not cpq_doc_id:
        return jsonify({"status": "error", "message": "El ID del documento CPQ es requerido."}), 400

    api_url = f"{CPQ_API_BASE_URL}{cpq_doc_id}"
    auth_cpq = (CPQ_USERNAME, CPQ_PASSWORD)
    payload = {
        "cus_FirmOK_c": True,
        "cus_approved_business_c": True
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.patch(
            api_url,
            auth=auth_cpq,
            headers=headers,
            json=payload,
            verify=False,
            timeout=30
        )
        response.raise_for_status()
        response_data = response.json()
        firm_ok_value = response_data.get("cus_FirmOK_c", "No disponible en respuesta")
        return jsonify({
            "status": "success",
            "message": f"Documento CPQ '{cpq_doc_id}' enviado correctamente. Valor de cus_FirmOK_c: {firm_ok_value}",
            "cus_FirmOK_c": firm_ok_value
        }), 200

    except requests.exceptions.HTTPError as http_err:
        error_message = f"Error HTTP al firmar documento CPQ {cpq_doc_id}: {http_err.response.status_code} - {http_err.response.text}"
        app.logger.error(error_message)
        try: # Intenta parsear error si es JSON
            error_details = http_err.response.json()
            error_message = f"Error CPQ ({http_err.response.status_code}): {error_details.get('message') or error_details.get('detail') or http_err.response.text}"
        except json.JSONDecodeError:
            pass
        return jsonify({"status": "error", "message": error_message}), http_err.response.status_code if http_err.response is not None else 500
    except requests.exceptions.ConnectionError as conn_err:
        error_message = f"Error de conexión al firmar documento CPQ {cpq_doc_id}: {conn_err}"
        app.logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500
    except requests.exceptions.Timeout as timeout_err:
        error_message = f"Tiempo de espera excedido al firmar documento CPQ {cpq_doc_id}: {timeout_err}"
        app.logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500
    except requests.exceptions.RequestException as req_err:
        error_message = f"Error inesperado de solicitud al firmar documento CPQ {cpq_doc_id}: {req_err}"
        app.logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500
    except json.JSONDecodeError as json_err:
        error_message = f"Error al decodificar la respuesta JSON de CPQ: {json_err}. Respuesta: {response.text[:200]}..."
        app.logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500
    except Exception as e:
        error_message = f"Ocurrió un error interno del servidor al firmar CPQ: {e}"
        app.logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=os.environ.get('PORT', 5000))
