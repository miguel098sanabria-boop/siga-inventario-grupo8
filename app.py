import sqlite3
from datetime import date
import pandas as pd
import streamlit as st

# Configuración general de la página
st.set_page_config(page_title="SIGA - La Casa del Panadero", layout="wide")


# ==========================================================
# 1. CONEXIÓN E INICIALIZACIÓN DE LA BASE DE DATOS
# ==========================================================
def inicializar_base_de_datos(conn):
    """Crea tablas, datos iniciales y vista solo si no existen."""
    cur = conn.cursor()

    # Creación de tablas respetando exactamente el esquema del Avance 4
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS proveedores (
        id_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        telefono TEXT
    );

    CREATE TABLE IF NOT EXISTS clientes (
        id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        telefono TEXT
    );

    CREATE TABLE IF NOT EXISTS productos (
        id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        categoria TEXT NOT NULL,
        unidad_medida TEXT NOT NULL,
        precio_unitario REAL NOT NULL,
        stock_minimo INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS movimientos (
        id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
        id_producto INTEGER NOT NULL,
        tipo TEXT NOT NULL CHECK (tipo IN ('entrada', 'salida')),
        cantidad INTEGER NOT NULL CHECK (cantidad > 0),
        fecha TEXT NOT NULL,
        id_proveedor INTEGER,
        id_cliente INTEGER,
        FOREIGN KEY (id_producto) REFERENCES productos(id_producto),
        FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedor),
        FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente)
    );
    """)

    # Insertar datos de prueba solo si aún no hay productos registrados
    total_productos = cur.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
    if total_productos == 0:
        # PROVEEDORES
        cur.executemany(
            "INSERT INTO proveedores (nombre, telefono) VALUES (?, ?)",
            [
                ("Harinas del Valle", "3000000001"),
                ("Distribuciones Panaderas del Pacifico", "3000000002"),
                ("Dulces y Reposteria S.A.S.", "3000000003"),
                ("Insumos Alimentarios del Valle", "3000000004"),
            ],
        )

        # CLIENTES
        cur.executemany(
            "INSERT INTO clientes (nombre, telefono) VALUES (?, ?)",
            [
                ("Panaderia El Trigal", "3100000001"),
                ("Pasteleria Dulce Hogar", "3100000002"),
                ("Reposteria Creativa", "3100000003"),
                ("Restaurante y Cafeteria Aroma", "3100000004"),
                ("Emprendimientos La Espiga", "3100000005"),
            ],
        )

        # PRODUCTOS
        cur.executemany(
            """INSERT INTO productos
            (nombre, categoria, unidad_medida, precio_unitario, stock_minimo)
            VALUES (?, ?, ?, ?, ?)""",
            [
                ("Harina de trigo", "Harinas", "Bulto de 50 kg", 120000, 10),
                ("Harina de maiz", "Harinas", "Bulto de 25 kg", 70000, 8),
                ("Levadura seca", "Levaduras", "Paquete de 500 g", 18000, 15),
                ("Azucar", "Insumos de reposteria", "Bulto de 50 kg", 150000, 10),
                ("Margarina", "Insumos de reposteria", "Caja de 15 kg", 95000, 8),
            ],
        )

        # ENTRADAS iniciales
        cur.executemany(
            """INSERT INTO movimientos
            (id_producto, tipo, cantidad, fecha, id_proveedor)
            VALUES (?, ?, ?, ?, ?)""",
            [
                (1, "entrada", 20, "2026-09-01", 1),
                (2, "entrada", 15, "2026-09-01", 1),
                (3, "entrada", 30, "2026-09-02", 2),
                (4, "entrada", 12, "2026-09-03", 3),
                (5, "entrada", 10, "2026-09-04", 4),
            ],
        )

        # SALIDAS iniciales
        cur.executemany(
            """INSERT INTO movimientos
            (id_producto, tipo, cantidad, fecha, id_cliente)
            VALUES (?, ?, ?, ?, ?)""",
            [
                (1, "salida", 2, "2026-09-10", 1),
                (3, "salida", 5, "2026-09-10", 2),
                (4, "salida", 1, "2026-09-11", 3),
            ],
        )

    # Vista de inventario actual (exacta del Avance 3 y 4)
    cur.execute("""
    CREATE VIEW IF NOT EXISTS vw_inventario AS
    SELECT
        p.id_producto,
        p.nombre,
        p.categoria,
        p.stock_minimo,
        COALESCE(SUM(CASE WHEN m.tipo = 'entrada' THEN m.cantidad ELSE -m.cantidad END), 0) AS stock
    FROM productos p
    LEFT JOIN movimientos m ON m.id_producto = p.id_producto
    GROUP BY p.id_producto, p.nombre, p.categoria, p.stock_minimo
    """)

    conn.commit()


@st.cache_resource
def obtener_conexion():
    """Abre y conserva la conexión SQLite para Streamlit."""
    conn = sqlite3.connect("mi_sistema.db", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    inicializar_base_de_datos(conn)
    return conn


conexion = obtener_conexion()
cursor = conexion.cursor()


# ==========================================================
# 2. FUNCIONES DEL AVANCE 4 (LÓGICA Y SQL SIN ALTERAR)
# ==========================================================
def existe_producto(id_producto):
    cursor.execute("SELECT 1 FROM productos WHERE id_producto = ?", (id_producto,))
    return cursor.fetchone() is not None


def registrar_entrada(id_producto, cantidad, id_proveedor=None, fecha=None):
    fecha = fecha or date.today().isoformat()
    if not isinstance(cantidad, int) or cantidad <= 0:
        return False, "La cantidad debe ser un número entero mayor que 0."
    if not existe_producto(id_producto):
        return False, f"El producto con ID {id_producto} no existe."

    try:
        cursor.execute(
            "INSERT INTO movimientos (id_producto, tipo, cantidad, fecha, id_proveedor) VALUES (?, 'entrada', ?, ?, ?)",
            (id_producto, cantidad, fecha, id_proveedor),
        )
        conexion.commit()
        return True, f"Entrada registrada: +{cantidad} unidades del producto {id_producto}."
    except Exception as e:
        conexion.rollback()
        return False, f"Error al guardar: {e}"


def registrar_salida(id_producto, cantidad, id_cliente=None, fecha=None):
    fecha = fecha or date.today().isoformat()
    if not isinstance(cantidad, int) or cantidad <= 0:
        return False, "La cantidad debe ser un número entero mayor que 0."
    if not existe_producto(id_producto):
        return False, f"El producto con ID {id_producto} no existe."

    # Consultar el stock actual en la vista
    cursor.execute("SELECT stock FROM vw_inventario WHERE id_producto = ?", (id_producto,))
    stock_actual = cursor.fetchone()[0]

    if cantidad > stock_actual:
        return False, f"Stock insuficiente: hay {stock_actual} y se piden {cantidad}."

    try:
        cursor.execute(
            "INSERT INTO movimientos (id_producto, tipo, cantidad, fecha, id_cliente) VALUES (?, 'salida', ?, ?, ?)",
            (id_producto, cantidad, fecha, id_cliente),
        )
        conexion.commit()
        return True, f"Salida registrada: -{cantidad} unidades del producto {id_producto}."
    except Exception as e:
        conexion.rollback()
        return False, f"Error al guardar: {e}"


def consultar_inventario(categoria=None):
    if categoria:
        return pd.read_sql_query(
            "SELECT * FROM vw_inventario WHERE categoria = ? ORDER BY nombre",
            conexion,
            params=(categoria,),
        )
    return pd.read_sql_query("SELECT * FROM vw_inventario ORDER BY nombre", conexion)


def alertas_stock_bajo(minimo=10):
    return pd.read_sql_query(
        "SELECT nombre, categoria, stock FROM vw_inventario WHERE stock < ? ORDER BY stock",
        conexion,
        params=(minimo,),
    )


def registrar_producto_nuevo(nombre, categoria, unidad_medida, precio_unitario, stock_minimo):
    if precio_unitario <= 0:
        return False, "El precio debe ser mayor a 0."
    try:
        cursor.execute(
            "INSERT INTO productos (nombre, categoria, unidad_medida, precio_unitario, stock_minimo) VALUES (?, ?, ?, ?, ?)",
            (nombre, categoria, unidad_medida, precio_unitario, stock_minimo),
        )
        conexion.commit()
        return True, f"Producto '{nombre}' registrado exitosamente."
    except Exception as e:
        conexion.rollback()
        return False, f"Error al registrar producto: {e}"


def registrar_entradas_lote(items, id_proveedor=None, fecha=None):
    """items = lista de pares (id_producto, cantidad)."""
    fecha = fecha or date.today().isoformat()
    try:
        for id_producto, cantidad in items:
            if not isinstance(cantidad, int) or cantidad <= 0:
                raise ValueError(f"Cantidad inválida para el producto {id_producto}.")
            if not existe_producto(id_producto):
                raise ValueError(f"El producto {id_producto} no existe.")

            cursor.execute(
                "INSERT INTO movimientos (id_producto, tipo, cantidad, fecha, id_proveedor) VALUES (?, 'entrada', ?, ?, ?)",
                (id_producto, cantidad, fecha, id_proveedor),
            )
        conexion.commit()
        return True, f"Lote registrado: {len(items)} entradas."
    except Exception as e:
        conexion.rollback()
        return False, f"Lote cancelado, no se guardó nada. Motivo: {e}"


# ==========================================================
# 3. FUNCIONES AUXILIARES PARA LA INTERFAZ
# ==========================================================
def obtener_listas_seleccion():
    """Devuelve diccionarios {nombre: id} para seleccionar por nombre en la interfaz."""
    df_prod = pd.read_sql_query("SELECT id_producto, nombre FROM productos ORDER BY nombre", conexion)
    df_prov = pd.read_sql_query("SELECT id_proveedor, nombre FROM proveedores ORDER BY nombre", conexion)
    df_cli = pd.read_sql_query("SELECT id_cliente, nombre FROM clientes ORDER BY nombre", conexion)

    mapa_productos = dict(zip(df_prod["nombre"], df_prod["id_producto"]))
    mapa_proveedores = {"Sin proveedor": None}
    mapa_proveedores.update(dict(zip(df_prov["nombre"], df_prov["id_proveedor"])))

    mapa_clientes = {"Sin cliente": None}
    mapa_clientes.update(dict(zip(df_cli["nombre"], df_cli["id_cliente"])))

    return mapa_productos, mapa_proveedores, mapa_clientes


def mostrar_mensaje_guardado(clave_sesion):
    """Muestra el resultado (éxito o error) conservado después de st.rerun()."""
    if clave_sesion in st.session_state:
        exito, mensaje = st.session_state.pop(clave_sesion)
        if exito:
            st.success(mensaje)
        else:
            st.error(mensaje)


# ==========================================================
# 4. INTERFAZ PRINCIPAL (4 PESTAÑAS)
# ==========================================================
st.title("SIGA - La Casa del Panadero")
st.caption("Sistema de Inventario de Insumos para Panaderías, Pastelerías y Repostería")

tab_inicio, tab_movimiento, tab_inventario, tab_alertas = st.tabs(
    ["Inicio", "Registrar movimiento", "Inventario", "Alertas"]
)

# Datos actualizados para las pestañas
df_inventario = consultar_inventario()

# --- PESTAÑA 1: INICIO ---
with tab_inicio:
    st.subheader("Resumen general del inventario")
    st.write(
        "Bienvenido al sistema de gestión de inventario de **La Casa del Panadero**. "
        "Aquí puedes controlar entradas de proveedores, salidas a clientes, consultar el stock en tiempo real y monitorear alertas de abastecimiento."
    )

    total_productos = len(df_inventario)
    unidades_stock = int(df_inventario["stock"].sum()) if not df_inventario.empty else 0
    productos_bajo_minimo = (
        len(df_inventario[df_inventario["stock"] <= df_inventario["stock_minimo"]])
        if not df_inventario.empty
        else 0
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Productos registrados", total_productos)
    col2.metric("Unidades en stock", unidades_stock)
    col3.metric("Productos en o bajo mínimo", productos_bajo_minimo)

# --- PESTAÑA 2: REGISTRAR MOVIMIENTO ---
with tab_movimiento:
    st.subheader("Registrar entrada o salida")
    mostrar_mensaje_guardado("msg_movimiento")

    mapa_productos, mapa_proveedores, mapa_clientes = obtener_listas_seleccion()

    with st.form("form_movimiento"):
        producto_nombre = st.selectbox("Producto", list(mapa_productos.keys()))
        tipo_movimiento = st.selectbox("Tipo de movimiento", ["entrada", "salida"])
        cantidad = st.number_input("Cantidad", value=1, step=1)
        proveedor_nombre = st.selectbox(
            "Proveedor (aplica para entradas)", list(mapa_proveedores.keys())
        )
        cliente_nombre = st.selectbox(
            "Cliente (aplica para salidas)", list(mapa_clientes.keys())
        )
        enviado = st.form_submit_button("Registrar movimiento")

        if enviado:
            id_prod = int(mapa_productos[producto_nombre])
            if tipo_movimiento == "entrada":
                id_prov = mapa_proveedores[proveedor_nombre]
                exito, mensaje = registrar_entrada(id_prod, int(cantidad), id_proveedor=id_prov)
            else:
                id_cli = mapa_clientes[cliente_nombre]
                exito, mensaje = registrar_salida(id_prod, int(cantidad), id_cliente=id_cli)

            st.session_state["msg_movimiento"] = (exito, mensaje)
            st.rerun()

    # Operaciones adicionales reutilizando tus funciones propias del Avance 4
    with st.expander("Registrar producto nuevo"):
        mostrar_mensaje_guardado("msg_producto")
        with st.form("form_nuevo_producto"):
            nuevo_nombre = st.text_input("Nombre del producto")
            nueva_categoria = st.text_input("Categoría (ej. Harinas, Levaduras, Insumos de reposteria)")
            nueva_unidad = st.text_input("Unidad de medida (ej. Bulto de 50 kg)")
            nuevo_precio = st.number_input("Precio unitario", min_value=0.0, value=25000.0, step=1000.0)
            nuevo_minimo = st.number_input("Stock mínimo", min_value=0, value=5, step=1)
            btn_producto = st.form_submit_button("Guardar producto")

            if btn_producto:
                if not nuevo_nombre.strip() or not nueva_categoria.strip() or not nueva_unidad.strip():
                    st.error("Completa el nombre, la categoría y la unidad de medida.")
                else:
                    exito, mensaje = registrar_producto_nuevo(
                        nuevo_nombre.strip(),
                        nueva_categoria.strip(),
                        nueva_unidad.strip(),
                        float(nuevo_precio),
                        int(nuevo_minimo),
                    )
                    st.session_state["msg_producto"] = (exito, mensaje)
                    st.rerun()

    with st.expander("Registrar lote de entradas (Transacción)"):
        mostrar_mensaje_guardado("msg_lote")
        with st.form("form_lote"):
            prod_1 = st.selectbox("Producto 1", list(mapa_productos.keys()), key="lote_p1")
            cant_1 = st.number_input("Cantidad 1", value=5, step=1, key="lote_c1")
            prod_2 = st.selectbox("Producto 2", list(mapa_productos.keys()), key="lote_p2")
            cant_2 = st.number_input("Cantidad 2", value=5, step=1, key="lote_c2")
            prov_lote = st.selectbox("Proveedor del lote", list(mapa_proveedores.keys()), key="lote_prov")
            btn_lote = st.form_submit_button("Registrar lote completo")

            if btn_lote:
                items = [
                    (int(mapa_productos[prod_1]), int(cant_1)),
                    (int(mapa_productos[prod_2]), int(cant_2)),
                ]
                exito, mensaje = registrar_entradas_lote(
                    items, id_proveedor=mapa_proveedores[prov_lote]
                )
                st.session_state["msg_lote"] = (exito, mensaje)
                st.rerun()

# --- PESTAÑA 3: INVENTARIO ---
with tab_inventario:
    st.subheader("Inventario actual")
    categorias = ["Todas"] + sorted(df_inventario["categoria"].dropna().unique().tolist())
    categoria_seleccionada = st.selectbox("Filtrar por categoría", categorias)

    if categoria_seleccionada == "Todas":
        df_mostrar = consultar_inventario()
    else:
        df_mostrar = consultar_inventario(categoria_seleccionada)

    st.dataframe(df_mostrar, hide_index=True)

# --- PESTAÑA 4: ALERTAS ---
with tab_alertas:
    st.subheader("Alertas de stock bajo")
    stock_limite = st.slider("Mostrar productos con stock menor a:", min_value=1, max_value=50, value=15)
    df_alertas = alertas_stock_bajo(stock_limite)

    if df_alertas.empty:
        st.info(f"No hay productos con stock menor a {stock_limite} unidades.")
    else:
        st.dataframe(df_alertas, hide_index=True)
        st.bar_chart(df_alertas.set_index("nombre")["stock"])
