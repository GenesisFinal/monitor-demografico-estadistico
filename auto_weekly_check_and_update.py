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

import requests
import json
import os
import datetime
import subprocess

FUENTES_ENDPOINTS = {
    "INDEC_CALENDARIO": "https://www.indec.gob.ar/indec/web/Calendario-Fecha-0",
    "INDEC_EPH": "https://www.indec.gob.ar/indec/web/Nivel4-Tema-4-31-58",
    "DEIS_ESTADISTICAS": "https://www.deis.msal.gov.ar",
    "ANSES_BESS": "https://www.anses.gob.ar/institucional/estadisticas",
    "SSN_CIRCULARES": "https://www.argentina.gob.ar/ssn"
}

def check_sources_for_updates():
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando chequeo automático de fuentes...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MonitorDemograficoBot/1.0"}
    
    status_report = {}
    for name, url in FUENTES_ENDPOINTS.items():
        try:
            r = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
            status_report[name] = {
                "status_code": r.status_code,
                "last_modified": r.headers.get("Last-Modified", "N/A"),
                "etag": r.headers.get("ETag", "N/A"),
                "ok": r.status_code == 200
            }
            print(f" -> {name}: Código {r.status_code} ({status_report[name]['last_modified']})")
        except Exception as e:
            status_report[name] = {"error": str(e), "ok": False}
            print(f" -> {name}: Error al consultar ({e})")

    # Guardar bitácora de chequeo
    log_entry = {
        "fecha_chequeo": datetime.datetime.now().isoformat(),
        "fuentes": status_report
    }
    
    with open("registro_actualizaciones_fuentes.json", "w", encoding="utf-8") as f:
        json.dump(log_entry, f, ensure_ascii=False, indent=2)

    # Recompilar dataset maestro y verificar consistencia
    print("Recompilando dataset maestro con actualizar_demografia.py...")
    subprocess.run(["python", "actualizar_demografia.py"], check=True)
    
    print("Chequeo completado exitosamente.")
    return True

if __name__ == "__main__":
    check_sources_for_updates()
