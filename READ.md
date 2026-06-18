# Sistema Empresa — Interfaz web con Flask

Interfaz gráfica (navegador) para el CRUD de Empleados, Departamentos, Proyectos
y Asignaciones que originalmente corría por terminal con `input()`.

## Estructura

```
flask_app/
├── app.py                  # Rutas Flask (toda la lógica que antes estaba en connection_db.py)
├── requirements.txt
├── static/
│   └── style.css
└── templates/
    ├── base.html            # layout con cabecera y pestañas de navegación
    ├── index.html
    ├── empleados_list.html
    ├── empleado_form.html
    ├── departamentos_list.html
    ├── departamento_form.html
    ├── proyectos_list.html
    ├── proyecto_form.html
    ├── asignaciones_list.html
    ├── asignar_form.html
    ├── consultas.html
    ├── consulta_resultado.html
    └── db_error.html
```
