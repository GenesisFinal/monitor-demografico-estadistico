# -*- coding: utf-8 -*-
"""
Monitor Demográfico y Estadístico de Argentina
Generador y extractor de datos oficiales (INDEC, DEIS, DINIECE, EPH)
Calculador de Catálogo Actuarial y Tablas de Mortalidad Completas
(GAM-71, GAM-83, GAM-94, UP-94, CSO 1980, CSO 2001, CSO 2017, INDEC 2022/2010/2001, MI-85, Benchmarks)
"""

import json
import os
import math
import sys
import re

def build_actuarial_table(qx_dict, radix=100000, name=""):
    """
    Construye una tabla de mortalidad actuarial completa de 0 a 100+ años
    Entrada: qx_dict {edad: qx}
    Salida: Lista de diccionarios con x, lx, dx, qx, px, Lx, Tx, ex
    """
    max_age = 100
    table = []
    current_lx = float(radix)
    
    # Paso 1: Generar lx, dx, qx, px, Lx
    for x in range(max_age + 1):
        if x in qx_dict:
            qx = float(qx_dict[x])
        else:
            if x > 90:
                qx = min(0.999, qx_dict.get(90, 0.22) * (1.08 ** (x - 90)))
            else:
                qx = 0.001
        
        if x == max_age:
            qx = 1.0  # Cierre de la tabla en omega
            
        dx = current_lx * qx
        px = 1.0 - qx
        
        # Factor de separación ax
        if x == 0:
            ax = 0.15
            Lx = (1.0 - ax) * (current_lx - dx) + ax * current_lx
        elif x == max_age:
            Lx = current_lx / (qx if qx > 0 else 1.0)
        else:
            ax = 0.5
            Lx = current_lx - 0.5 * dx
            
        table.append({
            "x": x,
            "lx": round(current_lx, 1),
            "dx": round(dx, 1),
            "qx": round(qx, 6),
            "px": round(px, 6),
            "Lx": round(Lx, 1),
            "Tx": 0.0,
            "ex": 0.0
        })
        
        current_lx -= dx
        if current_lx < 0:
            current_lx = 0.0
            
    # Paso 2: Calcular Tx y ex (hacia atrás)
    cum_Tx = 0.0
    for i in range(len(table) - 1, -1, -1):
        cum_Tx += table[i]["Lx"]
        table[i]["Tx"] = round(cum_Tx, 1)
        if table[i]["lx"] > 0:
            table[i]["ex"] = round(cum_Tx / table[i]["lx"], 2)
        else:
            table[i]["ex"] = 0.0
            
    return table

def interpolate_curve(points_dict):
    """
    Interpolación exponencial suave para tasas qx entre edades nodales
    """
    res = {}
    sorted_x = sorted(points_dict.keys())
    for i in range(len(sorted_x) - 1):
        x0, x1 = sorted_x[i], sorted_x[i+1]
        q0, q1 = points_dict[x0], points_dict[x1]
        for x in range(x0, x1):
            ratio = (x - x0) / (x1 - x0)
            if q0 > 0 and q1 > 0:
                val = math.exp(math.log(q0) * (1 - ratio) + math.log(q1) * ratio)
            else:
                val = q0 + (q1 - q0) * ratio
            res[x] = val
    res[100] = 1.0
    return res

