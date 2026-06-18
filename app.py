import os
from datetime import date

import psycopg2
from flask import Flask, g, flash, redirect, render_template, request, url_for
from psycopg2 import OperationalError

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "cambia-esta-clave-en-produccion")

# ------------------------------------------------------------------
#  CONFIGURACIÓN DE CONEXIÓN  (idéntica a tu script original)
# ------------------------------------------------------------------
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "database": "empresa_db",
    "user":     "spike",
    "password": "pass_1234",   # ← cambia por tu contraseña
}


def get_db():
    """Abre (o reutiliza) una conexión por cada request."""
    if "db" not in g:
        try:
            g.db = psycopg2.connect(**DB_CONFIG)
        except OperationalError as e:
            g.db = None
            g.db_error = str(e)
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.before_request
def check_db():
    if request.endpoint == "static":
        return
    conn = get_db()
    if conn is None:
        return render_template("db_error.html", error=g.get("db_error", "Error desconocido")), 500


def fetch_all(query, params=None):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(query, params or ())
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    return cols, rows


# ------------------------------------------------------------------
#  INICIO
# ------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# ------------------------------------------------------------------
#  EMPLEADOS
# ------------------------------------------------------------------
@app.route("/empleados")
def empleados_list():
    depto = request.args.get("depto", "").strip()
    base_query = """
        SELECT e.NSS, e.NombrePila, e.Paterno, e.Materno,
               e.Sexo, e.Salario, e.FechaNac, d.Nombre AS Depto
        FROM EMPLEADO e
        JOIN DEPARTAMENTO d ON e.Num_Depto = d.NumDepto
        {where}
        ORDER BY e.Paterno, e.NombrePila
    """
    if depto:
        cols, rows = fetch_all(base_query.format(where="WHERE e.Num_Depto = %s"), (depto,))
    else:
        cols, rows = fetch_all(base_query.format(where=""))

    _, deptos = fetch_all("SELECT NumDepto, Nombre FROM DEPARTAMENTO ORDER BY Nombre")
    return render_template(
        "empleados_list.html", rows=rows, deptos=deptos, depto_actual=depto
    )


@app.route("/empleados/nuevo", methods=["GET", "POST"])
def empleado_nuevo():
    conn = get_db()
    _, deptos = fetch_all("SELECT NumDepto, Nombre FROM DEPARTAMENTO ORDER BY Nombre")

    if request.method == "POST":
        nss         = request.form["nss"].strip()
        num_depto   = request.form["num_depto"]
        nombre_pila = request.form["nombre_pila"].strip()
        paterno     = request.form["paterno"].strip()
        materno     = request.form.get("materno", "").strip()
        direccion   = request.form["direccion"].strip()
        sexo        = request.form["sexo"].strip().upper()
        salario     = request.form["salario"]
        fecha_nac   = request.form["fecha_nac"]
        supervisor  = request.form.get("supervisor", "").strip() or None

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO EMPLEADO
                        (NSS, Num_Depto, NombrePila, Paterno, Materno,
                         Direccion, Sexo, Salario, FechaNac, NSS_Supervisor)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (nss, num_depto, nombre_pila, paterno, materno,
                     direccion, sexo, salario, fecha_nac, supervisor),
                )
            conn.commit()
            flash(f"Empleado {nombre_pila} {paterno} creado correctamente.", "success")
            return redirect(url_for("empleados_list"))
        except Exception as e:
            conn.rollback()
            flash(f"Error al crear empleado: {e}", "error")

    return render_template("empleado_form.html", deptos=deptos, empleado=None, modo="crear")


