import os
import requests
import json
from flask import Flask, render_template, request, jsonify
import urllib3 # Necesario para deshabilitar advertencias SSL si verify=False

# Deshabilita las advertencias SSL (¡SOLO PARA DESARROLLO/PRUEBAS!).
# En un entorno de producción, DEBES configurar la verificación SSL correctamente.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# --- Configuración de la API de SFA ---
SFA_API_BASE_URL = "https://fa-erry-saasfaprod1.fa.ocs.oraclecloud.com/crmRestApi/resources/11.13.18.05/serviceRequests/"
SFA_USERNAME = "Usuario.Pruebas.integracion"
SFA_PASSWORD = "Entel.123"

# --- Configuración de la API de CPQ ---
# Se actualiza la URL de CPQ para que apunte al mismo endpoint de SFA Service Requests
CPQ_API_BASE_URL = "https://fa-erry-saasfaprod1.fa.ocs.oraclecloud.com/crmRestApi/resources/11.13.18.05/serviceRequests/"
# Se asumen las mismas credenciales que SFA para esta URL
CPQ_USERNAME = "Usuario.Pruebas.integracion"
CPQ_PASSWORD = "Entel.123"


@app.route('/', methods=['GET'])
def index():
    """
    Renderiza la página principal de la aplicación.
    """
    return render_template('index.html')

@app.route('/sign_sfa_sr', methods=['POST'])
def sign_sfa_sr():
    """
    Maneja la solicitud para firmar una Service Request (SR) en SFA.
    Recibe el ID de la SR, construye la URL y el payload,
    luego realiza la llamada a la API de SFA.
    """
    sr_id = request.json.get('sr_id')

    if not sr_id:
        # Retorna un error si no se proporciona el ID de la SR
        return jsonify({"status": "error", "message": "El ID de la SR es requerido."}), 400

    # Construye la URL completa del servicio para la SR específica
    api_url = f"{SFA_API_BASE_URL}{sr_id}"

    # Define las credenciales para la autenticación Basic Auth
    auth_sfa = (SFA_USERNAME, SFA_PASSWORD)

    # Define el payload JSON a enviar para SFA SR
    payload = {
        "cus_FlagSignDocNoCPQ_c": True # Este campo se envía como 'true'
    }

    # Define las cabeceras de la solicitud
    headers = {
        "Content-Type": "application/json"
    }

    try:
        # Realiza la solicitud PATCH a la API de SFA para actualizar el campo
        response = requests.patch(
            api_url,
            auth=auth_sfa,
            headers=headers,
            json=payload,
            verify=False, # Precaución: Desactivado para desarrollo. Reconfigurar para producción.
            timeout=30 # Tiempo de espera en segundos
        )

        # Lanza una excepción HTTPError para respuestas con códigos de estado 4xx/5xx
        response.raise_for_status()

        # Si la solicitud fue exitosa, parsea la respuesta JSON
        response_data = response.json()

        # Verifica el valor del campo cus_FlagSignDocNoCPQ_c en la respuesta
        # Asumimos que la API de SFA devuelve el campo que acabamos de enviar o el estado actualizado
        flag_value = response_data.get("cus_FlagSignDocNoCPQ_c", "No disponible en respuesta")

        # Retorna una respuesta de éxito al frontend
        return jsonify({
            "status": "success",
            "message": f"SR firmada correctamente en SFA. Valor de cus_FlagSignDocNoCPQ_c: {flag_value}",
            "cus_FlagSignDocNoCPQ_c": flag_value
        }), 200

    except requests.exceptions.HTTPError as http_err:
        # Manejo de errores HTTP (ej. 404 Not Found, 401 Unauthorized, 500 Internal Server Error)
        error_message = f"Error HTTP al firmar SR {sr_id} en SFA: {http_err.response.status_code} - {http_err.response.text}"
        app.logger.error(error_message) # Registra el error en los logs de Flask
        return jsonify({"status": "error", "message": error_message}), http_err.response.status_code if http_err.response is not None else 500
    except requests.exceptions.ConnectionError as conn_err:
        # Manejo de errores de conexión (ej. el servidor no está accesible)
        error_message = f"Error de conexión al firmar SR {sr_id} en SFA: {conn_err}"
        app.logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500
    except requests.exceptions.Timeout as timeout_err:
        # Manejo de errores de tiempo de espera
        error_message = f"Tiempo de espera excedido al firmar SR {sr_id} en SFA: {timeout_err}"
        app.logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500
    except requests.exceptions.RequestException as req_err:
        # Manejo de cualquier otro error general de solicitudes
        error_message = f"Error inesperado de solicitud al firmar SR {sr_id} en SFA: {req_err}"
        app.logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500
    except json.JSONDecodeError as json_err:
        # Manejo de errores al decodificar la respuesta JSON
        error_message = f"Error al decodificar la respuesta JSON de SFA: {json_err}. Respuesta: {response.text[:200]}..."
        app.logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500
    except Exception as e:
        # Manejo de cualquier otra excepción no esperada
        error_message = f"Ocurrió un error interno del servidor al firmar SR en SFA: {e}"
        app.logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500

