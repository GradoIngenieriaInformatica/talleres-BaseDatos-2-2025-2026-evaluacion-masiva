import os
import subprocess
import json
import csv
from pathlib import Path
import io

# -----------------------------
# Configuración
# -----------------------------
ORG = "GradoIngenieriaInformatica"  # Corregido, nombre real de la organización
PREFIX = "Análisis y Selección de Bases de Datos NoSQL"

# -----------------------------
# Cargar respuestas desde secret
# -----------------------------
RESPUESTAS = json.loads(os.environ["RESPUESTAS_JSON"])
ALUMNOS_RAW = os.environ["ALUMNOS_CSV"]

# -----------------------------
# Cargar alumnos desde CSV (;)
# -----------------------------
f = io.StringIO(ALUMNOS_RAW)
reader = csv.reader(f, delimiter=';')

alumnos = {}
# Saltar cabecera
next(reader, None)

for linea in reader:
    if len(linea) < 4:
        print(f"Línea inválida (menos de 4 columnas), se salta: {linea}")
        continue

    nombre, numero, grupo, github = [x.strip() for x in linea[:4]]

    # Saltar alumnos sin github
    if not github:
        print(f"Alumno sin github, se salta: {nombre} ({numero})")
        continue

    # Saltar alumnos sin grupo
    if grupo.lower() in ("", "null"):
        print(f"Alumno sin grupo asignado, se salta: {nombre} ({github})")
        continue

    alumnos[github] = {
        "nombre": nombre,
        "numero": numero,
        "grupo": grupo.upper()
    }

print(f"Alumnos válidos cargados: {len(alumnos)}")

# -----------------------------
# Obtener repos de la org
# -----------------------------
try:
    repos_json = subprocess.check_output(
        ["gh", "repo", "list", ORG, "--limit", "200", "--json", "name"],
        text=True
    )
except subprocess.CalledProcessError as e:
    print("Error listando repos:", e)
    exit(1)

repos = json.loads(repos_json)
repos_filtrados = [r["name"] for r in repos if PREFIX in r["name"]]

resultados = []

# -----------------------------
# Evaluar cada repo
# -----------------------------
for repo in repos_filtrados:

    print("Evaluando:", repo)
    # Clonar repo
    try:
        subprocess.run(["gh", "repo", "clone", f"{ORG}/{repo}"], check=True)
    except subprocess.CalledProcessError:
        print(f"Error al clonar repo: {repo}, se salta")
        resultados.append({
            "repo": repo,
            "login": "DESCONOCIDO",
            "grupo": "DESCONOCIDO",
            "estado": "REPROBADO",
            "motivo": "ERROR_CLONAR_REPO"
        })
        continue

    login = repo.split("-")[-1]

    if login not in alumnos:
        print(f"Alumno no registrado en CSV: {login}")
        resultados.append({
            "repo": repo,
            "login": login,
            "grupo": "NO_REGISTRADO",
            "estado": "REPROBADO",
            "motivo": "LOGIN_NO_ENCONTRADO"
        })
        continue

    grupo = alumnos[login]["grupo"]
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

                if not any(p.lower() in texto for p in esperado["keywords"]):
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
    try:
        subprocess.run([
            "gh", "issue", "create",
            "--repo", f"{ORG}/{repo}",
            "--title", "Resultado Evaluación Oficial",
            "--body", cuerpo
        ], check=True)
    except subprocess.CalledProcessError:
        print(f"Error creando issue en repo: {repo}")

# -----------------------------
# Exportar resumen final
# -----------------------------
with open("resumen_final.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["repo", "login", "grupo", "estado", "motivo"]
    )
    writer.writeheader()
    writer.writerows(resultados)

print("Evaluación completada")