@app.route("/empleados/<nss>/editar", methods=["GET", "POST"])
def empleado_editar(nss):
    conn = get_db()
    _, deptos = fetch_all("SELECT NumDepto, Nombre FROM DEPARTAMENTO ORDER BY Nombre")

    if request.method == "POST":
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE EMPLEADO
                    SET Num_Depto = %s, NombrePila = %s, Paterno = %s, Materno = %s,
                        Direccion = %s, Sexo = %s, Salario = %s, FechaNac = %s,
                        NSS_Supervisor = %s
                    WHERE NSS = %s
                    """,
                    (
                        request.form["num_depto"],
                        request.form["nombre_pila"].strip(),
                        request.form["paterno"].strip(),
                        request.form.get("materno", "").strip(),
                        request.form["direccion"].strip(),
                        request.form["sexo"].strip().upper(),
                        request.form["salario"],
                        request.form["fecha_nac"],
                        request.form.get("supervisor", "").strip() or None,
                        nss,
                    ),
                )
            conn.commit()
            flash(f"Empleado {nss} actualizado correctamente.", "success")
            return redirect(url_for("empleados_list"))
        except Exception as e:
            conn.rollback()
            flash(f"Error al actualizar: {e}", "error")

    cols, rows = fetch_all(
        """
        SELECT NSS, Num_Depto, NombrePila, Paterno, Materno,
               Direccion, Sexo, Salario, FechaNac, NSS_Supervisor
        FROM EMPLEADO WHERE NSS = %s
        """,
        (nss,),
    )
    if not rows:
        flash(f"No existe empleado con NSS {nss}.", "error")
        return redirect(url_for("empleados_list"))

    empleado = dict(zip(cols, rows[0]))
    return render_template("empleado_form.html", deptos=deptos, empleado=empleado, modo="editar")


@app.route("/empleados/<nss>/eliminar", methods=["POST"])
def empleado_eliminar(nss):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM DEPENDIENTE WHERE NSS_Empleado = %s", (nss,))
            cur.execute("DELETE FROM TRABAJA_EN  WHERE NSS_Empleado = %s", (nss,))
            cur.execute("DELETE FROM EMPLEADO    WHERE NSS = %s", (nss,))
        conn.commit()
        flash(f"Empleado {nss} eliminado junto con sus registros dependientes.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error al eliminar: {e}", "error")
    return redirect(url_for("empleados_list"))


# ------------------------------------------------------------------
#  DEPARTAMENTOS
# ------------------------------------------------------------------
@app.route("/departamentos")
def departamentos_list():
    _, rows = fetch_all(
        """
        SELECT d.NumDepto, d.Nombre,
               CONCAT(e.NombrePila,' ',e.Paterno) AS Gerente,
               d.FechaInicGerente,
               STRING_AGG(dl.Lugar, ', ') AS Lugares,
               COUNT(emp.NSS) AS NumEmpleados
        FROM DEPARTAMENTO d
        LEFT JOIN EMPLEADO e   ON d.NSS_Gerente = e.NSS
        LEFT JOIN DEPT_LUGARES dl ON d.NumDepto = dl.Num_Depto
        LEFT JOIN EMPLEADO emp ON d.NumDepto = emp.Num_Depto
        GROUP BY d.NumDepto, d.Nombre, Gerente, d.FechaInicGerente
        ORDER BY d.NumDepto
        """
    )
    return render_template("departamentos_list.html", rows=rows)


@app.route("/departamentos/nuevo", methods=["GET", "POST"])
def departamento_nuevo():
    conn = get_db()
    if request.method == "POST":
        nombre  = request.form["nombre"].strip()
        gerente = request.form.get("gerente", "").strip() or None
        fecha   = request.form.get("fecha", "").strip() or str(date.today())
        lugares_str = request.form.get("lugares", "").strip()
        lugares = [l.strip() for l in lugares_str.split(",") if l.strip()]

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO DEPARTAMENTO (Nombre, NSS_Gerente, FechaInicGerente)
                    VALUES (%s, %s, %s) RETURNING NumDepto
                    """,
                    (nombre, gerente, fecha),
                )
                nuevo_id = cur.fetchone()[0]
                for lugar in lugares:
                    cur.execute("INSERT INTO DEPT_LUGARES VALUES (%s, %s)", (nuevo_id, lugar))
            conn.commit()
            flash(f"Departamento '{nombre}' creado con ID={nuevo_id}.", "success")
            return redirect(url_for("departamentos_list"))
        except Exception as e:
            conn.rollback()
            flash(f"Error: {e}", "error")

    return render_template("departamento_form.html")


# ------------------------------------------------------------------
#  PROYECTOS
# ------------------------------------------------------------------
@app.route("/proyectos")
def proyectos_list():
    _, rows = fetch_all(
        """
        SELECT p.NumProy, p.Nombre, p.Lugar, d.Nombre AS Departamento,
               COUNT(t.NSS_Empleado) AS Trabajadores,
               COALESCE(SUM(t.Horas), 0) AS TotalHoras
        FROM PROYECTO p
        JOIN DEPARTAMENTO d ON p.Num_departamento = d.NumDepto
        LEFT JOIN TRABAJA_EN t ON p.NumProy = t.Num_Proyecto
        GROUP BY p.NumProy, p.Nombre, p.Lugar, d.Nombre
        ORDER BY p.NumProy
        """
    )
    return render_template("proyectos_list.html", rows=rows)