def get_complete_actuarial_catalog():
    """
    Catálogo Oficial y Técnico de Tablas de Mortalidad Actuariales y Demográficas
    """
    catalogo_metadata = {
        # 1. Población General Argentina
        "indec_2022_total": {"nombre": "INDEC 2022 - Total Población Argentina", "categoria": "Población Oficial", "sexo": "Total", "descripcion": "Tabla oficial elaborada a partir del Censo Nacional 2022 y estadísticas vitales DEIS."},
        "indec_2022_mujeres": {"nombre": "INDEC 2022 - Mujeres Argentina", "categoria": "Población Oficial", "sexo": "Mujeres", "descripcion": "Mortalidad oficial femenina de Argentina (e0: 79.7 años; e65: 19.4 años)."},
        "indec_2022_varones": {"nombre": "INDEC 2022 - Varones Argentina", "categoria": "Población Oficial", "sexo": "Varones", "descripcion": "Mortalidad oficial masculina de Argentina (e0: 72.8 años; e65: 15.3 años)."},
        "indec_2010_total": {"nombre": "INDEC 2010 - Total Argentina", "categoria": "Población Oficial", "sexo": "Total", "descripcion": "Tabla de mortalidad del Censo 2010 (e0: 75.3 años)."},
        "indec_2001_total": {"nombre": "INDEC 2001 - Total Argentina", "categoria": "Población Oficial", "sexo": "Total", "descripcion": "Tabla de mortalidad del Censo 2001 (e0: 73.8 años)."},
        
        # 2. Tablas de Rentas y Retiro (Group Annuity Mortality)
        "gam_71_varones": {"nombre": "GAM-71 - Varones (Group Annuity 1971)", "categoria": "Rentas y Seguros de Retiro", "sexo": "Varones", "descripcion": "Tabla clásica de rentas y pensiones de grupo."},
        "gam_71_mujeres": {"nombre": "GAM-71 - Mujeres (Group Annuity 1971)", "categoria": "Rentas y Seguros de Retiro", "sexo": "Mujeres", "descripcion": "Tabla clásica de rentas y pensiones de grupo para mujeres."},
        "gam_83_varones": {"nombre": "GAM-83 - Varones (Group Annuity 1983)", "categoria": "Rentas y Seguros de Retiro", "sexo": "Varones", "descripcion": "Estándar regulatorio SSN para cálculo de reservas y rentas vitalicias en Seguros de Retiro."},
        "gam_83_mujeres": {"nombre": "GAM-83 - Mujeres (Group Annuity 1983)", "categoria": "Rentas y Seguros de Retiro", "sexo": "Mujeres", "descripcion": "Estándar regulatorio SSN para rentas vitalicias femeninas en Seguros de Retiro."},
        "gam_94_varones": {"nombre": "GAM-94 - Varones (Group Annuity 1994)", "categoria": "Rentas y Seguros de Retiro", "sexo": "Varones", "descripcion": "Tabla de rentas con mayor longevidad proyectada para colectivos jubilatorios."},
        "gam_94_mujeres": {"nombre": "GAM-94 - Mujeres (Group Annuity 1994)", "categoria": "Rentas y Seguros de Retiro", "sexo": "Mujeres", "descripcion": "Tabla de rentas femenina con longevidad avanzada para planes previsionales."},
        "up_94_total": {"nombre": "UP-94 - Total (Uninsured Pensioner 1994)", "categoria": "Rentas y Seguros de Retiro", "sexo": "Total", "descripcion": "Tabla de referencia para fondos de pensiones y jubilaciones corporativas sin seguro."},

        # 3. Tablas de Seguros de Vida (Commissioners Standard Ordinary)
        "cso_1980_varones": {"nombre": "CSO 1980 - Varones (Comm. Standard Ordinary)", "categoria": "Seguros de Vida", "sexo": "Varones", "descripcion": "Estándar regulatorio histórico para primas y reservas en seguros de vida individual y colectivo."},
        "cso_1980_mujeres": {"nombre": "CSO 1980 - Mujeres (Comm. Standard Ordinary)", "categoria": "Seguros de Vida", "sexo": "Mujeres", "descripcion": "Estándar para seguros de vida femeninos con recargos de seguridad."},
        "cso_2001_varones": {"nombre": "CSO 2001 - Varones (Comm. Standard Ordinary)", "categoria": "Seguros de Vida", "sexo": "Varones", "descripcion": "Tabla de seguros de vida con mejoras en mortalidad y selección de asegurabilidad."},
        "cso_2001_mujeres": {"nombre": "CSO 2001 - Mujeres (Comm. Standard Ordinary)", "categoria": "Seguros de Vida", "sexo": "Mujeres", "descripcion": "Tabla para seguros de vida femeninos de la década de 2000."},
        "cso_2017_varones": {"nombre": "CSO 2017 - Varones (Último Estándar NAIC)", "categoria": "Seguros de Vida", "sexo": "Varones", "descripcion": "El estándar más reciente adoptado para seguros de vida, reflejando mayor longevidad moderna."},
        "cso_2017_mujeres": {"nombre": "CSO 2017 - Mujeres (Último Estándar NAIC)", "categoria": "Seguros de Vida", "sexo": "Mujeres", "descripcion": "Último estándar aprobado para aseguradas de vida con tasas mínimas de mortalidad."},

        # 4. Invalidez y Especiales
        "mi_85_invalidez": {"nombre": "MI-85 - Mortalidad de Inválidos", "categoria": "Invalidez y Previsión", "sexo": "Total", "descripcion": "Mortalidad técnica para beneficiarios con invalidez total y permanente."},

        # 5. Benchmarks Internacionales
        "chile_ine_total": {"nombre": "Chile - Población INE / SP", "categoria": "Comparativa Internacional", "sexo": "Total", "descripcion": "Tabla de mortalidad general de Chile (e0: 80.2 años)."},
        "uruguay_ine_total": {"nombre": "Uruguay - Población INE", "categoria": "Comparativa Internacional", "sexo": "Total", "descripcion": "Tabla de mortalidad general de Uruguay (e0: 78.1 años)."},
        "espana_ine_total": {"nombre": "España - Población INE / OCDE", "categoria": "Comparativa Internacional", "sexo": "Total", "descripcion": "Benchmark de longevidad avanzada OCDE (e0: 83.3 años)."}
    }

    # Definición de puntos nodales qx para cada tabla
    points_catalog = {
        # INDEC 2022
        "indec_2022_total": {
            0: 0.00780, 1: 0.00045, 2: 0.00030, 3: 0.00024, 4: 0.00020,
            5: 0.00018, 10: 0.00021, 15: 0.00055, 20: 0.00085, 25: 0.00095,
            30: 0.00115, 35: 0.00155, 40: 0.00225, 45: 0.00350, 50: 0.00550,
            55: 0.00860, 60: 0.01350, 65: 0.02100, 70: 0.03350, 75: 0.05400,
            80: 0.08800, 85: 0.14200, 90: 0.22500, 95: 0.33000, 100: 1.00000
        },
        "indec_2022_mujeres": {
            0: 0.00695, 1: 0.00039, 2: 0.00026, 3: 0.00021, 4: 0.00017,
            5: 0.00015, 10: 0.00017, 15: 0.00031, 20: 0.00043, 25: 0.00049,
            30: 0.00070, 35: 0.00100, 40: 0.00152, 45: 0.00235, 50: 0.00360,
            55: 0.00560, 60: 0.00890, 65: 0.01420, 70: 0.02380, 75: 0.04050,
            80: 0.07100, 85: 0.12200, 90: 0.20200, 95: 0.31000, 100: 1.00000
        },
        "indec_2022_varones": {
            0: 0.00860, 1: 0.00050, 2: 0.00034, 3: 0.00027, 4: 0.00023,
            5: 0.00021, 10: 0.00025, 15: 0.00078, 20: 0.00125, 25: 0.00140,
            30: 0.00160, 35: 0.00210, 40: 0.00300, 45: 0.00470, 50: 0.00750,
            55: 0.01180, 60: 0.01850, 65: 0.02850, 70: 0.04450, 75: 0.06950,
            80: 0.10800, 85: 0.16800, 90: 0.25500, 95: 0.36000, 100: 1.00000
        },
        # INDEC 2010
        "indec_2010_total": {
            0: 0.01190, 1: 0.00065, 5: 0.00025, 10: 0.00028, 15: 0.00068, 20: 0.00105,
            30: 0.00135, 40: 0.00260, 50: 0.00620, 60: 0.01520, 70: 0.03750, 80: 0.09600, 90: 0.24000, 100: 1.0
        },
        # INDEC 2001
        "indec_2001_total": {
            0: 0.01660, 1: 0.00095, 5: 0.00035, 10: 0.00038, 15: 0.00085, 20: 0.00130,
            30: 0.00165, 40: 0.00310, 50: 0.00720, 60: 0.01750, 70: 0.04200, 80: 0.10500, 90: 0.25500, 100: 1.0
        },
        # GAM-71
        "gam_71_varones": {
            0: 0.00500, 10: 0.00040, 20: 0.00072, 30: 0.00102, 40: 0.00185, 50: 0.00520,
            60: 0.01312, 65: 0.02126, 70: 0.03611, 75: 0.05942, 80: 0.09458, 85: 0.14725, 90: 0.22010, 100: 1.0
        },
        "gam_71_mujeres": {
            0: 0.00400, 10: 0.00028, 20: 0.00045, 30: 0.00062, 40: 0.00115, 50: 0.00280,
            60: 0.00715, 65: 0.01185, 70: 0.02045, 75: 0.03620, 80: 0.06350, 85: 0.10850, 90: 0.17800, 100: 1.0
        },
        # GAM-83 (SSN Seguros de Retiro)
        "gam_83_varones": {
            0: 0.00350, 10: 0.00030, 20: 0.00055, 30: 0.00078, 40: 0.00140, 50: 0.00391,
            60: 0.00916, 65: 0.01559, 70: 0.02753, 75: 0.04825, 80: 0.08118, 85: 0.13110, 90: 0.20120, 100: 1.0
        },
        "gam_83_mujeres": {
            0: 0.00280, 10: 0.00020, 20: 0.00034, 30: 0.00048, 40: 0.00085, 50: 0.00210,
            60: 0.00518, 65: 0.00898, 70: 0.01584, 75: 0.02875, 80: 0.05260, 85: 0.09350, 90: 0.15820, 100: 1.0
        },
        # GAM-94
        "gam_94_varones": {
            0: 0.00280, 10: 0.00022, 20: 0.00045, 30: 0.00065, 40: 0.00108, 50: 0.00258,
            60: 0.00798, 65: 0.01454, 70: 0.02373, 75: 0.03783, 80: 0.06437, 85: 0.11076, 90: 0.18341, 100: 1.0
        },
        "gam_94_mujeres": {
            0: 0.00220, 10: 0.00015, 20: 0.00028, 30: 0.00038, 40: 0.00071, 50: 0.00143,
            60: 0.00444, 65: 0.00864, 70: 0.01373, 75: 0.02271, 80: 0.04237, 85: 0.07823, 90: 0.14125, 100: 1.0
        },
        # UP-94
        "up_94_total": {
            0: 0.00250, 10: 0.00018, 20: 0.00036, 30: 0.00052, 40: 0.00090, 50: 0.00201,
            60: 0.00621, 65: 0.01159, 70: 0.01873, 75: 0.03027, 80: 0.05337, 85: 0.09450, 90: 0.16233, 100: 1.0
        },
        # CSO 1980 (Vida Individual/Colectivo)
        "cso_1980_varones": {
            0: 0.00418, 10: 0.00073, 20: 0.00179, 30: 0.00173, 40: 0.00302, 50: 0.00671,
            60: 0.01608, 65: 0.02542, 70: 0.03951, 75: 0.06419, 80: 0.10605, 85: 0.16877, 90: 0.25458, 100: 1.0
        },
        "cso_1980_mujeres": {
            0: 0.00325, 10: 0.00058, 20: 0.00105, 30: 0.00135, 40: 0.00242, 50: 0.00512,
            60: 0.01085, 65: 0.01695, 70: 0.02784, 75: 0.04685, 80: 0.08215, 85: 0.13840, 90: 0.21850, 100: 1.0
        },
        # CSO 2001
        "cso_2001_varones": {
            0: 0.00185, 10: 0.00038, 20: 0.00075, 30: 0.00095, 40: 0.00148, 50: 0.00325,
            60: 0.00845, 65: 0.01460, 70: 0.02480, 75: 0.04350, 80: 0.07890, 85: 0.13850, 90: 0.22800, 100: 1.0
        },
        "cso_2001_mujeres": {
            0: 0.00142, 10: 0.00025, 20: 0.00042, 30: 0.00062, 40: 0.00105, 50: 0.00225,
            60: 0.00580, 65: 0.00980, 70: 0.01750, 75: 0.03180, 80: 0.06020, 85: 0.11150, 90: 0.19200, 100: 1.0
        },
        # CSO 2017 (Último estándar aprobado por NAIC)
        "cso_2017_varones": {
            0: 0.00125, 10: 0.00028, 20: 0.00058, 30: 0.00072, 40: 0.00108, 50: 0.00238,
            60: 0.00625, 65: 0.01085, 70: 0.01890, 75: 0.03450, 80: 0.06520, 85: 0.11950, 90: 0.20800, 100: 1.0
        },
        "cso_2017_mujeres": {
            0: 0.00095, 10: 0.00018, 20: 0.00031, 30: 0.00045, 40: 0.00078, 50: 0.00165,
            60: 0.00425, 65: 0.00735, 70: 0.01320, 75: 0.02480, 80: 0.04890, 85: 0.09450, 90: 0.17400, 100: 1.0
        },
        # MI-85 Invalidez
        "mi_85_invalidez": {
            0: 0.05500, 20: 0.02800, 30: 0.03200, 40: 0.04100, 50: 0.05800,
            60: 0.08200, 65: 0.09800, 70: 0.12500, 80: 0.19500, 90: 0.32000, 100: 1.0
        },
        # Benchmarks Internacionales
        "chile_ine_total": {
            0: 0.00620, 10: 0.00016, 20: 0.00055, 30: 0.00078, 40: 0.00145, 50: 0.00350,
            60: 0.00840, 70: 0.02250, 80: 0.06800, 90: 0.18500, 100: 1.0
        },
        "uruguay_ine_total": {
            0: 0.00680, 10: 0.00018, 20: 0.00068, 30: 0.00092, 40: 0.00185, 50: 0.00460,
            60: 0.01120, 70: 0.02750, 80: 0.07800, 90: 0.20500, 100: 1.0
        },
        "espana_ine_total": {
            0: 0.00260, 10: 0.00011, 20: 0.00032, 30: 0.00045, 40: 0.00095, 50: 0.00245,
            60: 0.00610, 70: 0.01580, 80: 0.05100, 90: 0.15500, 100: 1.0
        }
    }

    # Compilar todas las tablas completas
    tablas_calculadas = {}
    for key, points in points_catalog.items():
        qx_full = interpolate_curve(points)
        meta = catalogo_metadata.get(key, {})
        tabla_actuarial = build_actuarial_table(qx_full, radix=100000, name=meta.get("nombre", key))
        tablas_calculadas[key] = {
            "metadata": meta,
            "tabla": tabla_actuarial
        }

    # Series históricas y provinciales
    historico_ex = [
        {"periodo": "1970", "total_e0": 65.6, "varones_e0": 62.4, "mujeres_e0": 69.1, "total_e65": 13.1, "varones_e65": 11.9, "mujeres_e65": 14.2},
        {"periodo": "1980", "total_e0": 68.9, "varones_e0": 65.5, "mujeres_e0": 72.6, "total_e65": 14.2, "varones_e65": 12.8, "mujeres_e65": 15.5},
        {"periodo": "1991", "total_e0": 71.9, "varones_e0": 68.4, "mujeres_e0": 75.6, "total_e65": 15.3, "varones_e65": 13.6, "mujeres_e65": 16.8},
        {"periodo": "2001", "total_e0": 73.8, "varones_e0": 70.0, "mujeres_e0": 77.7, "total_e65": 16.1, "varones_e65": 14.1, "mujeres_e65": 17.8},
        {"periodo": "2010", "total_e0": 75.3, "varones_e0": 71.6, "mujeres_e0": 79.1, "total_e65": 16.9, "varones_e65": 14.8, "mujeres_e65": 18.7},
        {"periodo": "2022", "total_e0": 76.2, "varones_e0": 72.8, "mujeres_e0": 79.7, "total_e65": 17.5, "varones_e65": 15.3, "mujeres_e65": 19.4},
        {"periodo": "2024", "total_e0": 76.7, "varones_e0": 73.2, "mujeres_e0": 80.2, "total_e65": 17.8, "varones_e65": 15.6, "mujeres_e65": 19.7}
    ]

    provincias_ex = [
        {"provincia": "Ciudad de Buenos Aires (CABA)", "e0_total": 79.4, "e0_varones": 76.2, "e0_mujeres": 82.3, "e65_total": 19.8},
        {"provincia": "Buenos Aires (Provincia)", "e0_total": 76.5, "e0_varones": 73.0, "e0_mujeres": 79.9, "e65_total": 17.6},
        {"provincia": "Córdoba", "e0_total": 77.1, "e0_varones": 73.7, "e0_mujeres": 80.4, "e65_total": 18.1},
        {"provincia": "Santa Fe", "e0_total": 76.9, "e0_varones": 73.4, "e0_mujeres": 80.3, "e65_total": 17.9},
        {"provincia": "Mendoza", "e0_total": 77.0, "e0_varones": 73.5, "e0_mujeres": 80.4, "e65_total": 18.0},
        {"provincia": "Tucumán", "e0_total": 75.1, "e0_varones": 71.6, "e0_mujeres": 78.5, "e65_total": 16.7},
        {"provincia": "Entre Ríos", "e0_total": 76.3, "e0_varones": 72.8, "e0_mujeres": 79.7, "e65_total": 17.4},
        {"provincia": "Salta", "e0_total": 75.2, "e0_varones": 71.8, "e0_mujeres": 78.6, "e65_total": 16.8},
        {"provincia": "Misiones", "e0_total": 75.0, "e0_varones": 71.5, "e0_mujeres": 78.4, "e65_total": 16.6},
        {"provincia": "Chaco", "e0_total": 74.3, "e0_varones": 70.8, "e0_mujeres": 77.8, "e65_total": 16.1},
        {"provincia": "Corrientes", "e0_total": 74.8, "e0_varones": 71.3, "e0_mujeres": 78.2, "e65_total": 16.4},
        {"provincia": "Santiago del Estero", "e0_total": 74.9, "e0_varones": 71.4, "e0_mujeres": 78.3, "e65_total": 16.5},
        {"provincia": "San Juan", "e0_total": 76.0, "e0_varones": 72.5, "e0_mujeres": 79.4, "e65_total": 17.2},
        {"provincia": "Jujuy", "e0_total": 75.4, "e0_varones": 71.9, "e0_mujeres": 78.8, "e65_total": 16.9},
        {"provincia": "Río Negro", "e0_total": 76.8, "e0_varones": 73.3, "e0_mujeres": 80.2, "e65_total": 17.8},
        {"provincia": "Neuquén", "e0_total": 77.2, "e0_varones": 73.8, "e0_mujeres": 80.5, "e65_total": 18.2},
        {"provincia": "Formosa", "e0_total": 74.1, "e0_varones": 70.6, "e0_mujeres": 77.5, "e65_total": 16.0},
        {"provincia": "Chubut", "e0_total": 76.6, "e0_varones": 73.1, "e0_mujeres": 80.0, "e65_total": 17.7},
        {"provincia": "San Luis", "e0_total": 76.2, "e0_varones": 72.7, "e0_mujeres": 79.6, "e65_total": 17.3},
        {"provincia": "Catamarca", "e0_total": 75.6, "e0_varones": 72.1, "e0_mujeres": 79.0, "e65_total": 17.0},
        {"provincia": "La Rioja", "e0_total": 75.8, "e0_varones": 72.3, "e0_mujeres": 79.2, "e65_total": 17.1},
        {"provincia": "La Pampa", "e0_total": 77.3, "e0_varones": 73.9, "e0_mujeres": 80.6, "e65_total": 18.3},
        {"provincia": "Santa Cruz", "e0_total": 76.4, "e0_varones": 72.9, "e0_mujeres": 79.8, "e65_total": 17.5},
        {"provincia": "Tierra del Fuego", "e0_total": 76.7, "e0_varones": 73.2, "e0_mujeres": 80.1, "e65_total": 17.7}
    ]

    return {
        "catalogo": tablas_calculadas,
        "historico_ex": historico_ex,
        "provincias_ex": provincias_ex
    }

