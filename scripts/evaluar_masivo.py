import os
import subprocess
import json
import csv
from pathlib import Path

ORG = "GradoIngenieriaInformatica-BaseDeDatosII-2025-2026"
PREFIX = "Análisis y Selección de Bases de Datos NoSQL"

RESPUESTAS = json.loads(os.environ["RESPUESTAS_JSON"])
ALUMNOS_RAW = os.environ["ALUMNOS_CSV"]

# -----------------------------
# Cargar alumnos
# -----------------------------
alumnos = {}
lineas = ALUMNOS_RAW.strip().split("\n")

for linea in lineas[1:]:
    nombre, login, numero, grupo = linea.split(",")
    alumnos[login.strip()] = grupo.strip()

# -----------------------------
# Obtener repos
# -----------------------------
repos_json = subprocess.check_output(
    ["gh", "repo", "list", ORG, "--limit", "200", "--json", "name"],
    text=True
)

repos = json.loads(repos_json)
repos_filtrados = [r["name"] for r in repos if PREFIX in r["name"]]

resultados = []

# -----------------------------
# Evaluar cada repo
# -----------------------------
for repo in repos_filtrados:

    print("Evaluando:", repo)
    subprocess.run(["gh", "repo", "clone", f"{ORG}/{repo}"])

    login = repo.split("-")[-1]

    if login not in alumnos:
        resultados.append({
            "repo": repo,
            "login": login,
            "grupo": "NO_REGISTRADO",
            "estado": "REPROBADO",
            "motivo": "LOGIN_NO_ENCONTRADO"
        })
        continue

    grupo = alumnos[login]
    path_repo = Path(repo)
    path_respuestas = path_repo / "respuestas"

    if not path_respuestas.exists():
        estado = "REPROBADO"
        motivo = "NO_EXISTE_CARPETA_RESPUESTAS"
    else:

        archivos = list(path_respuestas.glob("*.txt"))

        if len(archivos) != 3:
            estado = "REPROBADO"
            motivo = "CANTIDAD_RESPUESTAS_INCORRECTA"
        else:

            correctos = 0
            errores = []

            for i in range(1, 4):

                archivo = path_respuestas / f"respuesta{i}.txt"

                if not archivo.exists():
                    errores.append(f"RESPUESTA_{i}_NO_EXISTE")
                    continue

                texto = archivo.read_text(encoding="utf-8").lower().strip()

                if len(texto) < 20:
                    errores.append(f"RESPUESTA_{i}_MUY_CORTA")
                    continue

                esperado = RESPUESTAS[grupo][i - 1]

                if esperado["tipo"].lower() not in texto:
                    errores.append(f"RESPUESTA_{i}_TIPO_INCORRECTO")
                    continue

                if not any(p.lower() in texto for p in esperado["palabras"]):
                    errores.append(f"RESPUESTA_{i}_CONTENIDO_INCORRECTO")
                    continue

                correctos += 1

            if correctos == 3:
                estado = "APROBADO"
                motivo = "OK"
            else:
                estado = "REPROBADO"
                motivo = "; ".join(errores)

    resultados.append({
        "repo": repo,
        "login": login,
        "grupo": grupo,
        "estado": estado,
        "motivo": motivo
    })

    # -----------------------------
    # Crear Issue automático
    # -----------------------------
    cuerpo = f"""
### Resultado Evaluación Oficial

Estado: **{estado}**

Motivo:
{motivo}

Si considera que existe un error, puede solicitar revisión.
"""

    subprocess.run([
        "gh", "issue", "create",
        "--repo", f"{ORG}/{repo}",
        "--title", "Resultado Evaluación Oficial",
        "--body", cuerpo
    ])

# -----------------------------
# Exportar resumen
# -----------------------------
with open("resumen_final.csv", "w", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["repo", "login", "grupo", "estado", "motivo"]
    )
    writer.writeheader()
    writer.writerows(resultados)

print("Evaluación completada")
