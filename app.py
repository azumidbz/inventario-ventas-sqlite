"""Sistema de inventario y ventas - Acceso a Datos 2026 (Python + SQLite)."""
import sqlite3

DB_NAME = "tienda.db"


# ---------------------------------------------------------------- conexión
def conectar(db=DB_NAME):
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite las desactiva por defecto
    return conn


def crear_tablas(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS productos (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre   TEXT    NOT NULL UNIQUE,
            precio   REAL    NOT NULL CHECK (precio >= 0),
            cantidad INTEGER NOT NULL CHECK (cantidad >= 0)
        );
        CREATE TABLE IF NOT EXISTS ventas (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            cantidad    INTEGER NOT NULL CHECK (cantidad > 0),
            total       REAL    NOT NULL,
            fecha       TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE RESTRICT
        );
    """)
    conn.commit()


# -------------------------------------------------------------------- CRUD
def registrar_producto(conn, nombre, precio, cantidad):
    cur = conn.execute(
        "INSERT INTO productos (nombre, precio, cantidad) VALUES (?, ?, ?)",
        (nombre, precio, cantidad))
    conn.commit()
    return cur.lastrowid


def listar_productos(conn):
    return conn.execute(
        "SELECT id, nombre, precio, cantidad FROM productos ORDER BY id").fetchall()


def obtener_producto(conn, producto_id):
    return conn.execute(
        "SELECT id, nombre, precio, cantidad FROM productos WHERE id = ?",
        (producto_id,)).fetchone()


def actualizar_producto(conn, producto_id, precio=None, cantidad=None):
    if obtener_producto(conn, producto_id) is None:
        raise ValueError("El producto no existe.")
    if precio is not None:
        conn.execute("UPDATE productos SET precio = ? WHERE id = ?", (precio, producto_id))
    if cantidad is not None:
        conn.execute("UPDATE productos SET cantidad = ? WHERE id = ?", (cantidad, producto_id))
    conn.commit()


def eliminar_producto(conn, producto_id):
    """No permite borrar productos con ventas (integridad referencial)."""
    if obtener_producto(conn, producto_id) is None:
        raise ValueError("El producto no existe.")
    try:
        conn.execute("DELETE FROM productos WHERE id = ?", (producto_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise ValueError("No se puede eliminar: el producto tiene ventas registradas.")


# ------------------------------------------------------------- transacción
def registrar_venta(conn, producto_id, cantidad, simular_error=False):
    """Registra una venta de forma atómica.

    1. Valida  2. INSERT en ventas  3. (error simulado)  4. UPDATE inventario
    5. commit().  Cualquier excepción -> rollback() y no queda nada a medias.
    """
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")
    try:
        producto = obtener_producto(conn, producto_id)
        if producto is None:
            raise ValueError("El producto no existe.")
        _, nombre, precio, stock = producto
        if stock < cantidad:
            raise ValueError(f"Stock insuficiente de '{nombre}': hay {stock}, se piden {cantidad}.")

        conn.execute(  # abre la transacción implícita
            "INSERT INTO ventas (producto_id, cantidad, total) VALUES (?, ?, ?)",
            (producto_id, cantidad, precio * cantidad))

        if simular_error:  # error controlado ENTRE el INSERT y el UPDATE
            raise RuntimeError("Fallo simulado después de registrar la venta.")

        conn.execute(
            "UPDATE productos SET cantidad = cantidad - ? WHERE id = ?",
            (cantidad, producto_id))
        conn.commit()
        return precio * cantidad
    except Exception:
        conn.rollback()  # cancela INSERT y UPDATE
        raise


def historial_ventas(conn):
    return conn.execute("""
        SELECT v.id, p.nombre, v.cantidad, v.total, v.fecha
        FROM ventas v JOIN productos p ON p.id = v.producto_id
        ORDER BY v.id""").fetchall()


# ------------------------------------------------------------ presentación
def mostrar_productos(conn):
    filas = listar_productos(conn)
    print(f"\n{'ID':<4}{'Nombre':<28}{'Precio':>12}{'Stock':>8}")
    print("-" * 52)
    for i, n, p, c in filas:
        print(f"{i:<4}{n:<28}{p:>12,.2f}{c:>8}")
    if not filas:
        print("(sin productos)")


def mostrar_historial(conn):
    filas = historial_ventas(conn)
    print(f"\n{'Venta':<7}{'Producto':<26}{'Cant.':>6}{'Total':>12}  Fecha")
    print("-" * 70)
    for i, n, c, t, f in filas:
        print(f"{i:<7}{n:<26}{c:>6}{t:>12,.2f}  {f}")
    if not filas:
        print("(sin ventas)")


def pedir_numero(msg, tipo=float, opcional=False):
    while True:
        txt = input(msg).strip()
        if opcional and txt == "":
            return None
        try:
            return tipo(txt)
        except ValueError:
            print("  Valor no válido, intenta de nuevo.")


MENU = """
===== TIENDA DE COMPONENTES =====
1. Registrar producto
2. Consultar productos
3. Actualizar precio / cantidad
4. Eliminar producto
5. Registrar venta
6. Historial de ventas
7. Demostrar rollback (error controlado)
0. Salir
"""


def main():
    conn = conectar()
    crear_tablas(conn)
    while True:
        print(MENU)
        op = input("Opción: ").strip()
        try:
            if op == "1":
                n = input("Nombre: ").strip()
                if not n:
                    raise ValueError("El nombre no puede estar vacío.")
                p = pedir_numero("Precio: ")
                c = pedir_numero("Cantidad: ", int)
                registrar_producto(conn, n, p, c)
                print("Producto registrado.")
            elif op == "2":
                mostrar_productos(conn)
            elif op == "3":
                mostrar_productos(conn)
                pid = pedir_numero("ID del producto: ", int)
                p = pedir_numero("Nuevo precio (Enter = no cambiar): ", float, True)
                c = pedir_numero("Nueva cantidad (Enter = no cambiar): ", int, True)
                actualizar_producto(conn, pid, p, c)
                print("Producto actualizado.")
            elif op == "4":
                mostrar_productos(conn)
                eliminar_producto(conn, pedir_numero("ID a eliminar: ", int))
                print("Producto eliminado.")
            elif op == "5":
                mostrar_productos(conn)
                pid = pedir_numero("ID del producto: ", int)
                cant = pedir_numero("Cantidad a vender: ", int)
                total = registrar_venta(conn, pid, cant)
                print(f"Venta registrada. Total: {total:,.2f}")
            elif op == "6":
                mostrar_historial(conn)
            elif op == "7":
                mostrar_productos(conn)
                pid = pedir_numero("ID del producto: ", int)
                cant = pedir_numero("Cantidad a vender: ", int)
                antes = obtener_producto(conn, pid)
                try:
                    registrar_venta(conn, pid, cant, simular_error=True)
                except RuntimeError as e:
                    print(f"Error capturado: {e}\n-> rollback() ejecutado.")
                print(f"Antes:   {antes}\nDespués: {obtener_producto(conn, pid)}")
            elif op == "0":
                break
            else:
                print("Opción no válida.")
        except (ValueError, sqlite3.Error) as e:
            print(f"Error: {e}")
    conn.close()


if __name__ == "__main__":
    main()