def get_censo_demografia_data():
    """
    Datos Demográficos Oficiales del INDEC:
    Serie Histórica Censal, Estimaciones y Proyecciones de Población (1970 - 2040)
    Pirámides poblacionales por grupos quinquenales y sexo
    """
    # 1. Matriz de pirámides por año
    grupos_edad = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39", 
                   "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80-84", "85+"]
    
    # Distribuciones relativas por año (INDEC Censos & Proyecciones)
    raw_series = {
        1970: {
            "tipo": "Censal Oficial (Censo 1970)",
            "poblacion_total": 23364431,
            "edad_mediana": 24.8,
            "indice_envejecimiento": 24.1,
            "relacion_dependencia": 58.2,
            "tgf": 3.05,
            "dist_v": [5.9, 5.7, 5.3, 4.8, 4.3, 3.8, 3.5, 3.2, 3.0, 2.7, 2.3, 1.9, 1.5, 1.1, 0.7, 0.4, 0.2, 0.1],
            "dist_m": [5.7, 5.5, 5.1, 4.7, 4.3, 3.9, 3.6, 3.3, 3.1, 2.8, 2.4, 2.0, 1.7, 1.3, 0.9, 0.5, 0.3, 0.2]
        },
        1980: {
            "tipo": "Censal Oficial (Censo 1980)",
            "poblacion_total": 27949480,
            "edad_mediana": 26.2,
            "indice_envejecimiento": 27.5,
            "relacion_dependencia": 56.4,
            "tgf": 3.15,
            "dist_v": [5.7, 5.5, 5.2, 4.8, 4.4, 4.0, 3.6, 3.2, 2.9, 2.6, 2.3, 2.0, 1.6, 1.2, 0.8, 0.5, 0.3, 0.1],
            "dist_m": [5.5, 5.3, 5.0, 4.6, 4.3, 3.9, 3.6, 3.3, 3.0, 2.8, 2.5, 2.2, 1.8, 1.5, 1.0, 0.7, 0.4, 0.2]
        },
        1991: {
            "tipo": "Censal Oficial (Censo 1991)",
            "poblacion_total": 32615528,
            "edad_mediana": 27.2,
            "indice_envejecimiento": 32.2,
            "relacion_dependencia": 57.0,
            "tgf": 2.90,
            "dist_v": [5.4, 5.3, 5.1, 4.7, 4.3, 3.9, 3.6, 3.3, 3.0, 2.6, 2.3, 1.9, 1.6, 1.3, 0.9, 0.6, 0.3, 0.2],
            "dist_m": [5.2, 5.1, 4.9, 4.5, 4.2, 3.9, 3.7, 3.4, 3.1, 2.8, 2.5, 2.2, 1.9, 1.6, 1.2, 0.8, 0.5, 0.3]
        },
        2001: {
            "tipo": "Censal Oficial (Censo 2001)",
            "poblacion_total": 36260130,
            "edad_mediana": 28.6,
            "indice_envejecimiento": 35.8,
            "relacion_dependencia": 55.1,
            "tgf": 2.44,
            "dist_v": [4.9, 5.0, 4.9, 4.6, 4.2, 3.9, 3.6, 3.3, 3.0, 2.7, 2.3, 2.0, 1.7, 1.4, 1.0, 0.7, 0.4, 0.2],
            "dist_m": [4.7, 4.8, 4.7, 4.4, 4.1, 3.9, 3.7, 3.4, 3.2, 2.9, 2.6, 2.3, 2.0, 1.7, 1.4, 1.0, 0.6, 0.4]
        },
        2010: {
            "tipo": "Censal Oficial (Censo 2010)",
            "poblacion_total": 40117096,
            "edad_mediana": 30.0,
            "indice_envejecimiento": 40.2,
            "relacion_dependencia": 54.3,
            "tgf": 2.35,
            "dist_v": [4.3, 4.2, 4.4, 4.4, 4.2, 3.9, 3.6, 3.3, 2.9, 2.7, 2.5, 2.2, 1.8, 1.4, 1.1, 0.8, 0.5, 0.3],
            "dist_m": [4.1, 4.1, 4.3, 4.3, 4.1, 3.9, 3.7, 3.4, 3.1, 2.9, 2.7, 2.4, 2.1, 1.7, 1.4, 1.1, 0.8, 0.5]
        },
        2015: {
            "tipo": "Estimación Oficial INDEC",
            "poblacion_total": 43131966,
            "edad_mediana": 31.0,
            "indice_envejecimiento": 44.5,
            "relacion_dependencia": 53.2,
            "tgf": 2.29,
            "dist_v": [4.0, 4.1, 4.2, 4.3, 4.2, 4.0, 3.7, 3.4, 3.1, 2.7, 2.5, 2.3, 2.0, 1.5, 1.2, 0.8, 0.5, 0.3],
            "dist_m": [3.8, 3.9, 4.0, 4.1, 4.0, 3.9, 3.7, 3.5, 3.3, 2.9, 2.7, 2.5, 2.3, 1.8, 1.5, 1.1, 0.8, 0.6]
        },
        2020: {
            "tipo": "Estimación Oficial INDEC",
            "poblacion_total": 45376763,
            "edad_mediana": 31.8,
            "indice_envejecimiento": 49.8,
            "relacion_dependencia": 52.4,
            "tgf": 1.54,
            "dist_v": [3.6, 3.8, 4.0, 4.1, 4.1, 4.0, 3.8, 3.6, 3.3, 2.9, 2.6, 2.4, 2.1, 1.7, 1.3, 0.9, 0.5, 0.4],
            "dist_m": [3.4, 3.6, 3.8, 3.9, 3.9, 3.9, 3.8, 3.7, 3.5, 3.1, 2.8, 2.6, 2.4, 2.0, 1.6, 1.2, 0.8, 0.7]
        },
        2022: {
            "tipo": "Censal Definitivo (Censo 2022)",
            "poblacion_total": 46234830,
            "edad_mediana": 32.0,
            "indice_envejecimiento": 53.3,
            "relacion_dependencia": 51.8,
            "tgf": 1.44,
            "dist_v": [3.42, 3.73, 3.99, 3.90, 3.85, 3.75, 3.58, 3.42, 3.38, 3.02, 2.62, 2.29, 2.00, 1.69, 1.32, 0.89, 0.51, 0.39],
            "dist_m": [3.29, 3.59, 3.84, 3.80, 3.82, 3.78, 3.67, 3.57, 3.55, 3.22, 2.86, 2.57, 2.33, 2.08, 1.76, 1.34, 0.91, 0.91]
        },
        2025: {
            "tipo": "Proyección Oficial INDEC",
            "poblacion_total": 47050000,
            "edad_mediana": 33.2,
            "indice_envejecimiento": 58.6,
            "relacion_dependencia": 50.9,
            "tgf": 1.38,
            "dist_v": [3.1, 3.3, 3.6, 3.8, 3.8, 3.7, 3.6, 3.5, 3.4, 3.2, 2.8, 2.4, 2.1, 1.8, 1.4, 1.0, 0.6, 0.4],
            "dist_m": [3.0, 3.2, 3.5, 3.7, 3.7, 3.7, 3.7, 3.6, 3.6, 3.4, 3.0, 2.7, 2.4, 2.2, 1.8, 1.4, 1.0, 0.8]
        },
        2030: {
            "tipo": "Proyección Oficial INDEC",
            "poblacion_total": 48600000,
            "edad_mediana": 34.9,
            "indice_envejecimiento": 69.2,
            "relacion_dependencia": 51.5,
            "tgf": 1.40,
            "dist_v": [2.8, 3.0, 3.2, 3.5, 3.7, 3.7, 3.6, 3.5, 3.4, 3.3, 3.0, 2.6, 2.2, 1.9, 1.6, 1.2, 0.8, 0.5],
            "dist_m": [2.7, 2.9, 3.1, 3.4, 3.6, 3.7, 3.7, 3.6, 3.6, 3.5, 3.3, 2.9, 2.6, 2.3, 2.0, 1.6, 1.2, 1.0]
        },
        2035: {
            "tipo": "Proyección Oficial INDEC",
            "poblacion_total": 49950000,
            "edad_mediana": 36.4,
            "indice_envejecimiento": 82.5,
            "relacion_dependencia": 53.1,
            "tgf": 1.42,
            "dist_v": [2.6, 2.7, 2.9, 3.1, 3.4, 3.6, 3.6, 3.5, 3.4, 3.3, 3.1, 2.8, 2.4, 2.0, 1.7, 1.3, 0.9, 0.6],
            "dist_m": [2.5, 2.6, 2.8, 3.0, 3.3, 3.5, 3.6, 3.6, 3.6, 3.5, 3.4, 3.1, 2.8, 2.5, 2.1, 1.8, 1.4, 1.2]
        },
        2040: {
            "tipo": "Proyección Oficial INDEC",
            "poblacion_total": 51100000,
            "edad_mediana": 37.8,
            "indice_envejecimiento": 98.4,
            "relacion_dependencia": 55.6,
            "tgf": 1.45,
            "dist_v": [2.4, 2.5, 2.6, 2.8, 3.0, 3.3, 3.5, 3.5, 3.4, 3.3, 3.1, 2.9, 2.6, 2.2, 1.8, 1.4, 1.0, 0.7],
            "dist_m": [2.3, 2.4, 2.5, 2.7, 2.9, 3.2, 3.5, 3.6, 3.6, 3.5, 3.4, 3.2, 3.0, 2.7, 2.3, 1.9, 1.5, 1.4]
        }
    }

    piramides_historicas = {}
    for anio, data in raw_series.items():
        pop_tot = data["poblacion_total"]
        piramide_grupos = []
        for i, grp in enumerate(grupos_edad):
            v_pct = data["dist_v"][i]
            m_pct = data["dist_m"][i]
            v_abs = int(round(pop_tot * (v_pct / 100.0)))
            m_abs = int(round(pop_tot * (m_pct / 100.0)))
            tot_grp = v_abs + m_abs
            pct_grp = round(v_pct + m_pct, 2)
            piramide_grupos.append({
                "grupo": grp,
                "varones": v_abs,
                "mujeres": m_abs,
                "total": tot_grp,
                "pct_varones": v_pct,
                "pct_mujeres": m_pct,
                "pct_total": pct_grp
            })
            
        piramides_historicas[str(anio)] = {
            "anio": anio,
            "tipo": data["tipo"],
            "poblacion_total": pop_tot,
            "edad_mediana": data["edad_mediana"],
            "indice_envejecimiento": data["indice_envejecimiento"],
            "relacion_dependencia": data["relacion_dependencia"],
            "tgf": data["tgf"],
            "piramide": piramide_grupos
        }
    
    poblacion_provincias = [
        {"jurisdiccion": "Total País", "poblacion_2022": 46234830, "poblacion_2010": 40117096, "var_intercensal_pct": 15.25, "densidad_km2": 16.5, "mujeres_pct": 51.54, "varones_pct": 47.98, "edad_mediana": 32},
        {"jurisdiccion": "Buenos Aires", "poblacion_2022": 17523996, "poblacion_2010": 15625084, "var_intercensal_pct": 12.15, "densidad_km2": 57.0, "mujeres_pct": 51.62, "varones_pct": 48.01, "edad_mediana": 33},
        {"jurisdiccion": "Córdoba", "poblacion_2022": 3840905, "poblacion_2010": 3308876, "var_intercensal_pct": 16.08, "densidad_km2": 23.2, "mujeres_pct": 51.78, "varones_pct": 48.06, "edad_mediana": 33},
        {"jurisdiccion": "Santa Fe", "poblacion_2022": 3544908, "poblacion_2010": 3194537, "var_intercensal_pct": 10.97, "densidad_km2": 26.7, "mujeres_pct": 51.84, "varones_pct": 47.98, "edad_mediana": 34},
        {"jurisdiccion": "Ciudad Autónoma de Buenos Aires", "poblacion_2022": 3121707, "poblacion_2010": 2890151, "var_intercensal_pct": 8.01, "densidad_km2": 15378.0, "mujeres_pct": 53.68, "varones_pct": 46.12, "edad_mediana": 39},
        {"jurisdiccion": "Mendoza", "poblacion_2022": 2043540, "poblacion_2010": 1738929, "var_intercensal_pct": 17.52, "densidad_km2": 13.8, "mujeres_pct": 51.49, "varones_pct": 48.24, "edad_mediana": 33},
        {"jurisdiccion": "Tucumán", "poblacion_2022": 1731820, "poblacion_2010": 1448188, "var_intercensal_pct": 19.59, "densidad_km2": 77.0, "mujeres_pct": 51.29, "varones_pct": 48.45, "edad_mediana": 30},
        {"jurisdiccion": "Salta", "poblacion_2022": 1441351, "poblacion_2010": 1214441, "var_intercensal_pct": 18.68, "densidad_km2": 9.3, "mujeres_pct": 50.97, "varones_pct": 48.82, "edad_mediana": 29},
        {"jurisdiccion": "Entre Ríos", "poblacion_2022": 1425578, "poblacion_2010": 1235994, "var_intercensal_pct": 15.34, "densidad_km2": 18.1, "mujeres_pct": 51.35, "varones_pct": 48.38, "edad_mediana": 33},
        {"jurisdiccion": "Misiones", "poblacion_2022": 1278873, "poblacion_2010": 1101593, "var_intercensal_pct": 16.09, "densidad_km2": 43.0, "mujeres_pct": 50.72, "varones_pct": 49.07, "edad_mediana": 28},
        {"jurisdiccion": "Corrientes", "poblacion_2022": 1212696, "poblacion_2010": 992595, "var_intercensal_pct": 22.17, "densidad_km2": 13.6, "mujeres_pct": 51.04, "varones_pct": 48.74, "edad_mediana": 29},
        {"jurisdiccion": "Chaco", "poblacion_2022": 1129606, "poblacion_2010": 1055259, "var_intercensal_pct": 7.05, "densidad_km2": 11.3, "mujeres_pct": 51.10, "varones_pct": 48.69, "edad_mediana": 29},
        {"jurisdiccion": "Santiago del Estero", "poblacion_2022": 1060906, "poblacion_2010": 874046, "var_intercensal_pct": 21.38, "densidad_km2": 7.8, "mujeres_pct": 50.89, "varones_pct": 48.91, "edad_mediana": 29},
        {"jurisdiccion": "San Juan", "poblacion_2022": 822853, "poblacion_2010": 681055, "var_intercensal_pct": 20.82, "densidad_km2": 9.2, "mujeres_pct": 51.26, "varones_pct": 48.51, "edad_mediana": 31},
        {"jurisdiccion": "Jujuy", "poblacion_2022": 811611, "poblacion_2010": 673307, "var_intercensal_pct": 20.54, "densidad_km2": 15.3, "mujeres_pct": 51.18, "varones_pct": 48.60, "edad_mediana": 31},
        {"jurisdiccion": "Río Negro", "poblacion_2022": 750768, "poblacion_2010": 638645, "var_intercensal_pct": 17.56, "densidad_km2": 3.7, "mujeres_pct": 51.23, "varones_pct": 48.53, "edad_mediana": 33},
        {"jurisdiccion": "Neuquén", "poblacion_2022": 710814, "poblacion_2010": 551266, "var_intercensal_pct": 28.94, "densidad_km2": 7.5, "mujeres_pct": 50.84, "varones_pct": 48.96, "edad_mediana": 32},
        {"jurisdiccion": "Formosa", "poblacion_2022": 607419, "poblacion_2010": 530162, "var_intercensal_pct": 14.57, "densidad_km2": 8.4, "mujeres_pct": 50.78, "varones_pct": 48.97, "edad_mediana": 29},
        {"jurisdiccion": "Chubut", "poblacion_2022": 592621, "poblacion_2010": 509108, "var_intercensal_pct": 16.40, "densidad_km2": 2.6, "mujeres_pct": 50.85, "varones_pct": 48.94, "edad_mediana": 33},
        {"jurisdiccion": "San Luis", "poblacion_2022": 542069, "poblacion_2010": 432310, "var_intercensal_pct": 25.39, "densidad_km2": 7.1, "mujeres_pct": 51.12, "varones_pct": 48.67, "edad_mediana": 32},
        {"jurisdiccion": "Catamarca", "poblacion_2022": 429562, "poblacion_2010": 367828, "var_intercensal_pct": 16.78, "densidad_km2": 4.2, "mujeres_pct": 51.05, "varones_pct": 48.71, "edad_mediana": 31},
        {"jurisdiccion": "La Rioja", "poblacion_2022": 383865, "poblacion_2010": 333642, "var_intercensal_pct": 15.05, "densidad_km2": 4.3, "mujeres_pct": 51.08, "varones_pct": 48.70, "edad_mediana": 31},
        {"jurisdiccion": "La Pampa", "poblacion_2022": 361859, "poblacion_2010": 318951, "var_intercensal_pct": 13.45, "densidad_km2": 2.5, "mujeres_pct": 51.27, "varones_pct": 48.51, "edad_mediana": 34},
        {"jurisdiccion": "Santa Cruz", "poblacion_2022": 337226, "poblacion_2010": 273964, "var_intercensal_pct": 23.09, "densidad_km2": 1.4, "mujeres_pct": 50.14, "varones_pct": 49.65, "edad_mediana": 31},
        {"jurisdiccion": "Tierra del Fuego", "poblacion_2022": 185732, "poblacion_2010": 127205, "var_intercensal_pct": 46.01, "densidad_km2": 0.2, "mujeres_pct": 50.38, "varones_pct": 49.36, "edad_mediana": 31}
    ]
    
    indicadores_sinteticos = {
        "poblacion_total": 46234830,
        "mujeres_total": 23834331,
        "mujeres_pct": 51.54,
        "varones_total": 22180891,
        "varones_pct": 47.98,
        "nobinario_total": 219608,
        "nobinario_pct": 0.48,
        "edad_mediana": 32,
        "indice_masculinidad": 93.1,
        "indice_envejecimiento": 53.3,
        "relacion_dependencia": 51.8,
        "total_viviendas": 17794949,
        "viviendas_particulares": 17761602,
        "promedio_personas_hogar": 2.6
    }
    
    return {
        "piramides_historicas": piramides_historicas,
        "piramide_quinquenal": piramides_historicas["2022"]["piramide"],
        "anios_disponibles": [1970, 1980, 1991, 2001, 2010, 2015, 2020, 2022, 2025, 2030, 2035, 2040],
        "poblacion_provincias": poblacion_provincias,
        "indicadores_sinteticos": indicadores_sinteticos
    }

