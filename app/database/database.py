from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./ecoinsumos.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def actualizar_esquema() -> None:
    """Actualiza instalaciones SQLite existentes sin borrar datos."""
    inspector = inspect(engine)
    if "usuarios" in inspector.get_table_names():
        columnas = {columna["name"] for columna in inspector.get_columns("usuarios")}
        if "whatsapp" not in columnas:
            with engine.begin() as conexion:
                conexion.execute(text("ALTER TABLE usuarios ADD COLUMN whatsapp VARCHAR(20) NOT NULL DEFAULT ''"))
    if "productos" in inspector.get_table_names():
        columnas = {columna["name"] for columna in inspector.get_columns("productos")}
        if "vendedor_id" not in columnas:
            with engine.begin() as conexion:
                conexion.execute(text("ALTER TABLE productos ADD COLUMN vendedor_id INTEGER"))
        if "imagen" not in columnas:
            with engine.begin() as conexion:
                conexion.execute(text("ALTER TABLE productos ADD COLUMN imagen VARCHAR(255)"))
        if "disponible" not in columnas:
            with engine.begin() as conexion:
                conexion.execute(text("ALTER TABLE productos ADD COLUMN disponible BOOLEAN NOT NULL DEFAULT 1"))
        if "es_intercambio" not in columnas:
            with engine.begin() as conexion:
                conexion.execute(text("ALTER TABLE productos ADD COLUMN es_intercambio BOOLEAN NOT NULL DEFAULT 0"))
        if "intercambio_por" not in columnas:
            with engine.begin() as conexion:
                conexion.execute(text("ALTER TABLE productos ADD COLUMN intercambio_por TEXT"))
    if "categorias" in inspector.get_table_names():
        columnas = {columna["name"] for columna in inspector.get_columns("categorias")}
        if "imagen" not in columnas:
            with engine.begin() as conexion:
                conexion.execute(text("ALTER TABLE categorias ADD COLUMN imagen VARCHAR(255)"))
    if "compras" in inspector.get_table_names():
        columnas = {columna["name"] for columna in inspector.get_columns("compras")}
        if "precio_unitario" not in columnas:
            with engine.begin() as conexion:
                conexion.execute(text("ALTER TABLE compras ADD COLUMN precio_unitario INTEGER NOT NULL DEFAULT 0"))
        if "total" not in columnas:
            with engine.begin() as conexion:
                conexion.execute(text("ALTER TABLE compras ADD COLUMN total INTEGER NOT NULL DEFAULT 0"))
        if "metodo_pago" not in columnas:
            with engine.begin() as conexion:
                conexion.execute(text("ALTER TABLE compras ADD COLUMN metodo_pago VARCHAR(40) NOT NULL DEFAULT 'tarjeta_prueba'"))
        if "referencia_pago" not in columnas:
            with engine.begin() as conexion:
                conexion.execute(text("ALTER TABLE compras ADD COLUMN referencia_pago VARCHAR(32) NOT NULL DEFAULT ''"))
        if "estado" not in columnas:
            with engine.begin() as conexion:
                conexion.execute(text("ALTER TABLE compras ADD COLUMN estado VARCHAR(40) NOT NULL DEFAULT 'confirmada'"))
    if "mensajes" in inspector.get_table_names():
        columnas = {columna["name"] for columna in inspector.get_columns("mensajes")}
        if "solicitud_intercambio_id" not in columnas:
            with engine.begin() as conexion:
                conexion.execute(text("ALTER TABLE mensajes ADD COLUMN solicitud_intercambio_id INTEGER REFERENCES solicitudes_intercambio(id)"))


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