@app.route("/proyectos/nuevo", methods=["GET", "POST"])
def proyecto_nuevo():
    conn = get_db()
    _, deptos = fetch_all("SELECT NumDepto, Nombre FROM DEPARTAMENTO ORDER BY Nombre")

    if request.method == "POST":
        nombre = request.form["nombre"].strip()
        lugar  = request.form["lugar"].strip()
        depto  = request.form["depto"]
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO PROYECTO (Nombre, Lugar, Num_departamento)
                    VALUES (%s, %s, %s) RETURNING NumProy
                    """,
                    (nombre, lugar, depto),
                )
                nid = cur.fetchone()[0]
            conn.commit()
            flash(f"Proyecto '{nombre}' creado con ID={nid}.", "success")
            return redirect(url_for("proyectos_list"))
        except Exception as e:
            conn.rollback()
            flash(f"Error: {e}", "error")

    return render_template("proyecto_form.html", deptos=deptos)


# ------------------------------------------------------------------
#  ASIGNACIONES (TRABAJA_EN)
# ------------------------------------------------------------------
@app.route("/asignaciones")
def asignaciones_list():
    nss = request.args.get("nss", "").strip() or None
    base_query = """
        SELECT CONCAT(e.NombrePila,' ',e.Paterno) AS Empleado, e.NSS,
               p.Nombre AS Proyecto, p.Lugar, t.Horas
        FROM TRABAJA_EN t
        JOIN EMPLEADO e ON t.NSS_Empleado = e.NSS
        JOIN PROYECTO p ON t.Num_Proyecto = p.NumProy
        {where}
        ORDER BY e.Paterno, p.Nombre
    """
    if nss:
        _, rows = fetch_all(base_query.format(where="WHERE t.NSS_Empleado = %s"), (nss,))
    else:
        _, rows = fetch_all(base_query.format(where=""))

    return render_template("asignaciones_list.html", rows=rows, nss_filtro=nss or "")


@app.route("/asignaciones/nueva", methods=["GET", "POST"])
def asignacion_nueva():
    conn = get_db()
    _, empleados = fetch_all("SELECT NSS, NombrePila, Paterno FROM EMPLEADO ORDER BY Paterno")
    _, proyectos = fetch_all("SELECT NumProy, Nombre FROM PROYECTO ORDER BY Nombre")

    if request.method == "POST":
        nss   = request.form["nss"].strip()
        proy  = request.form["proyecto"]
        horas = request.form["horas"]
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO TRABAJA_EN VALUES (%s, %s, %s)
                    ON CONFLICT (NSS_Empleado, Num_Proyecto)
                    DO UPDATE SET Horas = EXCLUDED.Horas
                    """,
                    (nss, proy, horas),
                )
            conn.commit()
            flash("Asignación guardada correctamente.", "success")
            return redirect(url_for("asignaciones_list"))
        except Exception as e:
            conn.rollback()
            flash(f"Error: {e}", "error")

    return render_template("asignar_form.html", empleados=empleados, proyectos=proyectos)


# ------------------------------------------------------------------
#  CONSULTAS ESPECIALES
# ------------------------------------------------------------------
CONSULTAS = {
    1: {
        "titulo": "Empleados con salario superior al promedio de su departamento",
        "sql": """
            SELECT e.NSS,
                   CONCAT(e.NombrePila,' ',e.Paterno) AS Empleado,
                   e.Salario,
                   ROUND(AVG(e2.Salario) OVER (PARTITION BY e.Num_Depto), 2) AS PromedioDepto,
                   d.Nombre AS Departamento
            FROM EMPLEADO e
            JOIN EMPLEADO e2 ON e.Num_Depto = e2.Num_Depto
            JOIN DEPARTAMENTO d ON e.Num_Depto = d.NumDepto
            WHERE e.Salario > (
                SELECT AVG(Salario) FROM EMPLEADO WHERE Num_Depto = e.Num_Depto
            )
            ORDER BY d.Nombre, e.Salario DESC
        """,
    },
    2: {
        "titulo": "Proyectos con más de 30 horas totales trabajadas",
        "sql": """
            SELECT p.NumProy, p.Nombre, p.Lugar,
                   d.Nombre AS Departamento,
                   COALESCE(SUM(t.Horas), 0) AS TotalHoras,
                   COUNT(t.NSS_Empleado) AS NumEmpleados
            FROM PROYECTO p
            JOIN DEPARTAMENTO d ON p.Num_departamento = d.NumDepto
            LEFT JOIN TRABAJA_EN t ON p.NumProy = t.Num_Proyecto
            GROUP BY p.NumProy, p.Nombre, p.Lugar, d.Nombre
            HAVING COALESCE(SUM(t.Horas), 0) > 30
            ORDER BY TotalHoras DESC
        """,
    },
    3: {
        "titulo": "Empleados y sus dependientes",
        "sql": """
            SELECT CONCAT(e.NombrePila,' ',e.Paterno) AS Empleado,
                   e.NSS,
                   dep.NomDependiente AS Dependiente,
                   dep.Parentesco,
                   dep.Sexo,
                   dep.FechaNac
            FROM EMPLEADO e
            LEFT JOIN DEPENDIENTE dep ON e.NSS = dep.NSS_Empleado
            ORDER BY e.Paterno, dep.NomDependiente
        """,
    },
}


@app.route("/consultas")
def consultas_menu():
    return render_template("consultas.html", consultas=CONSULTAS)


@app.route("/consultas/<int:n>")
def consulta_resultado(n):
    consulta = CONSULTAS.get(n)
    if not consulta:
        flash("Consulta no válida.", "error")
        return redirect(url_for("consultas_menu"))
    cols, rows = fetch_all(consulta["sql"])
    return render_template(
        "consulta_resultado.html", titulo=consulta["titulo"], cols=cols, rows=rows
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