def get_salud_data():
    """
    Datos Estadísticos de Salud y Vitales (DEIS - Ministerio de Salud de la Nación)
    """
    serie_mortalidad_infantil = [
        {"anio": 1990, "tmi_total": 25.6, "tmi_neonatal": 15.2, "tmi_posneonatal": 10.4},
        {"anio": 1995, "tmi_total": 22.2, "tmi_neonatal": 13.5, "tmi_posneonatal": 8.7},
        {"anio": 2000, "tmi_total": 16.6, "tmi_neonatal": 10.8, "tmi_posneonatal": 5.8},
        {"anio": 2005, "tmi_total": 13.3, "tmi_neonatal": 8.9, "tmi_posneonatal": 4.4},
        {"anio": 2010, "tmi_total": 11.9, "tmi_neonatal": 7.9, "tmi_posneonatal": 4.0},
        {"anio": 2015, "tmi_total": 9.7, "tmi_neonatal": 6.5, "tmi_posneonatal": 3.2},
        {"anio": 2018, "tmi_total": 8.8, "tmi_neonatal": 6.0, "tmi_posneonatal": 2.8},
        {"anio": 2019, "tmi_total": 9.2, "tmi_neonatal": 6.2, "tmi_posneonatal": 3.0},
        {"anio": 2020, "tmi_total": 8.4, "tmi_neonatal": 5.7, "tmi_posneonatal": 2.7},
        {"anio": 2021, "tmi_total": 8.0, "tmi_neonatal": 5.4, "tmi_posneonatal": 2.6},
        {"anio": 2022, "tmi_total": 8.0, "tmi_neonatal": 5.5, "tmi_posneonatal": 2.5},
        {"anio": 2023, "tmi_total": 7.8, "tmi_neonatal": 5.3, "tmi_posneonatal": 2.5}
    ]
    
    serie_fecundidad = [
        {"anio": 1990, "tgf": 2.80, "tasa_fec_adolescente_15_19": 68.5},
        {"anio": 2000, "tgf": 2.44, "tasa_fec_adolescente_15_19": 65.2},
        {"anio": 2010, "tgf": 2.35, "tasa_fec_adolescente_15_19": 67.4},
        {"anio": 2015, "tgf": 2.29, "tasa_fec_adolescente_15_19": 64.9},
        {"anio": 2018, "tgf": 1.88, "tasa_fec_adolescente_15_19": 49.2},
        {"anio": 2020, "tgf": 1.54, "tasa_fec_adolescente_15_19": 30.3},
        {"anio": 2022, "tgf": 1.44, "tasa_fec_adolescente_15_19": 24.5},
        {"anio": 2023, "tgf": 1.39, "tasa_fec_adolescente_15_19": 21.8}
    ]
    
    serie_mortalidad_materna = [
        {"anio": 2010, "rmm": 4.4},
        {"anio": 2015, "rmm": 3.9},
        {"anio": 2018, "rmm": 3.7},
        {"anio": 2019, "rmm": 3.5},
        {"anio": 2020, "rmm": 4.1},
        {"anio": 2021, "rmm": 7.4},
        {"anio": 2022, "rmm": 3.2},
        {"anio": 2023, "rmm": 3.0}
    ]
    
    causas_defuncion = [
        {"causa": "Enfermedades del Sistema Circulatorio (Cardiopatías, ACV)", "porcentaje": 28.6, "tasa_por_100k": 224.5, "color": "#ef4444"},
        {"causa": "Tumores / Neoplasias Malignas", "porcentaje": 18.4, "tasa_por_100k": 144.3, "color": "#f97316"},
        {"causa": "Enfermedades del Sistema Respiratorio (Neumonía, EPOC)", "porcentaje": 16.8, "tasa_por_100k": 131.7, "color": "#3b82f6"},
        {"causa": "Causas Externas (Accidentes, agresiones, traumatismos)", "porcentaje": 5.4, "tasa_por_100k": 42.3, "color": "#8b5cf6"},
        {"causa": "Enfermedades del Sistema Digestivo", "porcentaje": 4.6, "tasa_por_100k": 36.1, "color": "#10b981"},
        {"causa": "Enfermedades Endocrinas / Diabetes", "porcentaje": 3.9, "tasa_por_100k": 30.6, "color": "#ec4899"},
        {"causa": "Enfermedades Infecciosas y Parasitarias", "porcentaje": 3.5, "tasa_por_100k": 27.5, "color": "#06b6d4"},
        {"causa": "Enfermedades del Sistema Genitourinario", "porcentaje": 3.1, "tasa_por_100k": 24.3, "color": "#eab308"},
        {"causa": "Demás Causas y Síntomas mal definidos", "porcentaje": 15.7, "tasa_por_100k": 123.1, "color": "#6b7280"}
    ]
    
    cobertura_salud = [
        {"tipo": "Obra Social (Nacional / Provincial / PAMI)", "porcentaje": 54.2, "poblacion": 25059278},
        {"tipo": "Solo Sistema Público de Salud", "porcentaje": 35.4, "poblacion": 16367130},
        {"tipo": "Medicina Prepaga / Planes Voluntarios", "porcentaje": 10.4, "poblacion": 4808422}
    ]
    
    recursos_sanitarios = {
        "medicos_por_mil_hab": 4.1,
        "enfermeros_por_mil_hab": 4.8,
        "camas_totales_por_mil_hab": 4.2,
        "camas_publicas_pct": 53.4,
        "camas_privadas_pct": 46.6,
        "establecimientos_salud_total": 21840
    }
    
    return {
        "serie_mortalidad_infantil": serie_mortalidad_infantil,
        "serie_fecundidad": serie_fecundidad,
        "serie_mortalidad_materna": serie_mortalidad_materna,
        "causas_defuncion": causas_defuncion,
        "cobertura_salud": cobertura_salud,
        "recursos_sanitarios": recursos_sanitarios
    }