@app.route('/sign_cpq_doc', methods=['POST'])
def sign_cpq_doc():
    """
    Maneja la solicitud para firmar un documento en CPQ.
    Recibe el ID del documento/orden de CPQ, construye la URL y el payload,
    luego realiza la llamada a la API de CPQ.
    """
    # El ID puede venir de 'sr_id' o 'cpq_doc_id', usaremos 'cpq_doc_id' como principal para esta ruta
    cpq_doc_id = request.json.get('cpq_doc_id')

    if not cpq_doc_id:
        return jsonify({"status": "error", "message": "El ID del documento CPQ es requerido."}), 400

    # Construye la URL completa del servicio CPQ para el documento específico
    # Ahora apunta al mismo endpoint de SFA Service Requests
    api_url = f"{CPQ_API_BASE_URL}{cpq_doc_id}"

    # Define las credenciales para la autenticación Basic Auth de CPQ
    auth_cpq = (CPQ_USERNAME, CPQ_PASSWORD)

    # NUEVO PAYLOAD para CPQ (según lo especificado)
    payload = {
        "cus_FirmOK_c": True,
        "cus_approved_business_c": True
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        # Realiza la solicitud PATCH (asumiendo que es una actualización de campos de SR)
        response = requests.patch( # Cambiado de POST a PATCH para actualización parcial
            api_url,
            auth=auth_cpq,
            headers=headers,
            json=payload,
            verify=False, # Precaución: Desactivado para desarrollo. Reconfigurar para producción.
            timeout=30
        )

        response.raise_for_status() # Lanza HTTPError para 4xx/5xx

        response_data = response.json()

        # Verifica el valor del campo cus_FirmOK_c en la respuesta
        firm_ok_value = response_data.get("cus_FirmOK_c", "No disponible en respuesta")

        # Retorna una respuesta de éxito al frontend con el valor del campo
        return jsonify({
            "status": "success",
            "message": f"Documento CPQ '{cpq_doc_id}' enviado correctamente. Valor de cus_FirmOK_c: {firm_ok_value}",
            "cus_FirmOK_c": firm_ok_value
        }), 200

    except requests.exceptions.HTTPError as http_err:
        error_message = f"Error HTTP al firmar documento CPQ {cpq_doc_id}: {http_err.response.status_code} - {http_err.response.text}"
        app.logger.error(error_message)
        # Intenta obtener el mensaje de error del cuerpo de la respuesta si está disponible
        try:
            error_details = http_err.response.json()
            if 'message' in error_details:
                error_message = f"Error CPQ ({http_err.response.status_code}): {error_details['message']}"
            elif 'detail' in error_details:
                 error_message = f"Error CPQ ({http_err.response.status_code}): {error_details['detail']}"
        except json.JSONDecodeError:
            pass # No es JSON, usa el mensaje de error HTTP por defecto

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
    app.run(debug=True, host='0.0.0.0', port=5000)
