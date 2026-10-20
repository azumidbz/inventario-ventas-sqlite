"""Demuestra commit() y rollback() con una BD temporal."""
import os, tempfile
import app

def estado(conn):
    prod = app.obtener_producto(conn, 1)
    n_ventas = conn.execute("SELECT COUNT(*) FROM ventas").fetchone()[0]
    return f"stock={prod[3]}  ventas_registradas={n_ventas}"

def main():
    ruta = os.path.join(tempfile.mkdtemp(), "demo.db")
    conn = app.conectar(ruta)
    app.crear_tablas(conn)
    app.registrar_producto(conn, "Arduino UNO", 85000, 10)

    print("== 0. Estado inicial ==")
    print(estado(conn))

    print("\n== 1. Venta correcta (3 unidades) -> commit ==")
    total = app.registrar_venta(conn, 1, 3)
    print(f"Total: {total:,.0f}  |  {estado(conn)}")

    print("\n== 2. Venta con error controlado (2 unidades) ==")
    antes = estado(conn)
    print("Antes:  ", antes)
    try:
        app.registrar_venta(conn, 1, 2, simular_error=True)
    except RuntimeError as e:
        print("Excepción capturada:", e)
        print("-> rollback() cancela el INSERT de la venta")
    despues = estado(conn)
    print("Después:", despues)
    print("DATOS INTACTOS:", "SI" if antes == despues else "NO")

    print("\n== 3. Validaciones ==")
    for pid, cant in [(99, 1), (1, 500)]:
        try:
            app.registrar_venta(conn, pid, cant)
        except ValueError as e:
            print(f"venta(producto={pid}, cant={cant}) -> {e}")
    print(estado(conn))

    print("\n== 4. Integridad referencial ==")
    try:
        app.eliminar_producto(conn, 1)
    except ValueError as e:
        print(e)

    print("\n== 5. Historial (JOIN) ==")
    app.mostrar_historial(conn)
    conn.close()

if __name__ == "__main__":
    main()