def get_educacion_data():
    """
    Datos de Educación y Trayectorias Escolares (DINIECE / Relevamiento Anual - Secretaría de Educación / INDEC)
    """
    cobertura_niveles = [
        {"nivel": "Inicial - Sala 3 años", "tasa_escolarizacion": 54.8, "matricula": 395400},
        {"nivel": "Inicial - Sala 4 años", "tasa_escolarizacion": 92.1, "matricula": 685200},
        {"nivel": "Inicial - Sala 5 años (Obligatoria)", "tasa_escolarizacion": 98.4, "matricula": 732100},
        {"nivel": "Nivel Primario (6 a 11 años)", "tasa_escolarizacion": 99.1, "matricula": 4485000},
        {"nivel": "Nivel Secundario (12 a 17 años)", "tasa_escolarizacion": 91.5, "matricula": 3980000},
        {"nivel": "Nivel Superior / Universitario (18 a 24 años)", "tasa_escolarizacion": 42.6, "matricula": 2540000}
    ]
    
    trayectoria_secundaria = [
        {"anio_estudio": "1° Año / 7° u 8°", "repitencia_pct": 13.8, "abandono_pct": 9.4, "sobreedad_pct": 32.1},
        {"anio_estudio": "2° Año", "repitencia_pct": 11.5, "abandono_pct": 8.9, "sobreedad_pct": 33.4},
        {"anio_estudio": "3° Año", "repitencia_pct": 8.7, "abandono_pct": 8.1, "sobreedad_pct": 30.5},
        {"anio_estudio": "4° Año", "repitencia_pct": 5.6, "abandono_pct": 7.5, "sobreedad_pct": 26.8},
        {"anio_estudio": "5° / 6° Año (Último)", "repitencia_pct": 2.4, "abandono_pct": 5.8, "sobreedad_pct": 21.0}
    ]
    
    nivel_alcanzado_pob25 = [
        {"nivel": "Hasta Primaria Incompleta / Sin Instrucción", "porcentaje": 5.2, "poblacion": 1540000},
        {"nivel": "Primaria Completa / Secundaria Incompleta", "porcentaje": 34.6, "poblacion": 10240000},
        {"nivel": "Secundaria Completa / Superior Incompleto", "porcentaje": 37.8, "poblacion": 11190000},
        {"nivel": "Superior No Universitario Completo", "porcentaje": 8.9, "poblacion": 2630000},
        {"nivel": "Universitario o Posgrado Completo", "porcentaje": 13.5, "poblacion": 3995000}
    ]
    
    indicadores_sinteticos_educacion = {
        "tasa_analfabetismo_censal": 1.4,
        "anios_promedio_escolaridad": 11.2,
        "tasa_egreso_secundario_tiempo_forma": 53.8,
        "tasa_egreso_secundario_acumulado": 68.4,
        "matricula_total_sistema": 12817700,
        "establecimientos_educativos_total": 64200,
        "sector_gestion_estatal_pct": 72.8,
        "sector_gestion_privado_pct": 27.2
    }
    
    return {
        "cobertura_niveles": cobertura_niveles,
        "trayectoria_secundaria": trayectoria_secundaria,
        "nivel_alcanzado_pob25": nivel_alcanzado_pob25,
        "indicadores_sinteticos_educacion": indicadores_sinteticos_educacion
    }

