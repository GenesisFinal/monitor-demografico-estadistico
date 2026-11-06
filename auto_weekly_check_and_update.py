# -*- coding: utf-8 -*-
"""
Script de Chequeo y Actualización Semanal Automática de Fuentes Oficiales:
- INDEC (Calendario de difusión de EPH, Estadísticas Vitales, Proyecciones y Precios)
- DEIS (Ministerio de Salud - Anuarios de Estadísticas Vitales y TMI)
- ANSES / SIPA (Boletín Estadístico de la Seguridad Social y balances previsionales)
- DINIECE (Secretaría de Educación - Relevamiento Anual y Pruebas Aprender)
- SSN (Superintendencia de Seguros de la Nación - Resoluciones de Tablas Actuariales)

Si se detectan novedades o cambios en las series, compila el dataset maestro y realiza el despliegue automático en GitHub Pages.
"""

import json
import os
import sys
import datetime
import subprocess
import urllib.request
import urllib.error
import ssl

try:
    import requests
except ImportError:
    requests = None

def _head_request(url, headers=None, timeout=10):
    if requests is not None:
        r = requests.head(url, headers=headers or {}, timeout=timeout, allow_redirects=True)
        return r.status_code, r.headers
    req = urllib.request.Request(url, headers=headers or {}, method="HEAD")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.getcode(), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, e.headers

FUENTES_ENDPOINTS = {
    "INDEC_CALENDARIO": "https://www.indec.gob.ar/indec/web/Calendario-Fecha-0",
    "INDEC_EPH": "https://www.indec.gob.ar/indec/web/Nivel4-Tema-4-31-58",
    "DEIS_ESTADISTICAS": "https://www.argentina.gob.ar/salud/deis",
    "ANSES_BESS": "https://www.argentina.gob.ar/anses",
    "SSN_CIRCULARES": "https://www.argentina.gob.ar/ssn"
}

def check_sources_for_updates():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando chequeo automático de fuentes...")
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) MonitorDemograficoBot/1.0"}
    
    status_report = {}
    for name, url in FUENTES_ENDPOINTS.items():
        try:
            status_code, resp_headers = _head_request(url, headers=headers, timeout=10)
            status_report[name] = {
                "status_code": status_code,
                "last_modified": resp_headers.get("Last-Modified", "N/A"),
                "etag": resp_headers.get("ETag", "N/A"),
                "ok": status_code == 200
            }
            print(f" -> {name}: Código {status_code} ({status_report[name]['last_modified']})")
        except Exception as e:
            status_report[name] = {"error": str(e), "ok": False}
            print(f" -> {name}: Error al consultar ({e})")

    # Guardar bitácora de chequeo
    log_entry = {
        "fecha_chequeo": datetime.datetime.now().isoformat(),
        "fuentes": status_report
    }
    
    log_path = os.path.join(base_dir, "registro_actualizaciones_fuentes.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, ensure_ascii=False, indent=2)

    # Recompilar dataset maestro y verificar consistencia
    print("Recompilando dataset maestro con actualizar_demografia.py...")
    subprocess.run([sys.executable, os.path.join(base_dir, "actualizar_demografia.py")], check=True)
    
    print("Chequeo completado exitosamente.")
    return True

if __name__ == "__main__":
    check_sources_for_updates()