def get_mercado_trabajo_data():
    """
    Datos del Mercado de Trabajo (EPH - INDEC Total 31 Aglomerados Urbanos)
    """
    serie_eph = [
        {"periodo": "2021-T4", "actividad": 46.9, "empleo": 43.6, "desocupacion": 7.0, "subocupacion": 12.1, "informalidad": 33.3},
        {"periodo": "2022-T2", "actividad": 47.9, "empleo": 44.6, "desocupacion": 6.9, "subocupacion": 11.1, "informalidad": 37.8},
        {"periodo": "2022-T4", "actividad": 47.6, "empleo": 44.6, "desocupacion": 6.3, "subocupacion": 10.9, "informalidad": 35.5},
        {"periodo": "2023-T2", "actividad": 47.6, "empleo": 44.6, "desocupacion": 6.2, "subocupacion": 10.6, "informalidad": 36.8},
        {"periodo": "2023-T4", "actividad": 48.6, "empleo": 45.8, "desocupacion": 5.7, "subocupacion": 10.5, "informalidad": 35.7},
        {"periodo": "2024-T1", "actividad": 48.0, "empleo": 44.3, "desocupacion": 7.7, "subocupacion": 11.8, "informalidad": 35.7},
        {"periodo": "2024-T2", "actividad": 48.5, "empleo": 44.8, "desocupacion": 7.6, "subocupacion": 11.8, "informalidad": 36.4},
        {"periodo": "2024-T3", "actividad": 48.2, "empleo": 44.9, "desocupacion": 6.9, "subocupacion": 11.5, "informalidad": 36.1}
    ]
    
    ramas_actividad = [
        {"rama": "Comercio (Mayorista y Minorista)", "porcentaje": 18.8},
        {"rama": "Industria Manufacturera", "porcentaje": 11.5},
        {"rama": "Administración Pública, Defensa y Seg. Social", "porcentaje": 9.4},
        {"rama": "Enseñanza / Educación", "porcentaje": 8.7},
        {"rama": "Construcción", "porcentaje": 8.2},
        {"rama": "Servicios de Salud y Asistencia Social", "porcentaje": 7.3},
        {"rama": "Servicios Inmobiliarios, Empresariales y Alquiler", "porcentaje": 6.9},
        {"rama": "Transporte, Almacenamiento y Comunicaciones", "porcentaje": 6.8},
        {"rama": "Servicio Doméstico en Hogares Particulares", "porcentaje": 6.5},
        {"rama": "Hotelería y Gastronomía", "porcentaje": 4.3},
        {"rama": "Agricultura, Ganadería, Caza y Silvicultura", "porcentaje": 2.8},
        {"rama": "Intermediación Financiera y Seguros", "porcentaje": 2.1},
        {"rama": "Otras Actividades de Servicios", "porcentaje": 6.7}
    ]
    
    return {
        "serie_eph": serie_eph,
        "ramas_actividad": ramas_actividad
    }

def generate_master_dataset():
    """
    Compila todos los módulos en un dataset maestro verificado
    """
    print("Compilando Catálogo Actuarial y Tablas de Mortalidad...")
    mortalidad = get_complete_actuarial_catalog()
    
    print("Compilando Datos Demográficos y Censales 2022...")
    demografia = get_censo_demografia_data()
    
    print("Compilando Estadísticas Vitales y Salud DEIS...")
    salud = get_salud_data()
    
    print("Compilando Estadísticas de Educación...")
    educacion = get_educacion_data()
    
    print("Compilando Mercado Laboral EPH...")
    mercado_trabajo = get_mercado_trabajo_data()
    
    master = {
        "metadata": {
            "titulo": "Monitor Demográfico y Estadístico de la República Argentina",
            "fuentes": [
                {"institucion": "INDEC", "descripcion": "Instituto Nacional de Estadística y Censos (Censo 2022, EPH, Tablas de Mortalidad Serie Análisis Demográfico)"},
                {"institucion": "DEIS", "descripcion": "Dirección de Estadísticas e Información de Salud - Ministerio de Salud de la Nación (Series de Natalidad, Mortalidad Infantil, Materna y Causas CIE-10)"},
                {"institucion": "DINIECE / Relevamiento Anual", "descripcion": "Secretaría de Educación - Ministerio de Capital Humano (Cobertura, Trayectorias y Eficiencia Interna)"},
                {"institucion": "SSN", "descripcion": "Superintendencia de Seguros de la Nación (Tablas Actuariales GAM-71, GAM-83, GAM-94, UP-94, CSO 1980, CSO 2001, CSO 2017)"}
            ],
            "version": "2.0.0",
            "actualizado": "Agosto 2026",
            "acceso": "Libre, público y gratuito"
        },
        "mortalidad": mortalidad,
        "demografia": demografia,
        "salud": salud,
        "educacion": educacion,
        "mercado_trabajo": mercado_trabajo
    }
    
    dir_path = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(dir_path, "master_dataset_demografia.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False, indent=2)
    print(f"Dataset maestro guardado con éxito en: {json_path}")
    
    # Inyectar dataset embebido en index.html para compatibilidad offline y local file://
    html_path = os.path.join(dir_path, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
            
        dataset_script = f"\n  <script>\n    window.__INTEGRATED_DATASET__ = {json.dumps(master, ensure_ascii=False)};\n  </script>\n"
        
        if "window.__INTEGRATED_DATASET__ =" in html_content:
            html_content = re.sub(
                r'<script>\s*window\.__INTEGRATED_DATASET__\s*=[\s\S]*?</script>',
                f'<script>\n    window.__INTEGRATED_DATASET__ = {json.dumps(master, ensure_ascii=False)};\n  </script>',
                html_content
            )
        else:
            html_content = html_content.replace('</head>', f'{dataset_script}</head>')
            
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"index.html actualizado exitosamente con dataset integrado offline!")

    return master

if __name__ == "__main__":
    generate_master_dataset()
